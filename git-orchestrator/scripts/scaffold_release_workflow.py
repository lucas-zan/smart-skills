#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from repo_policy import resolve_config_path

DEFAULT_CONFIG_FILE = ".git-orchestrator.json"


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


def load_config(repo_root: Path, config_path: str) -> dict[str, Any]:
    path = resolve_config_path(repo_root, config_path)
    if not path.is_file():
        raise SystemExit(f"Workflow config file not found: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SystemExit(f"Workflow config file must contain a JSON object: {path}")
    return payload


def parse_platforms(value: Any) -> list[str]:
    if value is None:
        return ["macos", "linux"]
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        if items:
            return items
        raise SystemExit("release.after_merge.platforms must not be empty.")
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if items:
            return items
        raise SystemExit("release.after_merge.platforms must not be empty.")
    raise SystemExit("release.after_merge.platforms must be a string or array.")


def normalize_defaults(values: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            result[key] = "true" if value else "false"
        else:
            result[key] = str(value)
    return result


def yaml_quote(value: str) -> str:
    return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""


def input_description(name: str, platform_input: str) -> str:
    if name == platform_input:
        return "Comma-separated platforms to package."
    if name == "publish":
        return "Whether to publish a GitHub release."
    if name == "version":
        return "Release version tag. Leave empty to auto-generate."
    return f"Workflow input '{name}'."


def build_dispatch_inputs(
    allowed_inputs: list[str],
    required_inputs: set[str],
    default_inputs: dict[str, str],
    platform_input: str,
) -> str:
    lines = ["  workflow_dispatch:", "    inputs:"]
    for name in allowed_inputs:
        lines.append(f"      {name}:")
        lines.append(f"        description: {yaml_quote(input_description(name, platform_input))}")
        lines.append(f"        required: {'true' if name in required_inputs else 'false'}")
        if name in default_inputs and default_inputs[name] != "":
            lines.append(f"        default: {yaml_quote(default_inputs[name])}")
    return "\n".join(lines)


def resolve_release_settings(config: dict[str, Any]) -> dict[str, Any]:
    release_cfg = config.get("release", {}).get("after_merge", {})
    if not release_cfg or not release_cfg.get("enabled"):
        raise SystemExit("release.after_merge.enabled must be true before scaffolding a release workflow.")

    workflow_name = release_cfg.get("workflow")
    if not workflow_name:
        raise SystemExit("release.after_merge.workflow is required when release publishing is enabled.")

    workflow_cfg = config.get("workflows", {}).get(workflow_name)
    if not workflow_cfg:
        raise SystemExit(f"Workflow '{workflow_name}' is not configured in {DEFAULT_CONFIG_FILE}")

    platform_input = release_cfg.get("platform_input", "platforms")
    platforms = parse_platforms(release_cfg.get("platforms"))
    required_inputs = set(workflow_cfg.get("required_inputs", []))
    default_inputs = normalize_defaults(workflow_cfg.get("default_inputs", {}))
    release_inputs = normalize_defaults(release_cfg.get("inputs", {}))

    merged_defaults = dict(default_inputs)
    merged_defaults.update(release_inputs)
    merged_defaults.setdefault(platform_input, ",".join(platforms))
    merged_defaults.setdefault("publish", "true")

    allowed_inputs = list(workflow_cfg.get("allowed_inputs", []))
    ordered = [platform_input, "publish", "version"]
    for item in ordered:
        if item not in allowed_inputs:
            allowed_inputs.append(item)

    return {
        "workflow_name": workflow_name,
        "platform_input": platform_input,
        "platforms": platforms,
        "allowed_inputs": allowed_inputs,
        "required_inputs": required_inputs,
        "default_inputs": merged_defaults,
        "package": release_cfg.get("package", {}),
    }


def resolve_package_settings(repo_root: Path, package: dict[str, Any]) -> dict[str, str | list[str]]:
    package = package or {}
    mode = str(package.get("mode", "auto")).strip().lower() or "auto"
    if mode not in {"auto", "go"}:
        raise SystemExit(
            "Release workflow scaffolding currently supports Go binary packaging only. "
            "Set release.after_merge.package.mode to 'go' or use a Go repository."
        )

    if not (repo_root / "go.mod").is_file() and mode == "auto":
        raise SystemExit(
            "Release workflow scaffolding could not auto-detect a Go repository. "
            "Set release.after_merge.package.mode='go' and configure main_package/binary_name."
        )

    include_globs = package.get(
        "include_globs",
        [
            "README*",
            "LICENSE*",
            "NOTICE*",
            "config*.yml",
            "config*.yaml",
            "config/**/*.yml",
            "config/**/*.yaml",
            "*.example",
            "*.env.example",
        ],
    )
    if isinstance(include_globs, str):
        include_globs = [include_globs]
    if not isinstance(include_globs, list):
        raise SystemExit("release.after_merge.package.include_globs must be a string or array.")

    return {
        "binary_name": str(package.get("binary_name") or repo_root.name),
        "main_package": str(package.get("main_package") or "."),
        "arch": str(package.get("arch") or "amd64"),
        "include_globs": [str(item).strip() for item in include_globs if str(item).strip()],
    }


def build_include_lines(patterns: list[str]) -> str:
    return "\n".join(f"          {yaml_quote(pattern)}" for pattern in patterns)


def build_workflow_yaml(repo_root: Path, settings: dict[str, Any]) -> str:
    platform_input = settings["platform_input"]
    dispatch_inputs = build_dispatch_inputs(
        allowed_inputs=settings["allowed_inputs"],
        required_inputs=settings["required_inputs"],
        default_inputs=settings["default_inputs"],
        platform_input=platform_input,
    )
    package_if = "${{ contains(format(',{0},', github.event.inputs." + platform_input + "), format(',{0},', matrix.platform)) }}"
    package_settings = resolve_package_settings(repo_root, settings.get("package", {}))
    include_lines = build_include_lines(package_settings["include_globs"])

    return f"""name: Release

on:
{dispatch_inputs}

permissions:
  contents: write

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      version: ${{{{ steps.version.outputs.version }}}}
    steps:
      - uses: actions/checkout@v4
      - id: version
        shell: bash
        run: |
          if [ -n "${{{{ github.event.inputs.version }}}}" ]; then
            version="${{{{ github.event.inputs.version }}}}"
          else
            version="v$(date +%Y.%m.%d)-${{{{ github.sha }}}}"
            version="${{version:0:19}}"
          fi
          echo "version=${{version}}" >> "$GITHUB_OUTPUT"

  package:
    needs: prepare
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: linux
            runner: ubuntu-latest
          - platform: macos
            runner: macos-latest
    if: {package_if}
    runs-on: ${{{{ matrix.runner }}}}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - name: Build release payload
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p dist
          mkdir -p "dist/package"
          case "${{{{ matrix.platform }}}}" in
            linux) GOOS_VALUE=linux ;;
            macos) GOOS_VALUE=darwin ;;
            *) echo "Unsupported platform: ${{{{ matrix.platform }}}}" >&2; exit 1 ;;
          esac
          GOOS="$GOOS_VALUE" GOARCH="{package_settings["arch"]}" CGO_ENABLED=0 go build -o "dist/package/{package_settings["binary_name"]}" "{package_settings["main_package"]}"
          while IFS= read -r pattern; do
            [ -n "$pattern" ] || continue
            for match in $pattern; do
              [ -e "$match" ] || continue
              if [ -d "$match" ]; then
                mkdir -p "dist/package/$match"
                cp -R "$match"/. "dist/package/$match/"
              else
                mkdir -p "dist/package/$(dirname "$match")"
                cp "$match" "dist/package/$match"
              fi
            done
          done <<'EOF'
{include_lines}
EOF
          archive="${{{{ github.event.repository.name }}}}-${{{{ needs.prepare.outputs.version }}}}-${{{{ matrix.platform }}}}.tar.gz"
          tar -czf "dist/${{archive}}" -C "dist/package" .
      - name: Upload packaged asset
        uses: actions/upload-artifact@v4
        with:
          name: release-${{{{ matrix.platform }}}}
          path: dist/*.tar.gz

  publish:
    needs: [prepare, package]
    if: ${{{{ needs.package.result == 'success' && github.event.inputs.publish == 'true' }}}}
    runs-on: ubuntu-latest
    steps:
      - name: Download packaged assets
        uses: actions/download-artifact@v4
        with:
          pattern: release-*
          path: release-assets
          merge-multiple: true
      - name: Create or update GitHub release
        env:
          GH_TOKEN: ${{{{ github.token }}}}
          VERSION: ${{{{ needs.prepare.outputs.version }}}}
        shell: bash
        run: |
          if gh release view "$VERSION" >/dev/null 2>&1; then
            gh release upload "$VERSION" release-assets/* --clobber
          else
            gh release create "$VERSION" release-assets/* --title "$VERSION" --generate-notes --target "${{{{ github.sha }}}}"
          fi
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a default GitHub release workflow for git-orchestrator.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--out")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = find_repo_root(Path(args.repo_root).resolve())
    config = load_config(repo_root, args.config)
    settings = resolve_release_settings(config)

    default_output = Path(".github") / "workflows" / settings["workflow_name"]
    output_path = repo_root / (args.out or str(default_output))
    if output_path.exists() and not args.force:
        raise SystemExit(f"Workflow file already exists: {output_path}. Pass --force to overwrite.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_workflow_yaml(repo_root, settings))
    print(f"created={output_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
