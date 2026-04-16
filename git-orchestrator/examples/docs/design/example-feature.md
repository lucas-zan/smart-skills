# Design: Example Feature

## Summary

Use the current Git branch as the default development base and enforce a pre-commit evidence gate before any shared delivery workflow continues.

## Why

The workflow must be predictable for humans and agents. Defaulting to the current branch matches day-to-day team development, and an evidence gate prevents undocumented changes from being silently shared or landed.

## Design Decisions

### Base branch strategy

- Read repo policy from `.git-orchestrator.json`
- Default `policy.defaults.base_branch_strategy` to `current-branch`
- Resolve the current branch with `git branch --show-current`
- Only use `test`, `release`, or another branch when explicitly provided

### Evidence gate

Before commit:

- validate requirement evidence
- validate design evidence
- validate test evidence

Validation may use:

- explicit `--requirement`, `--design`, `--test` arguments
- repo policy glob matches when explicit paths are not provided

### Share-and-land safety

- push `share/<base-branch>-<yyyyMMddHHmmss>-<slug>` first
- run verification
- if base moved, rebase share branch and rerun verification
- if base is protected, stop and require PR workflow

## Interfaces

### Config

Repo-local `.git-orchestrator.json`:

- `policy.defaults.*`
- `policy.verify.command`
- `policy.evidence.*`
- `policy.share_and_land.*`

### Scripts

- `scripts/repo_policy.py`
- `scripts/validate_change_basis.py`
- `scripts/git_commit_and_push.sh`
- `scripts/git_share_and_land.sh`

## Test Plan

1. Base branch defaults to current branch.
2. Commit fails when evidence is missing.
3. Commit succeeds when requirement, design, and test evidence exists.
4. Share-and-land re-verifies when base changes mid-flight.
5. Protected branch policy returns PR-required status instead of direct landing.
