from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from .common import (
    ControlPlaneError,
    RenderAction,
    git_repo_root,
    install_rendered_file,
    main_guard,
    normalize_path,
    remove_managed_file,
    remove_managed_symlink,
    repo_root,
    show_diff,
    sync_relative_symlink,
)
from hooks.control_plane import HookRegistryError, load_hooks_registry, merge_claude_hooks


def deep_merge(base: Any, override: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = {key: value for key, value in base.items()}
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def should_skip_walk_dir(path: Path, repo_root_path: Path) -> bool:
    if path == repo_root_path:
        return False
    skipped = {
        ".git",
        ".tmp",
        ".claude",
        ".codex",
        ".build",
        "node_modules",
        "dist",
        "build",
        "tmp",
        "temp",
        "DerivedData",
        "SourcePackages",
        ".next",
        ".turbo",
        "coverage",
        "tmp",
        ".tmp",
        "__pycache__",
        ".venv",
        "venv",
    }
    return any(part in skipped for part in path.parts)


def discover_agents_files(repo_root_path: Path) -> list[Path]:
    discovered: list[Path] = []
    stack = [repo_root_path]
    while stack:
        current = stack.pop()
        if should_skip_walk_dir(current, repo_root_path):
            continue
        for child in sorted(current.iterdir(), key=lambda path: path.name):
            if child.is_dir():
                stack.append(child)
                continue
            if child.name == "AGENTS.md":
                discovered.append(child)
    return sorted(discovered)


def render_import_claude_md(*imports: str) -> str:
    lines = []
    for import_path in imports:
        if not isinstance(import_path, str) or not import_path.strip():
            raise ControlPlaneError("CLAUDE.md imports must be non-empty strings")
        lines.append(f"@{import_path}")
    return "\n".join(lines) + "\n"


def render_claude_mcp_server(name: str, preset: dict[str, Any]) -> dict[str, Any]:
    config = dict(preset)
    transport = config.pop("transport", config.pop("type", None))
    if transport not in {"http", "stdio"}:
        raise ControlPlaneError(f"MCP preset `{name}` must declare transport `http` or `stdio`")
    if transport == "http" and not isinstance(config.get("url"), str):
        raise ControlPlaneError(f"MCP preset `{name}` must define a string url")
    if transport == "stdio" and not isinstance(config.get("command"), str):
        raise ControlPlaneError(f"MCP preset `{name}` must define a string command")
    config["type"] = transport
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render managed repo-local Claude config files from the shared repo registry plus Claude-specific bootstrap defaults."
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes in place")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show diffs only (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--registry",
        default=str(repo_root() / "codex" / "config" / "repo-bootstrap.json"),
        help="Override shared repo bootstrap registry",
    )
    parser.add_argument(
        "--bootstrap",
        default=str(repo_root() / "claude" / "config" / "bootstrap.json"),
        help="Override Claude bootstrap defaults/overrides",
    )
    parser.add_argument(
        "--mcp-registry",
        default=str(repo_root() / "mcp" / "config" / "presets.json"),
        help="Override shared MCP registry",
    )
    parser.add_argument(
        "--hooks-registry",
        default=str(repo_root() / "hooks" / "registry.json"),
        help="Override shared hooks registry",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Limit sync to an exact repo path (repeatable)",
    )
    return parser.parse_args()


def build_actions(
    *,
    repo_registry_path: Path,
    bootstrap_path: Path,
    mcp_registry_path: Path,
    hooks_registry_path: Path,
    repo_filters: list[str],
    temp_dir: Path,
) -> list[RenderAction]:
    repo_data = json.loads(repo_registry_path.read_text(encoding="utf-8"))
    bootstrap_data = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    mcp_data = json.loads(mcp_registry_path.read_text(encoding="utf-8"))
    try:
        hooks_data = load_hooks_registry(hooks_registry_path)
    except HookRegistryError as exc:
        raise ControlPlaneError(str(exc)) from exc

    repos_raw = repo_data.get("repos", [])
    if not isinstance(repos_raw, list):
        raise ControlPlaneError("repos must be an array")

    bootstrap_defaults = bootstrap_data.get("defaults", {})
    if bootstrap_defaults is None:
        bootstrap_defaults = {}
    if not isinstance(bootstrap_defaults, dict):
        raise ControlPlaneError("defaults must be an object in Claude bootstrap config")

    bootstrap_repo_overrides = bootstrap_data.get("repo_overrides", {})
    if bootstrap_repo_overrides is None:
        bootstrap_repo_overrides = {}
    if not isinstance(bootstrap_repo_overrides, dict):
        raise ControlPlaneError(
            "repo_overrides must be an object in Claude bootstrap config"
        )

    override_map: dict[str, dict[str, Any]] = {}
    for raw_path, override in bootstrap_repo_overrides.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ControlPlaneError("repo_overrides keys must be non-empty strings")
        if override is None:
            override = {}
        if not isinstance(override, dict):
            raise ControlPlaneError(f"repo_overrides.{raw_path} must be an object")
        override_map[normalize_path(raw_path)] = override

    mcp_presets = mcp_data.get("presets", {})
    plugin_mcp_presets = mcp_data.get("plugin_presets", {})
    if not isinstance(mcp_presets, dict):
        raise ControlPlaneError("presets must be an object in shared MCP registry")
    if not isinstance(plugin_mcp_presets, dict):
        raise ControlPlaneError("plugin_presets must be an object in shared MCP registry")
    merged_mcp_presets = dict(mcp_presets)
    for name, preset in plugin_mcp_presets.items():
        if name in merged_mcp_presets and merged_mcp_presets[name] != preset:
            raise ControlPlaneError(
                f"plugin_presets conflicts with existing preset `{name}` in shared MCP registry"
            )
        merged_mcp_presets[str(name)] = preset

    default_settings = bootstrap_defaults.get("settings", {})
    if default_settings is None:
        default_settings = {}
    if not isinstance(default_settings, dict):
        raise ControlPlaneError("defaults.settings must be an object in Claude bootstrap config")

    filters = {normalize_path(path) for path in repo_filters if path}
    actions: list[RenderAction] = []

    for item in repos_raw:
        if not isinstance(item, dict):
            raise ControlPlaneError("each repo entry must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ControlPlaneError("repo.path must be a non-empty string")

        declared_repo_path = Path(normalize_path(raw_path))
        if filters and str(declared_repo_path) not in filters:
            continue
        actual_repo_path = git_repo_root(declared_repo_path)
        if actual_repo_path is None:
            if declared_repo_path.exists():
                print(
                    f"WARNING: skipping existing non-git path: {declared_repo_path}",
                    file=sys.stderr,
                )
            continue

        actual_repo = str(actual_repo_path)
        repo_name = actual_repo_path.name or actual_repo
        if filters and actual_repo not in filters:
            continue

        repo_override: dict[str, Any] = {}
        for key in (str(declared_repo_path), actual_repo):
            override = override_map.get(key)
            if override:
                repo_override = deep_merge(repo_override, override)

        repo_settings = repo_override.get("settings", {})
        if repo_settings is None:
            repo_settings = {}
        if not isinstance(repo_settings, dict):
            raise ControlPlaneError(f"settings for {actual_repo} must be an object")
        rendered_settings = deep_merge(default_settings, repo_settings)
        if not isinstance(rendered_settings, dict):
            raise ControlPlaneError(f"merged settings for {actual_repo} must be an object")
        try:
            rendered_settings = merge_claude_hooks(
                rendered_settings,
                hooks_data,
                repo_name=repo_name,
            )
        except HookRegistryError as exc:
            raise ControlPlaneError(str(exc)) from exc

        settings_path = temp_dir / (
            f"{hashlib.sha256((actual_repo + ':settings').encode()).hexdigest()}.json"
        )
        settings_path.write_text(render_json(rendered_settings), encoding="utf-8")
        actions.append(
            RenderAction(
                scope=actual_repo,
                kind="FILE",
                target=Path(actual_repo) / ".claude" / "settings.json",
                data=settings_path,
            )
        )

        preset_names = item.get("mcp_presets", [])
        if preset_names is None:
            preset_names = []
        if not isinstance(preset_names, list):
            raise ControlPlaneError(f"mcp_presets for {actual_repo} must be an array")
        plugin_preset_names = item.get("plugin_mcp_presets", [])
        if plugin_preset_names is None:
            plugin_preset_names = []
        if not isinstance(plugin_preset_names, list):
            raise ControlPlaneError(
                f"plugin_mcp_presets for {actual_repo} must be an array"
            )
        effective_preset_names: list[str] = []
        for raw_name in [*preset_names, *plugin_preset_names]:
            name = str(raw_name).strip()
            if not name or name in effective_preset_names:
                continue
            effective_preset_names.append(name)

        repo_mcp_servers = repo_override.get("mcp_servers", {})
        if repo_mcp_servers is None:
            repo_mcp_servers = {}
        if not isinstance(repo_mcp_servers, dict):
            raise ControlPlaneError(
                f"repo_overrides.mcp_servers for {actual_repo} must be an object"
            )

        mcp_servers: dict[str, dict[str, Any]] = {}
        for preset_name in effective_preset_names:
            if preset_name not in merged_mcp_presets:
                raise ControlPlaneError(f"Unknown MCP preset `{preset_name}` for {actual_repo}")
            preset = merged_mcp_presets[preset_name]
            if not isinstance(preset, dict):
                raise ControlPlaneError(f"MCP preset `{preset_name}` must be an object")
            mcp_servers[preset_name] = render_claude_mcp_server(preset_name, preset)
        for server_name, config in repo_mcp_servers.items():
            if not isinstance(config, dict):
                raise ControlPlaneError(
                    f"repo_overrides.mcp_servers.{server_name} for {actual_repo} must be an object"
                )
            mcp_servers[server_name] = config

        mcp_path = temp_dir / f"{hashlib.sha256((actual_repo + ':mcp').encode()).hexdigest()}.json"
        mcp_path.write_text(render_json({"mcpServers": mcp_servers}), encoding="utf-8")
        actions.append(
            RenderAction(
                scope=actual_repo,
                kind="FILE",
                target=Path(actual_repo) / ".mcp.json",
                data=mcp_path,
            )
        )

        repo_root_path = Path(actual_repo)
        sync_nested = repo_override.get(
            "sync_nested_claude_md_to_agents_md",
            bootstrap_defaults.get("sync_nested_claude_md_to_agents_md", False),
        )
        if not isinstance(sync_nested, bool):
            raise ControlPlaneError(
                f"sync_nested_claude_md_to_agents_md for {actual_repo} must be a boolean"
            )

        root_agents_md_path = repo_root_path / "AGENTS.md"
        claude_md_path = repo_root_path / "CLAUDE.md"
        if not root_agents_md_path.is_file():
            print(
                f"WARNING: skipping root CLAUDE.md for {actual_repo}; missing AGENTS.md",
                file=sys.stderr,
            )
        else:
            root_claude_path = temp_dir / (
                f"{hashlib.sha256((actual_repo + ':root-claude').encode()).hexdigest()}.md"
            )
            root_claude_path.write_text(render_import_claude_md("AGENTS.md"), encoding="utf-8")
            actions.append(
                RenderAction(
                    scope=actual_repo,
                    kind="FILE",
                    target=claude_md_path,
                    data=root_claude_path,
                )
            )

        nested_agents_files = discover_agents_files(repo_root_path) if sync_nested else []
        for agents_md_path in nested_agents_files:
            if agents_md_path == root_agents_md_path:
                continue
            nested_claude_md = agents_md_path.parent / "CLAUDE.md"
            nested_claude_path = temp_dir / (
                f"{hashlib.sha256((actual_repo + ':nested-claude:' + str(nested_claude_md)).encode()).hexdigest()}.md"
            )
            nested_claude_path.write_text(
                render_import_claude_md("AGENTS.md"),
                encoding="utf-8",
            )
            actions.append(
                RenderAction(
                    scope=actual_repo,
                    kind="FILE",
                    target=nested_claude_md,
                    data=nested_claude_path,
                )
            )

    return actions


def main() -> int:
    args = parse_args()
    repo_registry_path = Path(args.registry).expanduser().resolve()
    bootstrap_path = Path(args.bootstrap).expanduser().resolve()
    mcp_registry_path = Path(args.mcp_registry).expanduser().resolve()
    hooks_registry_path = Path(args.hooks_registry).expanduser().resolve()

    if not repo_registry_path.is_file():
        raise ControlPlaneError(f"Missing repo registry file: {repo_registry_path}")
    if not bootstrap_path.is_file():
        raise ControlPlaneError(f"Missing Claude bootstrap file: {bootstrap_path}")
    if not mcp_registry_path.is_file():
        raise ControlPlaneError(f"Missing MCP registry file: {mcp_registry_path}")
    if not hooks_registry_path.is_file():
        raise ControlPlaneError(f"Missing hooks registry file: {hooks_registry_path}")

    with tempfile.TemporaryDirectory() as temp_dir_raw:
        actions = build_actions(
            repo_registry_path=repo_registry_path,
            bootstrap_path=bootstrap_path,
            mcp_registry_path=mcp_registry_path,
            hooks_registry_path=hooks_registry_path,
            repo_filters=args.repo,
            temp_dir=Path(temp_dir_raw),
        )
        if not actions:
            raise ControlPlaneError("No managed repo configs were rendered.")

        print(f"Rendered {len(actions)} managed Claude operations from {repo_registry_path}.")

        for action in actions:
            print("")
            print(f"=== Repo Claude Item ({action.scope}) ===")
            if action.kind == "FILE":
                assert isinstance(action.data, Path)
                show_diff(action.target, action.data)
                if args.apply:
                    install_rendered_file(action.data, action.target, log=print)
            elif action.kind == "LINK":
                assert isinstance(action.data, str)
                sync_relative_symlink(action.target, action.data, apply=args.apply, log=print)
            elif action.kind == "CLEAN_FILE":
                remove_managed_file(action.target, apply=args.apply, log=print)
            elif action.kind == "CLEAN_LINK":
                assert isinstance(action.data, str)
                remove_managed_symlink(action.target, action.data, apply=args.apply, log=print)
            else:
                raise ControlPlaneError(f"Unknown manifest kind: {action.kind}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
