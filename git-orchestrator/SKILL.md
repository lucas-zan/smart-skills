---
name: git-orchestrator
description: "Use when an agent needs a repeatable Git or GitHub delivery workflow for branching, committing, pushing, pull requests, workflow dispatch, or share-and-land after explicit human confirmation."
---

# Git Orchestrator

Use this skill when the user wants delivery work, not product design work.

Good fits:
- submit the current work
- create a visible branch
- generate a commit message or PR body
- open, inspect, sync, or merge a PR
- trigger or watch a GitHub Actions workflow
- share-and-land after explicit human confirmation
- bootstrap release automation into the current branch before merge

Do not use this skill for code review, design review, or deciding whether the change itself is correct.
Do not use this skill to repair product code. Its automatic release bootstrap may create only release-automation files such as `.git-orchestrator.json` and `.github/workflows/release.yml`.

## Intent Router

Route the request before doing any work. Do not run the full submit flow when the user asked for a narrower action.

| User intent | Use |
| --- | --- |
| Create a feature branch | `bash scripts/git_start_branch.sh ...` |
| Commit and push current changes | `bash scripts/git_commit_and_push.sh ...` |
| Generate a commit message | `uv run python scripts/generate_commit_message.py ...` |
| Open a PR | `uv run python scripts/generate_pr_body.py ...` then `uv run python scripts/github_ops.py create-pr ...` |
| Inspect a PR | `uv run python scripts/github_ops.py get-pr ...` |
| Sync a PR branch with base | `uv run python scripts/github_ops.py update-branch ...` |
| Merge a PR | `uv run python scripts/github_ops.py merge-pr ...` |
| Trigger the configured post-merge release flow | `uv run python scripts/github_ops.py dispatch-release ...` |
| Merge current work and make release automation ready automatically | `bash scripts/git_share_and_land.sh --confirmed --with-release ...` |
| Scaffold a default release workflow | `uv run python scripts/scaffold_release_workflow.py` |
| Resolve workflow inputs | `uv run python scripts/resolve_workflow_inputs.py ...` |
| Dispatch or watch a workflow run | `uv run python scripts/github_ops.py dispatch-workflow ...` or `wait-run ...` |
| Share-and-land | `bash scripts/git_share_and_land.sh ...` |

## Hard Truths

- Plain git does not create PRs, inspect PRs, or dispatch GitHub Actions workflows. Use `scripts/github_ops.py` for those tasks.
- Evidence gating is real. `validate_change_basis.py` can return `ok`, `failed`, or `skipped` depending on repo policy.
- Submit flows now run a stricter preflight TODO checklist before evidence gating: requirements doc, design doc, test doc, test code, and TODO completion must pass before commit/share begins.
- Repo policy can disable those submit-time gates with `policy.evidence.pre_commit_checks_enabled: false`. Keep backward compatibility with `policy.evidence.enforce_before_commit: false`.
- Direct share-and-land always needs explicit human confirmation.
- For GitHub HTTPS remotes, auth may come from the current environment or `skills/.env`.

## Branch Naming Truth

The default branch naming pattern is:

`<prefix>/<base-branch>-<yyyyMMddHHmmss>-<slug>`

Examples:
- `agent/main-20260415010203-fix-login-bug`
- `share/release-20260415010203-doc-sync`

For deterministic tests or automation, `GIT_ORCHESTRATOR_BRANCH_DATE` overrides the timestamp segment.

## Mode-Specific Preconditions

### Base Local Git Flow

Require these before branch, commit, verify, or share-and-land flows:
- current directory is inside a git repository
- `git` is available
- `uv` is available for Python helper scripts
- the requested remote exists when the task needs fetch or push

### GitHub HTTPS / API Flow

Require these before PR or workflow operations:
- the remote is GitHub HTTPS, not SSH
- `CLAW_GITHUB_TOKEN` is available from the shell environment or `skills/.env`
- repository coordinates come from `--owner` / `--repo`, `GITHUB_OWNER` / `GITHUB_REPO`, or the `origin` remote

### Workflow Dispatch

Require these before `resolve_workflow_inputs.py` or `dispatch-workflow`:
- the target workflow supports `workflow_dispatch`
- a config file exists when the flow depends on presets or default workflow inputs; prefer repo-root `.git-orchestrator.json`, and fall back to `git-orchestrator/.git-orchestrator.json` in skill-collection repos
- required workflow inputs are known; do not guess prod-facing values

For post-merge release automation, the workflow file that GitHub will execute must exist in the repository root `.github/workflows/` before the merge that is going to dispatch it. A skill-local file such as `git-orchestrator/.github/workflows/release.yml` is only a template. If the executable root workflow is missing, scaffold it first with `uv run python scripts/scaffold_release_workflow.py`, review it, then submit that file through the normal git flow.
When the user explicitly asks for merge-and-release, prefer `git_share_and_land.sh --with-release`; it may create the root `.git-orchestrator.json` and `.github/workflows/release.yml` on the current branch before commit and merge, but it must not modify product source files.

### Share-And-Land

Require these before `git_share_and_land.sh`:
- explicit human confirmation
- repo policy allows direct share-and-land
- the base branch is not forced into PR-only mode by policy
- verification can run locally before the base branch is pushed

## Core Flows

### Submit Current Work Through a PR

1. Determine the base branch. Prefer the current branch unless the user names another base.
2. Create a feature branch with `bash scripts/git_start_branch.sh --slug ...`.
3. Run `bash scripts/lint_repo.sh` when the request is “submit this work” rather than a narrower action.
4. Generate a commit message only if the user did not provide one:
   `uv run python scripts/generate_commit_message.py --context "..." --json`
5. Commit and push with `bash scripts/git_commit_and_push.sh ...`.
   If requirement/design/test-doc/todo paths are known, pass them explicitly so the preflight TODO checklist validates the intended evidence files.
6. If deploy or workflow dispatch was requested, resolve inputs with:
   `uv run python scripts/resolve_workflow_inputs.py ...`
7. Generate the PR body:
   `uv run python scripts/generate_pr_body.py ...`
8. Create the PR:
   `uv run python scripts/github_ops.py create-pr ...`
9. Inspect or sync the PR only when asked.
10. Merge only when the user asked for merge and repository rules allow it.
11. If the resolved config enables `release.after_merge`, trigger `uv run python scripts/github_ops.py dispatch-release ...` after merge success.

### Narrow PR / Workflow Operations

If the user asks for one operation only, do only that operation:
- inspect PR status: `get-pr`
- update PR branch: `update-branch`
- merge approved PR: `merge-pr`
- dispatch workflow: `dispatch-workflow`
- watch workflow run: `wait-run`

Do not create branches, generate commits, or open new PRs unless the request requires it.

### Share-And-Land

1. Require `--confirmed`.
2. Treat the current branch as the base branch unless the user names another one.
3. Fetch the latest remote base branch.
4. Create a `share/...` branch from the current local state.
5. If `--with-release` was requested, ensure repo-root release automation files exist on the current branch before commit.
6. Run the preflight TODO checklist before any commit is created.
7. Commit dirty changes if needed; reuse local commits if already ahead.
8. Rebase the share branch onto the latest remote base branch.
9. Push the share branch first.
10. Run repository verification with `bash scripts/verify_repo.sh` or `VERIFY_CMD`.
11. If the base branch moved during verification, rebase, force-push with lease, and verify again.
12. If conflicts occur, auto-resolve only when repo policy explicitly allows it and the conflicted paths are allowed.
13. If verification fails, stop after the share-branch push.
14. If the base branch is protected and policy requires a PR, stop after the share-branch push and report `merge=pull_request_required`.
15. Only then merge back into the base branch and push the base branch.
16. If the resolved config enables `release.after_merge`, trigger `uv run python scripts/github_ops.py dispatch-release --ref <base-branch>`.

## Blocker Table

Stop on these markers. Do not improvise around them.

| Marker | Meaning | Next action |
| --- | --- | --- |
| `--confirmed is required` | share-and-land was requested without explicit human confirmation | stop and ask for confirmation |
| `No staged changes to commit` | `--no-add-all` was used but nothing is staged | stop and ask the user to stage files or remove `--no-add-all` |
| `Submission readiness check failed` | requirement/design/test-doc/test-code/TODO preflight failed | stop and ask for the missing or incomplete delivery evidence |
| `Missing required change basis` | requirement, design, or test evidence failed the gate | stop and ask for the missing evidence or matching files |
| `Workflow config file not found` | workflow defaults were requested but neither repo-root `.git-orchestrator.json` nor `git-orchestrator/.git-orchestrator.json` was found | stop and ask for config or explicit workflow inputs |
| `Missing required workflow inputs` | dispatch payload is incomplete | stop and ask for the missing keys |
| `GitHub remote must use HTTPS` | auth path is SSH or HTTP instead of GitHub HTTPS | stop and switch the remote to HTTPS |
| `Missing CLAW_GITHUB_TOKEN` | GitHub HTTPS auth is unavailable from the environment and `skills/.env` | stop and ask for token setup |
| `verification=failed` | verification failed after share-branch push | stop; do not attempt landing |
| `merge=pull_request_required` | repo policy blocks direct landing to the base branch | stop and open a PR instead |
| `conflict_resolution=blocked` | auto-resolution is disabled or not allowed for these paths | stop and hand conflict resolution to a human |
| `conflict_resolution=failed` | auto-resolution ran but left an unsafe result | stop and hand conflict resolution to a human |

## Command Notes

- Use `uv run python` for repo Python scripts.
- Use `uv run --with pytest python -m pytest ...` for test commands in environments that do not already provide `pytest`.
- Keep commit subjects reviewer-readable and under 72 characters when practical.
- Prefer conventional commit subjects such as `fix(auth): ...` or `feat(api): ...`.
- Keep machine-readable script output in the transcript before summarizing it in prose.

## Worked Example

User request: “submit this work as a PR”

1. Create a branch:
   `bash scripts/git_start_branch.sh --slug fix-login-bug`
2. If needed, generate a commit message:
   `uv run python scripts/generate_commit_message.py --context "handle empty refresh token before jwt parsing" --json`
3. Commit and push:
   `bash scripts/git_commit_and_push.sh --subject "fix(auth): handle empty refresh token" --body "Reject empty refresh token values before JWT parsing." --requirement docs/requirements/auth-refresh-token.md --design docs/design/auth-refresh-token.md --test-doc docs/tests/auth-refresh-token.md --test tests/test_auth_refresh_token.py --todo docs/todo/auth-refresh-token.md`
4. Generate the PR body:
   `uv run python scripts/generate_pr_body.py --title "fix(auth): handle empty refresh token" --base main --head agent/main-20260415010203-fix-login-bug --out /tmp/pr_body.md`
5. Open the PR:
   `uv run python scripts/github_ops.py create-pr --title "fix(auth): handle empty refresh token" --head agent/main-20260415010203-fix-login-bug --base main --body-file /tmp/pr_body.md`

Expected raw outputs to preserve:
- from branch creation: `base_branch=...`, `feature_branch=...`
- from commit/push: `branch=...`, `commit_sha=...`, `pushed=1`
- from PR creation: PR number, URL, and state from JSON output

## Checklist

Before reporting success, confirm all applicable items:
- branch naming matches `<prefix>/<base-branch>-<yyyyMMddHHmmss>-<slug>`
- auth requirements were satisfied through environment variables or `skills/.env`
- evidence gate result was recorded as `ok` or `skipped`
- preflight TODO checklist passed for requirements, design, test docs, test code, and TODO completion
- raw script output was preserved for `base_branch`, `feature_branch`, `commit_sha`, and `pushed`
- PR flows captured the PR number and URL
- workflow flows captured the run ID and status
- share-and-land flows captured `verification`, `merge`, `conflict_resolution`, and `conflict_context`
- blockers were surfaced immediately instead of being worked around

## Reference Boundary

Keep `SKILL.md` procedural.

Use `README.md` for:
- long command catalogs
- config examples
- extended operational notes
- cleanup policy and broader human-facing guidance
