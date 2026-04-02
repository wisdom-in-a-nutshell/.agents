#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"

CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
GLOBAL_CLAUDE_MD="${HOME}/.claude/CLAUDE.md"
GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
GLOBAL_CONFIG="${HOME}/.claude.json"
REPO_REGISTRY="${CANONICAL_DIR}/repo-bootstrap.json"
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
  --registry <path>         Override repo bootstrap registry path
  --skills-registry <path>  Override shared skills registry path
  --repo <path>             Limit repo-local validation to one repo path (repeatable)
  -h, --help                Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      REPO_REGISTRY="${CANONICAL_DIR}/repo-bootstrap.json"
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

python3 - "$CANONICAL_DIR" "$REPO_REGISTRY" "$SKILLS_REGISTRY" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

canonical_dir = Path(sys.argv[1]).expanduser().resolve()
repo_registry = Path(sys.argv[2]).expanduser().resolve()
skills_registry = Path(sys.argv[3]).expanduser().resolve()

global_claude = canonical_dir / "global.claude.md"
settings_json = canonical_dir / "settings.json"
mcp_json = canonical_dir / "mcp.json"

for path in (global_claude, settings_json, mcp_json, repo_registry, skills_registry):
    if not path.is_file():
        raise SystemExit(f"ERROR: missing required file: {path}")

settings = json.loads(settings_json.read_text(encoding="utf-8"))
if not isinstance(settings, dict):
    raise SystemExit(f"ERROR: settings root must be an object: {settings_json}")

mcp = json.loads(mcp_json.read_text(encoding="utf-8"))
if not isinstance(mcp, dict):
    raise SystemExit(f"ERROR: mcp root must be an object: {mcp_json}")
if "mcpServers" in mcp and not isinstance(mcp["mcpServers"], dict):
    raise SystemExit(f"ERROR: mcpServers must be an object in {mcp_json}")

repo_data = json.loads(repo_registry.read_text(encoding="utf-8"))
if not isinstance(repo_data, dict):
    raise SystemExit(f"ERROR: repo bootstrap root must be an object: {repo_registry}")

defaults = repo_data.get("defaults", {})
presets = repo_data.get("mcp_presets", {})
repos = repo_data.get("repos", [])
if not isinstance(defaults, dict):
    raise SystemExit(f"ERROR: defaults must be an object in {repo_registry}")
if not isinstance(presets, dict):
    raise SystemExit(f"ERROR: mcp_presets must be an object in {repo_registry}")
if not isinstance(repos, list):
    raise SystemExit(f"ERROR: repos must be an array in {repo_registry}")

default_settings = defaults.get("settings", {})
if default_settings is not None and not isinstance(default_settings, dict):
    raise SystemExit(f"ERROR: defaults.settings must be an object in {repo_registry}")

for idx, repo in enumerate(repos):
    if not isinstance(repo, dict):
        raise SystemExit(f"ERROR: repos[{idx}] must be an object")
    raw_path = repo.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit(f"ERROR: repos[{idx}].path must be a non-empty string")
    repo_settings = repo.get("settings", {})
    if repo_settings is not None and not isinstance(repo_settings, dict):
        raise SystemExit(f"ERROR: repos[{idx}].settings must be an object when present")
    preset_names = repo.get("mcp_presets", [])
    if preset_names is None:
        preset_names = []
    if not isinstance(preset_names, list):
        raise SystemExit(f"ERROR: repos[{idx}].mcp_presets must be an array")
    for preset_name in preset_names:
        if preset_name not in presets:
            raise SystemExit(f"ERROR: unknown MCP preset `{preset_name}` in repos[{idx}]")
    extra_servers = repo.get("mcp_servers", {})
    if extra_servers is not None and not isinstance(extra_servers, dict):
        raise SystemExit(f"ERROR: repos[{idx}].mcp_servers must be an object when present")

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

"${SCRIPT_DIR}/sync-global-claude-md.sh" --dry-run --global-claude-md "$GLOBAL_CLAUDE_MD"
"${SCRIPT_DIR}/sync-settings.sh" --dry-run --global-settings "$GLOBAL_SETTINGS"
"${SCRIPT_DIR}/sync-global-mcp.sh" --dry-run --global-config "$GLOBAL_CONFIG"
"${SCRIPT_DIR}/sync-skills.sh" --dry-run --registry "$SKILLS_REGISTRY" "${REPO_ARGS[@]}"
"${SCRIPT_DIR}/sync-repo-claude-configs.sh" --dry-run --registry "$REPO_REGISTRY" "${REPO_ARGS[@]}"

printf 'Claude control plane validation passed.\n'
