#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_FILE = ROOT_DIR / "codex" / "config" / "repo-bootstrap.json"
DEFAULT_MCP_REGISTRY_FILE = ROOT_DIR / "mcp" / "config" / "presets.json"

try:
    import tomllib  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore  # noqa: F401


ALLOWED_SCALAR_KEYS = {
    "codex_trust",
    "model",
    "model_auto_compact_token_limit",
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


def validate_registry(
    data: dict[str, Any],
    home: Path,
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

        for key in item:
            if key == "path":
                continue
            if key not in ALLOWED_SCALAR_KEYS and key not in ALLOWED_DEFAULT_TABLE_KEYS:
                raise ValueError(f"repos[{idx}] unsupported key: {key}")
        if "codex_trust" in item and not isinstance(item["codex_trust"], bool):
            raise ValueError(f"repos[{idx}].codex_trust must be a boolean")
        if "features" in item and not isinstance(item["features"], dict):
            raise ValueError(f"repos[{idx}].features must be an object")

        repos.append(
            {
                "path": str(repo_root),
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
        default=str(DEFAULT_REGISTRY_FILE),
        help="Path to repo bootstrap registry JSON file.",
    )
    parser.add_argument(
        "--mcp-registry",
        default=str(DEFAULT_MCP_REGISTRY_FILE),
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
    from mcp.control_plane import load_mcp_catalog_data
    from plugins.derived import validate_plugin_registry

    home = Path.home()
    try:
        _defaults, repos = validate_registry(data, home)
        catalog = load_mcp_catalog_data(mcp_data, data.get("repos"))
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
    print(f"MCP presets: {len(catalog.definitions)}")
    print(f"MCP target rules: {sum(len(targets) for targets in catalog.targets.values())}")
    print(f"Managed plugins: {len(managed_plugins)}")
    print(f"Repo-local plugins: {len(unmanaged_plugins)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
