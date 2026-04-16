#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

from repo_policy import DEFAULT_CONFIG_FILE, find_repo_root, resolve_config_path
from scaffold_release_workflow import (
    DEFAULT_CONFIG_FILE as SCAFFOLD_DEFAULT_CONFIG_FILE,
    build_workflow_yaml,
    load_config,
    resolve_release_settings,
)


SKILL_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_CONFIG = SKILL_ROOT / DEFAULT_CONFIG_FILE


def ensure_config(repo_root: Path, config_path: str) -> tuple[Path, bool]:
    resolved = resolve_config_path(repo_root, config_path)
    if resolved.is_file():
        return resolved, False

    if not BUNDLED_CONFIG.is_file():
        raise SystemExit(f"Bundled default config not found: {BUNDLED_CONFIG}")

    destination = repo_root / DEFAULT_CONFIG_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BUNDLED_CONFIG, destination)
    return destination, True


def ensure_workflow(repo_root: Path, config_path: str) -> tuple[Path, bool]:
    config = load_config(repo_root, config_path)
    workflow_name = config.get("release", {}).get("after_merge", {}).get("workflow", "release.yml")
    workflow_path = repo_root / ".github" / "workflows" / workflow_name
    if workflow_path.is_file():
        return workflow_path, False

    settings = resolve_release_settings(config)
    workflow_path = repo_root / ".github" / "workflows" / settings["workflow_name"]
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(build_workflow_yaml(settings))
    return workflow_path, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure repo-root release config and workflow exist before merge-and-release.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=SCAFFOLD_DEFAULT_CONFIG_FILE)
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root).resolve())
    config_path, config_created = ensure_config(repo_root, args.config)
    workflow_path, workflow_created = ensure_workflow(repo_root, args.config)

    status = "skipped"
    if config_created or workflow_created:
        status = "created"

    print(f"release_bootstrap={status}")
    print(f"config_path={config_path.relative_to(repo_root)}")
    print(f"config_created={1 if config_created else 0}")
    print(f"workflow_path={workflow_path.relative_to(repo_root)}")
    print(f"workflow_created={1 if workflow_created else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
