#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_REPO_ROOT="${WIN_REPO_ROOT:-/Users/dobby/GitHub/win}"
WIN_PYTHON="${WIN_PYTHON:-$WIN_REPO_ROOT/venv/bin/python}"
TOOLKIT_PY="$SCRIPT_DIR/media_toolkit.py"

if [[ ! -x "$WIN_PYTHON" ]]; then
  printf 'media-toolkit error: WIN python not found at %s\n' "$WIN_PYTHON" >&2
  exit 4
fi

if [[ ! -f "$TOOLKIT_PY" ]]; then
  printf 'media-toolkit error: toolkit script not found at %s\n' "$TOOLKIT_PY" >&2
  exit 4
fi

exec "$WIN_PYTHON" "$TOOLKIT_PY" "$@"
