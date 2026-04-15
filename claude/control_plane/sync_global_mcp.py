from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

from .common import (
    ControlPlaneError,
    install_rendered_file,
    load_json_file,
    main_guard,
    render_json,
    repo_root,
    show_diff,
)


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
        description="Merge managed global Claude MCP servers into ~/.claude.json without overwriting unrelated runtime state."
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show diffs only (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--global-config",
        default=str(Path.home() / ".claude.json"),
        help="Override ~/.claude.json target",
    )
    parser.add_argument(
        "--mcp-registry",
        default=str(repo_root() / "mcp" / "config" / "presets.json"),
        help="Override shared MCP registry source",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global_config = Path(args.global_config).expanduser().resolve()
    mcp_registry_path = Path(args.mcp_registry).expanduser().resolve()

    if not Path(args.global_config).is_absolute():
        raise ControlPlaneError("--global-config must be an absolute path")
    if not Path(args.mcp_registry).is_absolute():
        raise ControlPlaneError("--mcp-registry must be an absolute path")
    if not mcp_registry_path.is_file():
        raise ControlPlaneError(f"Missing MCP registry file: {mcp_registry_path}")

    runtime = {}
    if global_config.exists():
        runtime = load_json_file(global_config, label="runtime Claude config")
        if not isinstance(runtime, dict):
            raise ControlPlaneError(f"runtime Claude config root must be an object: {global_config}")

    mcp_registry = load_json_file(mcp_registry_path, label="shared MCP registry")
    if not isinstance(mcp_registry, dict):
        raise ControlPlaneError(f"shared MCP registry root must be an object: {mcp_registry_path}")

    presets = mcp_registry.get("presets", {})
    plugin_presets = mcp_registry.get("plugin_presets", {})
    global_presets = mcp_registry.get("global_presets", [])
    plugin_global_presets = mcp_registry.get("plugin_global_presets", [])
    if not isinstance(presets, dict):
        raise ControlPlaneError(f"shared MCP presets must be an object: {mcp_registry_path}")
    if not isinstance(plugin_presets, dict):
        raise ControlPlaneError(f"shared MCP plugin_presets must be an object: {mcp_registry_path}")
    if global_presets is None:
        global_presets = []
    if not isinstance(global_presets, list):
        raise ControlPlaneError(f"global_presets must be an array: {mcp_registry_path}")
    if plugin_global_presets is None:
        plugin_global_presets = []
    if not isinstance(plugin_global_presets, list):
        raise ControlPlaneError(f"plugin_global_presets must be an array: {mcp_registry_path}")

    merged_presets = dict(presets)
    for name, preset in plugin_presets.items():
        if name in merged_presets and merged_presets[name] != preset:
            raise ControlPlaneError(
                f"plugin_presets conflicts with existing preset `{name}`: {mcp_registry_path}"
            )
        merged_presets[str(name)] = preset

    managed_servers: dict[str, dict[str, Any]] = {}
    for preset_name in [str(name) for name in global_presets] + [
        str(name) for name in plugin_global_presets
    ]:
        if preset_name not in merged_presets:
            raise ControlPlaneError(
                f"unknown global MCP preset `{preset_name}` in {mcp_registry_path}"
            )
        preset = merged_presets[preset_name]
        if not isinstance(preset, dict):
            raise ControlPlaneError(
                f"preset `{preset_name}` must be an object in {mcp_registry_path}"
            )
        managed_servers[str(preset_name)] = render_claude_mcp_server(str(preset_name), preset)

    runtime_servers = runtime.get("mcpServers", {})
    if runtime_servers is None:
        runtime_servers = {}
    if not isinstance(runtime_servers, dict):
        raise ControlPlaneError(f"runtime mcpServers must be an object: {global_config}")

    managed_names = {str(name) for name in merged_presets}
    active_global_names = set(managed_servers)
    merged = dict(runtime)
    merged_servers = {
        name: config
        for name, config in runtime_servers.items()
        if name not in managed_names or name in active_global_names
    }
    for name, config in managed_servers.items():
        merged_servers[name] = config
    merged["mcpServers"] = merged_servers

    with tempfile.TemporaryDirectory() as temp_dir:
        rendered_config = Path(temp_dir) / ".claude.json"
        rendered_config.write_text(render_json(merged, sort_keys=False), encoding="utf-8")

        print("=== Global Claude MCP ===")
        show_diff(global_config, rendered_config)

        if args.apply:
            install_rendered_file(rendered_config, global_config, log=print)

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
