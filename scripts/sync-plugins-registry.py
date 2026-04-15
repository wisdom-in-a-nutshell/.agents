#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ALLOWED_SCOPES = {"global", "repo"}


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def ensure_str(value: Any, field: str, idx: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"managed_plugins[{idx}] invalid {field}: {value!r}")
    return value.strip()


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


def generated_views_dir(root_dir: Path) -> Path:
    return root_dir / "docs" / "references" / "registry"


def parse_plugin_id(plugin_id: str, idx: int) -> tuple[str, str]:
    if "@" not in plugin_id:
        raise ValueError(
            f"managed_plugins[{idx}] plugin_id must look like <plugin-name>@<marketplace>"
        )
    plugin_name, marketplace = plugin_id.rsplit("@", 1)
    plugin_name = plugin_name.strip()
    marketplace = marketplace.strip()
    if not plugin_name or not marketplace:
        raise ValueError(
            f"managed_plugins[{idx}] invalid plugin_id: {plugin_id!r}"
        )
    return plugin_name, marketplace


def validate_registry(
    data: dict[str, Any], home: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
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

    seen_plugin_ids: set[str] = set()
    validated_managed: list[dict[str, Any]] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")

        plugin_id = ensure_str(item.get("plugin_id"), "plugin_id", idx)
        plugin_name, marketplace = parse_plugin_id(plugin_id, idx)
        scope = ensure_str(item.get("scope"), "scope", idx)
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_plugins[{idx}] invalid scope: {scope}")
        if plugin_id in seen_plugin_ids:
            raise ValueError(f"duplicate managed plugin_id: {plugin_id}")
        seen_plugin_ids.add(plugin_id)

        repos_raw = item.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_plugins[{idx}] repos must be an array")
        repos = [str(repo).strip() for repo in repos_raw if str(repo).strip()]
        if scope == "repo" and not repos:
            raise ValueError(f"managed_plugins[{idx}] repo scope needs repos")
        if scope == "global":
            repos = []

        enabled_raw = item.get("enabled", True)
        if not isinstance(enabled_raw, bool):
            raise ValueError(f"managed_plugins[{idx}] enabled must be a boolean")

        category = str(item.get("category", "")).strip() or "Productivity"

        validated_managed.append(
            {
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "marketplace": marketplace,
                "scope": scope,
                "repos": repos,
                "enabled": enabled_raw,
                "category": category,
            }
        )

    validated_unmanaged: list[dict[str, Any]] = []
    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ValueError(f"unmanaged_repo_local_plugins[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", idx)
        plugin = ensure_str(item.get("plugin"), "plugin", idx)
        validated_unmanaged.append({"repo": repo, "plugin": plugin})

    return validated_managed, validated_unmanaged, github_root


def generate_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/plugins-items")'
formulas:
  scope_badge: 'if(scope == "global", "🌍 global", if(scope == "repo", "📦 repo", scope))'
  enabled_badge: 'if(enabled, "✅ enabled", "⛔ disabled")'
properties:
  registry_kind:
    displayName: Type
  plugin_id:
    displayName: Plugin Id
  plugin_name:
    displayName: Plugin
  marketplace:
    displayName: Marketplace
  scope:
    displayName: Scope
  formula.scope_badge:
    displayName: Scope
  enabled:
    displayName: Enabled
  formula.enabled_badge:
    displayName: Enabled
  category:
    displayName: Category
  repos:
    displayName: Repos
  repos_csv:
    displayName: Repos CSV
  repo:
    displayName: Repo
views:
  - type: table
    name: Managed Plugins
    filters: 'registry_kind == "managed"'
    order:
      - plugin_name
      - marketplace
      - formula.scope_badge
      - formula.enabled_badge
      - category
      - repos
    sort:
      - property: scope
        direction: ASC
      - property: plugin_name
        direction: ASC
  - type: table
    name: Repo-Local Plugins
    filters: 'registry_kind == "repo_local"'
    order:
      - repo
      - plugin
"""
    _write_if_changed(views_dir / "plugins.base", content)


def _sanitize_file_name(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-")


def generate_registry_items(
    views_dir: Path,
    managed: list[dict[str, Any]],
    unmanaged: list[dict[str, Any]],
) -> None:
    root = views_dir / "plugins-items"
    managed_dir = root / "managed"
    repo_local_dir = root / "repo-local"

    shutil.rmtree(managed_dir, ignore_errors=True)
    shutil.rmtree(repo_local_dir, ignore_errors=True)
    managed_dir.mkdir(parents=True, exist_ok=True)
    repo_local_dir.mkdir(parents=True, exist_ok=True)

    for item in managed:
        repos = item.get("repos", [])
        repos_csv = ",".join(repos) if repos else "*"
        lines = [
            "---",
            "registry_kind: managed",
            f"plugin_id: {_yaml_str(item['plugin_id'])}",
            f"plugin_name: {_yaml_str(item['plugin_name'])}",
            f"marketplace: {_yaml_str(item['marketplace'])}",
            f"scope: {_yaml_str(item['scope'])}",
            f"enabled: {'true' if item['enabled'] else 'false'}",
            f"category: {_yaml_str(item['category'])}",
            f"repos_csv: {_yaml_str(repos_csv)}",
            "repos:",
        ]
        if repos:
            lines.extend([f"  - {_yaml_str(repo)}" for repo in repos])
        else:
            lines.append('  - "*"')
        lines.extend(
            [
                "---",
                "",
                "Generated from `plugins/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(
            managed_dir / f"{_sanitize_file_name(item['plugin_id'])}.md",
            "\n".join(lines),
        )

    for item in unmanaged:
        file_name = (
            f"{_sanitize_file_name(item['repo'])}--"
            f"{_sanitize_file_name(item['plugin'])}.md"
        )
        lines = [
            "---",
            "registry_kind: repo_local",
            f"repo: {_yaml_str(item['repo'])}",
            f"plugin: {_yaml_str(item['plugin'])}",
            "---",
            "",
            "Generated from `plugins/registry.json`. Do not edit manually.",
            "",
        ]
        _write_if_changed(repo_local_dir / file_name, "\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical managed plugin registry and regenerate the "
            "Obsidian registry views."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Accepted for consistency; registry view generation is always written in-place.",
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip generating Obsidian registry view files.",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "plugins" / "registry.json"),
        help="Path to canonical plugin registry JSON file.",
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

    registry_dir = registry_file.parent
    root_dir = registry_dir.parent
    home = Path.home()

    try:
        managed, unmanaged, github_root = validate_registry(data, home)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    if not args.no_generate:
        views_dir = generated_views_dir(root_dir)
        generate_registry_base(views_dir)
        generate_registry_items(views_dir, managed, unmanaged)
        print(f"Generated registry Base artifacts in {views_dir}")

    print(
        "Registry sync complete. Codex plugin install/config state is applied by "
        "the Codex bootstrap, not by local marketplace rendering."
    )
    print(f"GitHub root: {github_root}")
    print(f"Managed plugins: {len(managed)}")
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
