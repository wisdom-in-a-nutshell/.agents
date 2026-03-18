#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REGISTRY_FILE=""
REPO_FILTERS=()
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${HOME}/.local/state/codex-control-plane/repo-config-backups"
BACKUP_MAX_AGE_DAYS=7

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local .codex/config.toml files from the canonical registry.
Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
  --backup-root <path>   Store repo-config backups outside git repos
                         (default: ~/.local/state/codex-control-plane/repo-config-backups)
  --repo <path>          Limit sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply
  ~/.agents/codex/scripts/sync-repo-codex-configs.sh --apply --repo ~/GitHub/win
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
  if [[ -n "${TMP_DIR:-}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

TMP_DIR="$(mktemp -d)"

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
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --backup-root)
      BACKUP_ROOT="${2:-}"
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
      die "Unknown option: $1"
      ;;
  esac
done

if [[ -z "$REGISTRY_FILE" ]]; then
  REGISTRY_FILE="$DEFAULT_REGISTRY_FILE"
fi

[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"

if (( APPLY == 1 )); then
  [[ -d "$BACKUP_ROOT" ]] || mkdir -p "$BACKUP_ROOT"
  find "$BACKUP_ROOT" -type f -name '*.bak.*' -mtime "+${BACKUP_MAX_AGE_DAYS}" -delete 2>/dev/null || true
fi

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
  local backup=""
  local mode="600"

  if [[ -f "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
    backup="${BACKUP_ROOT}/${target#/}.bak.${TIMESTAMP}"
    mkdir -p "$(dirname "$backup")"
    cp "$target" "$backup"
    log "Backup: $backup"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

mapfile -t MANIFEST < <(
  python3 - "$REGISTRY_FILE" "$TMP_DIR" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def render_repo_config(repo: str, defaults: dict, override: dict, presets: dict) -> str:
    lines = [
        "# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.",
        "# Edit ~/.agents/codex/config/repo-bootstrap.json and re-run the sync script.",
    ]
    rendered_anything = False

    scalar_keys = [
        "profile",
        "model",
        "model_reasoning_effort",
        "model_reasoning_summary",
        "model_verbosity",
        "model_instructions_file",
        "project_root_markers",
        "web_search",
        "approval_policy",
        "sandbox_mode",
        "personality",
        "service_tier",
    ]

    scalar_lines = []
    for key in scalar_keys:
        value = override.get(key, defaults.get(key))
        if value is not None:
            scalar_lines.append(f"{key} = {toml_value(value)}")
    if scalar_lines:
        rendered_anything = True
        lines.append("")
        lines.extend(scalar_lines)

    features = override.get("features")
    if features:
        if not isinstance(features, dict):
            raise TypeError(f"features for {repo} must be a table")
        rendered_anything = True
        lines.append("")
        lines.append("[features]")
        for key, value in features.items():
            lines.append(f"{key} = {toml_value(value)}")

    preset_names = override.get("mcp_presets", [])
    if not isinstance(preset_names, list):
        raise TypeError(f"mcp_presets for {repo} must be an array")

    for preset_name in preset_names:
        if preset_name not in presets:
            raise KeyError(f"Unknown MCP preset `{preset_name}` for {repo}")
        preset = presets[preset_name]
        if not isinstance(preset, dict):
            raise TypeError(f"MCP preset `{preset_name}` must be a table")
        rendered_anything = True
        lines.append("")
        lines.append(f"[mcp_servers.{preset_name}]")
        for key, value in preset.items():
            lines.append(f"{key} = {toml_value(value)}")

    if not rendered_anything:
        lines.append("# No repo-local Codex overrides are currently assigned.")

    return "\n".join(lines) + "\n"


registry_path = Path(sys.argv[1]).expanduser().resolve()
tmp_dir = Path(sys.argv[2]).resolve()
filters = {normalize_path(path) for path in sys.argv[3:] if path}

data = json.loads(registry_path.read_text(encoding="utf-8"))
defaults = data.get("defaults", {})
presets = data.get("mcp_presets", {})
repos_raw = data.get("repos", [])

if not isinstance(defaults, dict):
    raise TypeError("defaults must be an object")
if not isinstance(presets, dict):
    raise TypeError("mcp_presets must be an object")
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")

manifest_lines: list[str] = []
for item in repos_raw:
    if not isinstance(item, dict):
        raise TypeError("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise TypeError("repo.path must be a non-empty string")
    repo_path = Path(normalize_path(raw_path))
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(f"WARNING: skipping non-git path: {repo_path}", file=sys.stderr)
        continue

    actual_repo = str(Path(actual_repo).resolve())
    if filters and actual_repo not in filters:
        continue

    rendered = render_repo_config(actual_repo, defaults, item, presets)
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.toml"
    rendered_path.write_text(rendered, encoding="utf-8")
    target_path = Path(actual_repo) / ".codex" / "config.toml"
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed repo-local Codex configs from ${REGISTRY_FILE}."

for entry in "${MANIFEST[@]}"; do
  IFS=$'\t' read -r repo target rendered <<<"$entry"
  ensure_parent_dir "$target"

  log ""
  log "=== Repo Codex Config (${repo}) ==="
  show_diff "$target" "$rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$target"
  fi
done
