#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skill_env import get_env


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_diagnose_module():
    path = Path(__file__).with_name("diagnose_auth.py")
    spec = importlib.util.spec_from_file_location("git_orchestrator_diagnose_auth", path)
    if spec is None or spec.loader is None:
        raise SystemExit("Unable to load auth diagnostics helper.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer_repo_from_git_remote() -> Tuple[Optional[str], Optional[str]]:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
        url = result.stdout.strip()
    except Exception:
        return None, None

    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$",
        r"/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group("owner"), m.group("repo")
    return None, None


def ensure_auth_ready_for_flow() -> None:
    diagnose = load_diagnose_module()
    try:
        remote_url = diagnose.infer_remote_url("origin")
    except SystemExit:
        return
    diagnosis = diagnose.build_diagnosis(remote_url)
    if diagnosis["ready"]:
        return
    diagnose.emit_text(diagnosis, sys.stderr)
    raise SystemExit(1)


class GitHubClient:
    def __init__(self, owner: Optional[str], repo: Optional[str], api_url: Optional[str] = None):
        env_owner = os.getenv("GITHUB_OWNER")
        env_repo = os.getenv("GITHUB_REPO")
        inferred_owner, inferred_repo = infer_repo_from_git_remote()
        self.owner = owner or env_owner or inferred_owner
        self.repo = repo or env_repo or inferred_repo
        self.api_url = (api_url or os.getenv("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        self.token = get_env("CLAW_GITHUB_TOKEN")
        if not self.owner or not self.repo:
            raise SystemExit("Missing repository coordinates. Set --owner/--repo, or GITHUB_OWNER/GITHUB_REPO, or configure origin remote.")
        if not self.token:
            raise SystemExit("Missing CLAW_GITHUB_TOKEN. Export it or set skills/.env.")

    def request(self, method: str, path: str, body: Optional[dict] = None, query: Optional[dict] = None) -> dict:
        url = f"{self.api_url}{path}"
        if query:
            query_string = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
            if query_string:
                url = f"{url}?{query_string}"

        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git-orchestrator",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            eprint(f"GitHub API error {exc.code}: {payload}")
            raise SystemExit(exc.code)

    def repo_path(self) -> str:
        return f"/repos/{self.owner}/{self.repo}"


def print_json(data: dict):
    print(json.dumps(data, indent=2, sort_keys=True))


def parse_inputs(items):
    result = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"Invalid --input '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def normalize_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    prefixes = ["refs/heads/", "heads/"]
    for prefix in prefixes:
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def parse_github_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def summarize_run(run: Optional[dict]) -> Optional[dict]:
    if not run:
        return None
    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
        "head_branch": run.get("head_branch"),
        "event": run.get("event"),
        "created_at": run.get("created_at"),
    }


def find_dispatched_run(client: GitHubClient, workflow: str, ref: Optional[str], started_at: float, deadline: float, interval: int) -> Optional[dict]:
    started_after = datetime.fromtimestamp(started_at - 5, tz=timezone.utc)
    branch = normalize_ref(ref)

    while True:
        query = {
            "event": "workflow_dispatch",
            "branch": branch,
            "per_page": 20,
        }
        response = client.request("GET", f"{client.repo_path()}/actions/workflows/{workflow}/runs", query=query)
        runs = response.get("workflow_runs", [])
        for run in runs:
            if branch and run.get("head_branch") and run.get("head_branch") != branch:
                continue
            created_at = parse_github_datetime(run.get("created_at"))
            if created_at is not None and created_at < started_after:
                continue
            return run

        if time.time() >= deadline:
            return None
        time.sleep(interval)


def wait_for_run_completion(client: GitHubClient, run_id: int, deadline: float, interval: int, emit_progress: bool) -> dict:
    while True:
        run = client.request("GET", f"{client.repo_path()}/actions/runs/{run_id}")
        summary = summarize_run(run)
        if emit_progress:
            print_json(summary)
        if run.get("status") == "completed":
            return summary
        if time.time() >= deadline:
            raise SystemExit("Timed out while waiting for workflow run completion.")
        time.sleep(interval)


def cmd_create_pr(client: GitHubClient, args):
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text()
    payload = {
        "title": args.title,
        "head": args.head,
        "base": args.base,
        "body": body or "",
        "draft": args.draft,
    }
    print_json(client.request("POST", f"{client.repo_path()}/pulls", payload))


def cmd_get_pr(client: GitHubClient, args):
    print_json(client.request("GET", f"{client.repo_path()}/pulls/{args.number}"))


def cmd_list_prs(client: GitHubClient, args):
    query = {
        "state": args.state,
        "head": args.head,
        "base": args.base,
        "per_page": args.limit,
    }
    print_json(client.request("GET", f"{client.repo_path()}/pulls", query=query))


def cmd_merge_pr(client: GitHubClient, args):
    payload = {
        "merge_method": args.method,
    }
    if args.sha:
        payload["sha"] = args.sha
    if args.title:
        payload["commit_title"] = args.title
    if args.message:
        payload["commit_message"] = args.message
    print_json(client.request("PUT", f"{client.repo_path()}/pulls/{args.number}/merge", payload))


def cmd_update_branch(client: GitHubClient, args):
    payload = {}
    if args.expected_head_sha:
        payload["expected_head_sha"] = args.expected_head_sha
    print_json(client.request("PUT", f"{client.repo_path()}/pulls/{args.number}/update-branch", payload))


def cmd_dispatch_workflow(client: GitHubClient, args):
    inputs = parse_inputs(args.input)
    ref = args.ref
    if args.input_file:
        file_payload = json.loads(Path(args.input_file).read_text())
        if isinstance(file_payload, dict) and "inputs" in file_payload:
            inputs = {**file_payload.get("inputs", {}), **inputs}
            ref = ref or file_payload.get("ref")
        else:
            inputs = {**file_payload, **inputs}
    payload = {
        "ref": ref,
        "inputs": inputs,
    }
    if not payload["ref"]:
        raise SystemExit("Missing workflow ref. Pass --ref or provide it in --input-file JSON.")
    started_at = time.time()
    deadline = started_at + args.timeout
    client.request("POST", f"{client.repo_path()}/actions/workflows/{args.workflow}/dispatches", payload)

    run = find_dispatched_run(
        client,
        workflow=args.workflow,
        ref=payload["ref"],
        started_at=started_at,
        deadline=deadline,
        interval=args.interval,
    )
    summary = {
        "dispatched": True,
        "workflow": args.workflow,
        "ref": payload["ref"],
        "run": summarize_run(run),
    }

    if args.wait:
        if not run:
            raise SystemExit("Timed out while waiting for the dispatched workflow run to appear.")
        summary["run"] = wait_for_run_completion(
            client,
            run_id=run["id"],
            deadline=deadline,
            interval=args.interval,
            emit_progress=False,
        )

    print_json(summary)
    if args.wait and summary["run"] and summary["run"].get("conclusion") not in (None, "success"):
        raise SystemExit(1)


def cmd_list_runs(client: GitHubClient, args):
    query = {
        "branch": args.branch,
        "event": args.event,
        "status": args.status,
        "per_page": args.limit,
    }
    response = client.request("GET", f"{client.repo_path()}/actions/runs", query=query)
    print_json(response)


def cmd_get_run(client: GitHubClient, args):
    print_json(client.request("GET", f"{client.repo_path()}/actions/runs/{args.run_id}"))


def cmd_wait_run(client: GitHubClient, args):
    deadline = time.time() + args.timeout
    summary = wait_for_run_completion(client, args.run_id, deadline, args.interval, emit_progress=True)
    if summary.get("conclusion") != "success":
        raise SystemExit(1)


def cmd_rerun_run(client: GitHubClient, args):
    path = f"{client.repo_path()}/actions/runs/{args.run_id}/rerun"
    if args.failed_only:
        path = f"{client.repo_path()}/actions/runs/{args.run_id}/rerun-failed-jobs"
    print_json(client.request("POST", path, {}))


def build_parser():
    parser = argparse.ArgumentParser(description="GitHub REST operations for git orchestrator")
    parser.add_argument("--owner")
    parser.add_argument("--repo")
    parser.add_argument("--api-url")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("create-pr")
    p.add_argument("--title", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--draft", action="store_true")
    p.set_defaults(func=cmd_create_pr)

    p = subparsers.add_parser("get-pr")
    p.add_argument("--number", required=True, type=int)
    p.set_defaults(func=cmd_get_pr)

    p = subparsers.add_parser("list-prs")
    p.add_argument("--state", default="open")
    p.add_argument("--head")
    p.add_argument("--base")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list_prs)

    p = subparsers.add_parser("merge-pr")
    p.add_argument("--number", required=True, type=int)
    p.add_argument("--method", choices=["merge", "squash", "rebase"], default="squash")
    p.add_argument("--sha")
    p.add_argument("--title")
    p.add_argument("--message")
    p.set_defaults(func=cmd_merge_pr)

    p = subparsers.add_parser("update-branch")
    p.add_argument("--number", required=True, type=int)
    p.add_argument("--expected-head-sha")
    p.set_defaults(func=cmd_update_branch)

    p = subparsers.add_parser("dispatch-workflow")
    p.add_argument("--workflow", required=True, help="Workflow file name or workflow id")
    p.add_argument("--ref")
    p.add_argument("--input", action="append", default=[])
    p.add_argument("--input-file", help="JSON file containing either {ref, inputs} or a raw inputs object")
    p.add_argument("--wait", action="store_true", help="Wait for the dispatched workflow run to complete.")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--interval", type=int, default=15)
    p.set_defaults(func=cmd_dispatch_workflow)

    p = subparsers.add_parser("list-runs")
    p.add_argument("--branch")
    p.add_argument("--event")
    p.add_argument("--status")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list_runs)

    p = subparsers.add_parser("get-run")
    p.add_argument("--run-id", required=True, type=int)
    p.set_defaults(func=cmd_get_run)

    p = subparsers.add_parser("wait-run")
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--interval", type=int, default=15)
    p.set_defaults(func=cmd_wait_run)

    p = subparsers.add_parser("rerun-run")
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--failed-only", action="store_true")
    p.set_defaults(func=cmd_rerun_run)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    ensure_auth_ready_for_flow()
    client = GitHubClient(owner=args.owner, repo=args.repo, api_url=args.api_url)
    args.func(client, args)


if __name__ == "__main__":
    main()
