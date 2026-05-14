#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
SYNC_REPO_CONFIGS_SCRIPT="${SCRIPT_DIR}/sync-repo-codex-configs.sh"

GLOBAL_CONFIG="${HOME}/.codex/config.toml"
GLOBAL_HOOKS="${HOME}/.codex/hooks.json"
CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
REGISTRY_FILE="${CANONICAL_DIR}/repo-bootstrap.json"
MCP_REGISTRY_FILE="${ROOT_DIR}/mcp/config/presets.json"
HOOKS_REGISTRY_FILE="${ROOT_DIR}/hooks/registry.json"
PLUGIN_REGISTRY_FILE="${ROOT_DIR}/plugins/registry.json"
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate canonical Codex control-plane inputs and rendered runtime outputs.

Options:
  --canonical-dir <path>      Override canonical codex/config directory
  --global-config <path>      Override runtime ~/.codex/config.toml path
  --global-hooks <path>       Override runtime ~/.codex/hooks.json path
  --registry <path>           Override repo bootstrap registry path
  --mcp-registry <path>       Override shared MCP registry path
  --hooks-registry <path>     Override shared hooks registry path
  --plugin-registry <path>    Override native Codex plugin registry path
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
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --plugin-registry)
      PLUGIN_REGISTRY_FILE="${2:-}"
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

PYTHONPATH="$ROOT_DIR" python3 - "$CANONICAL_DIR" "$GLOBAL_CONFIG" "$GLOBAL_HOOKS" "$REGISTRY_FILE" "$MCP_REGISTRY_FILE" "$HOOKS_REGISTRY_FILE" "$PLUGIN_REGISTRY_FILE" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import json
import os
import shutil
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


def validate_no_agent_declarations(config_path: Path) -> None:
    data = load_toml(config_path)
    agents = data.get("agents", {}) or {}
    if not isinstance(agents, dict):
        fail(f"`agents` must be a TOML table in {config_path}")
    if agents:
        fail(f"{config_path} declares managed agents; this control plane no longer materializes agent roles")


def validate_global_plugin_runtime(
    config_path: Path,
    config_data: dict,
    managed_plugins: list,
) -> None:
    plugins_table = config_data.get("plugins", {}) or {}
    if not isinstance(plugins_table, dict):
        fail(f"`plugins` must be a TOML table in {config_path}")

    for plugin in managed_plugins:
        if plugin.scope != "global":
            continue
        plugin_config = plugins_table.get(plugin.plugin_id)
        if not isinstance(plugin_config, dict):
            fail(
                f"global Codex config missing managed plugin `{plugin.plugin_id}` in {config_path}. "
                "Re-run codex/scripts/sync-config.sh --apply"
            )
        actual_enabled = plugin_config.get("enabled")
        if actual_enabled is not plugin.enabled:
            fail(
                f"global Codex config has plugins.\"{plugin.plugin_id}\".enabled={actual_enabled!r}; "
                f"expected {plugin.enabled!r}. Re-run codex/scripts/sync-config.sh --apply"
            )

    bundled_marketplace = Path(
        os.environ.get(
            "CODEX_BUNDLED_MARKETPLACE",
            "/Applications/Codex.app/Contents/Resources/plugins/openai-bundled",
        )
    ).expanduser()
    if not bundled_marketplace.is_dir():
        return

    cache_root = Path.home() / ".codex/plugins/cache/openai-bundled"
    for plugin in managed_plugins:
        if not (plugin.enabled and plugin.marketplace == "openai-bundled" and plugin.scope in {"global", "repo"}):
            continue
        source = bundled_marketplace / "plugins" / plugin.plugin / ".codex-plugin/plugin.json"
        if not source.is_file():
            continue
        cached_manifests = list((cache_root / plugin.plugin).glob("*/.codex-plugin/plugin.json"))
        if not cached_manifests:
            fail(
                f"enabled bundled plugin `{plugin.plugin_id}` is missing from {cache_root}. "
                "Re-run codex/scripts/sync-config.sh --apply"
            )


FEATURE_RENAMES = {
    "codex_hooks": "hooks",
}


def load_codex_feature_statuses() -> dict[str, str]:
    fixture = os.environ.get("CODEX_FEATURES_LIST_OUTPUT")
    if fixture is not None:
        output = fixture
    else:
        codex_bin = os.environ.get("CODEX_BIN", "codex")
        if shutil.which(codex_bin) is None:
            return {}
        try:
            completed = subprocess.run(
                [codex_bin, "features", "list"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return {}
        if completed.returncode != 0:
            return {}
        output = completed.stdout

    statuses: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            statuses[parts[0]] = " ".join(parts[1:-1])
    return statuses


def validate_feature_flags(config_path: Path, feature_statuses: dict[str, str]) -> None:
    data = load_toml(config_path)
    features = data.get("features", {}) or {}
    if not isinstance(features, dict):
        fail(f"`features` must be a TOML table in {config_path}")

    for key in sorted(features):
        if key in FEATURE_RENAMES:
            fail(
                f"{config_path} uses deprecated Codex feature flag `{key}`; "
                f"use `{FEATURE_RENAMES[key]}` instead."
            )
        status = feature_statuses.get(str(key))
        if status == "deprecated":
            fail(f"{config_path} uses deprecated Codex feature flag `{key}`")


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
registry_path = Path(sys.argv[4]).expanduser().resolve()
mcp_registry_path = Path(sys.argv[5]).expanduser().resolve()
hooks_registry_path = Path(sys.argv[6]).expanduser().resolve()
plugin_registry_path = Path(sys.argv[7]).expanduser().resolve()
repo_filters = {str(Path(p).expanduser().resolve()) for p in sys.argv[8:] if p.strip()}

root_dir = canonical_dir.parent.parent.resolve()
sys.path.insert(0, str(root_dir))

from hooks.control_plane import load_hooks_registry, render_codex_hooks
from plugins.derived import validate_plugin_registry

global_template = canonical_dir / "global.config.toml"
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
codex_feature_statuses = load_codex_feature_statuses()

validate_no_agent_declarations(global_template)
validate_feature_flags(global_template, codex_feature_statuses)

if global_config.exists():
    validate_no_agent_declarations(global_config)
    validate_feature_flags(global_config, codex_feature_statuses)

if not registry_path.is_file():
    fail(f"missing registry file: {registry_path}")
if not mcp_registry_path.is_file():
    fail(f"missing MCP registry file: {mcp_registry_path}")
if not hooks_registry_path.is_file():
    fail(f"missing hooks registry file: {hooks_registry_path}")
if not plugin_registry_path.is_file():
    fail(f"missing plugin registry file: {plugin_registry_path}")
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
try:
    plugin_registry = json.loads(plugin_registry_path.read_text(encoding="utf-8"))
    managed_plugins, _unmanaged_plugins, _plugin_github_root = validate_plugin_registry(
        plugin_registry,
        root_dir=plugin_registry_path.parent.parent,
        home=Path.home(),
    )
except Exception as exc:
    fail(f"invalid plugin registry {plugin_registry_path}: {exc}")

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

resolved_repos: list[dict[str, str]] = []
for item in repos:
    if not isinstance(item, dict):
        fail("each repo entry must be an object")
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        fail("repo.path must be a non-empty string")
    repo_path = Path(raw_path).expanduser().resolve()
    repo_name = repo_path.name or str(repo_path)
    resolved_repos.append({"path": str(repo_path), "repo_name": repo_name})

if global_config.exists():
    global_data = load_toml(global_config)
    validate_disabled_skill_entries(global_config, bundled_skills_policy)
    validate_global_plugin_runtime(global_config, global_data, managed_plugins)
    features = global_data.get("features", {})
    hooks_enabled = isinstance(features, dict) and features.get("hooks") is True
    if hooks_enabled and not global_hooks.is_file():
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

    if not repo_path.exists() or not is_git_repo(repo_path):
        continue

    repo_config = repo_path / ".codex" / "config.toml"
    if not repo_config.exists():
        continue

    validate_no_agent_declarations(repo_config)
    validated_repo_count += 1

print("Codex structural validation passed")
print(f"  global runtime config checked: {'yes' if global_config.exists() else 'no'}")
print(f"  global runtime hooks checked: {'yes' if global_hooks.exists() else 'no'}")
print(f"  repo-local configs checked: {validated_repo_count}")
PY

if ! drift_output="$(
  "$SYNC_REPO_CONFIGS_SCRIPT" \
    --check \
    --registry "$REGISTRY_FILE" \
    --mcp-registry "$MCP_REGISTRY_FILE" \
    --hooks-registry "$HOOKS_REGISTRY_FILE" \
    --plugin-registry "$PLUGIN_REGISTRY_FILE" \
    "${REPO_ARGS[@]}" \
    2>&1
)"; then
  printf '%s\n' "$drift_output" >&2
  exit 1
fi

printf 'OK: Codex control plane validation passed\n'
