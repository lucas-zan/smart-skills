#!/usr/bin/env bash
set -euo pipefail

run_python() {
  uv run python "$@"
}

if [[ -n "${LINT_CMD:-}" ]]; then
  echo "Using LINT_CMD: ${LINT_CMD}"
  eval "${LINT_CMD}"
  exit 0
fi

run_js_lint() {
  local runner="$1"
  case "$runner" in
    pnpm) pnpm run lint ;;
    yarn) yarn lint ;;
    bun) bun run lint ;;
    npm) npm run lint ;;
    *) return 1 ;;
  esac
}

if [[ -f package.json ]]; then
  if run_python - <<'PY'
import json
from pathlib import Path
pkg = json.loads(Path('package.json').read_text())
raise SystemExit(0 if 'lint' in pkg.get('scripts', {}) else 1)
PY
  then
    if [[ -f pnpm-lock.yaml ]] && command -v pnpm >/dev/null 2>&1; then
      run_js_lint pnpm; exit 0
    elif [[ -f yarn.lock ]] && command -v yarn >/dev/null 2>&1; then
      run_js_lint yarn; exit 0
    elif [[ -f bun.lockb || -f bun.lock ]] && command -v bun >/dev/null 2>&1; then
      run_js_lint bun; exit 0
    elif command -v npm >/dev/null 2>&1; then
      run_js_lint npm; exit 0
    fi
  fi
fi

if [[ -f pyproject.toml || -f requirements.txt || -f setup.cfg ]]; then
  if command -v ruff >/dev/null 2>&1; then
    ruff check .
    exit 0
  elif command -v flake8 >/dev/null 2>&1; then
    flake8 .
    exit 0
  fi
fi

if [[ -f go.mod ]] && command -v golangci-lint >/dev/null 2>&1; then
  golangci-lint run
  exit 0
fi

if [[ -f Cargo.toml ]] && command -v cargo >/dev/null 2>&1; then
  cargo clippy -- -D warnings
  exit 0
fi

cat >&2 <<'ERR'
Could not determine a lint command automatically.
Set LINT_CMD explicitly, for example:
  LINT_CMD='pnpm lint' bash scripts/lint_repo.sh
ERR
exit 1
