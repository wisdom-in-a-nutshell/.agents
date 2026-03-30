#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${CONTROL_PLANE_DIR}/config/repo-bootstrap.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Render managed repo-local Codex config files from the canonical registry.
Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes in place
  --dry-run              Show diffs only (default)
  --registry <path>      Override repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
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

mapfile -t MANIFEST < <(
  python3 - "$REGISTRY_FILE" "$TMP_DIR" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


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


def validate_role_file(path: Path, expected_name: str) -> None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TypeError(f"Invalid agent role TOML at {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise TypeError(f"Agent role file must parse to a TOML table: {path}")

    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        raise TypeError(f"Agent role file must define a non-empty `name`: {path}")
    if not isinstance(description, str) or not description.strip():
        raise TypeError(f"Agent role file must define a non-empty `description`: {path}")
    if name.strip() != expected_name:
        raise TypeError(
            f"Agent role file name `{name.strip()}` does not match expected role `{expected_name}`: {path}"
        )


def render_repo_config(repo: str, defaults: dict, override: dict, presets: dict, agent_presets: dict) -> str:
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

    default_features = defaults.get("features", {})
    override_features = override.get("features", {})
    if default_features and not isinstance(default_features, dict):
        raise TypeError("defaults.features must be a table")
    if override_features and not isinstance(override_features, dict):
        raise TypeError(f"features for {repo} must be a table")

    features = dict(default_features)
    features.update(override_features)
    if features:
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

    custom_agent_names = override.get("custom_agents", [])
    if not isinstance(custom_agent_names, list):
        raise TypeError(f"custom_agents for {repo} must be an array")

    for agent_name in custom_agent_names:
        if agent_name not in agent_presets:
            raise KeyError(f"Unknown custom agent `{agent_name}` for {repo}")
        agent = agent_presets[agent_name]
        if not isinstance(agent.get("description"), str) or not agent["description"].strip():
            raise TypeError(f"custom agent `{agent_name}` must define a non-empty description")
        rendered_anything = True
        lines.append("")
        lines.append(f"[agents.{agent_name}]")
        lines.append(f"description = {toml_value(agent['description'])}")
        lines.append(f"config_file = {toml_value('agents/' + agent['config_file'])}")
        nickname_candidates = agent.get("nickname_candidates", [])
        if nickname_candidates:
            lines.append(f"nickname_candidates = {toml_value(nickname_candidates)}")

    if not rendered_anything:
        lines.append("# No repo-local Codex overrides are currently assigned.")

    return "\n".join(lines) + "\n"


registry_path = Path(sys.argv[1]).expanduser().resolve()
tmp_dir = Path(sys.argv[2]).resolve()
filters = {normalize_path(path) for path in sys.argv[3:] if path}

data = json.loads(registry_path.read_text(encoding="utf-8"))
defaults = data.get("defaults", {})
presets = data.get("mcp_presets", {})
agent_presets = data.get("agent_presets", {})
repos_raw = data.get("repos", [])

if not isinstance(defaults, dict):
    raise TypeError("defaults must be an object")
if not isinstance(presets, dict):
    raise TypeError("mcp_presets must be an object")
if not isinstance(agent_presets, dict):
    raise TypeError("agent_presets must be an object")
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")

manifest_lines: list[str] = []
agents_dir = registry_path.parent / "agents"
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

    rendered = render_repo_config(actual_repo, defaults, item, presets, agent_presets)
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.toml"
    rendered_path.write_text(rendered, encoding="utf-8")
    target_path = Path(actual_repo) / ".codex" / "config.toml"
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

    custom_agent_names = item.get("custom_agents", [])
    if not isinstance(custom_agent_names, list):
        raise TypeError(f"custom_agents for {actual_repo} must be an array")
    for agent_name in custom_agent_names:
        if agent_name not in agent_presets:
            raise KeyError(f"Unknown custom agent `{agent_name}` for {actual_repo}")
        preset = agent_presets[agent_name]
        config_file = preset.get("config_file")
        description = preset.get("description")
        if not isinstance(config_file, str) or not config_file.strip():
            raise TypeError(f"custom agent `{agent_name}` must define config_file")
        if not isinstance(description, str) or not description.strip():
            raise TypeError(f"custom agent `{agent_name}` must define a non-empty description")
        source_path = agents_dir / config_file
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing agent role file for `{agent_name}`: {source_path}")
        validate_role_file(source_path, agent_name)
        rendered_role_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':' + agent_name).encode()).hexdigest()}-{Path(config_file).name}"
        rendered_role_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')
        target_role_path = Path(actual_repo) / ".codex" / "agents" / Path(config_file).name
        manifest_lines.append(f"{actual_repo}\t{target_role_path}\t{rendered_role_path}")

for line in manifest_lines:
    print(line)
PY
)

if (( ${#MANIFEST[@]} == 0 )); then
  die "No managed repo configs were rendered."
fi

log "Rendered ${#MANIFEST[@]} managed repo-local Codex files from ${REGISTRY_FILE}."

for entry in "${MANIFEST[@]}"; do
  IFS=$'\t' read -r repo target rendered <<<"$entry"
  ensure_parent_dir "$target"

  log ""
  log "=== Repo Codex File (${repo}) ==="
  show_diff "$target" "$rendered"

  if (( APPLY == 1 )); then
    install_rendered_file "$rendered" "$target"
  fi
done
