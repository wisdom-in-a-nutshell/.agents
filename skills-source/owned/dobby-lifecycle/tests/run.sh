#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/pre-compact" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/hooks/codex-finalize-session" \
  "$SKILL_DIR/scripts/hooks/write-session-note"
