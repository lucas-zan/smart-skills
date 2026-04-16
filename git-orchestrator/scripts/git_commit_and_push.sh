#!/usr/bin/env bash
set -euo pipefail

SUBJECT=""
BODY=""
ADD_ALL=1
PUSH=1
REMOTE="origin"
REQUIREMENTS=()
DESIGNS=()
TESTS=()
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_AUTH_ARGS=()

run_python() {
  uv run python "$@"
}

append_basis_args() {
  local array_name="$1"
  local flag="$2"
  case "$array_name" in
    REQUIREMENTS)
      if [[ "${#REQUIREMENTS[@]}" -gt 0 ]]; then
        for item in "${REQUIREMENTS[@]}"; do
          basis_args+=("$flag" "$item")
        done
      fi
      ;;
    DESIGNS)
      if [[ "${#DESIGNS[@]}" -gt 0 ]]; then
        for item in "${DESIGNS[@]}"; do
          basis_args+=("$flag" "$item")
        done
      fi
      ;;
    TESTS)
      if [[ "${#TESTS[@]}" -gt 0 ]]; then
        for item in "${TESTS[@]}"; do
          basis_args+=("$flag" "$item")
        done
      fi
      ;;
  esac
}

usage() {
  cat <<'USAGE'
Usage: git_commit_and_push.sh --subject <message> [--body <details>] [--requirement <path>] [--design <path>] [--test <path>] [--no-add-all] [--no-push] [--remote <remote>]
USAGE
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
    --subject)
      SUBJECT="$2"; shift 2 ;;
    --body)
      BODY="$2"; shift 2 ;;
    --requirement)
      REQUIREMENTS+=("$2"); shift 2 ;;
    --design)
      DESIGNS+=("$2"); shift 2 ;;
    --test)
      TESTS+=("$2"); shift 2 ;;
    --no-add-all)
      ADD_ALL=0; shift ;;
    --no-push)
      PUSH=0; shift ;;
    --remote)
      REMOTE="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ -z "$SUBJECT" ]]; then
  echo "--subject is required" >&2
  exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Current directory is not a git repository" >&2
  exit 1
fi

current_branch=$(git branch --show-current)
if [[ -z "$current_branch" ]]; then
  echo "Detached HEAD is not supported for commit-and-push workflow" >&2
  exit 1
fi

if [[ "$ADD_ALL" -eq 1 ]]; then
  basis_args=()
  append_basis_args REQUIREMENTS --requirement
  append_basis_args DESIGNS --design
  append_basis_args TESTS --test
  if [[ "${#basis_args[@]}" -gt 0 ]]; then
    run_python "${SCRIPT_DIR}/validate_change_basis.py" "${basis_args[@]}"
  else
    run_python "${SCRIPT_DIR}/validate_change_basis.py"
  fi
  git add -A
  if [[ -z "$(git status --porcelain)" ]]; then
    echo "No changes to commit" >&2
    exit 1
  fi
else
  if git diff --cached --quiet --exit-code; then
    echo "No staged changes to commit. Stage files first, or omit --no-add-all." >&2
    exit 1
  fi
  basis_args=()
  append_basis_args REQUIREMENTS --requirement
  append_basis_args DESIGNS --design
  append_basis_args TESTS --test
  if [[ "${#basis_args[@]}" -gt 0 ]]; then
    run_python "${SCRIPT_DIR}/validate_change_basis.py" "${basis_args[@]}"
  else
    run_python "${SCRIPT_DIR}/validate_change_basis.py"
  fi
fi

if [[ -n "$BODY" ]]; then
  git commit -m "$SUBJECT" -m "$BODY"
else
  git commit -m "$SUBJECT"
fi

commit_sha=$(git rev-parse HEAD)

if [[ "$PUSH" -eq 1 ]]; then
  remote_url="$(git remote get-url "$REMOTE")"
  ensure_auth_ready "$remote_url"
  load_git_auth_args "$remote_url"
  git_network push -u "$REMOTE" "$current_branch"
fi

printf 'branch=%s\ncommit_sha=%s\npushed=%s\n' "$current_branch" "$commit_sha" "$PUSH"
