# Automation notes

## Commit message generation

Use `scripts/generate_commit_message.py` before committing when the user says “submit this work” without giving a commit message.

- The script inspects changed files and optional natural-language context.
- It outputs a conventional-commit-style subject and a generated body.
- Pass `--json` when another script or wrapper needs machine-readable output.

Before commit, run `scripts/validate_change_basis.py` or rely on the automatic check inside `scripts/git_commit_and_push.sh`.

- The default team policy expects requirement evidence, design evidence, and test evidence.
- Use explicit `--requirement`, `--design`, and `--test` arguments when the relevant files are not obvious from repository defaults.

## PR body generation

Use `scripts/generate_pr_body.py` after the branch is pushed and before opening the PR.

Recommended inputs:

- `--title`: usually the same as the commit subject or a slightly broader review title
- `--base`: target base branch
- `--head`: feature branch name
- `--validation`: repeat for lint/test/deploy prechecks that were run
- `--workflow-inputs-file`: JSON output from `scripts/resolve_workflow_inputs.py`

## Workflow input resolution

Copy `references/workflow_inputs.example.json` into the repository root as `.git-orchestrator.json` and edit it per repository.

This lets the skill resolve repository-specific workflow defaults and repository policy without hardcoding them into the skill package.

Useful repo policy fields include:

- `policy.defaults.base_branch_strategy`: use `current-branch` to make the active development branch the default base branch
- `policy.verify.command`: default verification pipeline
- `policy.evidence.*`: basis checks required before commit
- `policy.share_and_land.protected_branches`: branches that require a PR fallback
- `policy.share_and_land.reverify_on_base_change`: whether to rerun verification when the base branch advances during landing
