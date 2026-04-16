#!/usr/bin/env python3
import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

from repo_policy import find_repo_root, load_policy


def run(cmd: List[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def unique(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def changed_files(repo_root: Path, against_ref: str | None) -> List[str]:
    files: List[str] = []
    if against_ref:
        output = run(["git", "diff", "--name-only", f"{against_ref}...HEAD"], repo_root)
        files.extend([line for line in output.splitlines() if line.strip()])

    for cmd in (
        ["git", "diff", "--cached", "--name-only"],
        ["git", "diff", "--name-only"],
    ):
        output = run(cmd, repo_root)
        files.extend([line for line in output.splitlines() if line.strip()])

    status_output = run(["git", "status", "--porcelain"], repo_root)
    for line in status_output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip())
    return unique(files)


def ensure_paths_exist(repo_root: Path, paths: List[str], label: str) -> List[str]:
    resolved = []
    for item in paths:
        path = repo_root / item
        if not path.exists():
            raise SystemExit(f"{label} evidence file does not exist: {item}")
        resolved.append(item)
    return resolved


def find_matches(repo_root: Path, patterns: List[str]) -> List[str]:
    matches: List[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root).as_posix()
        if any(fnmatch.fnmatch(relative, pattern) for pattern in patterns):
            matches.append(relative)
    return sorted(matches)


def has_test_change(changed: List[str], test_globs: List[str]) -> bool:
    return any(any(fnmatch.fnmatch(path, pattern) for pattern in test_globs) for path in changed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that the current change has requirements, design, and test evidence.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=".git-orchestrator.json")
    parser.add_argument("--against-ref")
    parser.add_argument("--requirement", action="append", default=[])
    parser.add_argument("--design", action="append", default=[])
    parser.add_argument("--test", action="append", default=[])
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root).resolve())
    policy = load_policy(repo_root, args.config)
    evidence = policy["evidence"]

    if not evidence.get("enforce_before_commit", True):
        print("requirements=skipped")
        print("design=skipped")
        print("tests=skipped")
        return 0

    changed = changed_files(repo_root, args.against_ref)
    requirement_paths = ensure_paths_exist(repo_root, args.requirement, "Requirement")
    design_paths = ensure_paths_exist(repo_root, args.design, "Design")
    test_paths = ensure_paths_exist(repo_root, args.test, "Test")

    missing = []

    if evidence.get("require_requirements", True):
        if not requirement_paths:
            requirement_paths = find_matches(repo_root, evidence.get("requirement_globs", []))
        if not requirement_paths:
            missing.append("requirements")

    if evidence.get("require_design", True):
        if not design_paths:
            design_paths = find_matches(repo_root, evidence.get("design_globs", []))
        if not design_paths:
            missing.append("design")

    if evidence.get("require_tests", True):
        if not test_paths and not has_test_change(changed, evidence.get("test_globs", [])):
            missing.append("tests")

    if missing:
        print(
            "Missing required change basis: "
            + ", ".join(missing)
            + ". Provide --requirement/--design/--test or add matching files and changed tests.",
            file=sys.stderr,
        )
        return 1

    print("requirements=ok")
    print("design=ok")
    print("tests=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
