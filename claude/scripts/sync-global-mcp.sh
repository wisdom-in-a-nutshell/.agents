#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLY=0
GLOBAL_CONFIG="${HOME}/.claude.json"
CANONICAL_MCP="${CONTROL_PLANE_DIR}/config/mcp.json"
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Merge managed global Claude MCP servers into ~/.claude.json without
overwriting unrelated runtime state.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show diffs only (default)
  --global-config <p>    Override ~/.claude.json target
  --canonical-mcp <p>    Override canonical managed MCP source
  -h, --help             Show this help

Examples:
  ~/.agents/claude/scripts/sync-global-mcp.sh
  ~/.agents/claude/scripts/sync-global-mcp.sh --apply
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
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --canonical-mcp)
      CANONICAL_MCP="${2:-}"
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

[[ "$GLOBAL_CONFIG" = /* ]] || die "--global-config must be an absolute path"
[[ "$CANONICAL_MCP" = /* ]] || die "--canonical-mcp must be an absolute path"
[[ -f "$CANONICAL_MCP" ]] || die "Missing canonical MCP file: $CANONICAL_MCP"
[[ -r "$CANONICAL_MCP" ]] || die "Canonical MCP file is not readable: $CANONICAL_MCP"

TMP_DIR="$(mktemp -d)"
RENDERED_CONFIG="${TMP_DIR}/.claude.json"

python3 - "$GLOBAL_CONFIG" "$CANONICAL_MCP" "$RENDERED_CONFIG" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

runtime_path = Path(sys.argv[1]).expanduser().resolve()
canonical_path = Path(sys.argv[2]).resolve()
rendered_path = Path(sys.argv[3]).resolve()

if runtime_path.exists():
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if not isinstance(runtime, dict):
        raise SystemExit(f"ERROR: runtime Claude config root must be an object: {runtime_path}")
else:
    runtime = {}

canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
if not isinstance(canonical, dict):
    raise SystemExit(f"ERROR: canonical MCP root must be an object: {canonical_path}")

managed_servers = canonical.get("mcpServers", {})
if managed_servers is None:
    managed_servers = {}
if not isinstance(managed_servers, dict):
    raise SystemExit(f"ERROR: canonical mcpServers must be an object: {canonical_path}")

runtime_servers = runtime.get("mcpServers", {})
if runtime_servers is None:
    runtime_servers = {}
if not isinstance(runtime_servers, dict):
    raise SystemExit(f"ERROR: runtime mcpServers must be an object: {runtime_path}")

merged = dict(runtime)
merged_servers = dict(runtime_servers)
for name, config in managed_servers.items():
    if not isinstance(config, dict):
        raise SystemExit(f"ERROR: mcpServers.{name} must be an object in {canonical_path}")
    merged_servers[name] = config
merged["mcpServers"] = merged_servers

rendered_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
PY

ensure_parent_dir "$GLOBAL_CONFIG"

log "=== Global Claude MCP ==="
show_diff "$GLOBAL_CONFIG" "$RENDERED_CONFIG"

if (( APPLY == 1 )); then
  install_rendered_file "$RENDERED_CONFIG" "$GLOBAL_CONFIG"
fi
