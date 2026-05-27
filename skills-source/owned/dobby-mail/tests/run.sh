#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/test_dobby_mail.py"
if [[ "${RUN_LIVE:-0}" == "1" ]]; then
  "$SCRIPT_DIR/../scripts/dobby-mail" doctor --check-mail-app --no-input
else
  "$SCRIPT_DIR/../scripts/dobby-mail" doctor --no-input >/dev/null
fi
