#!/usr/bin/env bash
set -euo pipefail

BASE_BRANCH=""
PREFIX=""
SLUG=""
REMOTE="origin"
ALLOW_DIRTY=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_AUTH_ARGS=()

run_python() {
  uv run python "$@"
}

usage() {
  cat <<'USAGE'
Usage: git_start_branch.sh [--base <branch>] [--prefix <prefix>] --slug <slug> [--remote <remote>] [--allow-dirty]
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

discover_base_branch() {
  local remote="$1"
  local head_ref=""

  head_ref=$(git symbolic-ref --quiet --short "refs/remotes/${remote}/HEAD" 2>/dev/null || true)
  if [[ -z "$head_ref" ]]; then
    git remote set-head "$remote" --auto >/dev/null 2>&1 || true
    head_ref=$(git symbolic-ref --quiet --short "refs/remotes/${remote}/HEAD" 2>/dev/null || true)
  fi

  if [[ -n "$head_ref" ]]; then
    printf '%s\n' "${head_ref#${remote}/}"
    return 0
  fi

  printf 'main\n'
}

current_branch_or_empty() {
  git branch --show-current 2>/dev/null || true
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE_BRANCH="$2"; shift 2 ;;
    --prefix)
      PREFIX="$2"; shift 2 ;;
    --slug)
      SLUG="$2"; shift 2 ;;
    --remote)
      REMOTE="$2"; shift 2 ;;
    --allow-dirty)
      ALLOW_DIRTY=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ -z "$SLUG" ]]; then
  echo "--slug is required" >&2
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Current directory is not a git repository" >&2
  exit 1
fi

if [[ "$ALLOW_DIRTY" -ne 1 ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit or stash changes first, or pass --allow-dirty." >&2
  exit 1
fi

if [[ -z "$PREFIX" ]]; then
  PREFIX="$(policy_get defaults.feature_branch_prefix)"
fi

if git remote get-url "$REMOTE" >/dev/null 2>&1; then
  remote_url="$(git remote get-url "$REMOTE")"
  ensure_auth_ready "$remote_url"
  load_git_auth_args "$remote_url"
  if [[ -z "$BASE_BRANCH" ]]; then
    strategy="$(policy_get defaults.base_branch_strategy)"
    current_branch="$(current_branch_or_empty)"
    if [[ "$strategy" == "current-branch" && -n "$current_branch" ]]; then
      BASE_BRANCH="$current_branch"
    else
      BASE_BRANCH="$(discover_base_branch "$REMOTE")"
    fi
  fi
  git_network fetch "$REMOTE" "$BASE_BRANCH"
  if git show-ref --verify --quiet "refs/heads/${BASE_BRANCH}"; then
    git switch "$BASE_BRANCH"
  elif git show-ref --verify --quiet "refs/remotes/${REMOTE}/${BASE_BRANCH}"; then
    git switch -c "$BASE_BRANCH" --track "${REMOTE}/${BASE_BRANCH}"
  else
    echo "Base branch '${BASE_BRANCH}' not found on remote '${REMOTE}'" >&2
    exit 1
  fi
  git_network pull --ff-only "$REMOTE" "$BASE_BRANCH"
else
  echo "Remote '$REMOTE' not found" >&2
  exit 1
fi

base_slug="$(slugify_segment "$BASE_BRANCH")"
slugified="$(slugify_segment "$SLUG")"
date_stamp="$(branch_date_stamp)"
branch_suffix="${base_slug}-${date_stamp}-${slugified}"
if [[ -n "$PREFIX" ]]; then
  branch_name="${PREFIX}/${branch_suffix}"
else
  branch_name="${branch_suffix}"
fi

if git show-ref --verify --quiet "refs/heads/${branch_name}"; then
  git switch "$branch_name"
else
  git switch -c "$branch_name"
fi

printf 'base_branch=%s\nfeature_branch=%s\n' "$BASE_BRANCH" "$branch_name"
