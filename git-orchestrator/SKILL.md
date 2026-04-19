---
name: git-orchestrator
description: "Use when an agent needs a repeatable Git or GitHub delivery workflow for branching, committing, pushing, pull requests, workflow dispatch, share-and-land after explicit human confirmation, or cleaning mistakenly tracked files from Git history before continuing delivery."
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
- inspect when a sensitive or local-only file entered Git history
- stop tracking or purge a mistakenly committed file, then continue the delivery flow
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
| Inspect why a file is still being uploaded | `bash scripts/git_cleanup_history.sh --inspect --path <path>` |
| Stop tracking a local-only file without rewriting history | `git rm --cached -- <path>` then continue with normal commit / PR / share-and-land flow |
| Purge a file from Git history after explicit confirmation | `bash scripts/git_cleanup_history.sh --confirmed --path <path> [--path <path> ...]` then continue the delivery flow |

## Hard Truths

- Plain git does not create PRs, inspect PRs, or dispatch GitHub Actions workflows. Use `scripts/github_ops.py` for those tasks.
- `.gitignore` does not untrack a file that is already committed. If a file is already in history, you must either stop tracking it with `git rm --cached` or rewrite history.
- History cleanup is part of the delivery lifecycle when the user asks for it, but it is a high-risk subflow. Never run history rewrites as part of the default submit path.
- Prefer `scripts/git_cleanup_history.sh`, which uses `git filter-repo` and restores the active branch upstream mapping after force-push.
- Do not use `git filter-branch` unless the user explicitly requires it and accepts the tradeoff.
- Evidence gating is real. `validate_change_basis.py` can return `ok`, `failed`, or `skipped` depending on repo policy.
- Submit flows now run a stricter preflight TODO checklist before evidence gating: requirements doc, design doc, test doc, test code, and TODO completion must pass before commit/share begins.
- Repo policy can disable those submit-time gates with `policy.evidence.pre_commit_checks_enabled: false`. Keep backward compatibility with `policy.evidence.enforce_before_commit: false`.
- Direct share-and-land always needs explicit human confirmation.
- History rewrites always need explicit human confirmation.
- For GitHub HTTPS remotes, git auth may come from the current environment or `skills/.env`.
- For GitHub SSH remotes, git transport should use the local SSH setup; GitHub API operations still need `CLAW_GITHUB_TOKEN`.

## Branch Naming Truth

The default branch naming pattern is:

`<prefix>/<base-branch>-<yyyyMMddHHmmss>-<slug>`

Examples:
- `agent/main-20260415010203-fix-login-bug`
- `share/release-20260415010203-doc-sync`

For deterministic tests or automation, `GIT_ORCHESTRATOR_BRANCH_DATE` overrides the timestamp segment.

## Mode-Specific Preconditions

### Base Local Git Flow

Require these before branch, commit, verify, history inspection, history cleanup, or share-and-land flows:
- current directory is inside a git repository
- `git` is available
- `uv` is available for Python helper scripts
- the requested remote exists when the task needs fetch or push

### History Cleanup Flow

Require these before rewriting history:
- explicit human confirmation that force-push and history rewrite are intended
- the target file or path is known exactly; do not guess destructive path patterns
- the agent has checked whether simple untracking is sufficient before proposing a rewrite
- `git filter-repo` is available, or the user has approved an alternative tool
- the user understands secrets still need rotation even after the file is removed from history

### GitHub Remote / API Flow

Require these before PR or workflow operations:
- the remote is a GitHub remote; git transport should follow the current remote protocol first
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

## History Cleanup Flow

Use this flow only when the user explicitly asks to inspect or clean a tracked file, secret, or local-only artifact.

1. Inspect whether the file is tracked now with `bash scripts/git_cleanup_history.sh --inspect --path <path>`.
2. Inspect when it entered history with the same script output or `git log --follow -- <path>` and check `.gitignore` timing if relevant.
3. Decide which branch of the flow applies:
   - If the file only needs to stop being tracked going forward, use `git rm --cached -- <path>` and continue with the normal delivery flow.
   - If the file must be removed from history, require explicit confirmation and explain that refs will be rewritten and force-pushed.
4. For history rewrites, prefer `bash scripts/git_cleanup_history.sh --confirmed --path <path> [--path <path> ...]`.
5. Verify removal after the rewrite with the script summary and history inspection commands such as `git log --all -- <path>` or `git rev-list --objects --all`.
6. Continue the normal delivery flow:
   - commit any follow-up `.gitignore` or sample-config changes
   - push or force-push affected refs
   - if requested, continue with PR, merge, or share-and-land
7. After force-push, the cleanup script must check whether the current local branch still has upstream tracking configured and restore it if needed.
8. After the delivery action, re-check that the file is no longer tracked or reachable in history.
9. If secrets were ever committed, treat rotation as mandatory follow-up work, not optional cleanup.

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

### Delivery After Cleanup

If history cleanup was part of the request, do not stop after the rewrite unless the user asked for inspection only.

1. Finish the cleanup verification first.
2. Commit any current-tree follow-up changes such as `.gitignore`, replacement docs, or sample config updates.
3. Continue with the requested submit path:
   - commit and push
   - open or update a PR
   - share-and-land
4. After the final push or merge, run one more check that the target file is absent from the intended refs.
5. Before reporting success, confirm the active local branch still tracks its intended upstream branch; if not, restore that mapping.

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
| `history rewrite confirmation required` | the user asked to purge history but did not explicitly approve rewriting history and force-pushing refs | stop and ask for confirmation |
| `git filter-repo is required` | history rewrite was requested but the preferred rewrite tool is unavailable | stop and ask the user to install or approve an alternative |
| `sensitive path is ambiguous` | the cleanup target is not specific enough for a destructive history rewrite | stop and ask for an exact path or path set |
| `upstream branch mapping missing after rewrite` | history cleanup finished but the active local branch no longer tracks its remote branch | restore the upstream mapping before reporting success |
| `secret rotation still required` | a committed secret was removed from history but not rotated | stop and report that cleanup is incomplete until rotation is handled |
| `No staged changes to commit` | `--no-add-all` was used but nothing is staged | stop and ask the user to stage files or remove `--no-add-all` |
| `Submission readiness check failed` | requirement/design/test-doc/test-code/TODO preflight failed | stop and ask for the missing or incomplete delivery evidence |
| `Missing required change basis` | requirement, design, or test evidence failed the gate | stop and ask for the missing evidence or matching files |
| `Workflow config file not found` | workflow defaults were requested but neither repo-root `.git-orchestrator.json` nor `git-orchestrator/.git-orchestrator.json` was found | stop and ask for config or explicit workflow inputs |
| `Missing required workflow inputs` | dispatch payload is incomplete | stop and ask for the missing keys |
| `GitHub HTTP remotes are not supported` | auth path is HTTP instead of HTTPS or SSH | stop and switch the remote to HTTPS or SSH |
| `Missing CLAW_GITHUB_TOKEN` | HTTPS git auth or GitHub API auth is unavailable from the environment and `skills/.env` | stop and ask for token setup, or ask whether to switch the git remote protocol |
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

User request: “remove `config.yaml` from history, then land the fix”

1. Inspect tracking and history:
   `git ls-files -- config.yaml`
   `git log --follow -- config.yaml`
2. After explicit confirmation, rewrite history:
   `git filter-repo --path config.yaml --invert-paths`
3. Verify removal:
   `git log --all -- config.yaml`
4. Commit follow-up current-tree fixes such as `.gitignore` or `config-sample.yaml` updates.
5. Confirm the cleanup script reported a usable or restored upstream mapping for the active branch.
6. Continue with the requested delivery action, for example:
   `bash scripts/git_share_and_land.sh --confirmed --slug remove-config-yaml --subject "chore(repo): remove tracked config.yaml"`

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
- history-cleanup flows captured whether the file was only untracked or fully purged from history
- history-cleanup flows verified removal after the final push or merge
- history-cleanup flows verified the active local branch still had a usable upstream mapping, or restored it
- committed secrets were called out for rotation when relevant
- blockers were surfaced immediately instead of being worked around

## Reference Boundary

Keep `SKILL.md` procedural.

Use `README.md` for:
- long command catalogs
- config examples
- extended operational notes
- cleanup policy and broader human-facing guidance
