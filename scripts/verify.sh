#!/usr/bin/env bash
# One command to verify the whole stack, for humans, reviewers and agents.
#
#   scripts/verify.sh          static checks + backend tests + frontend build + E2E
#   scripts/verify.sh --fast   skip the browser E2E suite
#
# Works in Git Bash on Windows and in bash on Linux/macOS.
# Prerequisites: backend/.venv with requirements-dev.txt installed, `npm ci` in frontend/ and e2e/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAST=0
[[ "${1:-}" == "--fast" ]] && FAST=1

if [[ -x "$ROOT/backend/.venv/Scripts/python.exe" ]]; then
  PY="$ROOT/backend/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PY="$ROOT/backend/.venv/bin/python"
else
  echo "backend/.venv not found. Create it first (see README.md)." >&2
  exit 1
fi

results=()
step() {
  local name="$1"; shift
  echo
  echo "=== $name ==="
  if "$@"; then
    results+=("PASS  $name")
  else
    results+=("FAIL  $name")
    summary
    exit 1
  fi
}
summary() {
  echo
  echo "=== Verification summary ==="
  printf '%s\n' "${results[@]}"
}

cd "$ROOT/backend"
step "backend: ruff lint"            "$PY" -m ruff check .
step "backend: ruff format check"    "$PY" -m ruff format --check .
step "backend: rule + API tests"     "$PY" -m pytest -q

cd "$ROOT/frontend"
step "frontend: typecheck (tsc)"     npm run --silent typecheck
step "frontend: eslint"              npm run --silent lint
step "frontend: production build"    npm run --silent build

if [[ $FAST -eq 0 ]]; then
  cd "$ROOT/e2e"
  step "e2e: Playwright journeys"    npx playwright test
fi

summary
echo
echo "All checks passed."
