#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict

DEFAULT_CONFIG_FILE = ".git-orchestrator.json"


def load_json(path: str) -> Dict:
    config_path = Path(path)
    if not config_path.is_file():
        raise SystemExit(f"Workflow config file not found: {config_path}")
    try:
        payload = json.loads(config_path.read_text())
    except OSError as exc:
        raise SystemExit(f"Failed to read workflow config file {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Workflow config file is not valid JSON: {config_path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Workflow config file must contain a JSON object: {config_path}")
    return payload


def merge(a: Dict, b: Dict) -> Dict:
    result = dict(a)
    result.update(b)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve workflow inputs from repo defaults, presets, and ad hoc overrides.")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--preset")
    parser.add_argument("--ref")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--format", choices=["json", "kv"], default="json")
    args = parser.parse_args()

    config = load_json(args.config)
    workflow_cfg = config.get("workflows", {}).get(args.workflow)
    if not workflow_cfg:
        raise SystemExit(f"Workflow '{args.workflow}' is not configured in {args.config}")

    default_inputs = dict(workflow_cfg.get("default_inputs", {}))
    preset_inputs = {}
    if args.preset:
        preset_inputs = workflow_cfg.get("presets", {}).get(args.preset)
        if preset_inputs is None:
            raise SystemExit(f"Preset '{args.preset}' is not defined for workflow '{args.workflow}'")

    cli_inputs = {}
    for item in args.input:
        if "=" not in item:
            raise SystemExit(f"Invalid --input '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        cli_inputs[key] = value

    merged_inputs = merge(default_inputs, preset_inputs)
    merged_inputs = merge(merged_inputs, cli_inputs)

    required = workflow_cfg.get("required_inputs", [])
    missing = [key for key in required if key not in merged_inputs or merged_inputs[key] in (None, "")]
    if missing:
        raise SystemExit("Missing required workflow inputs: " + ", ".join(missing))

    allowed = workflow_cfg.get("allowed_inputs", [])
    if allowed:
        unexpected = sorted(set(merged_inputs) - set(allowed))
        if unexpected:
            raise SystemExit("Unexpected workflow inputs: " + ", ".join(unexpected))

    payload = {
        "workflow": args.workflow,
        "ref": args.ref or workflow_cfg.get("default_ref") or os.getenv("GITHUB_BASE_BRANCH") or "main",
        "inputs": merged_inputs,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload["inputs"].items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
