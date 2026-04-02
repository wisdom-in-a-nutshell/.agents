#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.json"
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local Claude config files from the canonical registry.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override repo bootstrap registry
                         (default: claude/config/repo-bootstrap.json)
  --repo <path>          Limit sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/.agents/claude/scripts/sync-repo-claude-configs.sh
  ~/.agents/claude/scripts/sync-repo-claude-configs.sh --apply
  ~/.agents/claude/scripts/sync-repo-claude-configs.sh --apply --repo ~/.agents
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

  if [[ -f "$target" ]] && [[ ! -L "$target" ]] && cmp -s "$target" "$rendered"; then
    log "No change: $target"
    return 0
  fi

  if [[ -f "$target" ]] && [[ ! -L "$target" ]]; then
    mode="$(stat -f "%Lp" "$target" 2>/dev/null || echo 600)"
  fi

  if [[ -L "$target" ]]; then
    rm -f "$target"
  fi

  install -m "$mode" "$rendered" "$target"
  log "Updated: $target"
}

sync_relative_symlink() {
  local target="$1"
  local link_to="$2"

  if [[ -L "$target" ]] && [[ "$(readlink "$target")" == "$link_to" ]]; then
    log "No change: $target -> $link_to"
    return 0
  fi

  if (( APPLY == 0 )); then
    if [[ -L "$target" ]]; then
      log "Would replace symlink: $target -> $(readlink "$target")"
    elif [[ -e "$target" ]]; then
      log "Would replace file: $target"
    else
      log "Would create symlink: $target"
    fi
    log "Would point to: $link_to"
    return 0
  fi

  ensure_parent_dir "$target"
  if [[ -e "$target" || -L "$target" ]]; then
    rm -f "$target"
  fi
  ln -s "$link_to" "$target"
  log "Linked $target -> $link_to"
}

remove_managed_file() {
  local target="$1"

  if [[ ! -e "$target" && ! -L "$target" ]]; then
    log "No managed file to remove: $target"
    return 0
  fi

  if (( APPLY == 0 )); then
    log "Would remove file: $target"
    return 0
  fi

  rm -f "$target"
  log "Removed file: $target"
}

remove_managed_symlink() {
  local target="$1"
  local link_to="$2"

  if [[ -L "$target" ]] && [[ "$(readlink "$target")" == "$link_to" ]]; then
    if (( APPLY == 0 )); then
      log "Would remove managed symlink: $target -> $link_to"
      return 0
    fi
    rm -f "$target"
    log "Removed managed symlink: $target"
    return 0
  fi

  log "No managed symlink to remove: $target"
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
    --registry)
      REGISTRY_FILE="${2:-}"
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

TMP_DIR="$(mktemp -d)"

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


def deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = {key: value for key, value in base.items()}
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def render_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def should_skip_walk_dir(path: Path, repo_root: Path) -> bool:
    if path == repo_root:
        return False
    skipped = {
        ".git",
        ".claude",
        ".codex",
        "node_modules",
        "dist",
        "build",
        ".next",
        ".turbo",
        "coverage",
        "__pycache__",
        ".venv",
        "venv",
    }
    return any(part in skipped for part in path.parts)


def discover_agents_files(repo_root: Path) -> list[Path]:
    discovered: list[Path] = []
    stack = [repo_root]
    while stack:
        current = stack.pop()
        if should_skip_walk_dir(current, repo_root):
            continue
        for child in sorted(current.iterdir(), key=lambda p: p.name):
            if child.is_dir():
                stack.append(child)
                continue
            if child.name == "AGENTS.md":
                discovered.append(child)
    return sorted(discovered)


def render_root_claude_md(repo_root: Path, model_instructions_file: str) -> str:
    codex_dir = repo_root / ".codex"
    resolved_model_file = (codex_dir / model_instructions_file).resolve()
    try:
        model_relative = resolved_model_file.relative_to(repo_root)
        model_import = model_relative.as_posix()
    except ValueError:
        model_import = resolved_model_file.as_posix()
    if not model_import:
        raise ValueError(f"Unable to derive root import path for {resolved_model_file}")
    return f"@{model_import}\n@AGENTS.md\n"


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

default_settings = defaults.get("settings", {})
if default_settings is None:
    default_settings = {}
if not isinstance(default_settings, dict):
    raise TypeError("defaults.settings must be an object")

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

    repo_settings = item.get("settings", {})
    if repo_settings is None:
        repo_settings = {}
    if not isinstance(repo_settings, dict):
        raise TypeError(f"settings for {actual_repo} must be an object")
    rendered_settings = deep_merge(default_settings, repo_settings)
    if not isinstance(rendered_settings, dict):
        raise TypeError(f"merged settings for {actual_repo} must be an object")

    settings_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':settings').encode()).hexdigest()}.json"
    settings_path.write_text(render_json(rendered_settings), encoding="utf-8")
    manifest_lines.append(f"{actual_repo}\tFILE\t{Path(actual_repo) / '.claude' / 'settings.json'}\t{settings_path}")

    preset_names = item.get("mcp_presets", [])
    if preset_names is None:
        preset_names = []
    if not isinstance(preset_names, list):
        raise TypeError(f"mcp_presets for {actual_repo} must be an array")

    repo_mcp_servers = item.get("mcp_servers", {})
    if repo_mcp_servers is None:
        repo_mcp_servers = {}
    if not isinstance(repo_mcp_servers, dict):
        raise TypeError(f"mcp_servers for {actual_repo} must be an object")

    mcp_servers: dict[str, dict] = {}
    for preset_name in preset_names:
        if preset_name not in presets:
            raise KeyError(f"Unknown MCP preset `{preset_name}` for {actual_repo}")
        preset = presets[preset_name]
        if not isinstance(preset, dict):
            raise TypeError(f"MCP preset `{preset_name}` must be an object")
        mcp_servers[preset_name] = preset
    for server_name, config in repo_mcp_servers.items():
        if not isinstance(config, dict):
            raise TypeError(f"mcp_servers.{server_name} for {actual_repo} must be an object")
        mcp_servers[server_name] = config

    mcp_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':mcp').encode()).hexdigest()}.json"
    mcp_path.write_text(render_json({"mcpServers": mcp_servers}), encoding="utf-8")
    manifest_lines.append(f"{actual_repo}\tFILE\t{Path(actual_repo) / '.mcp.json'}\t{mcp_path}")

    repo_root = Path(actual_repo)
    sync_nested = item.get(
        "sync_nested_claude_md_to_agents_md",
        defaults.get("sync_nested_claude_md_to_agents_md", False),
    )
    if not isinstance(sync_nested, bool):
        raise TypeError(f"sync_nested_claude_md_to_agents_md for {actual_repo} must be a boolean")

    model_instructions_file = item.get("model_instructions_file")
    if model_instructions_file is not None and (
        not isinstance(model_instructions_file, str) or not model_instructions_file.strip()
    ):
        raise TypeError(f"model_instructions_file for {actual_repo} must be a non-empty string")

    root_agents_md_path = repo_root / "AGENTS.md"
    claude_md_path = repo_root / "CLAUDE.md"
    if model_instructions_file is not None:
        if not root_agents_md_path.is_file():
            print(
                f"WARNING: skipping special root CLAUDE.md for {actual_repo}; missing AGENTS.md",
                file=sys.stderr,
            )
        else:
            rendered_root = render_root_claude_md(repo_root, model_instructions_file)
            root_claude_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':root-claude').encode()).hexdigest()}.md"
            root_claude_path.write_text(rendered_root, encoding="utf-8")
            manifest_lines.append(f"{actual_repo}\tFILE\t{claude_md_path}\t{root_claude_path}")
    else:
        agents_md_path = root_agents_md_path
        if not agents_md_path.is_file():
            print(
                f"WARNING: skipping root CLAUDE.md for {actual_repo}; missing AGENTS.md",
                file=sys.stderr,
            )
        else:
            manifest_lines.append(f"{actual_repo}\tLINK\t{claude_md_path}\tAGENTS.md")

    nested_agents_files = discover_agents_files(repo_root) if sync_nested else []
    for agents_md_path in nested_agents_files:
        if agents_md_path == root_agents_md_path:
            continue
        nested_claude_md = agents_md_path.parent / "CLAUDE.md"
        manifest_lines.append(
            f"{actual_repo}\tLINK\t{nested_claude_md}\tAGENTS.md"
        )

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed Claude operations from ${REGISTRY_FILE}."

for entry in "${MANIFEST[@]}"; do
  IFS=$'\t' read -r repo kind target data <<<"$entry"

  log ""
  log "=== Repo Claude Item (${repo}) ==="
  case "$kind" in
    FILE)
      ensure_parent_dir "$target"
      show_diff "$target" "$data"
      if (( APPLY == 1 )); then
        install_rendered_file "$data" "$target"
      fi
      ;;
    LINK)
      sync_relative_symlink "$target" "$data"
      ;;
    CLEAN_FILE)
      remove_managed_file "$target"
      ;;
    CLEAN_LINK)
      remove_managed_symlink "$target" "$data"
      ;;
    *)
      die "Unknown manifest kind: $kind"
      ;;
  esac
done
