#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLY=0
GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
CANONICAL_SETTINGS="${CONTROL_PLANE_DIR}/config/settings.json"
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render the canonical global Claude settings file into ~/.claude/settings.json.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                 Apply changes
  --dry-run               Show diffs only (default)
  --global-settings <p>   Override ~/.claude/settings.json target
  --canonical-settings <p> Override canonical settings source
  -h, --help              Show this help

Examples:
  ~/.agents/claude/scripts/sync-settings.sh
  ~/.agents/claude/scripts/sync-settings.sh --apply
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

ensure_parent_dir() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
}

show_diff() {
  local original="$1"
  local rendered="$2"
  if [[ -f "$original" ]]; then
    diff -u "$original" "$rendered" || true
  else
    diff -u /dev/null "$rendered" || true
  fi
}

install_rendered_file() {
  local rendered="$1"
  local target="$2"
  local mode="600"

  if [[ -f "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --global-settings)
      GLOBAL_SETTINGS="${2:-}"
      shift 2
      ;;
    --canonical-settings)
      CANONICAL_SETTINGS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

[[ "$GLOBAL_SETTINGS" = /* ]] || die "--global-settings must be an absolute path"
[[ "$CANONICAL_SETTINGS" = /* ]] || die "--canonical-settings must be an absolute path"
[[ -f "$CANONICAL_SETTINGS" ]] || die "Missing canonical settings file: $CANONICAL_SETTINGS"
[[ -r "$CANONICAL_SETTINGS" ]] || die "Canonical settings file is not readable: $CANONICAL_SETTINGS"

TMP_DIR="$(mktemp -d)"
RENDERED_SETTINGS="${TMP_DIR}/settings.json"

python3 - "$CANONICAL_SETTINGS" "$RENDERED_SETTINGS" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()

data = json.loads(source.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    raise SystemExit(f"ERROR: settings root must be an object: {source}")
target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

ensure_parent_dir "$GLOBAL_SETTINGS"

log "=== Global Claude Settings ==="
show_diff "$GLOBAL_SETTINGS" "$RENDERED_SETTINGS"

if (( APPLY == 1 )); then
  install_rendered_file "$RENDERED_SETTINGS" "$GLOBAL_SETTINGS"
fi
