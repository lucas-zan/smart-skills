#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

from repo_policy import find_repo_root, load_policy, pre_commit_checks_enabled
from validate_change_basis import changed_files, ensure_paths_exist, find_matches, has_test_change


UNCHECKED_BOX = re.compile(r"^\s*[-*]\s+\[ \]\s+.+$", re.MULTILINE)
CHECKBOX = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+.+$", re.MULTILINE)


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def filter_matches_for_changed(paths: list[str], changed: list[str]) -> list[str]:
    changed_set = set(changed)
    return [path for path in paths if path in changed_set]


def resolve_evidence_paths(
    repo_root: Path,
    changed: list[str],
    explicit_paths: list[str],
    patterns: list[str],
    label: str,
    prefer_changed: bool = False,
    require_single_auto_match: bool = False,
) -> list[str]:
    resolved = ensure_paths_exist(repo_root, explicit_paths, label)
    if resolved:
        return resolved

    matches = find_matches(repo_root, patterns)
    if prefer_changed:
        changed_matches = filter_matches_for_changed(matches, changed)
        if changed_matches:
            return changed_matches

    if require_single_auto_match and len(matches) > 1:
        raise SystemExit(
            f"Multiple {label.lower()} files matched automatically: {', '.join(matches)}. "
            f"Pass --{label.lower().replace(' ', '-')} to choose the intended file."
        )
    return matches


def ensure_todo_completed(repo_root: Path, todo_paths: list[str]) -> list[str]:
    failures = []
    for relative in todo_paths:
        content = (repo_root / relative).read_text()
        if not CHECKBOX.search(content):
            failures.append(f"{relative}: missing markdown checkbox items")
            continue
        if UNCHECKED_BOX.search(content):
            failures.append(f"{relative}: unfinished TODO items remain")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate delivery readiness before submit: requirements, design, test docs, tests, and TODO completion."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=".git-orchestrator.json")
    parser.add_argument("--against-ref")
    parser.add_argument("--requirement", action="append", default=[])
    parser.add_argument("--design", action="append", default=[])
    parser.add_argument("--test-doc", action="append", default=[])
    parser.add_argument("--test", action="append", default=[])
    parser.add_argument("--todo", action="append", default=[])
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root).resolve())
    policy = load_policy(repo_root, args.config)
    evidence = policy["evidence"]

    check_names = ["requirements", "design", "test_docs", "tests", "todo"]
    for item in check_names:
        print(f"todo_check_{item}=pending")

    if not pre_commit_checks_enabled(evidence):
        for item in check_names:
            print(f"todo_check_{item}=skipped")
        return 0

    changed = changed_files(repo_root, args.against_ref)
    failures: list[str] = []
    failure_details: list[str] = []

    requirement_paths = resolve_evidence_paths(
        repo_root,
        changed,
        args.requirement,
        evidence.get("requirement_globs", []),
        "Requirement",
    )
    if evidence.get("require_requirements", True) and not requirement_paths:
        failures.append("requirements")
        failure_details.append("requirements: no requirement document found")
    else:
        print("todo_check_requirements=ok")

    design_paths = resolve_evidence_paths(
        repo_root,
        changed,
        args.design,
        evidence.get("design_globs", []),
        "Design",
    )
    if evidence.get("require_design", True) and not design_paths:
        failures.append("design")
        failure_details.append("design: no design document found")
    else:
        print("todo_check_design=ok")

    test_doc_paths = resolve_evidence_paths(
        repo_root,
        changed,
        args.test_doc,
        evidence.get("test_doc_globs", []),
        "Test Doc",
    )
    if evidence.get("require_test_docs", True) and not test_doc_paths:
        failures.append("test_docs")
        failure_details.append("test_docs: no test documentation found")
    else:
        print("todo_check_test_docs=ok")

    test_paths = ensure_paths_exist(repo_root, args.test, "Test")
    if evidence.get("require_tests", True) and not test_paths and not has_test_change(changed, evidence.get("test_globs", [])):
        failures.append("tests")
        failure_details.append("tests: no test code found or changed")
    else:
        print("todo_check_tests=ok")

    todo_paths = resolve_evidence_paths(
        repo_root,
        changed,
        args.todo,
        evidence.get("todo_globs", []),
        "Todo",
        prefer_changed=True,
        require_single_auto_match=True,
    )
    if evidence.get("require_todo", True) and not todo_paths:
        failures.append("todo")
        failure_details.append("todo: no TODO status document found")
    else:
        print("todo_check_todo=ok")
        todo_failures = ensure_todo_completed(repo_root, todo_paths)
        if todo_failures:
            failures.append("todo_status")
            failure_details.extend(f"todo_status: {detail}" for detail in todo_failures)

    if failures:
        print(
            "Submission readiness check failed: "
            + ", ".join(unique(failures))
            + ".",
            file=sys.stderr,
        )
        for detail in failure_details:
            print(detail, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
