#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REMOTE="origin"
BRANCH=""
CONFIRMED=0
INSPECT_ONLY=0
PUSH=1
BACKUP_DIR=""
PATHS=()
GIT_AUTH_ARGS=()
UPSTREAM_STATUS="not_checked"
UPSTREAM_VALUE=""

run_python() {
  uv run python "$@"
}

usage() {
  cat <<'USAGE'
Usage: git_cleanup_history.sh --path <path> [--path <path> ...] [--inspect] [--confirmed] [--remote <remote>] [--branch <branch>] [--backup-dir <dir>] [--no-push]
USAGE
}

load_git_auth_args() {
  local remote_url="$1"
  eval "$(run_python "${SCRIPT_DIR}/resolve_git_auth.py" --remote-url "$remote_url" --format shell)"
}

ensure_auth_ready() {
  local remote_url="$1"
  run_python "${SCRIPT_DIR}/diagnose_auth.py" --remote-url "$remote_url" --require-ready --require-scope git
}

git_network() {
  if [[ "${#GIT_AUTH_ARGS[@]}" -gt 0 ]]; then
    git "${GIT_AUTH_ARGS[@]}" "$@"
  else
    git "$@"
  fi
}

current_branch() {
  git branch --show-current
}

current_upstream() {
  git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true
}

path_exists_in_history() {
  local path
  for path in "${PATHS[@]}"; do
    if git rev-list --all -- "$path" | grep -q .; then
      return 0
    fi
  done
  return 1
}

inspect_paths() {
  local path tracked ignored history_count first_commit
  for path in "${PATHS[@]}"; do
    tracked="false"
    ignored="false"
    history_count="$(git rev-list --all -- "$path" | wc -l | tr -d ' ')"
    first_commit="$(git log --diff-filter=A --follow --format='%H' -- "$path" | tail -n 1)"
    if git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
      tracked="true"
    fi
    if git check-ignore -q -- "$path"; then
      ignored="true"
    fi
    printf 'path=%s\ntracked=%s\nignored=%s\nhistory_commits=%s\nfirst_commit=%s\n' \
      "$path" "$tracked" "$ignored" "$history_count" "$first_commit"
  done
}

materialize_remote_branches() {
  local branch ref
  while IFS= read -r branch; do
    [[ -z "$branch" ]] && continue
    [[ "$branch" == "HEAD" ]] && continue
    ref="refs/heads/${branch}"
    if git show-ref --verify --quiet "$ref"; then
      continue
    fi
    git branch "$branch" "refs/remotes/${REMOTE}/${branch}" >/dev/null
  done < <(git for-each-ref --format='%(refname:strip=3)' "refs/remotes/${REMOTE}")
}

restore_backups() {
  local path backup_path target_dir
  [[ -z "$BACKUP_DIR" ]] && return 0
  for path in "${PATHS[@]}"; do
    backup_path="${BACKUP_DIR}/files/${path}"
    if [[ ! -f "$backup_path" ]]; then
      continue
    fi
    target_dir="$(dirname "$path")"
    mkdir -p "$target_dir"
    cp "$backup_path" "$path"
  done
}

restore_remote() {
  local remote_url="$1"
  if git remote get-url "$REMOTE" >/dev/null 2>&1; then
    git remote set-url "$REMOTE" "$remote_url"
  else
    git remote add "$REMOTE" "$remote_url"
  fi
}

restore_upstream_if_needed() {
  local branch="$1"
  local upstream_ref="${REMOTE}/${branch}"
  local existing
  existing="$(current_upstream)"
  if [[ -n "$existing" ]]; then
    UPSTREAM_STATUS="preserved"
    UPSTREAM_VALUE="$existing"
    return 0
  fi
  if ! git show-ref --verify --quiet "refs/remotes/${upstream_ref}"; then
    UPSTREAM_STATUS="missing_remote_ref"
    UPSTREAM_VALUE=""
    return 0
  fi
  git branch --set-upstream-to="$upstream_ref" "$branch" >/dev/null
  UPSTREAM_STATUS="restored"
  UPSTREAM_VALUE="$upstream_ref"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      PATHS+=("$2"); shift 2 ;;
    --remote)
      REMOTE="$2"; shift 2 ;;
    --branch)
      BRANCH="$2"; shift 2 ;;
    --backup-dir)
      BACKUP_DIR="$2"; shift 2 ;;
    --inspect)
      INSPECT_ONLY=1; shift ;;
    --confirmed)
      CONFIRMED=1; shift ;;
    --no-push)
      PUSH=0; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ "${#PATHS[@]}" -eq 0 ]]; then
  echo "--path is required" >&2
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Current directory is not a git repository" >&2
  exit 1
fi

if [[ "$INSPECT_ONLY" -eq 1 ]]; then
  inspect_paths
  exit 0
fi

if [[ "$CONFIRMED" -ne 1 ]]; then
  echo "history rewrite confirmation required" >&2
  exit 1
fi

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "git filter-repo is required" >&2
  exit 1
fi

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(current_branch)"
fi

if [[ -z "$BRANCH" ]]; then
  echo "Detached HEAD is not supported for history cleanup workflow" >&2
  exit 1
fi

if [[ -z "$BACKUP_DIR" ]]; then
  BACKUP_DIR="$(mktemp -d /tmp/git-cleanup-history.XXXXXX)"
else
  mkdir -p "$BACKUP_DIR"
fi

mkdir -p "${BACKUP_DIR}/files"
printf 'backup_dir=%s\n' "$BACKUP_DIR"

remote_url="$(git remote get-url "$REMOTE")"

if [[ "$PUSH" -eq 1 ]]; then
  ensure_auth_ready "$remote_url"
  load_git_auth_args "$remote_url"
  git_network fetch "$REMOTE" --prune >/dev/null
  materialize_remote_branches
fi

for path in "${PATHS[@]}"; do
  if [[ -f "$path" ]]; then
    mkdir -p "${BACKUP_DIR}/files/$(dirname "$path")"
    cp "$path" "${BACKUP_DIR}/files/${path}"
  fi
done

git bundle create "${BACKUP_DIR}/pre-cleanup.bundle" --all >/dev/null

filter_args=()
for path in "${PATHS[@]}"; do
  filter_args+=(--path "$path")
done

git filter-repo --force "${filter_args[@]}" --invert-paths >/dev/null

restore_remote "$remote_url"
restore_backups

if path_exists_in_history; then
  echo "history_cleanup_verify=failed_before_push" >&2
  exit 1
fi

if [[ "$PUSH" -eq 1 ]]; then
  git_network push --force --all "$REMOTE" >/dev/null
  git_network push --force --tags "$REMOTE" >/dev/null
  git_network fetch --prune "$REMOTE" >/dev/null
  restore_upstream_if_needed "$BRANCH"
fi

if path_exists_in_history; then
  echo "history_cleanup_verify=failed_after_push" >&2
  exit 1
fi

printf 'history_cleanup=done\nforce_pushed=%s\ncurrent_branch=%s\nupstream_status=%s\nupstream=%s\n' \
  "$PUSH" \
  "$(current_branch)" \
  "$UPSTREAM_STATUS" \
  "$UPSTREAM_VALUE"
