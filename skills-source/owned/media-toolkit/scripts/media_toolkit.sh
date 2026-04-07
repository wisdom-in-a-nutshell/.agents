#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  printf 'media-toolkit error: python not found at %s\n' "$PYTHON_BIN" >&2
  exit 4
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/media_toolkit.py" "$@"
