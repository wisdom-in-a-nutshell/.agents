#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"

APPLY=0
GLOBAL_CONFIG="${HOME}/.claude.json"
MCP_REGISTRY="${ROOT_DIR}/mcp/config/presets.json"
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
  --mcp-registry <p>     Override shared MCP registry source
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
    --mcp-registry)
      MCP_REGISTRY="${2:-}"
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
[[ "$MCP_REGISTRY" = /* ]] || die "--mcp-registry must be an absolute path"
[[ -f "$MCP_REGISTRY" ]] || die "Missing MCP registry file: $MCP_REGISTRY"
[[ -r "$MCP_REGISTRY" ]] || die "MCP registry file is not readable: $MCP_REGISTRY"

TMP_DIR="$(mktemp -d)"
RENDERED_CONFIG="${TMP_DIR}/.claude.json"

python3 - "$GLOBAL_CONFIG" "$MCP_REGISTRY" "$RENDERED_CONFIG" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


def render_claude_mcp_server(name: str, preset: dict) -> dict:
    config = dict(preset)
    transport = config.pop("transport", config.pop("type", None))
    if transport not in {"http", "stdio"}:
        raise SystemExit(f"ERROR: MCP preset `{name}` must declare transport `http` or `stdio`")
    if transport == "http" and not isinstance(config.get("url"), str):
        raise SystemExit(f"ERROR: MCP preset `{name}` must define a string url")
    if transport == "stdio" and not isinstance(config.get("command"), str):
        raise SystemExit(f"ERROR: MCP preset `{name}` must define a string command")
    config["type"] = transport
    return config


runtime_path = Path(sys.argv[1]).expanduser().resolve()
mcp_registry_path = Path(sys.argv[2]).resolve()
rendered_path = Path(sys.argv[3]).resolve()

if runtime_path.exists():
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if not isinstance(runtime, dict):
        raise SystemExit(f"ERROR: runtime Claude config root must be an object: {runtime_path}")
else:
    runtime = {}

mcp_registry = json.loads(mcp_registry_path.read_text(encoding="utf-8"))
if not isinstance(mcp_registry, dict):
    raise SystemExit(f"ERROR: shared MCP registry root must be an object: {mcp_registry_path}")

presets = mcp_registry.get("presets", {})
if not isinstance(presets, dict):
    raise SystemExit(f"ERROR: shared MCP presets must be an object: {mcp_registry_path}")

global_presets = mcp_registry.get("global_presets", [])
if global_presets is None:
    global_presets = []
if not isinstance(global_presets, list):
    raise SystemExit(f"ERROR: global_presets must be an array: {mcp_registry_path}")

managed_servers: dict[str, dict] = {}
for preset_name in global_presets:
    if preset_name not in presets:
        raise SystemExit(f"ERROR: unknown global MCP preset `{preset_name}` in {mcp_registry_path}")
    preset = presets[preset_name]
    if not isinstance(preset, dict):
        raise SystemExit(f"ERROR: preset `{preset_name}` must be an object in {mcp_registry_path}")
    managed_servers[str(preset_name)] = render_claude_mcp_server(str(preset_name), preset)

runtime_servers = runtime.get("mcpServers", {})
if runtime_servers is None:
    runtime_servers = {}
if not isinstance(runtime_servers, dict):
    raise SystemExit(f"ERROR: runtime mcpServers must be an object: {runtime_path}")

merged = dict(runtime)
merged_servers = dict(runtime_servers)
for name, config in managed_servers.items():
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
