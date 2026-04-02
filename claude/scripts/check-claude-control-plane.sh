#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"

CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
GLOBAL_CLAUDE_MD="${HOME}/.claude/CLAUDE.md"
GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
GLOBAL_CONFIG="${HOME}/.claude.json"
REPO_REGISTRY="${ROOT_DIR}/codex/config/repo-bootstrap.json"
BOOTSTRAP_FILE="${CANONICAL_DIR}/bootstrap.json"
MCP_REGISTRY="${ROOT_DIR}/mcp/config/presets.json"
SKILLS_REGISTRY="${ROOT_DIR}/skills/registry.json"
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate canonical Claude control-plane inputs and the dry-run bootstrap path.

Options:
  --canonical-dir <path>    Override canonical claude/config directory
  --global-claude-md <path> Override runtime ~/.claude/CLAUDE.md path
  --global-settings <path>  Override runtime ~/.claude/settings.json path
  --global-config <path>    Override runtime ~/.claude.json path
  --registry <path>         Override shared repo bootstrap registry path
  --bootstrap <path>        Override Claude bootstrap defaults/overrides path
  --mcp-registry <path>     Override shared MCP registry path
  --skills-registry <path>  Override shared skills registry path
  --repo <path>             Limit repo-local validation to one repo path (repeatable)
  -h, --help                Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      BOOTSTRAP_FILE="${CANONICAL_DIR}/bootstrap.json"
      shift 2
      ;;
    --global-claude-md)
      GLOBAL_CLAUDE_MD="${2:-}"
      shift 2
      ;;
    --global-settings)
      GLOBAL_SETTINGS="${2:-}"
      shift 2
      ;;
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --registry)
      REPO_REGISTRY="${2:-}"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP_FILE="${2:-}"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY="${2:-}"
      shift 2
      ;;
    --skills-registry)
      SKILLS_REGISTRY="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_FILTERS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

python3 - "$CANONICAL_DIR" "$REPO_REGISTRY" "$BOOTSTRAP_FILE" "$MCP_REGISTRY" "$SKILLS_REGISTRY" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

canonical_dir = Path(sys.argv[1]).expanduser().resolve()
repo_registry = Path(sys.argv[2]).expanduser().resolve()
bootstrap_file = Path(sys.argv[3]).expanduser().resolve()
mcp_registry = Path(sys.argv[4]).expanduser().resolve()
skills_registry = Path(sys.argv[5]).expanduser().resolve()

global_claude = canonical_dir / "global.claude.md"
settings_json = canonical_dir / "settings.json"

for path in (global_claude, settings_json, repo_registry, bootstrap_file, mcp_registry, skills_registry):
    if not path.is_file():
        raise SystemExit(f"ERROR: missing required file: {path}")

settings = json.loads(settings_json.read_text(encoding="utf-8"))
if not isinstance(settings, dict):
    raise SystemExit(f"ERROR: settings root must be an object: {settings_json}")

repo_data = json.loads(repo_registry.read_text(encoding="utf-8"))
if not isinstance(repo_data, dict):
    raise SystemExit(f"ERROR: repo bootstrap root must be an object: {repo_registry}")

repos = repo_data.get("repos", [])
if not isinstance(repos, list):
    raise SystemExit(f"ERROR: repos must be an array in {repo_registry}")

bootstrap_data = json.loads(bootstrap_file.read_text(encoding="utf-8"))
if not isinstance(bootstrap_data, dict):
    raise SystemExit(f"ERROR: Claude bootstrap root must be an object: {bootstrap_file}")

defaults = bootstrap_data.get("defaults", {})
if defaults is None:
    defaults = {}
if not isinstance(defaults, dict):
    raise SystemExit(f"ERROR: defaults must be an object in {bootstrap_file}")

default_settings = defaults.get("settings", {})
if default_settings is not None and not isinstance(default_settings, dict):
    raise SystemExit(f"ERROR: defaults.settings must be an object in {bootstrap_file}")

repo_overrides = bootstrap_data.get("repo_overrides", {})
if repo_overrides is None:
    repo_overrides = {}
if not isinstance(repo_overrides, dict):
    raise SystemExit(f"ERROR: repo_overrides must be an object in {bootstrap_file}")
for repo_key, override in repo_overrides.items():
    if not isinstance(repo_key, str) or not repo_key.strip():
        raise SystemExit(f"ERROR: repo_overrides keys must be non-empty strings in {bootstrap_file}")
    if override is None:
        continue
    if not isinstance(override, dict):
        raise SystemExit(f"ERROR: repo_overrides.{repo_key} must be an object in {bootstrap_file}")

mcp_data = json.loads(mcp_registry.read_text(encoding="utf-8"))
if not isinstance(mcp_data, dict):
    raise SystemExit(f"ERROR: MCP registry root must be an object: {mcp_registry}")

presets = mcp_data.get("presets", {})
global_presets = mcp_data.get("global_presets", [])
if not isinstance(presets, dict):
    raise SystemExit(f"ERROR: presets must be an object in {mcp_registry}")
if global_presets is None:
    global_presets = []
if not isinstance(global_presets, list):
    raise SystemExit(f"ERROR: global_presets must be an array in {mcp_registry}")
for preset_name, preset in presets.items():
    if not isinstance(preset, dict):
        raise SystemExit(f"ERROR: presets.{preset_name} must be an object in {mcp_registry}")
    transport = preset.get("transport", preset.get("type"))
    if transport not in {"http", "stdio"}:
        raise SystemExit(f"ERROR: presets.{preset_name} must declare transport `http` or `stdio`")
    if transport == "http" and not isinstance(preset.get("url"), str):
        raise SystemExit(f"ERROR: presets.{preset_name} must define a string url")
    if transport == "stdio" and not isinstance(preset.get("command"), str):
        raise SystemExit(f"ERROR: presets.{preset_name} must define a string command")
for preset_name in global_presets:
    if preset_name not in presets:
        raise SystemExit(f"ERROR: unknown global MCP preset `{preset_name}` in {mcp_registry}")

for idx, repo in enumerate(repos):
    if not isinstance(repo, dict):
        raise SystemExit(f"ERROR: repos[{idx}] must be an object")
    raw_path = repo.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit(f"ERROR: repos[{idx}].path must be a non-empty string")
    preset_names = repo.get("mcp_presets", [])
    if preset_names is None:
        preset_names = []
    if not isinstance(preset_names, list):
        raise SystemExit(f"ERROR: repos[{idx}].mcp_presets must be an array")
    for preset_name in preset_names:
        if preset_name not in presets:
            raise SystemExit(f"ERROR: unknown MCP preset `{preset_name}` in repos[{idx}]")

skills_data = json.loads(skills_registry.read_text(encoding="utf-8"))
if not isinstance(skills_data, dict):
    raise SystemExit(f"ERROR: skills registry root must be an object: {skills_registry}")
managed = skills_data.get("managed_skills", [])
unmanaged = skills_data.get("unmanaged_repo_local_skills", [])
if not isinstance(managed, list):
    raise SystemExit(f"ERROR: managed_skills must be an array in {skills_registry}")
if not isinstance(unmanaged, list):
    raise SystemExit(f"ERROR: unmanaged_repo_local_skills must be an array in {skills_registry}")
PY

REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

bash "${SCRIPT_DIR}/sync-global-claude-md.sh" --dry-run --global-claude-md "$GLOBAL_CLAUDE_MD"
bash "${SCRIPT_DIR}/sync-settings.sh" --dry-run --global-settings "$GLOBAL_SETTINGS"
bash "${SCRIPT_DIR}/sync-global-mcp.sh" --dry-run --global-config "$GLOBAL_CONFIG" --mcp-registry "$MCP_REGISTRY"
bash "${SCRIPT_DIR}/sync-skills.sh" --dry-run --registry "$SKILLS_REGISTRY" "${REPO_ARGS[@]}"
bash "${SCRIPT_DIR}/sync-repo-claude-configs.sh" --dry-run --registry "$REPO_REGISTRY" --bootstrap "$BOOTSTRAP_FILE" --mcp-registry "$MCP_REGISTRY" "${REPO_ARGS[@]}"

printf 'Claude control plane validation passed.\n'
