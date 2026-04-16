#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REMOTE="origin"
BASE_BRANCH=""
PREFIX=""
SLUG=""
SUBJECT=""
BODY=""
CONTEXT=""
CONFIRMED=0
ADD_ALL=1
VERIFY_CMD_ARG=""
MERGE_MODE="merge"
REQUIREMENTS=()
DESIGNS=()
TESTS=()
POST_SHARE_CMD="${POST_SHARE_CMD:-}"
GIT_AUTH_ARGS=()
CONFLICT_PATHS=()
RESOLVED_PATHS=()
CONFLICT_RESOLUTION_STATUS="not_needed"
CONFLICT_RESOLUTION_CONTEXT="none"
CONFLICT_RESOLUTION_ATTEMPTS=0
AUTO_RESOLVE_CONFLICTS="false"
AUTO_RESOLVE_CONFLICTS_COMMAND=""
ALLOWED_CONFLICT_PATHS="[]"
BLOCKED_CONFLICT_PATHS="[]"
MAX_CONFLICT_RESOLUTION_ATTEMPTS=0
VERIFY_AFTER_LANDING=0
RELEASE_STATUS="not_configured"
RELEASE_WORKFLOW=""
RELEASE_RUN_ID=""
RELEASE_URL=""
WITH_RELEASE=0
RELEASE_BOOTSTRAP_STATUS="not_requested"
RELEASE_BOOTSTRAP_CONFIG_PATH=""
RELEASE_BOOTSTRAP_WORKFLOW_PATH=""

run_python() {
  uv run python "$@"
}

usage() {
  cat <<'USAGE'
Usage: git_share_and_land.sh --confirmed --slug <slug> [--with-release] [--base <branch>] [--prefix <prefix>] [--subject <message>] [--body <details>] [--context <summary>] [--remote <remote>] [--verify-cmd <cmd>] [--requirement <path>] [--design <path>] [--test <path>] [--no-add-all] [--merge-mode <merge|ff-only>]
USAGE
}

slugify_segment() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//; s/--+/-/g'
}

branch_date_stamp() {
  if [[ -n "${GIT_ORCHESTRATOR_BRANCH_DATE:-}" ]]; then
    printf '%s\n' "${GIT_ORCHESTRATOR_BRANCH_DATE}"
    return 0
  fi
  date '+%Y%m%d%H%M%S'
}

summary() {
  printf 'base_branch=%s\nfeature_branch=%s\nverification=%s\nmerge=%s\nconflict_resolution=%s\nconflict_context=%s\nrelease_bootstrap=%s\nrelease_bootstrap_config=%s\nrelease_bootstrap_workflow=%s\nrelease=%s\nrelease_workflow=%s\nrelease_run_id=%s\nrelease_url=%s\n' \
    "${BASE_BRANCH:-}" \
    "${FEATURE_BRANCH:-}" \
    "${VERIFICATION_STATUS:-not_run}" \
    "${MERGE_STATUS:-not_attempted}" \
    "${CONFLICT_RESOLUTION_STATUS:-not_needed}" \
    "${CONFLICT_RESOLUTION_CONTEXT:-none}" \
    "${RELEASE_BOOTSTRAP_STATUS:-not_requested}" \
    "${RELEASE_BOOTSTRAP_CONFIG_PATH:-}" \
    "${RELEASE_BOOTSTRAP_WORKFLOW_PATH:-}" \
    "${RELEASE_STATUS:-not_configured}" \
    "${RELEASE_WORKFLOW:-}" \
    "${RELEASE_RUN_ID:-}" \
    "${RELEASE_URL:-}"
}

ensure_local_branch() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    git switch "$branch" >/dev/null
    return 0
  fi
  if git show-ref --verify --quiet "refs/remotes/${REMOTE}/${branch}"; then
    git switch -c "$branch" --track "${REMOTE}/${branch}" >/dev/null
    return 0
  fi
  echo "Base branch '${branch}' not found locally or on remote '${REMOTE}'" >&2
  exit 1
}

policy_get() {
  run_python "${SCRIPT_DIR}/repo_policy.py" --repo-root . --get "$1"
}

load_git_auth_args() {
  local remote_url="$1"
  eval "$(run_python "${SCRIPT_DIR}/resolve_git_auth.py" --remote-url "$remote_url" --format shell)"
}

ensure_auth_ready() {
  local remote_url="$1"
  run_python "${SCRIPT_DIR}/diagnose_auth.py" --remote-url "$remote_url" --require-ready
}

git_network() {
  if [[ "${#GIT_AUTH_ARGS[@]}" -gt 0 ]]; then
    git "${GIT_AUTH_ARGS[@]}" "$@"
  else
    git "$@"
  fi
}

build_basis_args() {
  BASIS_ARGS=()
  if [[ "${#REQUIREMENTS[@]}" -gt 0 ]]; then
    for item in "${REQUIREMENTS[@]}"; do
      BASIS_ARGS+=(--requirement "$item")
    done
  fi
  if [[ "${#DESIGNS[@]}" -gt 0 ]]; then
    for item in "${DESIGNS[@]}"; do
      BASIS_ARGS+=(--design "$item")
    done
  fi
  if [[ "${#TESTS[@]}" -gt 0 ]]; then
    for item in "${TESTS[@]}"; do
      BASIS_ARGS+=(--test "$item")
    done
  fi
}

run_basis_check() {
  build_basis_args
  if [[ "${#BASIS_ARGS[@]}" -gt 0 ]]; then
    run_python "${SCRIPT_DIR}/validate_change_basis.py" --against-ref "${REMOTE}/${BASE_BRANCH}" "${BASIS_ARGS[@]}"
  else
    run_python "${SCRIPT_DIR}/validate_change_basis.py" --against-ref "${REMOTE}/${BASE_BRANCH}"
  fi
}

run_verify() {
  if [[ -n "$VERIFY_CMD_ARG" ]]; then
    VERIFY_CMD="$VERIFY_CMD_ARG" bash "${SCRIPT_DIR}/verify_repo.sh"
    return $?
  fi
  bash "${SCRIPT_DIR}/verify_repo.sh"
}

ensure_release_assets() {
  local bootstrap_output

  if ! bootstrap_output="$(run_python "${SCRIPT_DIR}/bootstrap_release_assets.py" --repo-root .)"; then
    RELEASE_BOOTSTRAP_STATUS="failed"
    return 1
  fi

  RELEASE_BOOTSTRAP_STATUS="$(printf '%s\n' "$bootstrap_output" | awk -F= '$1=="release_bootstrap"{print $2}')"
  RELEASE_BOOTSTRAP_CONFIG_PATH="$(printf '%s\n' "$bootstrap_output" | awk -F= '$1=="config_path"{print $2}')"
  RELEASE_BOOTSTRAP_WORKFLOW_PATH="$(printf '%s\n' "$bootstrap_output" | awk -F= '$1=="workflow_path"{print $2}')"
}

trigger_release_after_merge() {
  local release_output

  if ! release_output="$(run_python "${SCRIPT_DIR}/github_ops.py" dispatch-release --ref "$BASE_BRANCH")"; then
    RELEASE_STATUS="failed"
    return 1
  fi

  RELEASE_STATUS="$(run_python -c 'import json,sys; payload=json.load(sys.stdin); print("triggered" if payload.get("dispatched") else "not_configured")' <<<"$release_output")"
  RELEASE_WORKFLOW="$(run_python -c 'import json,sys; payload=json.load(sys.stdin); print(payload.get("workflow", ""))' <<<"$release_output")"
  RELEASE_RUN_ID="$(run_python -c 'import json,sys; payload=json.load(sys.stdin); run=payload.get("run") or {}; print(run.get("id", ""))' <<<"$release_output")"
  RELEASE_URL="$(run_python -c 'import json,sys; payload=json.load(sys.stdin); run=payload.get("run") or {}; print(run.get("html_url", ""))' <<<"$release_output")"
}

collect_conflicted_paths() {
  CONFLICT_PATHS=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && CONFLICT_PATHS+=("$line")
  done < <(git diff --name-only --diff-filter=U)
}

has_active_rebase() {
  local rebase_merge
  local rebase_apply
  rebase_merge="$(git rev-parse --git-path rebase-merge)"
  rebase_apply="$(git rev-parse --git-path rebase-apply)"
  [[ -d "$rebase_merge" || -d "$rebase_apply" ]]
}

check_conflict_paths_allowed() {
  run_python - "$ALLOWED_CONFLICT_PATHS" "$BLOCKED_CONFLICT_PATHS" "${CONFLICT_PATHS[@]}" <<'PY'
import json
import sys
from pathlib import PurePosixPath


def matches(path: str, pattern: str) -> bool:
    pure_path = PurePosixPath(path)
    pure_pattern = pattern.replace("\\", "/")
    return pure_path.match(pure_pattern) or PurePosixPath(f"./{path}").match(pure_pattern)


allowed = json.loads(sys.argv[1])
blocked = json.loads(sys.argv[2])
paths = sys.argv[3:]

blocked_hits = [path for path in paths if any(matches(path, pattern) for pattern in blocked)]
if blocked_hits:
    raise SystemExit(
        "Auto-resolve is not allowed for conflicted paths: " + ", ".join(blocked_hits)
    )

if allowed:
    disallowed = [path for path in paths if not any(matches(path, pattern) for pattern in allowed)]
    if disallowed:
        raise SystemExit(
            "Auto-resolve is not allowed outside configured paths: " + ", ".join(disallowed)
        )
PY
}

check_conflict_markers_resolved() {
  if [[ "${#RESOLVED_PATHS[@]}" -eq 0 ]]; then
    echo "Conflict resolver did not report any conflicted paths." >&2
    return 1
  fi

  if command -v rg >/dev/null 2>&1; then
    if rg -n '^(<<<<<<< |=======|>>>>>>> )' -- "${RESOLVED_PATHS[@]}" >/dev/null 2>&1; then
      echo "Conflict resolver left merge markers in resolved files." >&2
      return 1
    fi
    return 0
  fi

  if grep -R -n -E '^(<<<<<<< |=======|>>>>>>> )' -- "${RESOLVED_PATHS[@]}" >/dev/null 2>&1; then
    echo "Conflict resolver left merge markers in resolved files." >&2
    return 1
  fi
}

attempt_conflict_resolution() {
  local context="$1"
  CONFLICT_RESOLUTION_CONTEXT="$context"
  collect_conflicted_paths
  if [[ "${#CONFLICT_PATHS[@]}" -eq 0 ]]; then
    echo "Git reported a ${context} failure without conflicted paths to resolve." >&2
    CONFLICT_RESOLUTION_STATUS="failed"
    return 1
  fi

  if [[ "$AUTO_RESOLVE_CONFLICTS" != "true" ]]; then
    echo "Auto-resolve is disabled by repo policy. Resolve conflicts manually." >&2
    CONFLICT_RESOLUTION_STATUS="blocked"
    return 1
  fi

  if [[ -z "$AUTO_RESOLVE_CONFLICTS_COMMAND" ]]; then
    echo "Auto-resolve is enabled but no auto_resolve_conflicts_command is configured." >&2
    CONFLICT_RESOLUTION_STATUS="blocked"
    return 1
  fi

  if (( CONFLICT_RESOLUTION_ATTEMPTS >= MAX_CONFLICT_RESOLUTION_ATTEMPTS )); then
    echo "Exceeded max conflict auto-resolution attempts (${MAX_CONFLICT_RESOLUTION_ATTEMPTS})." >&2
    CONFLICT_RESOLUTION_STATUS="blocked"
    return 1
  fi

  if ! check_conflict_paths_allowed 2>/tmp/git-orchestrator-conflict-check.$$; then
    cat /tmp/git-orchestrator-conflict-check.$$ >&2
    rm -f /tmp/git-orchestrator-conflict-check.$$
    CONFLICT_RESOLUTION_STATUS="blocked"
    return 1
  fi
  rm -f /tmp/git-orchestrator-conflict-check.$$

  CONFLICT_RESOLUTION_ATTEMPTS=$((CONFLICT_RESOLUTION_ATTEMPTS + 1))
  RESOLVED_PATHS=("${CONFLICT_PATHS[@]}")

  export GIT_ORCHESTRATOR_CONFLICT_CONTEXT="$context"
  export GIT_ORCHESTRATOR_CONFLICT_BASE_BRANCH="$BASE_BRANCH"
  export GIT_ORCHESTRATOR_CONFLICT_FEATURE_BRANCH="$FEATURE_BRANCH"
  export GIT_ORCHESTRATOR_CONFLICT_FILES
  GIT_ORCHESTRATOR_CONFLICT_FILES="$(printf '%s\n' "${RESOLVED_PATHS[@]}")"

  if ! eval "$AUTO_RESOLVE_CONFLICTS_COMMAND"; then
    echo "Auto-resolve command failed for ${context} conflicts." >&2
    CONFLICT_RESOLUTION_STATUS="failed"
    return 1
  fi

  if ! check_conflict_markers_resolved; then
    CONFLICT_RESOLUTION_STATUS="failed"
    return 1
  fi

  git add -- "${RESOLVED_PATHS[@]}"
  collect_conflicted_paths
  if [[ "${#CONFLICT_PATHS[@]}" -gt 0 ]]; then
    echo "Auto-resolve command did not resolve all conflicted files: ${CONFLICT_PATHS[*]}" >&2
    CONFLICT_RESOLUTION_STATUS="failed"
    return 1
  fi

  CONFLICT_RESOLUTION_STATUS="resolved"
  return 0
}

rebase_onto_base() {
  if git rebase "${REMOTE}/${BASE_BRANCH}" >/dev/null 2>&1; then
    return 0
  fi

  while has_active_rebase; do
    if ! attempt_conflict_resolution "rebase"; then
      return 1
    fi

    if GIT_EDITOR=true git rebase --continue >/dev/null 2>&1; then
      if ! has_active_rebase; then
        return 0
      fi
      continue
    fi

    collect_conflicted_paths
    if [[ "${#CONFLICT_PATHS[@]}" -eq 0 ]]; then
      echo "git rebase --continue failed after auto-resolution." >&2
      CONFLICT_RESOLUTION_STATUS="failed"
      return 1
    fi
  done

  echo "git rebase failed before the rebase state could be inspected." >&2
  CONFLICT_RESOLUTION_STATUS="failed"
  return 1
}

merge_feature_into_base() {
  if [[ "$MERGE_MODE" == "ff-only" ]]; then
    git merge --ff-only "$FEATURE_BRANCH" >/dev/null
    return 0
  fi

  if git merge --no-ff "$FEATURE_BRANCH" -m "merge(${BASE_BRANCH}): land ${FEATURE_BRANCH}" >/dev/null 2>&1; then
    return 0
  fi

  collect_conflicted_paths
  if [[ "${#CONFLICT_PATHS[@]}" -eq 0 ]]; then
    echo "git merge failed without conflicted paths to resolve." >&2
    return 1
  fi

  if ! attempt_conflict_resolution "merge"; then
    return 1
  fi

  if ! GIT_EDITOR=true git commit --no-edit >/dev/null 2>&1; then
    echo "git merge commit failed after auto-resolution." >&2
    CONFLICT_RESOLUTION_STATUS="failed"
    return 1
  fi

  VERIFY_AFTER_LANDING=1
  return 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirmed)
      CONFIRMED=1; shift ;;
    --with-release)
      WITH_RELEASE=1; shift ;;
    --base)
      BASE_BRANCH="$2"; shift 2 ;;
    --prefix)
      PREFIX="$2"; shift 2 ;;
    --slug)
      SLUG="$2"; shift 2 ;;
    --subject)
      SUBJECT="$2"; shift 2 ;;
    --body)
      BODY="$2"; shift 2 ;;
    --context)
      CONTEXT="$2"; shift 2 ;;
    --remote)
      REMOTE="$2"; shift 2 ;;
    --verify-cmd)
      VERIFY_CMD_ARG="$2"; shift 2 ;;
    --requirement)
      REQUIREMENTS+=("$2"); shift 2 ;;
    --design)
      DESIGNS+=("$2"); shift 2 ;;
    --test)
      TESTS+=("$2"); shift 2 ;;
    --no-add-all)
      ADD_ALL=0; shift ;;
    --merge-mode)
      MERGE_MODE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ "$CONFIRMED" -ne 1 ]]; then
  echo "--confirmed is required before sharing or landing changes." >&2
  exit 2
fi

if [[ -z "$SLUG" ]]; then
  echo "--slug is required" >&2
  exit 2
fi

if [[ "$MERGE_MODE" != "merge" && "$MERGE_MODE" != "ff-only" ]]; then
  echo "--merge-mode must be one of: merge, ff-only" >&2
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Current directory is not a git repository" >&2
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ -z "$CURRENT_BRANCH" ]]; then
  echo "Detached HEAD is not supported for share-and-land workflow" >&2
  exit 1
fi

if [[ -z "$BASE_BRANCH" ]]; then
  BASE_BRANCH="$CURRENT_BRANCH"
fi

if [[ -z "$PREFIX" ]]; then
  PREFIX="$(policy_get defaults.share_branch_prefix)"
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "Remote '$REMOTE' not found" >&2
  exit 1
fi
remote_url="$(git remote get-url "$REMOTE")"
ensure_auth_ready "$remote_url"
load_git_auth_args "$remote_url"

base_slug="$(slugify_segment "$BASE_BRANCH")"
slugified="$(slugify_segment "$SLUG")"
date_stamp="$(branch_date_stamp)"
branch_suffix="${base_slug}-${date_stamp}-${slugified}"
if [[ -n "$PREFIX" ]]; then
  FEATURE_BRANCH="${PREFIX}/${branch_suffix}"
else
  FEATURE_BRANCH="${branch_suffix}"
fi
VERIFICATION_STATUS="not_run"
MERGE_STATUS="not_attempted"
protected_branches="$(policy_get share_and_land.protected_branches)"
protected_mode="$(policy_get share_and_land.protected_branch_mode)"
allow_direct="$(policy_get share_and_land.allow_direct)"
reverify_on_base_change="$(policy_get share_and_land.reverify_on_base_change)"
max_reverify_attempts="$(policy_get share_and_land.max_reverify_attempts)"
AUTO_RESOLVE_CONFLICTS="$(policy_get share_and_land.auto_resolve_conflicts)"
AUTO_RESOLVE_CONFLICTS_COMMAND="${AUTO_RESOLVE_CONFLICTS_CMD:-$(policy_get share_and_land.auto_resolve_conflicts_command)}"
ALLOWED_CONFLICT_PATHS="$(policy_get share_and_land.allowed_conflict_paths)"
BLOCKED_CONFLICT_PATHS="$(policy_get share_and_land.blocked_conflict_paths)"
MAX_CONFLICT_RESOLUTION_ATTEMPTS="$(policy_get share_and_land.max_conflict_resolution_attempts)"

if [[ "$allow_direct" != "true" ]]; then
  echo "Direct share-and-land is disabled by repo policy." >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/${FEATURE_BRANCH}" || git show-ref --verify --quiet "refs/remotes/${REMOTE}/${FEATURE_BRANCH}"; then
  echo "Feature branch '${FEATURE_BRANCH}' already exists" >&2
  exit 1
fi

git_network fetch "$REMOTE" "$BASE_BRANCH" >/dev/null
if [[ -z "$(git status --porcelain)" ]]; then
  ensure_local_branch "$BASE_BRANCH"
  git_network pull --ff-only "$REMOTE" "$BASE_BRANCH" >/dev/null
fi
git switch -c "$FEATURE_BRANCH" >/dev/null

if [[ "$WITH_RELEASE" -eq 1 ]]; then
  if ! ensure_release_assets; then
    summary
    exit 1
  fi
fi

dirty_changes=0
if [[ -n "$(git status --porcelain)" ]]; then
  dirty_changes=1
fi

ahead_count="$(git rev-list --count "${REMOTE}/${BASE_BRANCH}..HEAD" 2>/dev/null || printf '0')"
if [[ "$dirty_changes" -eq 0 && "$ahead_count" == "0" ]]; then
  echo "No local changes or commits to share from '${BASE_BRANCH}'" >&2
  exit 1
fi

run_basis_check

if [[ "$dirty_changes" -eq 1 ]]; then
  if [[ -z "$SUBJECT" ]]; then
    generated="$(run_python "${SCRIPT_DIR}/generate_commit_message.py" --context "$CONTEXT" --json)"
    SUBJECT="$(run_python -c 'import json,sys; print(json.loads(sys.stdin.read())["subject"])' <<<"$generated")"
    BODY="$(run_python -c 'import json,sys; print(json.loads(sys.stdin.read())["body"])' <<<"$generated")"
  fi

  commit_args=(--subject "$SUBJECT" --no-push)
  if [[ -n "$BODY" ]]; then
    commit_args+=(--body "$BODY")
  fi
  if [[ "${#REQUIREMENTS[@]}" -gt 0 ]]; then
    for item in "${REQUIREMENTS[@]}"; do
      commit_args+=(--requirement "$item")
    done
  fi
  if [[ "${#DESIGNS[@]}" -gt 0 ]]; then
    for item in "${DESIGNS[@]}"; do
      commit_args+=(--design "$item")
    done
  fi
  if [[ "${#TESTS[@]}" -gt 0 ]]; then
    for item in "${TESTS[@]}"; do
      commit_args+=(--test "$item")
    done
  fi
  if [[ "$ADD_ALL" -eq 0 ]]; then
    commit_args+=(--no-add-all)
  fi
  bash "${SCRIPT_DIR}/git_commit_and_push.sh" "${commit_args[@]}" >/dev/null
fi

if ! rebase_onto_base; then
  summary
  exit 1
fi
verified_base_sha="$(git rev-parse "${REMOTE}/${BASE_BRANCH}")"
git_network push -u "$REMOTE" "$FEATURE_BRANCH" >/dev/null

if [[ -n "$POST_SHARE_CMD" ]]; then
  eval "${POST_SHARE_CMD}"
fi

attempt=0
while true; do
  if ! run_verify; then
    VERIFICATION_STATUS="failed"
    summary
    exit 1
  fi
  VERIFICATION_STATUS="passed"

  git_network fetch "$REMOTE" "$BASE_BRANCH" >/dev/null
  latest_base_sha="$(git rev-parse "${REMOTE}/${BASE_BRANCH}")"
  if [[ "$reverify_on_base_change" != "true" || "$latest_base_sha" == "$verified_base_sha" ]]; then
    break
  fi

  attempt=$((attempt + 1))
  if (( attempt >= max_reverify_attempts )); then
    VERIFICATION_STATUS="stale"
    MERGE_STATUS="blocked"
    summary
    exit 1
  fi

  git switch "$FEATURE_BRANCH" >/dev/null
  if ! rebase_onto_base; then
    MERGE_STATUS="blocked"
    summary
    exit 1
  fi
  git_network push --force-with-lease -u "$REMOTE" "$FEATURE_BRANCH" >/dev/null
  verified_base_sha="$latest_base_sha"
done

if run_python - <<'PY' "$protected_branches" "$BASE_BRANCH"
import json
import sys
branches = json.loads(sys.argv[1])
base = sys.argv[2]
raise SystemExit(0 if base in branches else 1)
PY
then
  if [[ "$protected_mode" == "require-pull-request" ]]; then
    MERGE_STATUS="pull_request_required"
    summary
    exit 0
  fi
fi

git_network fetch "$REMOTE" "$BASE_BRANCH" >/dev/null
ensure_local_branch "$BASE_BRANCH"
git_network pull --ff-only "$REMOTE" "$BASE_BRANCH" >/dev/null

if [[ "$MERGE_MODE" == "ff-only" ]]; then
  if ! merge_feature_into_base; then
    MERGE_STATUS="blocked"
    summary
    exit 1
  fi
elif ! merge_feature_into_base; then
  MERGE_STATUS="blocked"
  summary
  exit 1
fi

if [[ "$VERIFY_AFTER_LANDING" -eq 1 ]]; then
  if ! run_verify; then
    VERIFICATION_STATUS="failed"
    MERGE_STATUS="blocked"
    summary
    exit 1
  fi
  VERIFICATION_STATUS="passed"
fi

if ! git_network push "$REMOTE" "$BASE_BRANCH" >/dev/null; then
  MERGE_STATUS="blocked"
  summary
  exit 1
fi
MERGE_STATUS="done"
if ! trigger_release_after_merge; then
  summary
  exit 1
fi
summary
exit 0
