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
    "plan_mode_reasoning_effort",
    "service_tier",
    "profile",
    "model_reasoning_summary",
    "model_verbosity",
    "model_instructions_file",
    "developer_instructions",
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


def _effective_scope(global_terminal: bool, repos: list[str]) -> str:
    has_global = global_terminal
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
  plugin_count:
    displayName: Plugin Count
  plugins:
    displayName: Plugins
  global_plugins:
    displayName: Global Plugins
  repo_plugins:
    displayName: Repo Plugins
  skill_count:
    displayName: Skill Count
  repo_local_skill_count:
    displayName: Repo-Local Skill Count
  skills:
    displayName: Skills
  global_skills:
    displayName: Global Skills
  repo_skills:
    displayName: Repo Skills
  repo_local_skills:
    displayName: Repo-Local Skills
  model:
    displayName: Model
  reasoning:
    displayName: Reasoning
  service_tier:
    displayName: Service Tier
views:
  - type: table
    name: Repo Bootstrap
    order:
      - repo_name
      - plugin_count
      - skill_count
      - repo_local_skill_count
      - mcps
      - model
      - reasoning
      - service_tier
  - type: table
    name: MCP Enabled
    filters: 'mcp_count > 0'
    order:
      - repo_name
      - mcps
      - model
      - reasoning
      - service_tier
  - type: table
    name: Skill Detail
    filters: 'skill_count > 0'
    order:
      - repo_name
      - plugin_count
      - plugins
      - skill_count
      - repo_local_skill_count
      - global_skills
      - repo_skills
      - repo_local_skills
      - mcps
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
            f"plugin_count: {len(item['plugins'])}",
            f"skill_count: {len(item['skills'])}",
            f"repo_local_skill_count: {len(item['repo_local_skills'])}",
            f"model: {_yaml_str(_effective_value(defaults, item, 'model'))}",
            f"reasoning: {_yaml_str(_effective_value(defaults, item, 'model_reasoning_effort'))}",
            f"service_tier: {_yaml_str(_effective_value(defaults, item, 'service_tier'))}",
        ]
        _append_yaml_list(lines, "mcps", item["mcp_presets"])
        _append_yaml_list(lines, "global_plugins", item["global_plugins"])
        _append_yaml_list(lines, "repo_plugins", item["repo_scoped_plugins"])
        _append_yaml_list(lines, "plugins", item["plugins"])
        _append_yaml_list(lines, "global_skills", item["global_skills"])
        _append_yaml_list(lines, "repo_skills", item["repo_scoped_skills"])
        _append_yaml_list(lines, "repo_local_skills", item["repo_local_skills"])
        _append_yaml_list(lines, "skills", item["skills"])
        lines.extend(
            [
                "---",
                "",
                "Generated from `codex/config/repo-bootstrap.json`, `plugins/registry.json`, and `skills/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / file_name, "\n".join(lines))


def _mcp_transport(preset: dict[str, Any]) -> str:
    transport = preset.get("transport")
    if isinstance(transport, str):
        return transport
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


def _repo_local_skill_source(repo_root: Path, skill: str) -> Path:
    return repo_root / ".agents" / "skills" / skill / "SKILL.md"


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

    managed_skill_groups = [
        data.get("managed_skills", []),
        data.get("managed_plugin_skills", []),
    ]
    for group in managed_skill_groups:
        if not isinstance(group, list):
            continue
        for raw_item in group:
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
        if repo_root in repo_local and _repo_local_skill_source(repo_root, skill).is_file():
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


def _load_plugin_assignments(
    root_dir: Path, home: Path, repos: list[dict[str, Any]], registry_file: Path
) -> None:
    if not registry_file.is_file():
        for item in repos:
            item["global_plugins"] = []
            item["repo_scoped_plugins"] = []
            item["plugins"] = []
        return

    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from plugins.derived import resolve_repo_root, validate_plugin_registry

    data = json.loads(registry_file.read_text(encoding="utf-8"))
    managed_plugins, _unmanaged_plugins, github_root = validate_plugin_registry(
        data,
        root_dir=root_dir,
        home=home,
    )
    repo_by_root = {item["repo_root"]: item for item in repos}
    repo_scoped: dict[Path, set[str]] = {item["repo_root"]: set() for item in repos}
    global_plugins = sorted(
        plugin.plugin_id
        for plugin in managed_plugins
        if plugin.enabled and plugin.scope == "global"
    )

    for plugin in managed_plugins:
        if not plugin.enabled or plugin.scope != "repo":
            continue
        for repo_ref in plugin.repos:
            repo_root = _resolve_repo_root(resolve_repo_root(repo_ref, github_root, home))
            if repo_root in repo_scoped:
                repo_scoped[repo_root].add(plugin.plugin_id)

    for repo_root, item in repo_by_root.items():
        repo_scoped_list = sorted(repo_scoped.get(repo_root, set()))
        plugins = sorted(set(global_plugins) | set(repo_scoped_list))
        item["global_plugins"] = global_plugins
        item["repo_scoped_plugins"] = repo_scoped_list
        item["plugins"] = plugins


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
      - repos
      - transport
      - target
  - type: table
    name: Global MCPs
    filters: 'global_terminal == "true"'
    order:
      - mcp_name
      - formula.scope_badge
      - global_terminal
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
        lines = [
            "---",
            f"mcp_name: {_yaml_str(preset_name)}",
            f"effective_scope: {_yaml_str(_effective_scope(global_terminal, repos_for_preset))}",
            f"global_terminal: {_yaml_str(str(global_terminal).lower())}",
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
                "Generated from `codex/config/repo-bootstrap.json` and `mcp/config/presets.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(root / f"{_sanitize_file_name(preset_name)}.md", "\n".join(lines))


def cleanup_generated_agent_views(views_dir: Path) -> None:
    cleanup_generated_agent_views(views_dir)


def validate_mcp_registry(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        raise ValueError("MCP registry presets must be an object")
    plugin_presets = data.get("plugin_presets", {})
    if not isinstance(plugin_presets, dict):
        raise ValueError("MCP registry plugin_presets must be an object")

    global_presets = data.get("global_presets", [])
    if not isinstance(global_presets, list):
        raise ValueError("MCP registry global_presets must be an array")
    plugin_global_presets = data.get("plugin_global_presets", [])
    if not isinstance(plugin_global_presets, list):
        raise ValueError("MCP registry plugin_global_presets must be an array")

    validated_presets: dict[str, Any] = {}
    for group_name, preset_group in (
        ("presets", presets),
        ("plugin_presets", plugin_presets),
    ):
        for name, preset in preset_group.items():
            if not isinstance(preset, dict):
                raise ValueError(f"MCP preset `{name}` must be an object")
            transport = preset.get("transport")
            if transport not in {"http", "stdio"}:
                raise ValueError(f"MCP preset `{name}` must define transport `http` or `stdio`")
            if transport == "http":
                url = preset.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise ValueError(f"MCP preset `{name}` with transport http must define a non-empty url")
            if transport == "stdio":
                command = preset.get("command")
                if not isinstance(command, str) or not command.strip():
                    raise ValueError(f"MCP preset `{name}` with transport stdio must define a non-empty command")
            if "args" in preset and not isinstance(preset["args"], list):
                raise ValueError(f"MCP preset `{name}` args must be an array")
            if "env" in preset and not isinstance(preset["env"], dict):
                raise ValueError(f"MCP preset `{name}` env must be an object")
            if name in validated_presets and validated_presets[name] != preset:
                raise ValueError(f"{group_name} conflicts with existing MCP preset `{name}`")
            validated_presets[str(name)] = preset

    combined_global_presets = [str(name) for name in global_presets] + [
        str(name) for name in plugin_global_presets
    ]
    for name in combined_global_presets:
        if name not in validated_presets:
            raise ValueError(f"global_presets references unknown MCP preset `{name}`")

    return validated_presets, combined_global_presets


def validate_registry(
    data: dict[str, Any], config_dir: Path, home: Path, mcp_presets_map: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object")

    for key in defaults:
        if key not in ALLOWED_SCALAR_KEYS and key not in ALLOWED_DEFAULT_TABLE_KEYS:
            raise ValueError(f"unsupported default key: {key}")
    if "features" in defaults and not isinstance(defaults["features"], dict):
        raise ValueError("defaults.features must be an object")

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

        repo_root = (
            _resolve_repo_root(repo_path)
            if (repo_path / ".git").exists()
            else repo_path.resolve()
        )

        repo_mcp_presets = item.get("mcp_presets", [])
        if not isinstance(repo_mcp_presets, list):
            raise ValueError(f"repos[{idx}].mcp_presets must be an array")
        plugin_repo_mcp_presets = item.get("plugin_mcp_presets", [])
        if not isinstance(plugin_repo_mcp_presets, list):
            raise ValueError(f"repos[{idx}].plugin_mcp_presets must be an array")
        combined_repo_mcp_presets = [
            str(name) for name in repo_mcp_presets if str(name).strip()
        ]
        for name in plugin_repo_mcp_presets:
            name_str = str(name).strip()
            if name_str and name_str not in combined_repo_mcp_presets:
                combined_repo_mcp_presets.append(name_str)
        for preset_name in combined_repo_mcp_presets:
            if preset_name not in mcp_presets_map:
                raise ValueError(
                    f"repos[{idx}] references unknown MCP preset: {preset_name}"
                )

        validated = {
            "path": _display_path(repo_root, home),
            "repo_name": _repo_name(str(repo_root)),
            "repo_root": repo_root,
            "mcp_presets": combined_repo_mcp_presets,
            "mcp_presets_csv": ",".join(combined_repo_mcp_presets)
            if combined_repo_mcp_presets
            else "-",
        }
        for key in ALLOWED_SCALAR_KEYS:
            if key in item:
                validated[key] = item[key]
        if "features" in item:
            if not isinstance(item["features"], dict):
                raise ValueError(f"repos[{idx}].features must be an object")
            validated["features"] = item["features"]
        repos.append(validated)

    repos.sort(key=lambda item: item["path"])
    return defaults, repos


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
    parser.add_argument(
        "--mcp-registry",
        default=str(Path.home() / ".agents" / "mcp" / "config" / "presets.json"),
        help="Path to shared MCP registry JSON file.",
    )
    parser.add_argument(
        "--plugin-registry",
        default=None,
        help="Path to native Codex plugin registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1
    mcp_registry_file = Path(args.mcp_registry).expanduser().resolve()
    if not mcp_registry_file.is_file():
        print(f"MCP registry not found: {mcp_registry_file}", file=sys.stderr)
        return 1
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {registry_file}: {exc}", file=sys.stderr)
        return 1
    try:
        mcp_data = json.loads(mcp_registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {mcp_registry_file}: {exc}", file=sys.stderr)
        return 1

    config_dir = registry_file.parent
    root_dir = config_dir.parent.parent
    plugin_registry_file = (
        Path(args.plugin_registry).expanduser().resolve()
        if args.plugin_registry
        else (root_dir / "plugins" / "registry.json").resolve()
    )
    if not plugin_registry_file.is_file():
        print(f"Plugin registry not found: {plugin_registry_file}", file=sys.stderr)
        return 1
    home = Path.home()
    try:
        presets, global_presets = validate_mcp_registry(mcp_data)
        defaults, repos = validate_registry(data, config_dir, home, presets)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    views_dir = generated_views_dir(root_dir)
    _load_plugin_assignments(root_dir, home, repos, plugin_registry_file)
    _load_skill_assignments(root_dir, home, repos)
    generate_registry_base(views_dir)
    generate_registry_items(views_dir, defaults, repos)
    global_terminal_mcp = set(global_presets)
    generate_mcp_registry_base(views_dir)
    generate_mcp_registry_items(
        views_dir, presets, repos, global_terminal_mcp
    )
    legacy_agent_capabilities_base = views_dir / "agent-capabilities.base"
    if legacy_agent_capabilities_base.exists():
        legacy_agent_capabilities_base.unlink()
    shutil.rmtree(views_dir / "agent-capabilities-items", ignore_errors=True)
    print(f"Generated repo bootstrap Base artifacts in {views_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
