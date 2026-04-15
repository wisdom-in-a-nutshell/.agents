#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from plugins.derived import (
    ManagedPlugin,
    derive_plugin_mcp_state,
    derive_plugin_skill_entries,
    expand_path,
    resolve_repo_token,
    validate_plugin_registry,
)


def _yaml_str(value: str) -> str:
    return json.dumps(value)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != content:
        path.write_text(content, encoding="utf-8")


def _write_json_if_changed(path: Path, data: dict[str, Any]) -> None:
    content = json.dumps(data, indent=2) + "\n"
    _write_if_changed(path, content)


def generated_views_dir(root_dir: Path) -> Path:
    return root_dir / "docs" / "references" / "registry"


def generate_registry_base(views_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("docs/references/registry/plugins-items")'
formulas:
  scope_badge: 'if(scope == "global", "🌍 global", if(scope == "repo", "📦 repo", scope))'
  mcp_scope_badge: 'if(mcp_scope == "global", "🌍 global", if(mcp_scope == "repo", "📦 repo", mcp_scope))'
  origin_badge: 'if(origin == "external", "↗ external", if(origin == "owned", "✳ owned", origin))'
properties:
  registry_kind:
    displayName: Type
  plugin:
    displayName: Plugin
  origin:
    displayName: Origin
  formula.origin_badge:
    displayName: Origin
  scope:
    displayName: Skill Scope
  formula.scope_badge:
    displayName: Skill Scope
  mcp_scope:
    displayName: MCP Scope
  formula.mcp_scope_badge:
    displayName: MCP Scope
  extract_skills:
    displayName: Extract Skills
  extract_mcp:
    displayName: Extract MCP
  category:
    displayName: Category
  repos:
    displayName: Skill Repos
  repos_csv:
    displayName: Skill Repos CSV
  mcp_repos:
    displayName: MCP Repos
  mcp_repos_csv:
    displayName: MCP Repos CSV
  source_path:
    displayName: Source Path
  upstream_ref:
    displayName: Upstream
  repo:
    displayName: Repo
views:
  - type: table
    name: Managed Plugins
    filters: 'registry_kind == "managed"'
    order:
      - plugin
      - formula.origin_badge
      - formula.scope_badge
      - formula.mcp_scope_badge
      - extract_skills
      - extract_mcp
      - repos
      - mcp_repos
      - upstream_ref
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
        repos_csv = ",".join(item.repos) if item.repos else "*"
        mcp_repos_csv = ",".join(item.mcp_repos) if item.mcp_repos else "*"
        lines = [
            "---",
            "registry_kind: managed",
            f"plugin: {_yaml_str(item.plugin)}",
            f"origin: {_yaml_str(item.origin)}",
            f"scope: {_yaml_str(item.scope)}",
            f"mcp_scope: {_yaml_str(item.mcp_scope)}",
            f"extract_skills: {'true' if item.extract_skills else 'false'}",
            f"extract_mcp: {'true' if item.extract_mcp else 'false'}",
            f"category: {_yaml_str(item.category)}",
            f"repos_csv: {_yaml_str(repos_csv)}",
            "repos:",
        ]
        if item.repos:
            lines.extend([f"  - {_yaml_str(repo)}" for repo in item.repos])
        else:
            lines.append('  - "*"')
        lines.extend(
            [
                f"mcp_repos_csv: {_yaml_str(mcp_repos_csv)}",
                "mcp_repos:",
            ]
        )
        if item.mcp_repos:
            lines.extend([f"  - {_yaml_str(repo)}" for repo in item.mcp_repos])
        else:
            lines.append('  - "*"')
        lines.extend(
            [
                f"source_path: {_yaml_str(item.source_path)}",
                f"upstream_ref: {_yaml_str(item.upstream_ref)}",
                "---",
                "",
                "Generated from `plugins/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(
            managed_dir / f"{_sanitize_file_name(item.plugin)}.md",
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


def update_skills_registry(root_dir: Path, plugin_skills: list[dict[str, Any]]) -> None:
    registry_path = root_dir / "skills" / "registry.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    managed = data.get("managed_skills", [])
    if not isinstance(managed, list):
        raise ValueError("managed_skills must be an array in skills/registry.json")

    seen: set[tuple[str, str]] = set()
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_skills[{idx}] must be an object in skills/registry.json")
        skill = str(item.get("skill", "")).strip()
        scope = str(item.get("scope", "")).strip()
        if skill and scope:
            seen.add((skill, scope))

    for item in plugin_skills:
        key = (str(item["skill"]), str(item["scope"]))
        if key in seen:
            raise ValueError(
                f"plugin-derived skill conflicts with managed_skills entry: {key[0]}/{key[1]}"
            )
        seen.add(key)

    data["managed_plugin_skills"] = sorted(
        plugin_skills,
        key=lambda item: (str(item["skill"]), str(item["scope"]), str(item["source_plugin"])),
    )
    _write_json_if_changed(registry_path, data)


def update_mcp_registry(
    root_dir: Path,
    plugin_presets: dict[str, dict[str, Any]],
    plugin_global_presets: list[str],
) -> None:
    registry_path = root_dir / "mcp" / "config" / "presets.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        raise ValueError("presets must be an object in mcp/config/presets.json")

    conflicting = sorted(set(presets).intersection(plugin_presets))
    if conflicting:
        raise ValueError(
            "plugin-derived MCP preset name conflicts with canonical preset(s): "
            + ", ".join(conflicting)
        )

    data["plugin_presets"] = dict(sorted(plugin_presets.items()))
    data["plugin_global_presets"] = list(plugin_global_presets)
    _write_json_if_changed(registry_path, data)


def canonical_mcp_preset_names(root_dir: Path) -> set[str]:
    registry_path = root_dir / "mcp" / "config" / "presets.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    presets = data.get("presets", {})
    if not isinstance(presets, dict):
        raise ValueError("presets must be an object in mcp/config/presets.json")
    return {str(name) for name in presets.keys()}


def update_repo_bootstrap(
    root_dir: Path,
    plugin_repo_assignments: dict[str, list[str]],
    *,
    github_root: Path,
    home: Path,
) -> None:
    registry_path = root_dir / "codex" / "config" / "repo-bootstrap.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        raise ValueError("repos must be an array in codex/config/repo-bootstrap.json")

    remaining = {token: list(values) for token, values in plugin_repo_assignments.items()}

    for idx, item in enumerate(repos):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{idx}] must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"repos[{idx}].path must be a non-empty string")
        repo_path = expand_path(raw_path.strip(), home).resolve()

        matched_tokens: list[str] = []
        preset_names: list[str] = []
        for token, names in list(remaining.items()):
            if resolve_repo_token(token, github_root, home) != repo_path:
                continue
            matched_tokens.append(token)
            for name in names:
                if name not in preset_names:
                    preset_names.append(name)

        if preset_names:
            item["plugin_mcp_presets"] = preset_names
        else:
            item.pop("plugin_mcp_presets", None)

        for token in matched_tokens:
            remaining.pop(token, None)

    if remaining:
        unresolved = ", ".join(sorted(remaining))
        raise ValueError(
            "plugin MCP repo targets are not present in codex/config/repo-bootstrap.json: "
            + unresolved
        )

    _write_json_if_changed(registry_path, data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the canonical plugin source registry, regenerate the "
            "Obsidian views, and refresh generated plugin-derived skills/MCP state."
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
        plugin_skills = derive_plugin_skill_entries(managed, root_dir=root_dir)
        reserved_mcp_names = canonical_mcp_preset_names(root_dir)
        plugin_presets, plugin_global_presets, plugin_repo_assignments = derive_plugin_mcp_state(
            managed,
            reserved_names=reserved_mcp_names,
        )
        update_skills_registry(root_dir, plugin_skills)
        update_mcp_registry(root_dir, plugin_presets, plugin_global_presets)
        update_repo_bootstrap(
            root_dir,
            plugin_repo_assignments,
            github_root=github_root,
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

    print("Registry sync complete. Plugin-derived skills and MCP state were refreshed.")
    print(f"GitHub root: {github_root}")
    print(f"Managed plugins: {len(managed)}")
    print(f"Derived skills: {len(plugin_skills)}")
    print(f"Derived MCP presets: {len(plugin_presets)}")
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
