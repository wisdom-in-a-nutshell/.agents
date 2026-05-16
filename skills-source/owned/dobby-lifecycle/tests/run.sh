#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/consolidate-thread"

forbidden_var="DOBBY_INTERNAL_""SIDECAR"
if grep -R "$forbidden_var" "$SKILL_DIR/scripts" "$SKILL_DIR/references" >/dev/null; then
  echo "$forbidden_var should not be part of the current simple design" >&2
  exit 1
fi
