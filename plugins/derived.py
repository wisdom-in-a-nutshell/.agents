from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_ORIGINS = {"external", "owned"}
ALLOWED_SCOPES = {"global", "repo"}


@dataclass(frozen=True)
class ManagedPlugin:
    plugin: str
    origin: str
    scope: str
    repos: list[str]
    source_path: str
    source_abs: Path
    upstream_ref: str
    category: str
    extract_skills: bool
    extract_mcp: bool
    mcp_scope: str
    mcp_repos: list[str]


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def ensure_str(value: Any, field: str, idx: int, *, label: str = "managed_plugins") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}[{idx}] invalid {field}: {value!r}")
    return value.strip()


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def rel_to(base: Path, target: Path) -> str:
    return os.path.relpath(str(target), str(base))


def slug(value: str) -> str:
    safe: list[str] = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-")


def resolve_repo_token(token: str, github_root: Path, home: Path) -> Path:
    if token.startswith("~/") or token.startswith("/"):
        return expand_path(token, home).resolve()
    return (github_root / token).resolve()


def derived_mcp_preset_name(plugin_name: str, server_name: str) -> str:
    return f"plugin-{slug(plugin_name)}-{slug(server_name)}"


def validate_plugin_registry(
    data: dict[str, Any],
    *,
    root_dir: Path,
    home: Path,
) -> tuple[list[ManagedPlugin], list[dict[str, str]], Path]:
    managed = data.get("managed_plugins", [])
    if not isinstance(managed, list):
        raise ValueError("managed_plugins must be an array")

    unmanaged = data.get("unmanaged_repo_local_plugins", [])
    if not isinstance(unmanaged, list):
        raise ValueError("unmanaged_repo_local_plugins must be an array")

    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("paths must be an object")

    github_root_raw = str(paths.get("github_root", "~/GitHub")).strip()
    if not github_root_raw:
        raise ValueError("paths.github_root must be a non-empty string")
    github_root = expand_path(github_root_raw, home).resolve()

    seen_plugins: set[str] = set()
    validated_managed: list[ManagedPlugin] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")

        plugin = ensure_str(item.get("plugin"), "plugin", idx)
        origin = ensure_str(item.get("origin"), "origin", idx)
        scope = ensure_str(item.get("scope"), "scope", idx)
        source_path = ensure_str(item.get("source_path"), "source_path", idx)
        upstream_ref = str(item.get("upstream_ref", "-")).strip() or "-"
        category = str(item.get("category", "")).strip() or "Coding"

        if origin not in ALLOWED_ORIGINS:
            raise ValueError(f"managed_plugins[{idx}] invalid origin: {origin}")
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_plugins[{idx}] invalid scope: {scope}")
        if plugin in seen_plugins:
            raise ValueError(f"duplicate managed plugin: {plugin}")
        seen_plugins.add(plugin)

        repos_raw = item.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_plugins[{idx}] repos must be an array")
        repos = ordered_unique([str(repo) for repo in repos_raw])
        if scope == "repo" and not repos:
            raise ValueError(f"managed_plugins[{idx}] repo scope needs repos")
        if scope == "global":
            repos = []

        extract_skills = item.get("extract_skills", True)
        extract_mcp = item.get("extract_mcp", True)
        if not isinstance(extract_skills, bool):
            raise ValueError(f"managed_plugins[{idx}] extract_skills must be a boolean")
        if not isinstance(extract_mcp, bool):
            raise ValueError(f"managed_plugins[{idx}] extract_mcp must be a boolean")

        mcp_scope = str(item.get("mcp_scope", scope)).strip() or scope
        if mcp_scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_plugins[{idx}] invalid mcp_scope: {mcp_scope}")

        mcp_repos_raw = item.get("mcp_repos", repos)
        if not isinstance(mcp_repos_raw, list):
            raise ValueError(f"managed_plugins[{idx}] mcp_repos must be an array")
        mcp_repos = ordered_unique([str(repo) for repo in mcp_repos_raw])
        if mcp_scope == "repo" and extract_mcp and not mcp_repos:
            raise ValueError(f"managed_plugins[{idx}] repo mcp_scope needs mcp_repos")
        if mcp_scope == "global":
            mcp_repos = []

        src = Path(source_path)
        if not src.is_absolute():
            src = (root_dir / src).resolve()
        else:
            src = src.resolve()
        if not src.exists():
            raise ValueError(f"managed_plugins[{idx}] source_path does not exist: {src}")

        validated_managed.append(
            ManagedPlugin(
                plugin=plugin,
                origin=origin,
                scope=scope,
                repos=repos,
                source_path=source_path,
                source_abs=src,
                upstream_ref=upstream_ref,
                category=category,
                extract_skills=extract_skills,
                extract_mcp=extract_mcp,
                mcp_scope=mcp_scope,
                mcp_repos=mcp_repos,
            )
        )

    validated_unmanaged: list[dict[str, str]] = []
    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ValueError(f"unmanaged_repo_local_plugins[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", idx, label="unmanaged_repo_local_plugins")
        plugin = ensure_str(
            item.get("plugin"), "plugin", idx, label="unmanaged_repo_local_plugins"
        )
        validated_unmanaged.append({"repo": repo, "plugin": plugin})

    return validated_managed, validated_unmanaged, github_root


def derive_plugin_skill_entries(
    plugins: list[ManagedPlugin],
    *,
    root_dir: Path,
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    entries: list[dict[str, Any]] = []
    for plugin in plugins:
        if not plugin.extract_skills:
            continue
        skills_dir = plugin.source_abs / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir(), key=lambda path: path.name):
            if not skill_dir.is_dir():
                continue
            if not (skill_dir / "SKILL.md").is_file():
                continue
            skill = skill_dir.name
            key = (skill, plugin.scope)
            if key in seen:
                raise ValueError(
                    f"duplicate plugin-derived skill+scope entry: {skill}/{plugin.scope}"
                )
            seen.add(key)
            entries.append(
                {
                    "skill": skill,
                    "origin": plugin.origin,
                    "scope": plugin.scope,
                    "repos": list(plugin.repos),
                    "source_path": rel_to(root_dir, skill_dir.resolve()),
                    "upstream_ref": "-",
                    "source_plugin": plugin.plugin,
                }
            )
    return entries


def _normalize_plugin_mcp_server(
    plugin_name: str,
    server_name: str,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    normalized = dict(config)
    transport = normalized.pop("transport", normalized.pop("type", None))
    if transport is None:
        if isinstance(normalized.get("url"), str):
            transport = "http"
        elif isinstance(normalized.get("command"), str):
            transport = "stdio"
    if transport not in {"http", "stdio"}:
        raise ValueError(
            f"plugin `{plugin_name}` MCP server `{server_name}` must define transport, url, or command"
        )
    normalized["transport"] = transport
    if transport == "http":
        url = normalized.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(
                f"plugin `{plugin_name}` MCP server `{server_name}` must define a non-empty url"
            )
    if transport == "stdio":
        command = normalized.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(
                f"plugin `{plugin_name}` MCP server `{server_name}` must define a non-empty command"
            )
    if "args" in normalized and not isinstance(normalized["args"], list):
        raise ValueError(
            f"plugin `{plugin_name}` MCP server `{server_name}` args must be an array"
        )
    if "env" in normalized and not isinstance(normalized["env"], dict):
        raise ValueError(
            f"plugin `{plugin_name}` MCP server `{server_name}` env must be an object"
        )
    if "cwd" in normalized and not isinstance(normalized["cwd"], str):
        raise ValueError(
            f"plugin `{plugin_name}` MCP server `{server_name}` cwd must be a string"
        )
    return derived_mcp_preset_name(plugin_name, server_name), normalized


def derive_plugin_mcp_state(
    plugins: list[ManagedPlugin],
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, list[str]]]:
    presets: dict[str, dict[str, Any]] = {}
    global_presets: list[str] = []
    repo_assignments: dict[str, list[str]] = {}

    for plugin in plugins:
        if not plugin.extract_mcp:
            continue
        mcp_file = plugin.source_abs / ".mcp.json"
        if not mcp_file.is_file():
            continue
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"plugin `{plugin.plugin}` .mcp.json root must be an object")
        mcp_servers = data.get("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            raise ValueError(f"plugin `{plugin.plugin}` .mcp.json mcpServers must be an object")

        plugin_preset_names: list[str] = []
        for server_name, raw_config in sorted(mcp_servers.items()):
            if not isinstance(raw_config, dict):
                raise ValueError(
                    f"plugin `{plugin.plugin}` MCP server `{server_name}` must be an object"
                )
            preset_name, normalized = _normalize_plugin_mcp_server(
                plugin.plugin, str(server_name), raw_config
            )
            existing = presets.get(preset_name)
            if existing is not None and existing != normalized:
                raise ValueError(f"conflicting plugin-derived MCP preset name: {preset_name}")
            presets[preset_name] = normalized
            plugin_preset_names.append(preset_name)

        if plugin.mcp_scope == "global":
            for preset_name in plugin_preset_names:
                if preset_name not in global_presets:
                    global_presets.append(preset_name)
            continue

        for repo in plugin.mcp_repos:
            current = repo_assignments.setdefault(repo, [])
            for preset_name in plugin_preset_names:
                if preset_name not in current:
                    current.append(preset_name)

    return presets, global_presets, repo_assignments
