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
    github_api_auth_ready = remote_kind == "github_https" and token_present
    release_dispatch_auth_ready = github_api_auth_ready

    checks = {
        "uses_https_for_github": remote_kind == "github_https",
        "claw_github_token_present": token_present,
        "github_api_auth_ready": github_api_auth_ready,
        "release_dispatch_auth_ready": release_dispatch_auth_ready,
    }
    advice: list[str] = []

    if remote_kind == "local":
        ready = True
    else:
        ready = remote_kind == "github_https" and token_present

    if remote_kind == "github_ssh":
        advice.append("Change origin to HTTPS: git remote set-url origin https://github.com/<owner>/<repo>.git")
    elif remote_kind == "github_http":
        advice.append("Use HTTPS instead of HTTP for GitHub remotes.")
    elif remote_kind not in ("github_https", "local"):
        advice.append("This skill is optimized for GitHub HTTPS remotes.")

    if remote_kind == "github_https" and not token_present:
        advice.append("Export CLAW_GITHUB_TOKEN in the current shell or set it in skills/.env before git or GitHub API operations.")
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
    args = parser.parse_args()

    remote_url = args.remote_url
    if not remote_url:
        try:
            remote_url = infer_remote_url(args.remote)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"Unable to resolve git remote '{args.remote}'.") from exc

    diagnosis = build_diagnosis(remote_url.strip())

    if args.require_ready:
        if diagnosis["ready"]:
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
