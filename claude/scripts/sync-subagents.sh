#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REPO_REGISTRY_FILE=""
AGENT_REGISTRY_FILE=""
GLOBAL_AGENTS_DIR="${HOME}/.claude/agents"
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
DEFAULT_REPO_REGISTRY_FILE="${ROOT_DIR}/codex/config/repo-bootstrap.json"
DEFAULT_AGENT_REGISTRY_FILE="${ROOT_DIR}/agents/registry.json"
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed Claude subagents from the shared agent registry.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override shared repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
  --agent-registry <p>   Override shared agent registry
                         (default: agents/registry.json)
  --global-agents-dir <p>
                         Override runtime ~/.claude/agents target
  --repo <path>          Limit repo-local sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/.agents/claude/scripts/sync-subagents.sh
  ~/.agents/claude/scripts/sync-subagents.sh --apply
  ~/.agents/claude/scripts/sync-subagents.sh --apply --repo ~/GitHub/adi
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
    --agent-registry)
      AGENT_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --global-agents-dir)
      GLOBAL_AGENTS_DIR="${2:-}"
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
if [[ -z "$AGENT_REGISTRY_FILE" ]]; then
  AGENT_REGISTRY_FILE="$DEFAULT_AGENT_REGISTRY_FILE"
fi

[[ -f "$REPO_REGISTRY_FILE" ]] || die "Missing repo registry file: $REPO_REGISTRY_FILE"
[[ -r "$REPO_REGISTRY_FILE" ]] || die "Repo registry file is not readable: $REPO_REGISTRY_FILE"
[[ -f "$AGENT_REGISTRY_FILE" ]] || die "Missing agent registry file: $AGENT_REGISTRY_FILE"
[[ -r "$AGENT_REGISTRY_FILE" ]] || die "Agent registry file is not readable: $AGENT_REGISTRY_FILE"

TMP_DIR="$(mktemp -d)"

mapfile -t MANIFEST < <(
  python3 - "$REPO_REGISTRY_FILE" "$AGENT_REGISTRY_FILE" "$GLOBAL_AGENTS_DIR" "$TMP_DIR" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def ordered_unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if "\n" in value:
            escaped = value.rstrip("\n")
            indented = "\n".join(f"  {line}" for line in escaped.splitlines())
            return f"|\n{indented}"
        return json.dumps(value)
    raise TypeError(f"Unsupported YAML scalar: {value!r}")


def emit_yaml_lines(lines: list[str], key: str, value: Any, indent: int = 0) -> None:
    prefix = "  " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(f"{prefix}{key}: {{}}")
            return
        lines.append(f"{prefix}{key}:")
        for subkey, subvalue in value.items():
            emit_yaml_lines(lines, str(subkey), subvalue, indent + 1)
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{prefix}{key}: []")
            return
        lines.append(f"{prefix}{key}:")
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}  -")
                if isinstance(item, dict):
                    for subkey, subvalue in item.items():
                        emit_yaml_lines(lines, str(subkey), subvalue, indent + 2)
                else:
                    emit_yaml_lines(lines, "value", item, indent + 2)
                continue
            lines.append(f"{prefix}  - {yaml_scalar(item)}")
        return
    scalar = yaml_scalar(value)
    if scalar.startswith("|\n"):
        lines.append(f"{prefix}{key}: {scalar.splitlines()[0]}")
        lines.extend(f"{prefix}{line}" for line in scalar.splitlines()[1:])
        return
    lines.append(f"{prefix}{key}: {scalar}")


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        emit_yaml_lines(lines, key, value)
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_subagent(frontmatter: dict[str, Any], prompt_body: str) -> str:
    prompt = prompt_body.strip()
    body = f"{prompt}\n" if prompt else ""
    return render_frontmatter(frontmatter) + "\n" + body


def read_manifest(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        files = data.get("files", [])
    else:
        files = data
    if not isinstance(files, list):
        return []
    return ordered_unique([str(value) for value in files if isinstance(value, str) and value.strip()])


def render_manifest(files: list[str]) -> str:
    payload = {
        "generated_by": "~/.agents/claude/scripts/sync-subagents.sh",
        "files": ordered_unique(sorted(files)),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def claude_permission_mode(agent: dict[str, Any], claude: dict[str, Any]) -> str | None:
    if "permission_mode" in claude:
        return str(claude["permission_mode"])
    if agent.get("access_profile") == "full_access":
        return "bypassPermissions"
    return None


repo_registry_path = Path(sys.argv[1]).expanduser().resolve()
agent_registry_path = Path(sys.argv[2]).expanduser().resolve()
global_agents_dir = Path(sys.argv[3]).expanduser().resolve()
tmp_dir = Path(sys.argv[4]).resolve()
filters = {normalize_path(path) for path in sys.argv[5:] if path}

root_dir = agent_registry_path.parent.parent.resolve()
sys.path.insert(0, str(root_dir))

from agents.registry import load_agent_registry


repo_data = json.loads(repo_registry_path.read_text(encoding="utf-8"))
repos_raw = repo_data.get("repos", [])
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")

repo_roots_by_name: dict[str, str] = {}
selected_repo_roots: dict[str, str] = {}
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
    repo_name = Path(actual_repo).name or actual_repo
    repo_roots_by_name[repo_name] = actual_repo
    if not filters or actual_repo in filters:
        selected_repo_roots[repo_name] = actual_repo

managed_agents = load_agent_registry(
    agent_registry_path,
    root_dir=root_dir,
    valid_repo_names=set(repo_roots_by_name),
)

desired_files_by_dir: dict[Path, dict[str, Path]] = {global_agents_dir: {}}
manifest_lines: list[str] = []

for agent in managed_agents:
    claude = agent.get("claude")
    if not isinstance(claude, dict) or not claude.get("materialize"):
        continue

    source_path = Path(claude["source_path"])
    if not source_path.is_file():
        raise FileNotFoundError(f"Missing Claude prompt source for `{agent['agent']}`: {source_path}")
    prompt_body = source_path.read_text(encoding="utf-8")

    frontmatter: dict[str, Any] = {
        "name": str(claude["name"]),
        "description": str(claude["description"]),
    }
    key_mapping = [
        ("tools", "tools"),
        ("disallowed_tools", "disallowedTools"),
        ("model", "model"),
        ("max_turns", "maxTurns"),
        ("skills", "skills"),
        ("mcp_servers", "mcpServers"),
        ("hooks", "hooks"),
        ("memory", "memory"),
        ("background", "background"),
        ("effort", "effort"),
        ("isolation", "isolation"),
        ("color", "color"),
        ("initial_prompt", "initialPrompt"),
    ]
    for source_key, output_key in key_mapping:
        if source_key in claude:
            frontmatter[output_key] = claude[source_key]
    permission_mode = claude_permission_mode(agent, claude)
    if permission_mode is not None:
        frontmatter["permissionMode"] = permission_mode

    rendered = render_subagent(frontmatter, prompt_body)
    filename = f"{agent['agent']}.md"

    target_dirs: list[Path] = []
    if agent["scope"] == "global":
        target_dirs.append(global_agents_dir)
    else:
        for repo_name in agent["repos"]:
            repo_root = selected_repo_roots.get(str(repo_name))
            if repo_root:
                target_dirs.append(Path(repo_root) / ".claude" / "agents")

    for target_dir in target_dirs:
        desired_files_by_dir.setdefault(target_dir, {})
        target_path = target_dir / filename
        rendered_path = tmp_dir / (
            f"{hashlib.sha256((str(target_path) + ':subagent').encode()).hexdigest()}-{filename}"
        )
        rendered_path.write_text(rendered, encoding="utf-8")
        desired_files_by_dir[target_dir][filename] = target_path
        manifest_lines.append(f"{target_dir}\tFILE\t{target_path}\t{rendered_path}")

candidate_dirs = [global_agents_dir]
for repo_root in selected_repo_roots.values():
    candidate_dirs.append(Path(repo_root) / ".claude" / "agents")

for target_dir in candidate_dirs:
    desired_names = sorted(desired_files_by_dir.get(target_dir, {}).keys())
    manifest_path = target_dir / ".managed-subagents.json"
    previous_names = read_manifest(manifest_path)
    stale_names = sorted(set(previous_names) - set(desired_names))
    for stale_name in stale_names:
        manifest_lines.append(f"{target_dir}\tCLEAN_FILE\t{target_dir / stale_name}\t-")

    if desired_names:
        rendered_manifest = render_manifest(desired_names)
        rendered_manifest_path = tmp_dir / (
            f"{hashlib.sha256((str(manifest_path) + ':manifest').encode()).hexdigest()}-managed-subagents.json"
        )
        rendered_manifest_path.write_text(rendered_manifest, encoding="utf-8")
        manifest_lines.append(f"{target_dir}\tFILE\t{manifest_path}\t{rendered_manifest_path}")
    elif previous_names:
        manifest_lines.append(f"{target_dir}\tCLEAN_FILE\t{manifest_path}\t-")

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed Claude subagent operations were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed Claude subagent operations from ${AGENT_REGISTRY_FILE}."

for entry in "${MANIFEST[@]}"; do
  IFS=$'\t' read -r scope kind target data <<<"$entry"

  log ""
  log "=== Claude Subagent Item (${scope}) ==="
  case "$kind" in
    FILE)
      ensure_parent_dir "$target"
      show_diff "$target" "$data"
      if (( APPLY == 1 )); then
        install_rendered_file "$data" "$target"
      fi
      ;;
    CLEAN_FILE)
      remove_managed_file "$target"
      ;;
    *)
      die "Unknown manifest kind: $kind"
      ;;
  esac
done
