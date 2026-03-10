#!/bin/bash
set -euo pipefail
LOG_DIR="$HOME/.codex/log"
mkdir -p "$LOG_DIR"
echo "$(date -u '+%Y-%m-%d %H:%M:%SZ') notify-wrapper: cwd=$PWD" >> "$LOG_DIR/notify-wrapper.log"
exec python3 "$HOME/.agents/codex/scripts/notify.py" "$@"
