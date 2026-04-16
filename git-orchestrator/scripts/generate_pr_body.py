#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path
from typing import List


def run(cmd: List[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def list_changed_files(base: str) -> List[str]:
    out = run(["git", "diff", "--name-only", f"{base}...HEAD"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def git_log_summary(base: str, limit: int) -> List[str]:
    out = run(["git", "log", "--pretty=format:%s", f"{base}..HEAD", f"-n{limit}"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def render_markdown(title: str, base: str, head: str, summary: str, why: str, validation: List[str], files: List[str], workflow_inputs: dict) -> str:
    top_files = files[:12]
    body = []
    body.append(f"# {title}")
    body.append("")
    body.append("## Summary")
    body.append(summary.strip() if summary.strip() else "- Update the implementation in this branch and prepare it for review.")
    body.append("")
    body.append("## Why")
    body.append(why.strip() if why.strip() else "- Align the branch changes with the requested implementation goal.")
    body.append("")
    body.append("## Scope")
    body.append(f"- base: `{base}`")
    body.append(f"- head: `{head}`")
    body.append(f"- changed files: `{len(files)}`")
    body.append("")
    body.append("## Files changed")
    if top_files:
        body.extend([f"- `{item}`" for item in top_files])
        if len(files) > len(top_files):
            body.append(f"- `+{len(files) - len(top_files)} more files`")
    else:
        body.append("- No file list available.")
    body.append("")
    body.append("## Validation")
    if validation:
        body.extend([f"- {item}" for item in validation])
    else:
        body.append("- Not run yet")
    body.append("")
    body.append("## CI/CD request")
    if workflow_inputs:
        body.append("```json")
        body.append(json.dumps(workflow_inputs, indent=2, sort_keys=True))
        body.append("```")
    else:
        body.append("- No workflow input payload attached.")
    body.append("")
    body.append("## Risks / review focus")
    body.append("- Confirm branch diff matches the intended scope.")
    body.append("- Confirm required checks and protected branch rules pass before merge.")
    body.append("")
    body.append("## Checklist")
    body.append("- [ ] Lint / tests have been reviewed")
    body.append("- [ ] CI workflow inputs are correct")
    body.append("- [ ] Ready for reviewer attention")
    return "\n".join(body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a PR body markdown document from branch diff context.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--why", default="")
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--workflow-inputs-file")
    parser.add_argument("--commit-limit", type=int, default=8)
    parser.add_argument("--out")
    args = parser.parse_args()

    files = list_changed_files(args.base)
    if not args.summary:
        commits = git_log_summary(args.base, args.commit_limit)
        if commits:
            args.summary = "- " + "\n- ".join(commits[:5])

    workflow_inputs = {}
    if args.workflow_inputs_file:
        workflow_inputs = json.loads(Path(args.workflow_inputs_file).read_text())

    markdown = render_markdown(
        title=args.title,
        base=args.base,
        head=args.head,
        summary=args.summary,
        why=args.why,
        validation=args.validation,
        files=files,
        workflow_inputs=workflow_inputs,
    )

    if args.out:
        Path(args.out).write_text(markdown)
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
