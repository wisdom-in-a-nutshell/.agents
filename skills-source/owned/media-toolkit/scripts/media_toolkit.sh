#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON3_BIN="$(command -v python3 || true)"

if [[ -z "$PYTHON3_BIN" || ! -x "$PYTHON3_BIN" ]]; then
  printf 'media-toolkit error: python3 not found in PATH\n' >&2
  exit 4
fi

exec "$PYTHON3_BIN" "$SCRIPT_DIR/media_toolkit.py" "$@"
