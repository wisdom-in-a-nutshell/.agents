#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REPO_REGISTRY_FILE=""
BOOTSTRAP_FILE=""
MCP_REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
DEFAULT_REPO_REGISTRY_FILE="${ROOT_DIR}/codex/config/repo-bootstrap.json"
DEFAULT_BOOTSTRAP_FILE="${CONTROL_PLANE_DIR}/config/bootstrap.json"
DEFAULT_MCP_REGISTRY_FILE="${ROOT_DIR}/mcp/config/presets.json"
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local Claude config files from the shared repo registry plus
Claude-specific bootstrap defaults.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override shared repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
  --bootstrap <path>     Override Claude bootstrap defaults/overrides
                         (default: claude/config/bootstrap.json)
  --mcp-registry <path>  Override shared MCP registry
                         (default: mcp/config/presets.json)
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
  if [[ -L "$original" || -f "$original" ]]; then
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
      REPO_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP_FILE="${2:-}"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY_FILE="${2:-}"
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

if [[ -z "$REPO_REGISTRY_FILE" ]]; then
  REPO_REGISTRY_FILE="$DEFAULT_REPO_REGISTRY_FILE"
fi

if [[ -z "$BOOTSTRAP_FILE" ]]; then
  BOOTSTRAP_FILE="$DEFAULT_BOOTSTRAP_FILE"
fi

if [[ -z "$MCP_REGISTRY_FILE" ]]; then
  MCP_REGISTRY_FILE="$DEFAULT_MCP_REGISTRY_FILE"
fi

[[ -f "$REPO_REGISTRY_FILE" ]] || die "Missing repo registry file: $REPO_REGISTRY_FILE"
[[ -r "$REPO_REGISTRY_FILE" ]] || die "Repo registry file is not readable: $REPO_REGISTRY_FILE"
[[ -f "$BOOTSTRAP_FILE" ]] || die "Missing Claude bootstrap file: $BOOTSTRAP_FILE"
[[ -r "$BOOTSTRAP_FILE" ]] || die "Claude bootstrap file is not readable: $BOOTSTRAP_FILE"
[[ -f "$MCP_REGISTRY_FILE" ]] || die "Missing MCP registry file: $MCP_REGISTRY_FILE"
[[ -r "$MCP_REGISTRY_FILE" ]] || die "MCP registry file is not readable: $MCP_REGISTRY_FILE"

TMP_DIR="$(mktemp -d)"

mapfile -t MANIFEST < <(
  python3 - "$REPO_REGISTRY_FILE" "$BOOTSTRAP_FILE" "$MCP_REGISTRY_FILE" "$TMP_DIR" "${REPO_FILTERS[@]}" <<'PY'
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


def render_import_claude_md(*imports: str) -> str:
    lines = []
    for import_path in imports:
        if not isinstance(import_path, str) or not import_path.strip():
            raise ValueError("CLAUDE.md imports must be non-empty strings")
        lines.append(f"@{import_path}")
    return "\n".join(lines) + "\n"


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
    return render_import_claude_md(model_import, "AGENTS.md")


def render_claude_mcp_server(name: str, preset: dict) -> dict:
    config = dict(preset)
    transport = config.pop("transport", config.pop("type", None))
    if transport not in {"http", "stdio"}:
        raise TypeError(f"MCP preset `{name}` must declare transport `http` or `stdio`")
    if transport == "http" and not isinstance(config.get("url"), str):
        raise TypeError(f"MCP preset `{name}` must define a string url")
    if transport == "stdio" and not isinstance(config.get("command"), str):
        raise TypeError(f"MCP preset `{name}` must define a string command")
    config["type"] = transport
    return config


repo_registry_path = Path(sys.argv[1]).expanduser().resolve()
bootstrap_path = Path(sys.argv[2]).expanduser().resolve()
mcp_registry_path = Path(sys.argv[3]).expanduser().resolve()
tmp_dir = Path(sys.argv[4]).resolve()
filters = {normalize_path(path) for path in sys.argv[5:] if path}

repo_data = json.loads(repo_registry_path.read_text(encoding="utf-8"))
bootstrap_data = json.loads(bootstrap_path.read_text(encoding="utf-8"))
mcp_data = json.loads(mcp_registry_path.read_text(encoding="utf-8"))

repos_raw = repo_data.get("repos", [])
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")

bootstrap_defaults = bootstrap_data.get("defaults", {})
if bootstrap_defaults is None:
    bootstrap_defaults = {}
if not isinstance(bootstrap_defaults, dict):
    raise TypeError("defaults must be an object in Claude bootstrap config")

bootstrap_repo_overrides = bootstrap_data.get("repo_overrides", {})
if bootstrap_repo_overrides is None:
    bootstrap_repo_overrides = {}
if not isinstance(bootstrap_repo_overrides, dict):
    raise TypeError("repo_overrides must be an object in Claude bootstrap config")

override_map = {}
for raw_path, override in bootstrap_repo_overrides.items():
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise TypeError("repo_overrides keys must be non-empty strings")
    if override is None:
        override = {}
    if not isinstance(override, dict):
        raise TypeError(f"repo_overrides.{raw_path} must be an object")
    override_map[normalize_path(raw_path)] = override

mcp_presets = mcp_data.get("presets", {})
if not isinstance(mcp_presets, dict):
    raise TypeError("presets must be an object in shared MCP registry")

default_settings = bootstrap_defaults.get("settings", {})
if default_settings is None:
    default_settings = {}
if not isinstance(default_settings, dict):
    raise TypeError("defaults.settings must be an object in Claude bootstrap config")

manifest_lines: list[str] = []
for item in repos_raw:
    if not isinstance(item, dict):
        raise TypeError("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise TypeError("repo.path must be a non-empty string")

    declared_repo_path = Path(normalize_path(raw_path))
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(declared_repo_path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        print(f"WARNING: skipping non-git path: {declared_repo_path}", file=sys.stderr)
        continue

    actual_repo = str(Path(actual_repo).resolve())
    if filters and actual_repo not in filters:
        continue

    repo_override = {}
    for key in (str(declared_repo_path), actual_repo):
        override = override_map.get(key)
        if override:
            repo_override = deep_merge(repo_override, override)

    repo_settings = repo_override.get("settings", {})
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

    repo_mcp_servers = repo_override.get("mcp_servers", {})
    if repo_mcp_servers is None:
        repo_mcp_servers = {}
    if not isinstance(repo_mcp_servers, dict):
        raise TypeError(f"repo_overrides.mcp_servers for {actual_repo} must be an object")

    mcp_servers: dict[str, dict] = {}
    for preset_name in preset_names:
        if preset_name not in mcp_presets:
            raise KeyError(f"Unknown MCP preset `{preset_name}` for {actual_repo}")
        preset = mcp_presets[preset_name]
        if not isinstance(preset, dict):
            raise TypeError(f"MCP preset `{preset_name}` must be an object")
        mcp_servers[preset_name] = render_claude_mcp_server(preset_name, preset)
    for server_name, config in repo_mcp_servers.items():
        if not isinstance(config, dict):
            raise TypeError(f"repo_overrides.mcp_servers.{server_name} for {actual_repo} must be an object")
        mcp_servers[server_name] = config

    mcp_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':mcp').encode()).hexdigest()}.json"
    mcp_path.write_text(render_json({"mcpServers": mcp_servers}), encoding="utf-8")
    manifest_lines.append(f"{actual_repo}\tFILE\t{Path(actual_repo) / '.mcp.json'}\t{mcp_path}")

    repo_root = Path(actual_repo)
    sync_nested = repo_override.get(
        "sync_nested_claude_md_to_agents_md",
        bootstrap_defaults.get("sync_nested_claude_md_to_agents_md", False),
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
        if not root_agents_md_path.is_file():
            print(
                f"WARNING: skipping root CLAUDE.md for {actual_repo}; missing AGENTS.md",
                file=sys.stderr,
            )
        else:
            root_claude_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':root-claude').encode()).hexdigest()}.md"
            root_claude_path.write_text(render_import_claude_md("AGENTS.md"), encoding="utf-8")
            manifest_lines.append(f"{actual_repo}\tFILE\t{claude_md_path}\t{root_claude_path}")

    nested_agents_files = discover_agents_files(repo_root) if sync_nested else []
    for agents_md_path in nested_agents_files:
        if agents_md_path == root_agents_md_path:
            continue
        nested_claude_md = agents_md_path.parent / "CLAUDE.md"
        nested_claude_path = tmp_dir / (
            f"{hashlib.sha256((actual_repo + ':nested-claude:' + str(nested_claude_md)).encode()).hexdigest()}.md"
        )
        nested_claude_path.write_text(render_import_claude_md("AGENTS.md"), encoding="utf-8")
        manifest_lines.append(f"{actual_repo}\tFILE\t{nested_claude_md}\t{nested_claude_path}")

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed Claude operations from ${REPO_REGISTRY_FILE}."

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
