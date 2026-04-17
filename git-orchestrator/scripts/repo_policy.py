#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG_FILE = ".git-orchestrator.json"
FALLBACK_CONFIG_FILE = "git-orchestrator/.git-orchestrator.json"
DEFAULT_POLICY = {
    "defaults": {
        "base_branch_strategy": "current-branch",
        "feature_branch_prefix": "agent",
        "share_branch_prefix": "share",
    },
    "lint": {},
    "verify": {},
    "evidence": {
        "enforce_before_commit": True,
        "pre_commit_checks_enabled": True,
        "require_requirements": True,
        "require_design": True,
        "require_tests": True,
        "require_test_docs": True,
        "require_todo": True,
        "requirement_globs": [
            "docs/requirements/**/*.md",
            "docs/prd/**/*.md",
            "docs/**/*requirement*.md",
        ],
        "design_globs": [
            "docs/design/**/*.md",
            "docs/architecture/**/*.md",
            "docs/**/*design*.md",
        ],
        "test_globs": [
            "tests/**/*",
            "**/*_test.py",
            "**/*_test.rs",
            "**/*.spec.ts",
            "**/*.test.ts",
            "**/*.spec.js",
            "**/*.test.js",
            "**/*.spec.tsx",
            "**/*.test.tsx",
        ],
        "test_doc_globs": [
            "docs/tests/*.md",
            "docs/tests/**/*.md",
            "docs/test/*.md",
            "docs/test/**/*.md",
            "docs/**/*test-case*.md",
            "docs/**/*test-plan*.md",
            "docs/**/*test*.md",
        ],
        "todo_globs": [
            "docs/todo/*.md",
            "docs/todo/**/*.md",
            "docs/**/*todo*.md",
            "TODO.md",
            "TODO*.md",
        ],
    },
    "share_and_land": {
        "allow_direct": True,
        "protected_branches": [],
        "protected_branch_mode": "require-pull-request",
        "reverify_on_base_change": True,
        "max_reverify_attempts": 3,
        "auto_resolve_conflicts": False,
        "auto_resolve_conflicts_command": "",
        "allowed_conflict_paths": [],
        "blocked_conflict_paths": [],
        "max_conflict_resolution_attempts": 3,
    },
}


def pre_commit_checks_enabled(evidence: Dict[str, Any]) -> bool:
    if "pre_commit_checks_enabled" in evidence:
        return bool(evidence["pre_commit_checks_enabled"])
    return bool(evidence.get("enforce_before_commit", True))


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def find_repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return start


def resolve_config_path(repo_root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> Path:
    path = repo_root / config_path
    if path.is_file():
        return path
    if config_path == DEFAULT_CONFIG_FILE:
        fallback = repo_root / FALLBACK_CONFIG_FILE
        if fallback.is_file():
            return fallback
    return path


def load_policy(repo_root: Path, config_path: str = DEFAULT_CONFIG_FILE) -> Dict[str, Any]:
    path = resolve_config_path(repo_root, config_path)
    if not path.is_file():
        return deep_merge({}, DEFAULT_POLICY)
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SystemExit(f"Policy file must contain a JSON object: {path}")
    policy = payload.get("policy", {})
    if not isinstance(policy, dict):
        raise SystemExit(f"'policy' must be a JSON object in: {path}")
    return deep_merge(DEFAULT_POLICY, policy)


def get_path(data: Dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Load git-orchestrator repo policy.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--get")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root).resolve())
    policy = load_policy(repo_root, args.config)

    if args.get:
        try:
            value = get_path(policy, args.get)
        except KeyError as exc:
            raise SystemExit(f"Unknown policy path: {exc.args[0]}") from exc
        if isinstance(value, (dict, list, bool)):
            print(json.dumps(value))
        else:
            print(value)
        return 0

    if args.json or not args.get:
        print(json.dumps(policy, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
