#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_AGENTS_DIR="${HOME}/.codex/agents"
XCODE_CONFIG="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/config.toml"
XCODE_AGENTS_DIR="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/agents"
CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
REGISTRY_FILE="${CANONICAL_DIR}/repo-bootstrap.json"
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate canonical Codex control-plane inputs and rendered runtime outputs.

Options:
  --canonical-dir <path>      Override canonical codex/config directory
  --global-config <path>      Override runtime ~/.codex/config.toml path
  --global-agents-dir <path>  Override runtime ~/.codex/agents path
  --xcode-config <path>       Override Xcode runtime config path
  --xcode-agents-dir <path>   Override Xcode runtime agents dir
  --registry <path>           Override repo bootstrap registry path
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

python3 - "$CANONICAL_DIR" "$GLOBAL_CONFIG" "$GLOBAL_AGENTS_DIR" "$XCODE_CONFIG" "$XCODE_AGENTS_DIR" "$REGISTRY_FILE" "${REPO_FILTERS[@]}" <<'PY'
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


ROLE_OVERRIDE_SCALAR_KEYS = {
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
}


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


def validate_policy_object(policy: dict, *, label: str, mcp_presets: dict) -> None:
    allowed_keys = ROLE_OVERRIDE_SCALAR_KEYS | {"tools", "features", "mcp"}
    unexpected = sorted(set(policy.keys()) - allowed_keys)
    if unexpected:
        fail(f"{label} has unsupported keys: {', '.join(unexpected)}")

    for key in ROLE_OVERRIDE_SCALAR_KEYS:
        if key in policy:
            value = policy[key]
            if value is not None and not isinstance(value, (str, int, bool, list)):
                fail(f"{label}.{key} must be a TOML-scalar-compatible value")

    for table_key in ("tools", "features"):
        if table_key in policy:
            table = policy[table_key]
            if not isinstance(table, dict):
                fail(f"{label}.{table_key} must be an object")
            if any(not isinstance(name, str) for name in table):
                fail(f"{label}.{table_key} keys must be strings")

    if "mcp" in policy:
        mcp = policy["mcp"]
        if not isinstance(mcp, dict):
            fail(f"{label}.mcp must be an object")
        mode = mcp.get("mode", "inherit")
        if mode not in {"inherit", "deny_all", "allow_list"}:
            fail(f"{label}.mcp.mode must be one of: inherit, deny_all, allow_list")
        presets = mcp.get("presets", [])
        if presets is None:
            presets = []
        if not isinstance(presets, list) or any(not isinstance(item, str) for item in presets):
            fail(f"{label}.mcp.presets must be an array of strings")
        unknown = sorted(set(presets) - set(mcp_presets))
        if unknown:
            fail(f"{label}.mcp references unknown MCP presets: {', '.join(unknown)}")


def normalize_repo_agent_names(custom_agents: list[str], agent_policies: dict[str, object]) -> list[str]:
    ordered: list[str] = []
    for agent_name in [*custom_agents, *agent_policies.keys()]:
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
global_agents_dir = Path(sys.argv[3]).expanduser().resolve()
xcode_config = Path(sys.argv[4]).expanduser().resolve()
xcode_agents_dir = Path(sys.argv[5]).expanduser().resolve()
registry_path = Path(sys.argv[6]).expanduser().resolve()
repo_filters = {str(Path(p).expanduser().resolve()) for p in sys.argv[7:] if p.strip()}

canonical_agents_dir = canonical_dir / "agents"
global_template = canonical_dir / "global.config.toml"
xcode_template = canonical_dir / "xcode.config.toml"

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
try:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
except Exception as exc:
    fail(f"invalid JSON in {registry_path}: {exc}")

agent_presets = registry.get("agent_presets", {})
if agent_presets is None:
    agent_presets = {}
if not isinstance(agent_presets, dict):
    fail(f"agent_presets must be an object in {registry_path}")

agent_policy_presets = registry.get("agent_policy_presets", {})
if agent_policy_presets is None:
    agent_policy_presets = {}
if not isinstance(agent_policy_presets, dict):
    fail(f"agent_policy_presets must be an object in {registry_path}")

mcp_presets = registry.get("mcp_presets", {})
if mcp_presets is None:
    mcp_presets = {}
if not isinstance(mcp_presets, dict):
    fail(f"mcp_presets must be an object in {registry_path}")

for agent_name, preset in sorted(agent_presets.items()):
    if not isinstance(preset, dict):
        fail(f"agent_presets.{agent_name} must be an object")
    description = preset.get("description")
    config_file = preset.get("config_file")
    if not isinstance(description, str) or not description.strip():
        fail(f"agent_presets.{agent_name} must define a non-empty description")
    if not isinstance(config_file, str) or not config_file.strip():
        fail(f"agent_presets.{agent_name} must define a non-empty config_file")
    role_path = (registry_path.parent / "agents" / config_file).resolve()
    validate_role_file(role_path, agent_name)

for preset_name, preset in sorted(agent_policy_presets.items()):
    if not isinstance(preset_name, str) or not preset_name.strip():
        fail("agent_policy_presets keys must be non-empty strings")
    if not isinstance(preset, dict):
        fail(f"agent_policy_presets.{preset_name} must be an object")
    validate_policy_object(
        preset,
        label=f"agent_policy_presets.{preset_name}",
        mcp_presets=mcp_presets,
    )

repos = registry.get("repos", [])
if not isinstance(repos, list):
    fail(f"repos must be an array in {registry_path}")

validated_repo_count = 0
for item in repos:
    if not isinstance(item, dict):
        fail("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        fail("repo.path must be a non-empty string")
    repo_path = Path(raw_path).expanduser().resolve()
    if repo_filters and str(repo_path) not in repo_filters:
        continue

    custom_agents = item.get("custom_agents", [])
    if custom_agents is None:
        custom_agents = []
    if not isinstance(custom_agents, list):
        fail(f"custom_agents for {repo_path} must be an array")
    for agent_name in custom_agents:
        if agent_name not in agent_presets:
            fail(f"repo {repo_path} references unknown custom agent `{agent_name}`")

    raw_agent_policies = item.get("agent_policies", {})
    if raw_agent_policies is None:
        raw_agent_policies = {}
    if not isinstance(raw_agent_policies, dict):
        fail(f"agent_policies for {repo_path} must be an object")
    for agent_name, raw_policy in raw_agent_policies.items():
        if agent_name not in agent_presets:
            fail(f"repo {repo_path} references unknown agent policy target `{agent_name}`")
        if isinstance(raw_policy, str):
            if raw_policy not in agent_policy_presets:
                fail(f"repo {repo_path} references unknown agent policy preset `{raw_policy}` for `{agent_name}`")
            continue
        if isinstance(raw_policy, dict):
            validate_policy_object(
                raw_policy,
                label=f"repos[{repo_path}].agent_policies.{agent_name}",
                mcp_presets=mcp_presets,
            )
            continue
        fail(f"agent_policies.{agent_name} for {repo_path} must be a preset name or object")

    expected_repo_agents = normalize_repo_agent_names(
        [str(agent_name) for agent_name in custom_agents],
        {str(agent_name): raw_policy for agent_name, raw_policy in raw_agent_policies.items()},
    )

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
    if sorted(declared_repo_agents) != sorted(expected_repo_agents):
        fail(
            f"repo {repo_path} declares agents {sorted(declared_repo_agents)} but registry expects {sorted(expected_repo_agents)}"
        )
    validated_repo_count += 1

print("OK: Codex control plane validation passed")
print(f"  canonical agent roles: {len(list(canonical_agents_dir.glob('*.toml')))}")
print(f"  global runtime config checked: {'yes' if global_config.exists() else 'no'}")
print(f"  xcode runtime config checked: {'yes' if xcode_config.exists() else 'no'}")
print(f"  repo-local configs checked: {validated_repo_count}")
PY
