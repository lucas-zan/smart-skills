#!/usr/bin/env python3
import argparse
import base64
import json
from pathlib import Path
import shlex
import sys
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from skill_env import get_env


def is_local_remote(remote_url: str) -> bool:
    if remote_url.startswith(("file://", "/", "./", "../")):
        return True
    if remote_url.startswith("git@"):
        return False
    if "://" in remote_url:
        parsed = urlparse(remote_url)
        return parsed.scheme == "file"
    return True


def github_auth_args(remote_url: str) -> list[str]:
    parsed = urlparse(remote_url)

    if remote_url.startswith("git@github.com:") or (
        parsed.scheme == "ssh" and parsed.hostname == "github.com"
    ):
        raise SystemExit(
            "GitHub remote must use HTTPS. Change origin to https://github.com/<owner>/<repo>.git."
        )

    if parsed.scheme == "http" and parsed.hostname == "github.com":
        raise SystemExit(
            "GitHub remote must use HTTPS. Change origin to https://github.com/<owner>/<repo>.git."
        )

    if parsed.scheme == "https" and parsed.hostname == "github.com":
        token = get_env("CLAW_GITHUB_TOKEN")
        if not token:
            raise SystemExit(
                "Missing CLAW_GITHUB_TOKEN for HTTPS GitHub remote authentication. Export it or set skills/.env."
            )
        basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        return [
            "-c",
            "credential.helper=",
            "-c",
            f"http.https://github.com/.extraheader=Authorization: Basic {basic}",
        ]

    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve git network auth args.")
    parser.add_argument("--remote-url", required=True)
    parser.add_argument("--format", choices=["json", "shell"], default="json")
    args = parser.parse_args()

    remote_url = args.remote_url.strip()
    if is_local_remote(remote_url):
        git_args: list[str] = []
    else:
        git_args = github_auth_args(remote_url)

    if args.format == "shell":
        rendered = " ".join(shlex.quote(item) for item in git_args)
        print(f"GIT_AUTH_ARGS=({rendered})")
        return 0

    print(json.dumps({"git_args": git_args}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
