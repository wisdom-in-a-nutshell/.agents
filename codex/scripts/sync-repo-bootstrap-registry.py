#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


try:
    import tomllib  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore  # noqa: F401


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
ALLOWED_DEFAULT_TABLE_KEYS = {"features"}


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


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
    data: dict[str, Any],
    home: Path,
    mcp_presets_map: dict[str, Any],
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

        for key in item:
            if key in {"path", "mcp_presets", "plugin_mcp_presets"}:
                continue
            if key not in ALLOWED_SCALAR_KEYS and key not in ALLOWED_DEFAULT_TABLE_KEYS:
                raise ValueError(f"repos[{idx}] unsupported key: {key}")
        if "features" in item and not isinstance(item["features"], dict):
            raise ValueError(f"repos[{idx}].features must be an object")

        repos.append(
            {
                "path": str(repo_root),
                "mcp_presets": combined_repo_mcp_presets,
            }
        )

    return defaults, repos


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Codex repo bootstrap registry and shared MCP assignments."
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

    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from plugins.derived import validate_plugin_registry

    home = Path.home()
    try:
        presets, global_presets = validate_mcp_registry(mcp_data)
        _defaults, repos = validate_registry(data, home, presets)
        plugin_data = json.loads(plugin_registry_file.read_text(encoding="utf-8"))
        managed_plugins, unmanaged_plugins, _github_root = validate_plugin_registry(
            plugin_data,
            root_dir=root_dir,
            home=home,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    print("Repo bootstrap registry validated.")
    print(f"Repos: {len(repos)}")
    print(f"MCP presets: {len(presets)}")
    print(f"Global MCP presets: {len(global_presets)}")
    print(f"Managed plugins: {len(managed_plugins)}")
    print(f"Repo-local plugins: {len(unmanaged_plugins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
