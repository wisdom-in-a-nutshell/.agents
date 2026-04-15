#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


ALLOWED_ORIGINS = {"external", "owned"}
ALLOWED_SCOPES = {"global", "repo"}
ALLOWED_INSTALLATION_POLICIES = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
ALLOWED_AUTH_POLICIES = {"ON_INSTALL", "ON_USE"}


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def ensure_str(value: Any, field: str, idx: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"managed_plugins[{idx}] invalid {field}: {value!r}")
    return value.strip()


def rel_link(dst: Path, src: Path) -> str:
    return os.path.relpath(str(src), str(dst.parent))


def resolved_target(link_path: Path) -> Path:
    cur = os.readlink(link_path)
    if os.path.isabs(cur):
        return Path(cur).resolve()
    return (link_path.parent / cur).resolve()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_path(repo, home).resolve()
    return (github_root / repo).resolve()


def sync_link(dst: Path, src: Path, apply: bool) -> None:
    rel = rel_link(dst, src)
    if dst.is_symlink() and resolved_target(dst) == src.resolve():
        print(f"UNCHANGED {dst}")
        return

    print(f"SYNC {dst} -> {rel}")
    if not apply:
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    elif dst.exists():
        dst.unlink()
    dst.symlink_to(rel)


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
  scope_badge: 'if(scope == "global", "🌍 global", if(scope == "repo", "📦 repo", scope))'
  origin_badge: 'if(origin == "external", "↗ external", if(origin == "owned", "✳ owned", origin))'
properties:
  registry_kind:
    displayName: Type
  plugin:
    displayName: Plugin
  origin:
    displayName: Origin
  scope:
    displayName: Scope
  formula.scope_badge:
    displayName: Scope
  repos:
    displayName: Repos
  repos_csv:
    displayName: Repos CSV
  upstream_ref:
    displayName: Upstream
  formula.origin_badge:
    displayName: Origin
  repo:
    displayName: Repo
  source_path:
    displayName: Source Path
  category:
    displayName: Category
  installation_policy:
    displayName: Install Policy
  authentication_policy:
    displayName: Auth Policy
views:
  - type: table
    name: Managed Plugins
    filters: 'registry_kind == "managed"'
    order:
      - plugin
      - formula.origin_badge
      - formula.scope_badge
      - category
      - installation_policy
      - authentication_policy
      - repos
      - upstream_ref
    sort:
      - property: scope
        direction: ASC
      - property: origin
        direction: ASC
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
        policy = item["policy"]
        lines = [
            "---",
            "registry_kind: managed",
            f"plugin: {_yaml_str(item['plugin'])}",
            f"origin: {_yaml_str(item['origin'])}",
            f"scope: {_yaml_str(item['scope'])}",
            f"category: {_yaml_str(item['category'])}",
            f"installation_policy: {_yaml_str(policy['installation'])}",
            f"authentication_policy: {_yaml_str(policy['authentication'])}",
            f"repos_csv: {_yaml_str(repos_csv)}",
            f"source_path: {_yaml_str(item['source_path'])}",
            f"upstream_ref: {_yaml_str(item.get('upstream_ref', '-'))}",
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
            managed_dir / f"{_sanitize_file_name(item['plugin'])}.md",
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


def _load_plugin_manifest(plugin_root: Path) -> dict[str, Any]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise ValueError(f"source missing .codex-plugin/plugin.json: {plugin_root}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid plugin manifest JSON at {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"plugin manifest root must be an object: {manifest_path}")
    return manifest


def _normalize_policy(raw: Any, idx: int) -> dict[str, str]:
    if raw is None:
        return {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        }
    if not isinstance(raw, dict):
        raise ValueError(f"managed_plugins[{idx}] policy must be an object")
    installation = str(raw.get("installation", "")).strip() or "AVAILABLE"
    authentication = str(raw.get("authentication", "")).strip() or "ON_INSTALL"
    if installation not in ALLOWED_INSTALLATION_POLICIES:
        raise ValueError(
            f"managed_plugins[{idx}] invalid policy.installation: {installation}"
        )
    if authentication not in ALLOWED_AUTH_POLICIES:
        raise ValueError(
            f"managed_plugins[{idx}] invalid policy.authentication: {authentication}"
        )
    return {
        "installation": installation,
        "authentication": authentication,
    }


def _normalize_marketplace(data: dict[str, Any]) -> tuple[str, str]:
    raw = data.get("marketplaces", {}).get("global", {})
    if not isinstance(raw, dict):
        raise ValueError("marketplaces.global must be an object")
    name = str(raw.get("name", "")).strip() or "managed-plugins"
    display_name = str(raw.get("display_name", "")).strip() or "Managed Plugins"
    return name, display_name


def validate_registry(
    data: dict[str, Any], root_dir: Path, home: Path
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    Path,
    Path,
    tuple[str, str],
]:
    managed = data.get("managed_plugins")
    if not isinstance(managed, list) or not managed:
        raise ValueError("managed_plugins must be a non-empty array")

    unmanaged = data.get("unmanaged_repo_local_plugins", [])
    if not isinstance(unmanaged, list):
        raise ValueError("unmanaged_repo_local_plugins must be an array")

    seen: set[tuple[str, str]] = set()
    validated_managed: list[dict[str, Any]] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")

        plugin = ensure_str(item.get("plugin"), "plugin", idx)
        origin = ensure_str(item.get("origin"), "origin", idx)
        scope = ensure_str(item.get("scope"), "scope", idx)
        source_path = ensure_str(item.get("source_path"), "source_path", idx)
        upstream_ref = item.get("upstream_ref", "-")
        category = str(item.get("category", "")).strip() or "Productivity"
        policy = _normalize_policy(item.get("policy"), idx)

        if origin not in ALLOWED_ORIGINS:
            raise ValueError(f"managed_plugins[{idx}] invalid origin: {origin}")
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_plugins[{idx}] invalid scope: {scope}")
        if (plugin, scope) in seen:
            raise ValueError(f"duplicate plugin+scope entry: {plugin}/{scope}")
        seen.add((plugin, scope))

        repos_raw = item.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_plugins[{idx}] repos must be an array")
        repos = [str(repo).strip() for repo in repos_raw if str(repo).strip()]
        if scope == "repo" and not repos:
            raise ValueError(f"managed_plugins[{idx}] repo scope needs repos")
        if scope == "global":
            repos = []

        src = Path(source_path)
        if not src.is_absolute():
            src = (root_dir / src).resolve()
        manifest = _load_plugin_manifest(src)
        manifest_name = str(manifest.get("name", "")).strip()
        if manifest_name != plugin:
            raise ValueError(
                f"plugin manifest name mismatch for {plugin}: {manifest_name or '<missing>'}"
            )

        validated_managed.append(
            {
                "plugin": plugin,
                "origin": origin,
                "scope": scope,
                "repos": repos,
                "source_path": source_path,
                "source_abs": src,
                "upstream_ref": str(upstream_ref).strip() or "-",
                "category": category,
                "policy": policy,
            }
        )

    validated_unmanaged: list[dict[str, Any]] = []
    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ValueError(f"unmanaged_repo_local_plugins[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", idx)
        plugin = ensure_str(item.get("plugin"), "plugin", idx)
        validated_unmanaged.append({"repo": repo, "plugin": plugin})

    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("paths must be an object")

    github_root_raw = paths.get("github_root", "~/GitHub")
    if not isinstance(github_root_raw, str) or not github_root_raw.strip():
        raise ValueError("paths.github_root must be a non-empty string")
    github_root = expand_path(github_root_raw.strip(), home).resolve()

    codex_plugin_root_raw = paths.get("codex_plugin_root", "~/.codex/plugins")
    if not isinstance(codex_plugin_root_raw, str) or not codex_plugin_root_raw.strip():
        raise ValueError("paths.codex_plugin_root must be a non-empty string")
    codex_plugin_root = expand_path(codex_plugin_root_raw.strip(), home).resolve()

    return (
        validated_managed,
        validated_unmanaged,
        github_root,
        codex_plugin_root,
        _normalize_marketplace(data),
    )


def prune_obsolete_global_links(
    codex_plugin_root: Path,
    managed_source_root: Path,
    desired_links: dict[Path, Path],
    apply: bool,
) -> None:
    if not codex_plugin_root.exists():
        return
    for entry in sorted(codex_plugin_root.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        if not is_relative_to(target, managed_source_root):
            continue
        if entry in desired_links:
            continue
        print(f"PRUNE {entry}")
        if apply:
            entry.unlink()


def build_marketplace_payload(
    marketplace_name: str,
    display_name: str,
    entries: list[dict[str, Any]],
    *,
    source_prefix: str,
) -> dict[str, Any]:
    plugins: list[dict[str, Any]] = []
    for item in sorted(entries, key=lambda entry: entry["plugin"]):
        plugins.append(
            {
                "name": item["plugin"],
                "source": {
                    "source": "local",
                    "path": f"{source_prefix}/{item['plugin']}",
                },
                "policy": {
                    "installation": item["policy"]["installation"],
                    "authentication": item["policy"]["authentication"],
                },
                "category": item["category"],
            }
        )
    return {
        "name": marketplace_name,
        "interface": {
            "displayName": display_name,
        },
        "plugins": plugins,
    }


def _marketplace_content(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def sync_marketplace(path: Path, payload: dict[str, Any], apply: bool) -> None:
    content = _marketplace_content(payload)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        print(f"UNCHANGED {path}")
        return
    print(f"SYNC {path}")
    if apply:
        _write_if_changed(path, content)


def repo_marketplace_metadata(repo_root: Path) -> tuple[str, str]:
    repo_name = repo_root.name.lstrip(".") or "repo"
    slug = _sanitize_file_name(repo_name).lower() or "repo"
    display = f"{repo_name} Managed Plugins"
    return f"{slug}-managed-plugins", display


def run_sync(
    managed: list[dict[str, Any]],
    root_dir: Path,
    github_root: Path,
    codex_plugin_root: Path,
    global_marketplace: tuple[str, str],
    apply: bool,
) -> None:
    home = Path.home()
    desired_global_links: dict[Path, Path] = {}
    repo_entries: dict[Path, list[dict[str, Any]]] = {}

    global_entries: list[dict[str, Any]] = []
    for item in managed:
        plugin = item["plugin"]
        src = item["source_abs"]
        if item["scope"] == "global":
            dst = codex_plugin_root / plugin
            desired_global_links[dst] = src
            global_entries.append(item)
            sync_link(dst, src, apply)
            continue

        for repo in item["repos"]:
            repo_root = resolve_repo_root(repo, github_root, home)
            repo_entries.setdefault(repo_root, []).append(item)
            dst = repo_root / "plugins" / plugin
            sync_link(dst, src, apply)

    prune_obsolete_global_links(
        codex_plugin_root,
        (root_dir / "plugins-source").resolve(),
        desired_global_links,
        apply,
    )

    marketplace_path = root_dir / "plugins" / "marketplace.json"
    marketplace_payload = build_marketplace_payload(
        global_marketplace[0],
        global_marketplace[1],
        global_entries,
        source_prefix="./.codex/plugins",
    )
    _write_if_changed(marketplace_path, _marketplace_content(marketplace_payload))
    print(f"SYNC {marketplace_path}")

    for repo_root, entries in sorted(repo_entries.items(), key=lambda item: str(item[0])):
        marketplace_name, display_name = repo_marketplace_metadata(repo_root)
        payload = build_marketplace_payload(
            marketplace_name,
            display_name,
            entries,
            source_prefix="./plugins",
        )
        repo_marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
        sync_marketplace(repo_marketplace_path, payload, apply)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync plugin symlinks from a canonical JSON registry, render marketplace "
            "files, and generate Obsidian Base artifacts."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply link changes (default is dry-run for linking).",
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
        managed, unmanaged, github_root, codex_plugin_root, global_marketplace = (
            validate_registry(data, root_dir, home)
        )
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    if not args.no_generate:
        views_dir = generated_views_dir(root_dir)
        generate_registry_base(views_dir)
        generate_registry_items(views_dir, managed, unmanaged)
        print(f"Generated registry Base artifacts in {views_dir}")

    run_sync(
        managed,
        root_dir,
        github_root,
        codex_plugin_root,
        global_marketplace,
        args.apply,
    )

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute link changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
