#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import List, Tuple


def run(cmd: List[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def parse_paths(output: str) -> List[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def parse_status_paths(output: str) -> List[str]:
    files = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip())
    return files


def unique(items: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def changed_files(staged: bool = False) -> List[str]:
    if staged:
        return parse_paths(run(["git", "diff", "--cached", "--name-only"]))

    staged_files = parse_paths(run(["git", "diff", "--cached", "--name-only"]))
    unstaged_files = parse_paths(run(["git", "diff", "--name-only"]))
    status_files = parse_status_paths(run(["git", "status", "--porcelain"]))
    return unique(staged_files + unstaged_files + status_files)


def classify_type(files: List[str], context: str) -> str:
    lowered = context.lower()
    if any(token in lowered for token in ["fix", "bug", "error", "issue", "broken", "hotfix"]):
        return "fix"
    if any(token in lowered for token in ["docs", "readme", "documentation"]):
        return "docs"
    if any(token in lowered for token in ["refactor", "cleanup", "restructure"]):
        return "refactor"
    if any(token in lowered for token in ["test", "spec", "coverage"]):
        return "test"
    if any(token in lowered for token in ["build", "ci", "workflow", "deploy", "docker"]):
        return "build"
    if any(token in lowered for token in ["perf", "performance", "optimiz"]):
        return "perf"

    joined = " ".join(files).lower()
    if any(p.endswith(('.md', '.mdx', '.rst')) for p in files):
        if all(p.endswith(('.md', '.mdx', '.rst')) for p in files):
            return "docs"
    if ".github/workflows/" in joined or joined.endswith(".yml") or joined.endswith(".yaml"):
        return "build"
    if any("test" in p.lower() or p.endswith(("_test.py", ".spec.ts", ".test.ts", ".spec.js", ".test.js")) for p in files):
        return "test"
    return "feat"


def infer_scope(files: List[str]) -> str:
    candidates = []
    for path in files:
        parts = [p for p in Path(path).parts if p not in {"src", "app", "apps", "packages", "services", "internal", "lib", "cmd"}]
        if not parts:
            continue
        raw = parts[0]
        if "." in raw:
            raw = Path(raw).stem
        first = re.sub(r"[^a-zA-Z0-9_-]", "", raw).lower()
        if first and first not in {"github", "scripts", "test", "tests", "docs"}:
            candidates.append(first)
    if not candidates:
        return "repo"
    return Counter(candidates).most_common(1)[0][0]


def summarize_files(files: List[str], limit: int = 5) -> Tuple[str, List[str]]:
    display = files[:limit]
    more = len(files) - len(display)
    parts = display.copy()
    if more > 0:
        parts.append(f"+{more} more")
    return ", ".join(parts), display


def make_subject(commit_type: str, scope: str, files: List[str], context: str) -> str:
    display, _ = summarize_files(files, limit=3)
    if context.strip():
        cleaned = re.sub(r"\s+", " ", context.strip())
        cleaned = cleaned[0].lower() + cleaned[1:] if len(cleaned) > 1 else cleaned.lower()
        return f"{commit_type}({scope}): {cleaned}"[:72]
    if len(files) == 1:
        target = Path(files[0]).stem.replace("_", "-")
        return f"{commit_type}({scope}): update {target}"[:72]
    return f"{commit_type}({scope}): update {display}"[:72]


def make_body(files: List[str], context: str) -> str:
    lines = []
    if context.strip():
        lines.append(context.strip())
    display, items = summarize_files(files, limit=8)
    lines.append(f"Changed files: {display}.")
    touched = sorted({Path(p).parts[0] if len(Path(p).parts) > 1 else Path(p).stem for p in files})
    if touched:
        shown = ", ".join(touched[:6])
        if len(touched) > 6:
            shown += f", +{len(touched) - 6} more"
        lines.append(f"Touched areas: {shown}.")
    return "\n\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a conventional commit message from repo changes.")
    parser.add_argument("--context", default="", help="Optional natural language summary to bias the message.")
    parser.add_argument("--staged", action="store_true", help="Use staged changes only.")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    args = parser.parse_args()

    try:
        files = changed_files(staged=args.staged)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        return 1

    if not files:
        print("No changed files found.", file=sys.stderr)
        return 1

    commit_type = classify_type(files, args.context)
    scope = infer_scope(files)
    subject = make_subject(commit_type, scope, files, args.context)
    body = make_body(files, args.context)

    if args.json:
        print(json.dumps({"subject": subject, "body": body}, indent=2))
    else:
        print(subject)
        print()
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
