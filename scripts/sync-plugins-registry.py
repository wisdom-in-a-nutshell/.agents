#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from plugins.derived import (
    ManagedPlugin,
    validate_plugin_registry,
)


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


def generated_views_dir(root_dir: Path) -> Path:
    return root_dir / "docs" / "references" / "registry"


def generate_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/plugins-items")'
formulas:
  enabled_badge: 'if(enabled, "✅ enabled", "⏸ disabled")'
properties:
  registry_kind:
    displayName: Type
  plugin:
    displayName: Plugin
  plugin_id:
    displayName: Plugin ID
  marketplace:
    displayName: Marketplace
  enabled:
    displayName: Enabled
  formula.enabled_badge:
    displayName: State
  category:
    displayName: Category
  repo:
    displayName: Repo
views:
  - type: table
    name: Managed Plugins
    filters: 'registry_kind == "managed"'
    order:
      - plugin
      - plugin_id
      - marketplace
      - formula.enabled_badge
      - category
    sort:
      - property: plugin
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
    managed: list[ManagedPlugin],
    unmanaged: list[dict[str, str]],
) -> None:
    root = views_dir / "plugins-items"
    managed_dir = root / "managed"
    repo_local_dir = root / "repo-local"

    shutil.rmtree(managed_dir, ignore_errors=True)
    shutil.rmtree(repo_local_dir, ignore_errors=True)
    managed_dir.mkdir(parents=True, exist_ok=True)
    repo_local_dir.mkdir(parents=True, exist_ok=True)

    for item in managed:
        lines = [
            "---",
            "registry_kind: managed",
            f"plugin: {_yaml_str(item.plugin)}",
            f"plugin_id: {_yaml_str(item.plugin_id)}",
            f"marketplace: {_yaml_str(item.marketplace)}",
            f"enabled: {'true' if item.enabled else 'false'}",
            f"category: {_yaml_str(item.category)}",
        ]
        lines.extend(
            [
                "---",
                "",
                "Generated from `plugins/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(managed_dir / f"{_sanitize_file_name(item.plugin_id)}.md", "\n".join(lines))

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
            "Validate the canonical Codex plugin registry and regenerate "
            "the Obsidian registry views."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Accepted for consistency; generated artifacts are always written in-place.",
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
        managed, unmanaged, github_root = validate_plugin_registry(
            data,
            root_dir=root_dir,
            home=home,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Registry sync failed: {exc}", file=sys.stderr)
        return 1

    if not args.no_generate:
        views_dir = generated_views_dir(root_dir)
        generate_registry_base(views_dir)
        generate_registry_items(views_dir, managed, unmanaged)
        print(f"Generated registry Base artifacts in {views_dir}")

    print("Registry sync complete. Codex plugin views were refreshed.")
    print(f"GitHub root: {github_root}")
    print(f"Managed plugins: {len(managed)}")
    print(f"Enabled plugins: {sum(1 for item in managed if item.enabled)}")
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
