#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ALLOWED_SCALAR_KEYS = {
    "model",
    "model_reasoning_effort",
    "service_tier",
    "profile",
    "model_reasoning_summary",
    "model_verbosity",
    "model_instructions_file",
    "project_root_markers",
    "web_search",
    "approval_policy",
    "sandbox_mode",
    "personality",
}
ALLOWED_DEFAULT_TABLE_KEYS = {
    "features",
}
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


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _display_path(path: Path, home: Path) -> str:
    try:
        rel = path.relative_to(home)
    except ValueError:
        return str(path)
    if not rel.parts:
        return "~"
    return f"~/{rel.as_posix()}"


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


def generated_views_dir(root_dir: Path) -> Path:
    return root_dir / "docs" / "references" / "registry"


def _sanitize_file_name(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-")


def _repo_name(path: str) -> str:
    return Path(path).name or path


def _append_yaml_list(lines: list[str], key: str, values: list[str]) -> None:
    if not values:
        lines.append(f"{key}: []")
        return
    lines.append(f"{key}:")
    lines.extend([f"  - {_yaml_str(value)}" for value in values])


def _effective_value(defaults: dict[str, Any], item: dict[str, Any], key: str) -> str:
    value = item.get(key, defaults.get(key))
    if value is None:
        return "-"
    return str(value)


def _effective_fast_mode(defaults: dict[str, Any], item: dict[str, Any]) -> str:
    default_features = defaults.get("features", {})
    item_features = item.get("features", {})
    if default_features and not isinstance(default_features, dict):
        return "-"
    if item_features and not isinstance(item_features, dict):
        return "-"
    merged = dict(default_features)
    merged.update(item_features)
    if "fast_mode" not in merged:
        return "-"
    return str(merged["fast_mode"]).lower()


def _effective_scope(global_terminal: bool, global_xcode: bool, repos: list[str]) -> str:
    has_global = global_terminal or global_xcode
    has_repos = bool(repos)
    if has_global and has_repos:
        return "mixed"
    if has_global:
        return "global"
    if has_repos:
        return "repo"
    return "-"


def _load_agent_role_config(config_path: Path) -> dict[str, str]:
    if not config_path.is_file():
        return {
            "model": "-",
            "reasoning": "-",
            "sandbox_mode": "-",
        }
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return {
        "model": str(data.get("model", "-")),
        "reasoning": str(data.get("model_reasoning_effort", "-")),
        "sandbox_mode": str(data.get("sandbox_mode", "-")),
    }


def _load_agent_role_data(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        return {}
    return data


def _validate_policy_object(policy: dict[str, Any], *, label: str, mcp_presets: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = ROLE_OVERRIDE_SCALAR_KEYS | {"tools", "features", "mcp"}
    unexpected = sorted(set(policy.keys()) - allowed_keys)
    if unexpected:
        raise ValueError(f"{label} has unsupported keys: {', '.join(unexpected)}")

    normalized: dict[str, Any] = {}
    for key in ROLE_OVERRIDE_SCALAR_KEYS:
        if key in policy:
            value = policy[key]
            if value is not None and not isinstance(value, (str, int, bool, list)):
                raise ValueError(f"{label}.{key} must be a TOML-scalar-compatible value")
            normalized[key] = value

    for table_key in ("tools", "features"):
        if table_key in policy:
            table = policy[table_key]
            if not isinstance(table, dict):
                raise ValueError(f"{label}.{table_key} must be an object")
            if any(not isinstance(name, str) for name in table):
                raise ValueError(f"{label}.{table_key} keys must be strings")
            normalized[table_key] = dict(table)

    if "mcp" in policy:
        mcp = policy["mcp"]
        if not isinstance(mcp, dict):
            raise ValueError(f"{label}.mcp must be an object")
        mode = mcp.get("mode", "inherit")
        if mode not in {"inherit", "deny_all", "allow_list"}:
            raise ValueError(f"{label}.mcp.mode must be one of: inherit, deny_all, allow_list")
        presets = mcp.get("presets", [])
        if presets is None:
            presets = []
        if not isinstance(presets, list) or any(not isinstance(item, str) for item in presets):
            raise ValueError(f"{label}.mcp.presets must be an array of strings")
        unknown = sorted(set(presets) - set(mcp_presets))
        if unknown:
            raise ValueError(f"{label}.mcp references unknown MCP presets: {', '.join(unknown)}")
        normalized["mcp"] = {
            "mode": mode,
            "presets": [str(item) for item in presets],
        }

    return normalized


def _resolve_repo_agent_names(custom_agents: list[str], agent_policy_map: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    for agent_name in [*custom_agents, *agent_policy_map.keys()]:
        if agent_name not in ordered:
            ordered.append(agent_name)
    return ordered


def _merge_boolish_table(base: dict[str, Any] | None, overrides: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    if overrides:
        merged.update(overrides)
    return merged


def _apply_agent_policy_to_role(
    role_data: dict[str, Any],
    *,
    repo_mcp_preset_names: list[str],
    mcp_presets: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(role_data)
    for key in ROLE_OVERRIDE_SCALAR_KEYS:
        if key in policy:
            merged[key] = policy[key]

    for table_key in ("tools", "features"):
        merged_table = _merge_boolish_table(
            merged.get(table_key) if isinstance(merged.get(table_key), dict) else None,
            policy.get(table_key) if isinstance(policy.get(table_key), dict) else None,
        )
        if merged_table:
            merged[table_key] = merged_table
        else:
            merged.pop(table_key, None)

    base_mcp_servers = dict(merged.get("mcp_servers", {}) or {})
    mcp_policy = policy.get("mcp")
    if isinstance(mcp_policy, dict):
        mode = str(mcp_policy.get("mode", "inherit"))
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _tool_state_lists(role_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    tools = role_data.get("tools", {})
    if not isinstance(tools, dict):
        return [], []
    enabled = sorted(str(name) for name, value in tools.items() if value is True)
    disabled = sorted(str(name) for name, value in tools.items() if value is False)
    return enabled, disabled


def _feature_state_lists(role_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    features = role_data.get("features", {})
    if not isinstance(features, dict):
        return [], []
    enabled = sorted(str(name) for name, value in features.items() if value is True)
    disabled = sorted(str(name) for name, value in features.items() if value is False)
    return enabled, disabled


def _mcp_state_lists(role_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    mcp_servers = role_data.get("mcp_servers", {})
    if not isinstance(mcp_servers, dict):
        return [], []
    enabled: list[str] = []
    disabled: list[str] = []
    for name, config in mcp_servers.items():
        if isinstance(config, dict) and config.get("enabled") is False:
            disabled.append(str(name))
        else:
            enabled.append(str(name))
    return sorted(enabled), sorted(disabled)


def _capability_item(
    *,
    agent_name: str,
    config_file: str,
    role_data: dict[str, Any],
    scope_type: str,
    repo_name: str,
    policy_binding: str,
) -> dict[str, Any]:
    enabled_tools, disabled_tools = _tool_state_lists(role_data)
    enabled_features, disabled_features = _feature_state_lists(role_data)
    enabled_mcps, disabled_mcps = _mcp_state_lists(role_data)
    js_repl = "-"
    features = role_data.get("features", {})
    if isinstance(features, dict) and "js_repl" in features:
        js_repl = str(features["js_repl"]).lower()
    return {
        "agent_name": agent_name,
        "scope_type": scope_type,
        "repo_name": repo_name,
        "config_file": config_file,
        "model": str(role_data.get("model", "-")),
        "reasoning": str(role_data.get("model_reasoning_effort", "-")),
        "sandbox_mode": str(role_data.get("sandbox_mode", "-")),
        "web_search": str(role_data.get("web_search", "-")),
        "js_repl": js_repl,
        "policy_binding": policy_binding,
        "enabled_tools": enabled_tools,
        "disabled_tools": disabled_tools,
        "enabled_features": enabled_features,
        "disabled_features": disabled_features,
        "enabled_mcps": enabled_mcps,
        "disabled_mcps": disabled_mcps,
        "description": str(role_data.get("description", "-")),
    }


def generate_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/repo-bootstrap-items")'
properties:
  repo_name:
    displayName: Repo
  path:
    displayName: Path
  mcp_count:
    displayName: MCP Count
  mcps:
    displayName: MCPs
  skill_count:
    displayName: Skill Count
  repo_local_skill_count:
    displayName: Repo-Local Skill Count
  global_agent_count:
    displayName: Global Agent Count
  custom_agent_count:
    displayName: Custom Agent Count
  repo_agent_count:
    displayName: Repo Agent Count
  agent_policy_count:
    displayName: Agent Policy Count
  agent_count:
    displayName: Agent Count
  skills:
    displayName: Skills
  global_skills:
    displayName: Global Skills
  repo_skills:
    displayName: Repo Skills
  repo_local_skills:
    displayName: Repo-Local Skills
  agents:
    displayName: Agents
  global_agents:
    displayName: Global Agents
  custom_agents:
    displayName: Custom Agents
  repo_agents:
    displayName: Repo Agents
  agent_policy_agents:
    displayName: Agent Policy Agents
  agent_policy_bindings:
    displayName: Agent Policies
  model:
    displayName: Model
  reasoning:
    displayName: Reasoning
  fast_mode:
    displayName: Fast Mode
  service_tier:
    displayName: Service Tier
views:
  - type: table
    name: Repo Bootstrap
    order:
      - repo_name
      - skill_count
      - repo_local_skill_count
      - mcps
      - repo_agents
      - agents
      - model
      - reasoning
      - fast_mode
      - service_tier
  - type: table
    name: MCP Enabled
    filters: 'mcp_count > 0'
    order:
      - repo_name
      - mcps
      - agents
      - model
      - reasoning
      - fast_mode
      - service_tier
  - type: table
    name: Custom Agents
    filters: 'custom_agent_count > 0'
    order:
      - repo_name
      - skill_count
      - repo_local_skill_count
      - custom_agents
      - repo_agents
      - agent_policy_bindings
      - global_agents
      - mcps
      - model
      - reasoning
      - fast_mode
      - service_tier
  - type: table
    name: Skill Detail
    filters: 'skill_count > 0'
    order:
      - repo_name
      - skill_count
      - repo_local_skill_count
      - global_skills
      - repo_skills
      - repo_local_skills
      - mcps
      - agents
"""
    _write_if_changed(views_dir / "repo-bootstrap.base", content)


def generate_registry_items(
    views_dir: Path, defaults: dict[str, Any], repos: list[dict[str, Any]]
) -> None:
    root = views_dir / "repo-bootstrap-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    for item in repos:
        file_name = f"{_sanitize_file_name(item['repo_name'])}.md"
        lines = [
            "---",
            f"repo_name: {_yaml_str(item['repo_name'])}",
            f"path: {_yaml_str(item['path'])}",
            f"mcp_count: {len(item['mcp_presets'])}",
            f"skill_count: {len(item['skills'])}",
            f"repo_local_skill_count: {len(item['repo_local_skills'])}",
            f"global_agent_count: {len(item['global_agents'])}",
            f"custom_agent_count: {len(item['custom_agents'])}",
            f"repo_agent_count: {len(item['repo_agents'])}",
            f"agent_policy_count: {len(item['agent_policy_agents'])}",
            f"agent_count: {len(item['agents'])}",
            f"model: {_yaml_str(_effective_value(defaults, item, 'model'))}",
            f"reasoning: {_yaml_str(_effective_value(defaults, item, 'model_reasoning_effort'))}",
            f"fast_mode: {_yaml_str(_effective_fast_mode(defaults, item))}",
            f"service_tier: {_yaml_str(_effective_value(defaults, item, 'service_tier'))}",
        ]
        _append_yaml_list(lines, "mcps", item["mcp_presets"])
        _append_yaml_list(lines, "global_agents", item["global_agents"])
        _append_yaml_list(lines, "custom_agents", item["custom_agents"])
        _append_yaml_list(lines, "repo_agents", item["repo_agents"])
        _append_yaml_list(lines, "agent_policy_agents", item["agent_policy_agents"])
        _append_yaml_list(lines, "agent_policy_bindings", item["agent_policy_bindings"])
        _append_yaml_list(lines, "agents", item["agents"])
        _append_yaml_list(lines, "global_skills", item["global_skills"])
        _append_yaml_list(lines, "repo_skills", item["repo_scoped_skills"])
        _append_yaml_list(lines, "repo_local_skills", item["repo_local_skills"])
        _append_yaml_list(lines, "skills", item["skills"])
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json` and `skills/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / file_name, "\n".join(lines))


def _load_global_mcp_names(config_path: Path) -> set[str]:
    if not config_path.is_file():
        return set()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    mcp_servers = data.get("mcp_servers", {})
    if not isinstance(mcp_servers, dict):
        return set()
    return {str(name) for name in mcp_servers.keys()}


def _mcp_transport(preset: dict[str, Any]) -> str:
    if "url" in preset:
        return "url"
    if "command" in preset:
        return "command"
    return "-"


def _mcp_target(preset: dict[str, Any]) -> str:
    if "url" in preset:
        return str(preset["url"])
    if "command" in preset:
        args = preset.get("args", [])
        if isinstance(args, list) and args:
            return " ".join([str(preset["command"]), *[str(arg) for arg in args]])
        return str(preset["command"])
    return "-"


def _resolve_repo_root(path: Path) -> Path:
    try:
        repo_root_out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return Path(repo_root_out).resolve()
    except subprocess.CalledProcessError:
        return path.resolve()


def _load_skill_assignments(
    root_dir: Path, home: Path, repos: list[dict[str, Any]]
) -> None:
    registry_file = root_dir / "skills" / "registry.json"
    if not registry_file.is_file():
        for item in repos:
            item["global_skills"] = []
            item["repo_scoped_skills"] = []
            item["repo_local_skills"] = []
            item["skills"] = []
        return

    data = json.loads(registry_file.read_text(encoding="utf-8"))
    github_root_raw = data.get("paths", {}).get("github_root", "~/GitHub")
    github_root = expand_path(str(github_root_raw), home).resolve()
    repo_by_root = {item["repo_root"]: item for item in repos}
    global_skills: set[str] = set()
    repo_scoped: dict[Path, set[str]] = {item["repo_root"]: set() for item in repos}
    repo_local: dict[Path, set[str]] = {item["repo_root"]: set() for item in repos}

    for raw_item in data.get("managed_skills", []):
        if not isinstance(raw_item, dict):
            continue
        skill = str(raw_item.get("skill", "")).strip()
        scope = str(raw_item.get("scope", "")).strip()
        if not skill:
            continue
        if scope == "global":
            global_skills.add(skill)
            continue
        if scope != "repo":
            continue
        repos_raw = raw_item.get("repos", [])
        if not isinstance(repos_raw, list):
            continue
        for repo_ref in repos_raw:
            repo_root = _resolve_repo_root(
                expand_path(str(repo_ref), home)
                if str(repo_ref).startswith(("~/", "/"))
                else github_root / str(repo_ref)
            )
            if repo_root in repo_scoped:
                repo_scoped[repo_root].add(skill)

    for raw_item in data.get("unmanaged_repo_local_skills", []):
        if not isinstance(raw_item, dict):
            continue
        skill = str(raw_item.get("skill", "")).strip()
        repo_ref = str(raw_item.get("repo", "")).strip()
        if not skill or not repo_ref:
            continue
        repo_root = _resolve_repo_root(
            expand_path(repo_ref, home)
            if repo_ref.startswith(("~/", "/"))
            else github_root / repo_ref
        )
        if repo_root in repo_local:
            repo_local[repo_root].add(skill)

    global_skill_list = sorted(global_skills)
    for repo_root, item in repo_by_root.items():
        repo_scoped_list = sorted(repo_scoped.get(repo_root, set()))
        repo_local_list = sorted(repo_local.get(repo_root, set()))
        skills = sorted(
            set(global_skill_list) | set(repo_scoped_list) | set(repo_local_list)
        )
        item["global_skills"] = global_skill_list
        item["repo_scoped_skills"] = repo_scoped_list
        item["repo_local_skills"] = repo_local_list
        item["skills"] = skills


def generate_mcp_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/mcp-registry-items")'
formulas:
  scope_badge: 'if(effective_scope == "global", "🌍 global", if(effective_scope == "repo", "📦 repo", if(effective_scope == "mixed", "🧩 mixed", effective_scope)))'
properties:
  mcp_name:
    displayName: MCP
  effective_scope:
    displayName: Scope
  formula.scope_badge:
    displayName: Scope
  global_terminal:
    displayName: Global Terminal
  global_xcode:
    displayName: Global Xcode
  repos:
    displayName: Repos
  repos_csv:
    displayName: Repos CSV
  transport:
    displayName: Transport
  target:
    displayName: Target
views:
  - type: table
    name: MCP Registry
    order:
      - mcp_name
      - formula.scope_badge
      - global_terminal
      - global_xcode
      - repos
      - transport
      - target
  - type: table
    name: Global MCPs
    filters: 'global_terminal == "true" || global_xcode == "true"'
    order:
      - mcp_name
      - formula.scope_badge
      - global_terminal
      - global_xcode
      - repos
      - transport
      - target
  - type: table
    name: Repo MCPs
    filters: 'repos_csv != "-"'
    order:
      - mcp_name
      - formula.scope_badge
      - repos
      - transport
      - target
"""
    _write_if_changed(views_dir / "mcp-registry.base", content)


def generate_mcp_registry_items(
    views_dir: Path,
    presets: dict[str, Any],
    repos: list[dict[str, Any]],
    global_terminal_mcp: set[str],
    global_xcode_mcp: set[str],
) -> None:
    root = views_dir / "mcp-registry-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    repo_usage: dict[str, list[str]] = {name: [] for name in presets}
    for item in repos:
        for preset_name in item["mcp_presets"]:
            repo_usage.setdefault(preset_name, []).append(item["repo_name"])

    for preset_name in sorted(presets):
        preset = presets[preset_name]
        repos_for_preset = sorted(repo_usage.get(preset_name, []))
        global_terminal = preset_name in global_terminal_mcp
        global_xcode = preset_name in global_xcode_mcp
        lines = [
            "---",
            f"mcp_name: {_yaml_str(preset_name)}",
            f"effective_scope: {_yaml_str(_effective_scope(global_terminal, global_xcode, repos_for_preset))}",
            f"global_terminal: {_yaml_str(str(global_terminal).lower())}",
            f"global_xcode: {_yaml_str(str(global_xcode).lower())}",
            f"repos_csv: {_yaml_str(','.join(repos_for_preset) if repos_for_preset else '-')}",
            f"transport: {_yaml_str(_mcp_transport(preset))}",
            f"target: {_yaml_str(_mcp_target(preset))}",
            "repos:",
        ]
        if repos_for_preset:
            lines.extend([f"  - {_yaml_str(repo_name)}" for repo_name in repos_for_preset])
        else:
            lines.append('  - "-"')
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json` plus the managed global Codex config templates. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / f"{_sanitize_file_name(preset_name)}.md", "\n".join(lines))


def generate_agent_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/agent-registry-items")'
formulas:
  scope_badge: 'if(effective_scope == "global", "🌍 global", if(effective_scope == "repo", "📦 repo", if(effective_scope == "mixed", "🧩 mixed", effective_scope)))'
properties:
  agent_name:
    displayName: Agent
  effective_scope:
    displayName: Scope
  formula.scope_badge:
    displayName: Scope
  global_terminal:
    displayName: Global Terminal
  global_xcode:
    displayName: Global Xcode
  repos:
    displayName: Repos
  repos_csv:
    displayName: Repos CSV
  config_file:
    displayName: Config File
  model:
    displayName: Model
  reasoning:
    displayName: Reasoning
  sandbox_mode:
    displayName: Sandbox
  description:
    displayName: Description
views:
  - type: table
    name: Agent Registry
    order:
      - agent_name
      - formula.scope_badge
      - global_terminal
      - global_xcode
      - repos
      - model
      - reasoning
      - sandbox_mode
      - config_file
      - description
  - type: table
    name: Global Agents
    filters: 'global_terminal == "true" || global_xcode == "true"'
    order:
      - agent_name
      - formula.scope_badge
      - global_terminal
      - global_xcode
      - repos
      - model
      - reasoning
      - sandbox_mode
      - config_file
      - description
  - type: table
    name: Repo Agents
    filters: 'repos_csv != "-"'
    order:
      - agent_name
      - formula.scope_badge
      - repos
      - model
      - reasoning
      - sandbox_mode
      - config_file
      - description
"""
    _write_if_changed(views_dir / "agent-registry.base", content)


def _load_global_agent_declarations(config_path: Path) -> dict[str, dict[str, Any]]:
    if not config_path.is_file():
        return {}
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        return {}
    declarations: dict[str, dict[str, str]] = {}
    for name, agent in agents.items():
        if not isinstance(agent, dict):
            continue
        description = str(agent.get("description", "")).strip() or "-"
        config_file = str(agent.get("config_file", "")).strip() or "-"
        role_path = (config_path.parent / config_file).resolve() if config_file != "-" else None
        role_meta = _load_agent_role_config(role_path) if role_path else {
            "model": "-",
            "reasoning": "-",
            "sandbox_mode": "-",
        }
        role_data = _load_agent_role_data(role_path) if role_path else {}
        declarations[str(name)] = {
            "description": description,
            "config_file": config_file,
            "model": role_meta["model"],
            "reasoning": role_meta["reasoning"],
            "sandbox_mode": role_meta["sandbox_mode"],
            "role_data": role_data,
        }
    return declarations


def apply_agent_assignments(
    repos: list[dict[str, Any]],
    global_terminal_agents: dict[str, dict[str, Any]],
    global_xcode_agents: dict[str, dict[str, Any]],
) -> None:
    global_agents = sorted(set(global_terminal_agents) | set(global_xcode_agents))
    global_agent_set = set(global_agents)
    for item in repos:
        item["global_agents"] = global_agents
        item["agents"] = sorted(global_agent_set | set(item["repo_agents"]))


def generate_agent_registry_items(
    views_dir: Path,
    global_terminal_agents: dict[str, dict[str, Any]],
    global_xcode_agents: dict[str, dict[str, Any]],
    agent_presets: dict[str, Any],
    repos: list[dict[str, Any]],
) -> None:
    root = views_dir / "agent-registry-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    repo_usage: dict[str, list[str]] = {}
    for item in repos:
        for agent_name in item["repo_agents"]:
            repo_usage.setdefault(agent_name, []).append(item["repo_name"])

    all_agent_names = sorted(
        set(global_terminal_agents)
        | set(global_xcode_agents)
        | set(agent_presets)
        | set(repo_usage)
    )

    for agent_name in all_agent_names:
        global_terminal = agent_name in global_terminal_agents
        global_xcode = agent_name in global_xcode_agents
        repos_for_agent = sorted(repo_usage.get(agent_name, []))
        if agent_name in agent_presets:
            description = str(agent_presets[agent_name]["description"])
            config_file = f"agents/{agent_presets[agent_name]['config_file']}"
            model = str(agent_presets[agent_name].get("model", "-"))
            reasoning = str(agent_presets[agent_name].get("reasoning", "-"))
            sandbox_mode = str(agent_presets[agent_name].get("sandbox_mode", "-"))
        else:
            source = global_terminal_agents.get(agent_name) or global_xcode_agents.get(agent_name) or {}
            description = str(source.get("description", "-"))
            config_file = str(source.get("config_file", "-"))
            model = str(source.get("model", "-"))
            reasoning = str(source.get("reasoning", "-"))
            sandbox_mode = str(source.get("sandbox_mode", "-"))
        lines = [
            "---",
            f"agent_name: {_yaml_str(agent_name)}",
            f"effective_scope: {_yaml_str(_effective_scope(global_terminal, global_xcode, repos_for_agent))}",
            f"global_terminal: {_yaml_str(str(global_terminal).lower())}",
            f"global_xcode: {_yaml_str(str(global_xcode).lower())}",
            f"repos_csv: {_yaml_str(','.join(repos_for_agent) if repos_for_agent else '-')}",
            f"model: {_yaml_str(model)}",
            f"reasoning: {_yaml_str(reasoning)}",
            f"sandbox_mode: {_yaml_str(sandbox_mode)}",
            f"config_file: {_yaml_str(config_file)}",
            f"description: {_yaml_str(description)}",
            "repos:",
        ]
        if repos_for_agent:
            lines.extend([f"  - {_yaml_str(repo_name)}" for repo_name in repos_for_agent])
        else:
            lines.append('  - "-"')
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json` plus the managed global Codex config templates. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / f"{_sanitize_file_name(agent_name)}.md", "\n".join(lines))


def generate_agent_capabilities_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/agent-capabilities-items")'
properties:
  agent_name:
    displayName: Agent
  scope_type:
    displayName: Scope
  repo_name:
    displayName: Repo
  model:
    displayName: Model
  reasoning:
    displayName: Reasoning
  sandbox_mode:
    displayName: Sandbox
  web_search:
    displayName: Web Search
  js_repl:
    displayName: JS REPL
  enabled_mcps:
    displayName: Enabled MCPs
  disabled_mcps:
    displayName: Disabled MCPs
  disabled_tools:
    displayName: Disabled Tools
  enabled_tools:
    displayName: Enabled Tools
  disabled_features:
    displayName: Disabled Features
  enabled_features:
    displayName: Enabled Features
  policy_binding:
    displayName: Policy
  config_file:
    displayName: Config File
views:
  - type: table
    name: Agent Capabilities
    order:
      - agent_name
      - scope_type
      - repo_name
      - model
      - web_search
      - js_repl
      - enabled_mcps
      - disabled_mcps
      - disabled_tools
      - policy_binding
  - type: table
    name: Repo Agent Capabilities
    filters: 'scope_type == "repo"'
    order:
      - repo_name
      - agent_name
      - model
      - web_search
      - js_repl
      - enabled_mcps
      - disabled_mcps
      - disabled_tools
      - policy_binding
  - type: table
    name: MCP Restricted
    filters: 'disabled_mcps.length() > 0'
    order:
      - agent_name
      - scope_type
      - repo_name
      - enabled_mcps
      - disabled_mcps
      - policy_binding
"""
    _write_if_changed(views_dir / "agent-capabilities.base", content)


def generate_agent_capabilities_items(
    views_dir: Path,
    global_terminal_agents: dict[str, dict[str, Any]],
    global_xcode_agents: dict[str, dict[str, Any]],
    agent_presets: dict[str, Any],
    repos: list[dict[str, Any]],
    mcp_presets: dict[str, Any],
) -> None:
    root = views_dir / "agent-capabilities-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []

    for agent_name, meta in sorted(global_terminal_agents.items()):
        role_data = meta.get("role_data", {}) if isinstance(meta.get("role_data"), dict) else {}
        items.append(
            _capability_item(
                agent_name=agent_name,
                config_file=str(meta.get("config_file", "-")),
                role_data=role_data,
                scope_type="global_terminal",
                repo_name="-",
                policy_binding="-",
            )
        )

    for agent_name, meta in sorted(global_xcode_agents.items()):
        role_data = meta.get("role_data", {}) if isinstance(meta.get("role_data"), dict) else {}
        items.append(
            _capability_item(
                agent_name=agent_name,
                config_file=str(meta.get("config_file", "-")),
                role_data=role_data,
                scope_type="global_xcode",
                repo_name="-",
                policy_binding="-",
            )
        )

    for repo in repos:
        repo_name = str(repo["repo_name"])
        repo_mcp_presets = [str(name) for name in repo["mcp_presets"]]
        policy_map = repo.get("resolved_agent_policies", {})
        binding_map = repo.get("agent_policy_binding_map", {})
        for agent_name in repo["repo_agents"]:
            preset = agent_presets.get(agent_name, {})
            role_data = preset.get("role_data", {}) if isinstance(preset.get("role_data"), dict) else {}
            effective_role = _apply_agent_policy_to_role(
                role_data,
                repo_mcp_preset_names=repo_mcp_presets,
                mcp_presets=mcp_presets,
                policy=policy_map.get(agent_name, {}),
            )
            items.append(
                _capability_item(
                    agent_name=str(agent_name),
                    config_file=f"agents/{preset.get('config_file', '-')}",
                    role_data=effective_role,
                    scope_type="repo",
                    repo_name=repo_name,
                    policy_binding=str(binding_map.get(agent_name, "-")),
                )
            )

    for item in items:
        repo_slug = item["repo_name"] if item["repo_name"] != "-" else item["scope_type"]
        file_name = f"{_sanitize_file_name(repo_slug)}--{_sanitize_file_name(item['agent_name'])}.md"
        lines = [
            "---",
            f"agent_name: {_yaml_str(item['agent_name'])}",
            f"scope_type: {_yaml_str(item['scope_type'])}",
            f"repo_name: {_yaml_str(item['repo_name'])}",
            f"model: {_yaml_str(item['model'])}",
            f"reasoning: {_yaml_str(item['reasoning'])}",
            f"sandbox_mode: {_yaml_str(item['sandbox_mode'])}",
            f"web_search: {_yaml_str(item['web_search'])}",
            f"js_repl: {_yaml_str(item['js_repl'])}",
            f"policy_binding: {_yaml_str(item['policy_binding'])}",
            f"config_file: {_yaml_str(item['config_file'])}",
        ]
        _append_yaml_list(lines, "enabled_mcps", item["enabled_mcps"])
        _append_yaml_list(lines, "disabled_mcps", item["disabled_mcps"])
        _append_yaml_list(lines, "enabled_tools", item["enabled_tools"])
        _append_yaml_list(lines, "disabled_tools", item["disabled_tools"])
        _append_yaml_list(lines, "enabled_features", item["enabled_features"])
        _append_yaml_list(lines, "disabled_features", item["disabled_features"])
        lines.extend(
            [
                f"description: {_yaml_str(item['description'])}",
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json` plus the managed agent templates. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / file_name, "\n".join(lines))


def validate_registry(
    data: dict[str, Any], config_dir: Path, home: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object")

    for key in defaults:
        if key not in ALLOWED_SCALAR_KEYS and key not in ALLOWED_DEFAULT_TABLE_KEYS:
            raise ValueError(f"unsupported default key: {key}")
    if "features" in defaults and not isinstance(defaults["features"], dict):
        raise ValueError("defaults.features must be an object")

    presets = data.get("mcp_presets", {})
    if not isinstance(presets, dict):
        raise ValueError("mcp_presets must be an object")

    agent_presets = data.get("agent_presets", {})
    if not isinstance(agent_presets, dict):
        raise ValueError("agent_presets must be an object")
    agent_policy_presets = data.get("agent_policy_presets", {})
    if not isinstance(agent_policy_presets, dict):
        raise ValueError("agent_policy_presets must be an object")
    agents_dir = config_dir / "agents"
    validated_agent_presets: dict[str, Any] = {}
    for name, preset in agent_presets.items():
        if not isinstance(preset, dict):
            raise ValueError(f"agent_presets.{name} must be an object")
        description = preset.get("description")
        config_file = preset.get("config_file")
        nickname_candidates = preset.get("nickname_candidates", [])
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"agent_presets.{name}.description must be a non-empty string")
        if not isinstance(config_file, str) or not config_file.strip():
            raise ValueError(f"agent_presets.{name}.config_file must be a non-empty string")
        if not isinstance(nickname_candidates, list) or any(not isinstance(item, str) for item in nickname_candidates):
            raise ValueError(f"agent_presets.{name}.nickname_candidates must be an array of strings")
        config_path = agents_dir / config_file
        if not config_path.is_file():
            raise ValueError(f"agent_presets.{name}.config_file points to missing file: {config_path}")
        validated_agent_presets[str(name)] = {
            "description": description,
            "config_file": config_file,
            "nickname_candidates": nickname_candidates,
            "role_data": _load_agent_role_data(config_path),
            **_load_agent_role_config(config_path),
        }

    validated_agent_policy_presets: dict[str, Any] = {}
    for name, preset in agent_policy_presets.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("agent_policy_presets keys must be non-empty strings")
        if not isinstance(preset, dict):
            raise ValueError(f"agent_policy_presets.{name} must be an object")
        validated_agent_policy_presets[str(name)] = _validate_policy_object(
            preset,
            label=f"agent_policy_presets.{name}",
            mcp_presets=presets,
        )

    repos_raw = data.get("repos")
    if not isinstance(repos_raw, list) or not repos_raw:
        raise ValueError("repos must be a non-empty array")

    seen: set[str] = set()
    repos: list[dict[str, Any]] = []
    for idx, item in enumerate(repos_raw):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{idx}] must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"repos[{idx}].path must be a non-empty string")
        path_str = raw_path.strip()
        repo_path = expand_path(path_str, home).resolve()
        if str(repo_path) in seen:
            raise ValueError(f"duplicate repo path: {path_str}")
        seen.add(str(repo_path))

        repo_root = _resolve_repo_root(repo_path)
        if repo_root == repo_path.resolve() and not (repo_root / ".git").exists():
            print(f"WARNING: skipping non-git path: {path_str}", file=sys.stderr)
            continue

        mcp_presets = item.get("mcp_presets", [])
        if not isinstance(mcp_presets, list):
            raise ValueError(f"repos[{idx}].mcp_presets must be an array")
        for preset_name in mcp_presets:
            if preset_name not in presets:
                raise ValueError(
                    f"repos[{idx}] references unknown MCP preset: {preset_name}"
                )

        validated = {
            "path": _display_path(repo_root, home),
            "repo_name": _repo_name(str(repo_root)),
            "repo_root": repo_root,
            "mcp_presets": [str(name) for name in mcp_presets],
            "mcp_presets_csv": ",".join(mcp_presets) if mcp_presets else "-",
            "custom_agents": [],
            "agent_policy_agents": [],
            "agent_policy_bindings": [],
            "agent_policy_binding_map": {},
            "resolved_agent_policies": {},
        }
        custom_agents = item.get("custom_agents", [])
        if not isinstance(custom_agents, list):
            raise ValueError(f"repos[{idx}].custom_agents must be an array")
        for agent_name in custom_agents:
            agent_name = str(agent_name)
            if agent_name not in validated_agent_presets:
                raise ValueError(f"repos[{idx}] references unknown custom agent: {agent_name}")
            validated["custom_agents"].append(agent_name)

        raw_agent_policies = item.get("agent_policies", {})
        if raw_agent_policies is None:
            raw_agent_policies = {}
        if not isinstance(raw_agent_policies, dict):
            raise ValueError(f"repos[{idx}].agent_policies must be an object")
        resolved_agent_policies: dict[str, Any] = {}
        for agent_name, raw_policy in raw_agent_policies.items():
            agent_name = str(agent_name)
            if agent_name not in validated_agent_presets:
                raise ValueError(f"repos[{idx}] references unknown agent policy target: {agent_name}")
            if isinstance(raw_policy, str):
                if raw_policy not in validated_agent_policy_presets:
                    raise ValueError(
                        f"repos[{idx}].agent_policies.{agent_name} references unknown preset: {raw_policy}"
                    )
                resolved_agent_policies[agent_name] = dict(validated_agent_policy_presets[raw_policy])
                validated["agent_policy_bindings"].append(f"{agent_name}={raw_policy}")
                validated["agent_policy_binding_map"][agent_name] = str(raw_policy)
                continue
            if isinstance(raw_policy, dict):
                resolved_agent_policies[agent_name] = _validate_policy_object(
                    raw_policy,
                    label=f"repos[{idx}].agent_policies.{agent_name}",
                    mcp_presets=presets,
                )
                validated["agent_policy_bindings"].append(f"{agent_name}=inline")
                validated["agent_policy_binding_map"][agent_name] = "inline"
                continue
            raise ValueError(
                f"repos[{idx}].agent_policies.{agent_name} must be a preset name or object"
            )
        validated["agent_policy_agents"] = sorted(resolved_agent_policies.keys())
        validated["resolved_agent_policies"] = resolved_agent_policies
        validated["repo_agents"] = _resolve_repo_agent_names(
            validated["custom_agents"], resolved_agent_policies
        )
        for key in ALLOWED_SCALAR_KEYS:
            if key in item:
                validated[key] = item[key]
        if "features" in item:
            if not isinstance(item["features"], dict):
                raise ValueError(f"repos[{idx}].features must be an object")
            validated["features"] = item["features"]
        repos.append(validated)

    repos.sort(key=lambda item: item["path"])
    return defaults, presets, validated_agent_presets, repos


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Obsidian Base artifacts for the Codex repo bootstrap registry."
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "codex" / "config" / "repo-bootstrap.json"),
        help="Path to repo bootstrap registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {registry_file}: {exc}", file=sys.stderr)
        return 1

    config_dir = registry_file.parent
    root_dir = config_dir.parent.parent
    home = Path.home()
    try:
        defaults, presets, agent_presets, repos = validate_registry(data, config_dir, home)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    views_dir = generated_views_dir(root_dir)
    _load_skill_assignments(root_dir, home, repos)
    global_terminal_agents = _load_global_agent_declarations(config_dir / "global.config.toml")
    global_xcode_agents = _load_global_agent_declarations(config_dir / "xcode.config.toml")
    apply_agent_assignments(repos, global_terminal_agents, global_xcode_agents)
    generate_registry_base(views_dir)
    generate_registry_items(views_dir, defaults, repos)
    global_terminal_mcp = _load_global_mcp_names(config_dir / "global.config.toml")
    global_xcode_mcp = _load_global_mcp_names(config_dir / "xcode.config.toml")
    generate_mcp_registry_base(views_dir)
    generate_mcp_registry_items(
        views_dir, presets, repos, global_terminal_mcp, global_xcode_mcp
    )
    generate_agent_registry_base(views_dir)
    generate_agent_registry_items(
        views_dir, global_terminal_agents, global_xcode_agents, agent_presets, repos
    )
    generate_agent_capabilities_base(views_dir)
    generate_agent_capabilities_items(
        views_dir,
        global_terminal_agents,
        global_xcode_agents,
        agent_presets,
        repos,
        presets,
    )
    print(f"Generated repo bootstrap Base artifacts in {views_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
