#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


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
            f"agent_count: {len(item['agents'])}",
            f"model: {_yaml_str(_effective_value(defaults, item, 'model'))}",
            f"reasoning: {_yaml_str(_effective_value(defaults, item, 'model_reasoning_effort'))}",
            f"fast_mode: {_yaml_str(_effective_fast_mode(defaults, item))}",
            f"service_tier: {_yaml_str(_effective_value(defaults, item, 'service_tier'))}",
        ]
        _append_yaml_list(lines, "mcps", item["mcp_presets"])
        _append_yaml_list(lines, "global_agents", item["global_agents"])
        _append_yaml_list(lines, "custom_agents", item["custom_agents"])
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
  repos_csv:
    displayName: Repos
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
      - repos_csv
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
      - repos_csv
      - transport
      - target
  - type: table
    name: Repo MCPs
    filters: 'repos_csv != "-"'
    order:
      - mcp_name
      - formula.scope_badge
      - repos_csv
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
  repos_csv:
    displayName: Repos
  config_file:
    displayName: Config File
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
      - repos_csv
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
      - repos_csv
      - config_file
      - description
  - type: table
    name: Repo Agents
    filters: 'repos_csv != "-"'
    order:
      - agent_name
      - formula.scope_badge
      - repos_csv
      - config_file
      - description
"""
    _write_if_changed(views_dir / "agent-registry.base", content)


def _load_global_agent_declarations(config_path: Path) -> dict[str, dict[str, str]]:
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
        declarations[str(name)] = {
            "description": description,
            "config_file": config_file,
        }
    return declarations


def apply_agent_assignments(
    repos: list[dict[str, Any]],
    global_terminal_agents: dict[str, dict[str, str]],
    global_xcode_agents: dict[str, dict[str, str]],
) -> None:
    global_agents = sorted(set(global_terminal_agents) | set(global_xcode_agents))
    global_agent_set = set(global_agents)
    for item in repos:
        item["global_agents"] = global_agents
        item["agents"] = sorted(global_agent_set | set(item["custom_agents"]))


def generate_agent_registry_items(
    views_dir: Path,
    global_terminal_agents: dict[str, dict[str, str]],
    global_xcode_agents: dict[str, dict[str, str]],
    agent_presets: dict[str, Any],
    repos: list[dict[str, Any]],
) -> None:
    root = views_dir / "agent-registry-items"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    repo_usage: dict[str, list[str]] = {}
    for item in repos:
        for agent_name in item["custom_agents"]:
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
        else:
            source = global_terminal_agents.get(agent_name) or global_xcode_agents.get(agent_name) or {}
            description = str(source.get("description", "-"))
            config_file = str(source.get("config_file", "-"))
        lines = [
            "---",
            f"agent_name: {_yaml_str(agent_name)}",
            f"effective_scope: {_yaml_str(_effective_scope(global_terminal, global_xcode, repos_for_agent))}",
            f"global_terminal: {_yaml_str(str(global_terminal).lower())}",
            f"global_xcode: {_yaml_str(str(global_xcode).lower())}",
            f"repos_csv: {_yaml_str(','.join(repos_for_agent) if repos_for_agent else '-')}",
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
        }

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
        }
        custom_agents = item.get("custom_agents", [])
        if not isinstance(custom_agents, list):
            raise ValueError(f"repos[{idx}].custom_agents must be an array")
        for agent_name in custom_agents:
            agent_name = str(agent_name)
            if agent_name not in validated_agent_presets:
                raise ValueError(f"repos[{idx}] references unknown custom agent: {agent_name}")
            validated["custom_agents"].append(agent_name)
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
    print(f"Generated repo bootstrap Base artifacts in {views_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
