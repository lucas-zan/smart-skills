#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skill_env import get_env


def infer_remote_url(remote: str) -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", remote],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def classify_remote(remote_url: str) -> str:
    parsed = urlparse(remote_url)

    if remote_url.startswith(("file://", "/", "./", "../")):
        return "local"
    if remote_url.startswith("git@github.com:"):
        return "github_ssh"
    if parsed.scheme == "ssh" and parsed.hostname == "github.com":
        return "github_ssh"
    if parsed.scheme == "https" and parsed.hostname == "github.com":
        return "github_https"
    if parsed.scheme == "http" and parsed.hostname == "github.com":
        return "github_http"
    if parsed.scheme == "https":
        return "https"
    if parsed.scheme == "http":
        return "http"
    if remote_url.startswith("git@"):
        return "ssh"
    return "other"


def infer_github_repo(remote_url: str) -> tuple[Optional[str], Optional[str]]:
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$",
        r"/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, remote_url)
        if match:
            return match.group("owner"), match.group("repo")
    return None, None


def build_diagnosis(remote_url: str) -> dict:
    remote_kind = classify_remote(remote_url)
    owner, repo = infer_github_repo(remote_url)
    token_present = bool(get_env("CLAW_GITHUB_TOKEN"))
    github_remote = remote_kind in {"github_https", "github_http", "github_ssh"}
    git_transport_ready = False
    if remote_kind == "local":
        git_transport_ready = True
    elif remote_kind == "github_https":
        git_transport_ready = token_present
    elif remote_kind == "github_ssh":
        git_transport_ready = True
    elif remote_kind in {"https", "ssh"}:
        git_transport_ready = True
    github_api_auth_ready = github_remote and token_present
    release_dispatch_auth_ready = github_api_auth_ready

    checks = {
        "uses_https_for_github": remote_kind == "github_https",
        "uses_ssh_for_github": remote_kind == "github_ssh",
        "claw_github_token_present": token_present,
        "git_transport_ready": git_transport_ready,
        "github_api_auth_ready": github_api_auth_ready,
        "release_dispatch_auth_ready": release_dispatch_auth_ready,
    }
    advice: list[str] = []

    ready = git_transport_ready

    if remote_kind == "github_ssh":
        advice.append("Current remote will use SSH for git transport.")
        if not token_present:
            advice.append("GitHub API operations still need CLAW_GITHUB_TOKEN. If SSH does not work, ask whether to switch origin to HTTPS or complete the local SSH setup.")
    elif remote_kind == "github_http":
        advice.append("GitHub HTTP remotes are not supported. Switch origin to HTTPS or SSH.")
    elif remote_kind not in ("github_https", "local"):
        advice.append("This skill is optimized for GitHub remotes.")

    if remote_kind == "github_https" and not token_present:
        advice.append("Current remote will use HTTPS for git transport.")
        advice.append("Export CLAW_GITHUB_TOKEN in the current shell or set it in skills/.env before git or GitHub API operations. If HTTPS does not work here, ask whether to switch origin to SSH.")
    elif github_api_auth_ready:
        advice.append("GitHub API auth is ready. If post-merge release still does not run, check .git-orchestrator.json release.after_merge and workflow inputs/tests.")

    return {
        "remote_url": remote_url,
        "remote_kind": remote_kind,
        "github_owner": owner,
        "github_repo": repo,
        "checks": checks,
        "ready": ready,
        "advice": advice,
    }


def ready_for_scope(diagnosis: dict, scope: str) -> bool:
    checks = diagnosis.get("checks", {})
    if scope == "git":
        return bool(checks.get("git_transport_ready"))
    if scope == "api":
        return bool(checks.get("github_api_auth_ready"))
    return bool(diagnosis.get("ready"))


def emit_text(diagnosis: dict, stream) -> None:
    print(f"remote_url={diagnosis['remote_url']}", file=stream)
    print(f"remote_kind={diagnosis['remote_kind']}", file=stream)
    print(f"ready={str(diagnosis['ready']).lower()}", file=stream)
    print("checks=" + json.dumps(diagnosis["checks"], sort_keys=True), file=stream)
    for item in diagnosis["advice"]:
        print(f"advice={item}", file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose git-orchestrator authentication readiness.")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--remote-url")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--require-scope", choices=["default", "git", "api"], default="default")
    args = parser.parse_args()

    remote_url = args.remote_url
    if not remote_url:
        try:
            remote_url = infer_remote_url(args.remote)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"Unable to resolve git remote '{args.remote}'.") from exc

    diagnosis = build_diagnosis(remote_url.strip())

    if args.require_ready:
        if ready_for_scope(diagnosis, args.require_scope):
            return 0
        emit_text(diagnosis, sys.stderr)
        return 1

    if args.format == "text":
        emit_text(diagnosis, sys.stdout)
        return 0

    print(json.dumps(diagnosis, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
