#!/usr/bin/env bash
# Fast checks for the shared Dobby workspace shape linter.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile "$SKILL_DIR/scripts/lint-workspace"

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT

mkdir -p \
  "$workspace/memory/areas" \
  "$workspace/memory/sessions" \
  "$workspace/journal/daily" \
  "$workspace/journal/monthly" \
  "$workspace/journal/templates" \
  "$workspace/state" \
  "$workspace/dobby" \
  "$workspace/projects" \
  "$workspace/scripts/hooks" \
  "$workspace/scripts/local"

touch \
  "$workspace/soul.md" \
  "$workspace/memory/now.md" \
  "$workspace/dobby/growth.md" \
  "$workspace/scripts/check-fast.sh" \
  "$workspace/scripts/check-full.sh" \
  "$workspace/scripts/lint-workspace.py"

cat >"$workspace/state/shelf.json" <<JSON
{"revision": 1, "items": []}
JSON

"$SKILL_DIR/scripts/lint-workspace" --workspace-root "$workspace"

touch "$workspace/STRUCTURE.md"
if "$SKILL_DIR/scripts/lint-workspace" --workspace-root "$workspace" >/tmp/dobby-workspace-lint-test.out 2>&1; then
  echo "expected linter to reject STRUCTURE.md" >&2
  exit 1
fi
if ! grep -q 'STRUCTURE.md' /tmp/dobby-workspace-lint-test.out; then
  echo "expected unexpected STRUCTURE.md failure to mention STRUCTURE.md" >&2
  cat /tmp/dobby-workspace-lint-test.out >&2
  exit 1
fi
