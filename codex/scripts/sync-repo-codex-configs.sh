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

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


REPO_SCALAR_KEYS = [
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
ROLE_OVERRIDE_SCALAR_KEYS = [
    "model",
    "model_provider",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "web_search",
    "approval_policy",
    "sandbox_mode",
    "personality",
    "service_tier",
]
ROLE_RENDER_ORDER = [
    "name",
    "description",
    "model",
    "model_provider",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "web_search",
    "approval_policy",
    "sandbox_mode",
    "personality",
    "service_tier",
    "developer_instructions",
]


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if "\n" in value:
            escaped = value.replace('"""', '\\"""').rstrip("\n")
            return f'"""\n{escaped}\n"""'
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def validate_role_data(data: dict, expected_name: str, *, source_path: Path) -> dict:
    if not isinstance(data, dict):
        raise TypeError(f"Agent role file must parse to a TOML table: {source_path}")

    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        raise TypeError(f"Agent role file must define a non-empty `name`: {source_path}")
    if not isinstance(description, str) or not description.strip():
        raise TypeError(f"Agent role file must define a non-empty `description`: {source_path}")
    if name.strip() != expected_name:
        raise TypeError(
            f"Agent role file name `{name.strip()}` does not match expected role `{expected_name}`: {source_path}"
        )
    return data


def load_role_file(path: Path, expected_name: str) -> dict:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TypeError(f"Invalid agent role TOML at {path}: {exc}") from exc
    return validate_role_data(data, expected_name, source_path=path)


def normalize_repo_agent_names(custom_agent_names: list[str], agent_policies: dict[str, dict]) -> list[str]:
    ordered: list[str] = []
    for agent_name in [*custom_agent_names, *agent_policies.keys()]:
        if agent_name not in ordered:
            ordered.append(agent_name)
    return ordered


def validate_policy_object(policy: dict, *, label: str, mcp_presets: dict) -> dict:
    allowed_keys = set(ROLE_OVERRIDE_SCALAR_KEYS) | {"tools", "features", "mcp"}
    unexpected = sorted(set(policy.keys()) - allowed_keys)
    if unexpected:
        raise TypeError(f"{label} has unsupported keys: {', '.join(unexpected)}")

    normalized: dict = {}
    for key in ROLE_OVERRIDE_SCALAR_KEYS:
        if key in policy:
            value = policy[key]
            if value is not None and not isinstance(value, (str, int, bool, list)):
                raise TypeError(f"{label}.{key} must be a TOML-scalar-compatible value")
            normalized[key] = value

    for table_key in ("tools", "features"):
        if table_key in policy:
            table = policy[table_key]
            if not isinstance(table, dict):
                raise TypeError(f"{label}.{table_key} must be an object")
            if any(not isinstance(name, str) for name in table):
                raise TypeError(f"{label}.{table_key} keys must be strings")
            normalized[table_key] = dict(table)

    if "mcp" in policy:
        mcp = policy["mcp"]
        if not isinstance(mcp, dict):
            raise TypeError(f"{label}.mcp must be an object")
        mode = mcp.get("mode", "inherit")
        if mode not in {"inherit", "deny_all", "allow_list"}:
            raise TypeError(f"{label}.mcp.mode must be one of: inherit, deny_all, allow_list")
        presets = mcp.get("presets", [])
        if presets is None:
            presets = []
        if not isinstance(presets, list) or any(not isinstance(item, str) for item in presets):
            raise TypeError(f"{label}.mcp.presets must be an array of strings")
        unknown = sorted(set(presets) - set(mcp_presets))
        if unknown:
            raise KeyError(f"{label}.mcp references unknown MCP presets: {', '.join(unknown)}")
        normalized["mcp"] = {
            "mode": mode,
            "presets": [str(item) for item in presets],
        }

    return normalized


def resolve_agent_policies(repo: str, override: dict, *, agent_presets: dict, policy_presets: dict, mcp_presets: dict) -> dict[str, dict]:
    raw_policies = override.get("agent_policies", {})
    if raw_policies is None:
        return {}
    if not isinstance(raw_policies, dict):
        raise TypeError(f"agent_policies for {repo} must be an object")

    resolved: dict[str, dict] = {}
    for agent_name, raw_policy in raw_policies.items():
        if agent_name not in agent_presets:
            raise KeyError(f"Unknown agent policy target `{agent_name}` for {repo}")
        if isinstance(raw_policy, str):
            if raw_policy not in policy_presets:
                raise KeyError(f"Unknown agent policy preset `{raw_policy}` for {repo}.{agent_name}")
            resolved[agent_name] = copy.deepcopy(policy_presets[raw_policy])
            continue
        if isinstance(raw_policy, dict):
            resolved[agent_name] = validate_policy_object(
                raw_policy,
                label=f"repos[{repo}].agent_policies.{agent_name}",
                mcp_presets=mcp_presets,
            )
            continue
        raise TypeError(f"agent_policies.{agent_name} for {repo} must be a preset name or object")

    return resolved


def merge_boolish_table(base: dict | None, overrides: dict | None) -> dict:
    merged = dict(base or {})
    if overrides:
        merged.update(overrides)
    return merged


def apply_agent_policy(role_data: dict, *, repo_mcp_preset_names: list[str], mcp_presets: dict, policy: dict) -> dict:
    merged = copy.deepcopy(role_data)
    for key in ROLE_OVERRIDE_SCALAR_KEYS:
        if key in policy:
            merged[key] = policy[key]

    for table_key in ("tools", "features"):
        merged_table = merge_boolish_table(merged.get(table_key), policy.get(table_key))
        if merged_table:
            merged[table_key] = merged_table
        else:
            merged.pop(table_key, None)

    base_mcp_servers = dict(merged.get("mcp_servers", {}) or {})
    mcp_policy = policy.get("mcp")
    if mcp_policy:
        mode = mcp_policy.get("mode", "inherit")
        if mode in {"deny_all", "allow_list"}:
            allowed = set(mcp_policy.get("presets", [])) if mode == "allow_list" else set()
            for preset_name in repo_mcp_preset_names:
                server_config = dict(mcp_presets[preset_name])
                server_config["enabled"] = preset_name in allowed
                base_mcp_servers[preset_name] = server_config
    if base_mcp_servers:
        merged["mcp_servers"] = base_mcp_servers
    else:
        merged.pop("mcp_servers", None)

    return merged


def render_role_file(role_data: dict) -> str:
    lines = [
        "# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.",
        "# Edit ~/.agents/codex/config/repo-bootstrap.json or ~/.agents/codex/config/agents/*.toml and re-run the sync script.",
    ]

    for key in ROLE_RENDER_ORDER:
        if key in role_data and role_data[key] is not None:
            lines.append(f"{key} = {toml_value(role_data[key])}")

    for table_name in ("tools", "features"):
        table = role_data.get(table_name, {}) or {}
        if not table:
            continue
        lines.append("")
        lines.append(f"[{table_name}]")
        for key, value in table.items():
            lines.append(f"{key} = {toml_value(value)}")

    mcp_servers = role_data.get("mcp_servers", {}) or {}
    for server_name, config in mcp_servers.items():
        lines.append("")
        lines.append(f"[mcp_servers.{server_name}]")
        for key, value in config.items():
            lines.append(f"{key} = {toml_value(value)}")

    return "\n".join(lines) + "\n"


def render_repo_config(repo: str, defaults: dict, override: dict, presets: dict, agent_presets: dict, repo_agent_names: list[str]) -> str:
    lines = [
        "# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.",
        "# Edit ~/.agents/codex/config/repo-bootstrap.json and re-run the sync script.",
    ]
    rendered_anything = False

    scalar_lines = []
    for key in REPO_SCALAR_KEYS:
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

    for agent_name in repo_agent_names:
        if agent_name not in agent_presets:
            raise KeyError(f"Unknown repo agent `{agent_name}` for {repo}")
        agent = agent_presets[agent_name]
        if not isinstance(agent.get("description"), str) or not agent["description"].strip():
            raise TypeError(f"repo agent `{agent_name}` must define a non-empty description")
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
agent_policy_presets = data.get("agent_policy_presets", {})
repos_raw = data.get("repos", [])

if not isinstance(defaults, dict):
    raise TypeError("defaults must be an object")
if not isinstance(presets, dict):
    raise TypeError("mcp_presets must be an object")
if not isinstance(agent_presets, dict):
    raise TypeError("agent_presets must be an object")
if not isinstance(agent_policy_presets, dict):
    raise TypeError("agent_policy_presets must be an object")
if not isinstance(repos_raw, list):
    raise TypeError("repos must be an array")

validated_agent_policy_presets: dict[str, dict] = {}
for preset_name, preset in agent_policy_presets.items():
    if not isinstance(preset_name, str) or not preset_name.strip():
        raise TypeError("agent_policy_presets keys must be non-empty strings")
    if not isinstance(preset, dict):
        raise TypeError(f"agent_policy_presets.{preset_name} must be an object")
    validated_agent_policy_presets[preset_name] = validate_policy_object(
        preset,
        label=f"agent_policy_presets.{preset_name}",
        mcp_presets=presets,
    )

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

    repo_agent_policies = resolve_agent_policies(
        actual_repo,
        item,
        agent_presets=agent_presets,
        policy_presets=validated_agent_policy_presets,
        mcp_presets=presets,
    )
    custom_agent_names = item.get("custom_agents", [])
    if not isinstance(custom_agent_names, list):
        raise TypeError(f"custom_agents for {actual_repo} must be an array")
    repo_agent_names = normalize_repo_agent_names(custom_agent_names, repo_agent_policies)

    rendered = render_repo_config(actual_repo, defaults, item, presets, agent_presets, repo_agent_names)
    rendered_path = tmp_dir / f"{hashlib.sha256(actual_repo.encode()).hexdigest()}.toml"
    rendered_path.write_text(rendered, encoding="utf-8")
    target_path = Path(actual_repo) / ".codex" / "config.toml"
    manifest_lines.append(f"{actual_repo}\t{target_path}\t{rendered_path}")

    repo_mcp_preset_names = item.get("mcp_presets", [])
    if not isinstance(repo_mcp_preset_names, list):
        raise TypeError(f"mcp_presets for {actual_repo} must be an array")

    for agent_name in repo_agent_names:
        if agent_name not in agent_presets:
            raise KeyError(f"Unknown repo agent `{agent_name}` for {actual_repo}")
        preset = agent_presets[agent_name]
        config_file = preset.get("config_file")
        description = preset.get("description")
        if not isinstance(config_file, str) or not config_file.strip():
            raise TypeError(f"repo agent `{agent_name}` must define config_file")
        if not isinstance(description, str) or not description.strip():
            raise TypeError(f"repo agent `{agent_name}` must define a non-empty description")
        source_path = agents_dir / config_file
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing agent role file for `{agent_name}`: {source_path}")
        role_data = load_role_file(source_path, agent_name)
        policy = repo_agent_policies.get(agent_name, {})
        rendered_role = render_role_file(
            apply_agent_policy(
                role_data,
                repo_mcp_preset_names=repo_mcp_preset_names,
                mcp_presets=presets,
                policy=policy,
            )
        )
        rendered_role_path = tmp_dir / f"{hashlib.sha256((actual_repo + ':' + agent_name).encode()).hexdigest()}-{Path(config_file).name}"
        rendered_role_path.write_text(rendered_role, encoding='utf-8')
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
