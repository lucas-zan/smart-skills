#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_python() {
  uv run python "$@"
}

policy_get() {
  run_python "${SCRIPT_DIR}/repo_policy.py" --repo-root . --get "$1"
}

if [[ -n "${VERIFY_CMD:-}" ]]; then
  echo "Using VERIFY_CMD: ${VERIFY_CMD}"
  eval "${VERIFY_CMD}"
  exit 0
fi

policy_verify_cmd="$(policy_get verify.command 2>/dev/null || true)"
if [[ -n "$policy_verify_cmd" && "$policy_verify_cmd" != "null" ]]; then
  echo "Using verify.command from policy: ${policy_verify_cmd}"
  eval "${policy_verify_cmd}"
  exit 0
fi

run_js_script() {
  local runner="$1"
  local script_name="$2"
  case "$runner" in
    pnpm) pnpm run "$script_name" ;;
    yarn) yarn "$script_name" ;;
    bun) bun run "$script_name" ;;
    npm) npm run "$script_name" ;;
    *) return 1 ;;
  esac
}

detect_js_runner() {
  if [[ -f pnpm-lock.yaml ]] && command -v pnpm >/dev/null 2>&1; then
    printf 'pnpm\n'
    return 0
  fi
  if [[ -f yarn.lock ]] && command -v yarn >/dev/null 2>&1; then
    printf 'yarn\n'
    return 0
  fi
  if [[ -f bun.lockb || -f bun.lock ]] && command -v bun >/dev/null 2>&1; then
    printf 'bun\n'
    return 0
  fi
  if command -v npm >/dev/null 2>&1; then
    printf 'npm\n'
    return 0
  fi
  return 1
}

if [[ -f package.json ]]; then
  scripts_json=$(run_python - <<'PY'
import json
from pathlib import Path
pkg = json.loads(Path("package.json").read_text())
scripts = pkg.get("scripts", {})
print(json.dumps({name: name in scripts for name in ["lint", "test", "build"]}))
PY
)
  runner=""
  runner=$(detect_js_runner || true)
  if [[ -n "$runner" ]]; then
    if [[ "$(run_python -c 'import json,sys; print("1" if json.loads(sys.argv[1])["lint"] else "0")' "$scripts_json")" == "1" ]]; then
      run_js_script "$runner" lint
    fi
    if [[ "$(run_python -c 'import json,sys; print("1" if json.loads(sys.argv[1])["test"] else "0")' "$scripts_json")" == "1" ]]; then
      run_js_script "$runner" test
    fi
    if [[ "$(run_python -c 'import json,sys; print("1" if json.loads(sys.argv[1])["build"] else "0")' "$scripts_json")" == "1" ]]; then
      run_js_script "$runner" build
    fi
    exit 0
  fi
fi

if [[ -f Cargo.toml ]] && command -v cargo >/dev/null 2>&1; then
  cargo fmt --check
  cargo clippy --all-targets --all-features -- -D warnings
  cargo test
  exit 0
fi

if [[ -f pyproject.toml || -f requirements.txt || -f setup.cfg ]]; then
  if command -v ruff >/dev/null 2>&1; then
    ruff check .
  fi
  if command -v pytest >/dev/null 2>&1; then
    pytest
    exit 0
  fi
fi

if [[ -f go.mod ]] && command -v go >/dev/null 2>&1; then
  go test ./...
  exit 0
fi

cat >&2 <<'ERR'
Could not determine a verification command automatically.
Set VERIFY_CMD explicitly, for example:
  VERIFY_CMD='cargo fmt --check && cargo clippy --all-targets --all-features -- -D warnings && cargo test' bash scripts/verify_repo.sh
ERR
exit 1
