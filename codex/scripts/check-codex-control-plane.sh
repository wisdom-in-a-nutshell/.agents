#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
SYNC_REPO_CONFIGS_SCRIPT="${SCRIPT_DIR}/sync-repo-codex-configs.sh"

GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_HOOKS="${HOME}/.codex/hooks.json"
GLOBAL_AGENTS_DIR="${HOME}/.codex/agents"
XCODE_CONFIG="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/config.toml"
XCODE_AGENTS_DIR="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/agents"
CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
REGISTRY_FILE="${CANONICAL_DIR}/repo-bootstrap.json"
MCP_REGISTRY_FILE="${ROOT_DIR}/mcp/config/presets.json"
AGENT_REGISTRY_FILE="${ROOT_DIR}/agents/registry.json"
HOOKS_REGISTRY_FILE="${ROOT_DIR}/hooks/registry.json"
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate canonical Codex control-plane inputs and rendered runtime outputs.

Options:
  --canonical-dir <path>      Override canonical codex/config directory
  --global-config <path>      Override runtime ~/.codex/config.toml path
  --global-hooks <path>       Override runtime ~/.codex/hooks.json path
  --global-agents-dir <path>  Override runtime ~/.codex/agents path
  --xcode-config <path>       Override Xcode runtime config path
  --xcode-agents-dir <path>   Override Xcode runtime agents dir
  --registry <path>           Override repo bootstrap registry path
  --mcp-registry <path>       Override shared MCP registry path
  --agent-registry <path>     Override shared agent registry path
  --hooks-registry <path>     Override shared hooks registry path
  --repo <path>               Limit repo-local validation to one repo path (repeatable)
  -h, --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      REGISTRY_FILE="${CANONICAL_DIR}/repo-bootstrap.json"
      shift 2
      ;;
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --global-hooks)
      GLOBAL_HOOKS="${2:-}"
      shift 2
      ;;
    --global-agents-dir)
      GLOBAL_AGENTS_DIR="${2:-}"
      shift 2
      ;;
    --xcode-config)
      XCODE_CONFIG="${2:-}"
      shift 2
      ;;
    --xcode-agents-dir)
      XCODE_AGENTS_DIR="${2:-}"
      shift 2
      ;;
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --agent-registry)
      AGENT_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY_FILE="${2:-}"
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
      echo "ERROR: Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

[[ -x "$SYNC_REPO_CONFIGS_SCRIPT" ]] || {
  echo "ERROR: Missing executable: $SYNC_REPO_CONFIGS_SCRIPT" >&2
  exit 1
}

REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

PYTHONPATH="$ROOT_DIR" python3 - "$CANONICAL_DIR" "$GLOBAL_CONFIG" "$GLOBAL_HOOKS" "$GLOBAL_AGENTS_DIR" "$XCODE_CONFIG" "$XCODE_AGENTS_DIR" "$REGISTRY_FILE" "$MCP_REGISTRY_FILE" "$AGENT_REGISTRY_FILE" "$HOOKS_REGISTRY_FILE" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_toml(path: Path) -> dict:
    if not path.is_file():
        fail(f"missing file: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid TOML in {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"TOML root must be a table: {path}")
    return data


def validate_role_file(path: Path, expected_name: str) -> dict:
    data = load_toml(path)
    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        fail(f"agent role file at {path} must define a non-empty `name`")
    if not isinstance(description, str) or not description.strip():
        fail(f"agent role `{name if isinstance(name, str) and name else expected_name}` must define a description")
    if expected_name and name.strip() != expected_name:
        fail(f"agent role file {path} declares `{name.strip()}` but expected `{expected_name}`")
    return data


def normalize_repo_agent_names(custom_agents: list[str]) -> list[str]:
    ordered: list[str] = []
    for agent_name in custom_agents:
        if agent_name not in ordered:
            ordered.append(agent_name)
    return ordered


def validate_agent_declarations(config_path: Path, *, agent_files_base: Path, require_runtime_files: bool, check_runtime_extras: bool) -> list[str]:
    data = load_toml(config_path)
    agents = data.get("agents", {}) or {}
    if not isinstance(agents, dict):
        fail(f"`agents` must be a TOML table in {config_path}")

    declared_names: list[str] = []
    expected_basenames: list[str] = []
    for role_name, value in sorted(agents.items()):
        if not isinstance(role_name, str):
            fail(f"agent role name must be a string in {config_path}")
        if not isinstance(value, dict):
            fail(f"agents.{role_name} must be a TOML table in {config_path}")
        declared_names.append(role_name)
        description = value.get("description")
        config_file = value.get("config_file")
        if not isinstance(description, str) or not description.strip():
            fail(f"agents.{role_name} must define a non-empty description in {config_path}")
        if not isinstance(config_file, str) or not config_file.strip():
            fail(f"agents.{role_name} must define a non-empty config_file in {config_path}")
        resolved = (config_path.parent / config_file).resolve()
        basename = os.path.basename(config_file)
        expected_basenames.append(basename)
        if require_runtime_files and not resolved.is_file():
            fail(f"runtime config {config_path} references missing role file: {resolved}")
        validate_role_file(resolved if require_runtime_files else resolved, role_name)

    if check_runtime_extras and agent_files_base.exists():
        actual = sorted(p.name for p in agent_files_base.glob("*.toml"))
        extras = sorted(set(actual) - set(expected_basenames))
        if extras:
            fail(
                f"runtime agents dir {agent_files_base} contains unreferenced role files: {', '.join(extras)}"
            )

    return declared_names


def is_git_repo(path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


canonical_dir = Path(sys.argv[1]).expanduser().resolve()
global_config = Path(sys.argv[2]).expanduser().resolve()
global_hooks = Path(sys.argv[3]).expanduser().resolve()
global_agents_dir = Path(sys.argv[4]).expanduser().resolve()
xcode_config = Path(sys.argv[5]).expanduser().resolve()
xcode_agents_dir = Path(sys.argv[6]).expanduser().resolve()
registry_path = Path(sys.argv[7]).expanduser().resolve()
mcp_registry_path = Path(sys.argv[8]).expanduser().resolve()
agent_registry_path = Path(sys.argv[9]).expanduser().resolve()
hooks_registry_path = Path(sys.argv[10]).expanduser().resolve()
repo_filters = {str(Path(p).expanduser().resolve()) for p in sys.argv[11:] if p.strip()}

root_dir = agent_registry_path.parent.parent.resolve()
sys.path.insert(0, str(root_dir))

from agents.registry import load_agent_registry
from hooks.control_plane import load_hooks_registry, render_codex_hooks

canonical_agents_dir = canonical_dir / "agents"
global_template = canonical_dir / "global.config.toml"
xcode_template = canonical_dir / "xcode.config.toml"
bundled_skills_policy_path = canonical_dir / "bundled-skills-policy.json"


def load_bundled_skills_policy(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        fail(f"missing bundled skills policy file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"bundled skills policy root must be an object: {path}")
    if data.get("version") != 1:
        fail(f"bundled skills policy version must be 1 in {path}")
    roots = data.get("roots")
    if not isinstance(roots, dict):
        fail(f"bundled skills policy roots must be an object in {path}")

    normalized: dict[str, dict[str, object]] = {}
    for root_name, root_config in sorted(roots.items()):
        if not isinstance(root_name, str) or not root_name.strip():
            fail(f"bundled skills policy has an invalid root name in {path}")
        if not isinstance(root_config, dict):
            fail(f"bundled skills policy roots.{root_name} must be an object in {path}")
        root_path = root_config.get("path")
        allowed = root_config.get("allowed", [])
        disabled = root_config.get("disabled", [])
        if not isinstance(root_path, str) or not root_path.strip():
            fail(f"bundled skills policy roots.{root_name}.path must be a non-empty string in {path}")
        if not isinstance(allowed, list) or not all(isinstance(item, str) and item.strip() and "/" not in item for item in allowed):
            fail(f"bundled skills policy roots.{root_name}.allowed must be an array of skill names in {path}")
        if not isinstance(disabled, list) or not all(isinstance(item, str) and item.strip() and "/" not in item for item in disabled):
            fail(f"bundled skills policy roots.{root_name}.disabled must be an array of skill names in {path}")
        allowed_set = set(allowed)
        disabled_set = set(disabled)
        overlap = sorted(allowed_set & disabled_set)
        if overlap:
            fail(
                f"bundled skills policy roots.{root_name} classifies skill(s) as both allowed and disabled: "
                f"{', '.join(overlap)}"
            )
        normalized[root_name] = {
            "allowed": allowed_set,
            "disabled": disabled_set,
            "path": root_path,
        }
    return normalized


def expand_policy_path(raw_path: str) -> Path:
    home = os.environ.get("HOME")
    if home and (raw_path == "~" or raw_path.startswith("~/")):
        return Path(home + raw_path[1:]).resolve()
    return Path(raw_path).expanduser().resolve()


def audit_installed_bundled_skills(policy: dict[str, dict[str, object]]) -> None:
    for root_name, root_config in sorted(policy.items()):
        root_path = expand_policy_path(str(root_config["path"]))
        allowed = root_config["allowed"]
        disabled = root_config["disabled"]
        if not isinstance(allowed, set) or not isinstance(disabled, set):
            fail(f"internal bundled skills policy normalization error for {root_name}")
        if not root_path.exists():
            continue
        installed = sorted(path.parent.name for path in root_path.glob("*/SKILL.md"))
        unclassified = sorted(set(installed) - allowed - disabled)
        if unclassified:
            fail(
                f"unclassified bundled Codex skill(s) under {root_path}: {', '.join(unclassified)}. "
                f"Classify each in {bundled_skills_policy_path} as allowed or disabled."
            )


def expected_disabled_skill_paths(policy: dict[str, dict[str, object]]) -> set[str]:
    paths: set[str] = set()
    for root_config in policy.values():
        root_path = expand_policy_path(str(root_config["path"]))
        disabled = root_config["disabled"]
        if not isinstance(disabled, set):
            fail("internal bundled skills policy normalization error")
        for skill_name in disabled:
            paths.add(str(root_path / str(skill_name) / "SKILL.md"))
    return paths


def validate_disabled_skill_entries(config_path: Path, policy: dict[str, dict[str, object]]) -> None:
    data = load_toml(config_path)
    skills = data.get("skills", {})
    configs = skills.get("config", []) if isinstance(skills, dict) else []
    if not isinstance(configs, list):
        fail(f"skills.config must be an array of tables in {config_path}")

    disabled_paths = expected_disabled_skill_paths(policy)
    actual_disabled_paths: set[str] = set()
    for item in configs:
        if not isinstance(item, dict):
            fail(f"skills.config entries must be TOML tables in {config_path}")
        path = item.get("path")
        enabled = item.get("enabled")
        if isinstance(path, str) and enabled is False:
            actual_disabled_paths.add(path)

    missing = sorted(disabled_paths - actual_disabled_paths)
    if missing:
        fail(
            f"runtime config {config_path} is missing disabled bundled-skill entries: "
            f"{', '.join(missing)}. Re-run codex/scripts/sync-config.sh --apply."
        )


bundled_skills_policy = load_bundled_skills_policy(bundled_skills_policy_path)
audit_installed_bundled_skills(bundled_skills_policy)

validate_agent_declarations(
    global_template,
    agent_files_base=canonical_agents_dir,
    require_runtime_files=False,
    check_runtime_extras=False,
)
validate_agent_declarations(
    xcode_template,
    agent_files_base=canonical_agents_dir,
    require_runtime_files=False,
    check_runtime_extras=False,
)

if global_config.exists():
    validate_agent_declarations(
        global_config,
        agent_files_base=global_agents_dir,
        require_runtime_files=True,
        check_runtime_extras=True,
    )

if xcode_config.exists():
    validate_agent_declarations(
        xcode_config,
        agent_files_base=xcode_agents_dir,
        require_runtime_files=True,
        check_runtime_extras=True,
    )

if not registry_path.is_file():
    fail(f"missing registry file: {registry_path}")
if not mcp_registry_path.is_file():
    fail(f"missing MCP registry file: {mcp_registry_path}")
if not agent_registry_path.is_file():
    fail(f"missing agent registry file: {agent_registry_path}")
if not hooks_registry_path.is_file():
    fail(f"missing hooks registry file: {hooks_registry_path}")
try:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
except Exception as exc:
    fail(f"invalid JSON in {registry_path}: {exc}")
try:
    mcp_registry = json.loads(mcp_registry_path.read_text(encoding="utf-8"))
except Exception as exc:
    fail(f"invalid JSON in {mcp_registry_path}: {exc}")
try:
    hooks_registry = load_hooks_registry(hooks_registry_path)
except Exception as exc:
    fail(str(exc))

if not isinstance(mcp_registry, dict):
    fail(f"MCP registry root must be an object in {mcp_registry_path}")
mcp_presets = mcp_registry.get("presets", {})
if not isinstance(mcp_presets, dict):
    fail(f"presets must be an object in {mcp_registry_path}")
plugin_mcp_presets = mcp_registry.get("plugin_presets", {})
if not isinstance(plugin_mcp_presets, dict):
    fail(f"plugin_presets must be an object in {mcp_registry_path}")
global_presets = mcp_registry.get("global_presets", [])
if not isinstance(global_presets, list):
    fail(f"global_presets must be an array in {mcp_registry_path}")
plugin_global_presets = mcp_registry.get("plugin_global_presets", [])
if not isinstance(plugin_global_presets, list):
    fail(f"plugin_global_presets must be an array in {mcp_registry_path}")
merged_mcp_presets = dict(mcp_presets)
for preset_name, preset in sorted(plugin_mcp_presets.items()):
    existing = merged_mcp_presets.get(preset_name)
    if existing is not None and existing != preset:
        fail(f"plugin_presets conflicts with existing preset `{preset_name}` in {mcp_registry_path}")
    merged_mcp_presets[str(preset_name)] = preset
for preset_name, preset in sorted(merged_mcp_presets.items()):
    if not isinstance(preset, dict):
        fail(f"presets.{preset_name} must be an object in {mcp_registry_path}")
    transport = preset.get("transport")
    if transport not in {"http", "stdio"}:
        fail(f"presets.{preset_name}.transport must be `http` or `stdio` in {mcp_registry_path}")
    if transport == "http":
        url = preset.get("url")
        if not isinstance(url, str) or not url.strip():
            fail(f"presets.{preset_name}.url must be a non-empty string in {mcp_registry_path}")
    if transport == "stdio":
        command = preset.get("command")
        if not isinstance(command, str) or not command.strip():
            fail(f"presets.{preset_name}.command must be a non-empty string in {mcp_registry_path}")
for preset_name in [str(name) for name in global_presets] + [str(name) for name in plugin_global_presets]:
    if preset_name not in merged_mcp_presets:
        fail(f"global_presets references unknown MCP preset `{preset_name}` in {mcp_registry_path}")

repos = registry.get("repos", [])
if not isinstance(repos, list):
    fail(f"repos must be an array in {registry_path}")

resolved_repo_names: set[str] = set()
resolved_repos: list[dict[str, str]] = []
for item in repos:
    if not isinstance(item, dict):
        fail("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        fail("repo.path must be a non-empty string")
    repo_path = Path(raw_path).expanduser().resolve()
    repo_name = repo_path.name or str(repo_path)
    resolved_repo_names.add(repo_name)
    resolved_repos.append({"path": str(repo_path), "repo_name": repo_name})

managed_agents = load_agent_registry(
    agent_registry_path,
    root_dir=root_dir,
    valid_repo_names=resolved_repo_names,
)

expected_global_agents: list[str] = []
expected_repo_agents: dict[str, list[str]] = {}
for agent in managed_agents:
    codex = agent.get("codex")
    if not isinstance(codex, dict) or not codex.get("materialize"):
        continue
    role_path = Path(codex["source_path"])
    validate_role_file(role_path, str(codex["name"]))
    if agent["scope"] == "global":
        expected_global_agents.append(str(codex["name"]))
    else:
        for repo_name in agent["repos"]:
            expected_repo_agents.setdefault(str(repo_name), []).append(str(codex["name"]))

expected_global_agents = normalize_repo_agent_names(expected_global_agents)
for repo_name, names in list(expected_repo_agents.items()):
    expected_repo_agents[repo_name] = normalize_repo_agent_names(names)

if global_config.exists():
    declared_global_agents = validate_agent_declarations(
        global_config,
        agent_files_base=global_agents_dir,
        require_runtime_files=True,
        check_runtime_extras=True,
    )
    if sorted(declared_global_agents) != sorted(expected_global_agents):
        fail(
            f"global runtime declares agents {sorted(declared_global_agents)} but registry expects {sorted(expected_global_agents)}"
        )

if xcode_config.exists():
    declared_xcode_agents = validate_agent_declarations(
        xcode_config,
        agent_files_base=xcode_agents_dir,
        require_runtime_files=True,
        check_runtime_extras=True,
    )
    if sorted(declared_xcode_agents) != sorted(expected_global_agents):
        fail(
            f"xcode runtime declares agents {sorted(declared_xcode_agents)} but registry expects {sorted(expected_global_agents)}"
        )

if global_config.exists():
    global_data = load_toml(global_config)
    validate_disabled_skill_entries(global_config, bundled_skills_policy)
    features = global_data.get("features", {})
    codex_hooks_enabled = isinstance(features, dict) and features.get("codex_hooks") is True
    if codex_hooks_enabled and not global_hooks.is_file():
        fail(f"Codex hooks are enabled but hooks file is missing: {global_hooks}")
    if global_hooks.is_file():
        try:
            actual_hooks = json.loads(global_hooks.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid JSON in {global_hooks}: {exc}")
        expected_hooks = render_codex_hooks(hooks_registry)
        if actual_hooks != expected_hooks:
            fail(
                f"global Codex hooks are out of sync: {global_hooks}. "
                "Re-run codex/scripts/sync-config.sh --apply"
            )

validated_repo_count = 0
for item in resolved_repos:
    repo_path = Path(item["path"]).resolve()
    if repo_filters and str(repo_path) not in repo_filters:
        continue
    repo_name = item["repo_name"]
    expected_repo_agent_names = expected_repo_agents.get(repo_name, [])

    if not repo_path.exists() or not is_git_repo(repo_path):
        continue

    repo_config = repo_path / ".codex" / "config.toml"
    if not repo_config.exists():
        continue

    declared_repo_agents = validate_agent_declarations(
        repo_config,
        agent_files_base=repo_path / ".codex" / "agents",
        require_runtime_files=True,
        check_runtime_extras=False,
    )
    if sorted(declared_repo_agents) != sorted(expected_repo_agent_names):
        fail(
            f"repo {repo_path} declares agents {sorted(declared_repo_agents)} but registry expects {sorted(expected_repo_agent_names)}"
        )
    validated_repo_count += 1

print("Codex structural validation passed")
print(f"  canonical agent roles: {len(list(canonical_agents_dir.glob('*.toml')))}")
print(f"  global runtime config checked: {'yes' if global_config.exists() else 'no'}")
print(f"  global runtime hooks checked: {'yes' if global_hooks.exists() else 'no'}")
print(f"  xcode runtime config checked: {'yes' if xcode_config.exists() else 'no'}")
print(f"  repo-local configs checked: {validated_repo_count}")
PY

if ! drift_output="$(
  "$SYNC_REPO_CONFIGS_SCRIPT" \
    --check \
    --registry "$REGISTRY_FILE" \
    --mcp-registry "$MCP_REGISTRY_FILE" \
    --agent-registry "$AGENT_REGISTRY_FILE" \
    --hooks-registry "$HOOKS_REGISTRY_FILE" \
    "${REPO_ARGS[@]}" \
    2>&1
)"; then
  printf '%s\n' "$drift_output" >&2
  exit 1
fi

printf 'OK: Codex control plane validation passed\n'
