# GitHub API guide for this skill

## Environment variables

Set these before running the API script or GitHub HTTPS git operations:

- `CLAW_GITHUB_TOKEN`: required bearer token for this skill.
- `GITHUB_OWNER`: repository owner. Optional if inferable from `origin`.
- `GITHUB_REPO`: repository name. Optional if inferable from `origin`.
- `GITHUB_API_URL`: optional. Defaults to `https://api.github.com`.

For git network operations, prefer:

- `origin = https://github.com/<owner>/<repo>.git`
- `CLAW_GITHUB_TOKEN` exported only in the current shell session
- revoke the token after use

## Token permissions

For a fine-grained token, plan for these minimum permissions:

- pull requests: read/write
- contents: read/write
- actions: read/write when dispatching or rerunning workflows
- checks: read, and write if rerequesting checks

## Endpoints used by the script

- create pull request: `POST /repos/{owner}/{repo}/pulls`
- get pull request: `GET /repos/{owner}/{repo}/pulls/{pull_number}`
- list pull requests: `GET /repos/{owner}/{repo}/pulls`
- merge pull request: `PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge`
- update pull request branch: `PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch`
- list workflow runs: `GET /repos/{owner}/{repo}/actions/runs`
- get workflow run: `GET /repos/{owner}/{repo}/actions/runs/{run_id}`
- rerun workflow: `POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun`
- dispatch workflow: `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches`

## Practical notes

- `dispatch-workflow` only works for workflows configured with `workflow_dispatch`.
- `merge-pr` can still be blocked by branch protection, merge queue, required reviews, required checks, environment rules, or stale head SHA.
- `update-branch` merges the latest base branch into the PR branch on GitHub's side.
- `wait-run` polls the workflow run until it reaches a terminal state or times out.
- Prefer using the PR head SHA with merge requests to avoid merging an unexpected newer head.
