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


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def ensure_str(value: Any, field: str, idx: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"managed_skills[{idx}] invalid {field}: {value!r}")
    return value.strip()


def rel_link(dst: Path, src: Path) -> str:
    return os.path.relpath(str(src), str(dst.parent))


def resolved_target(link_path: Path) -> Path:
    cur = os.readlink(link_path)
    if os.path.isabs(cur):
        return Path(cur).resolve()
    return (link_path.parent / cur).resolve()


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


def generate_registry_base(registry_dir: Path) -> None:
    content = """filters:
  and:
    - 'file.inFolder("skills/registry-items")'
properties:
  registry_kind:
    displayName: Type
  skill:
    displayName: Skill
  origin:
    displayName: Origin
  scope:
    displayName: Scope
  repos_csv:
    displayName: Repos
  upstream_ref:
    displayName: Upstream
  repo:
    displayName: Repo
  source_path:
    displayName: Source Path
views:
  - type: table
    name: Managed Skills
    filters: 'registry_kind == "managed"'
    order:
      - skill
      - origin
      - scope
      - repos_csv
      - upstream_ref
    sort:
      - property: scope
        direction: ASC
      - property: origin
        direction: ASC
      - property: skill
        direction: ASC
  - type: table
    name: Repo-Local Skills
    filters: 'registry_kind == "repo_local"'
    order:
      - repo
      - skill
"""
    _write_if_changed(registry_dir / "registry.base", content)


def _sanitize_file_name(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("-")
    return "".join(safe).strip("-")


def generate_registry_items(
    registry_dir: Path,
    managed: list[dict[str, Any]],
    unmanaged: list[dict[str, Any]],
) -> None:
    root = registry_dir / "registry-items"
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
            f"skill: {_yaml_str(item['skill'])}",
            f"origin: {_yaml_str(item['origin'])}",
            f"scope: {_yaml_str(item['scope'])}",
            f"repos_csv: {_yaml_str(repos_csv)}",
            f"source_path: {_yaml_str(item['source_path'])}",
            f"upstream_ref: {_yaml_str(item.get('upstream_ref', '-'))}",
            "repos:",
        ]
        if repos:
            lines.extend([f"  - {_yaml_str(repo)}" for repo in repos])
        else:
            lines.append("  - \"*\"")
        lines.extend(
            [
                "---",
                "",
                "Generated from `skills/registry.json`. Do not edit manually.",
                "",
            ]
        )
        _write_if_changed(
            managed_dir / f"{_sanitize_file_name(item['skill'])}.md",
            "\n".join(lines),
        )

    for item in unmanaged:
        file_name = (
            f"{_sanitize_file_name(item['repo'])}--"
            f"{_sanitize_file_name(item['skill'])}.md"
        )
        lines = [
            "---",
            "registry_kind: repo_local",
            f"repo: {_yaml_str(item['repo'])}",
            f"skill: {_yaml_str(item['skill'])}",
            "---",
            "",
            "Generated from `skills/registry.json`. Do not edit manually.",
            "",
        ]
        _write_if_changed(repo_local_dir / file_name, "\n".join(lines))


def validate_registry(
    data: dict[str, Any], registry_dir: Path, home: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
    managed = data.get("managed_skills")
    if not isinstance(managed, list) or not managed:
        raise ValueError("managed_skills must be a non-empty array")

    unmanaged = data.get("unmanaged_repo_local_skills", [])
    if not isinstance(unmanaged, list):
        raise ValueError("unmanaged_repo_local_skills must be an array")

    seen: set[tuple[str, str]] = set()
    validated_managed: list[dict[str, Any]] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_skills[{idx}] must be an object")
        skill = ensure_str(item.get("skill"), "skill", idx)
        origin = ensure_str(item.get("origin"), "origin", idx)
        scope = ensure_str(item.get("scope"), "scope", idx)
        source_path = ensure_str(item.get("source_path"), "source_path", idx)
        upstream_ref = item.get("upstream_ref", "-")
        if origin not in ALLOWED_ORIGINS:
            raise ValueError(f"managed_skills[{idx}] invalid origin: {origin}")
        if scope not in ALLOWED_SCOPES:
            raise ValueError(f"managed_skills[{idx}] invalid scope: {scope}")

        if (skill, scope) in seen:
            raise ValueError(f"duplicate skill+scope entry: {skill}/{scope}")
        seen.add((skill, scope))

        repos_raw = item.get("repos", [])
        if not isinstance(repos_raw, list):
            raise ValueError(f"managed_skills[{idx}] repos must be an array")
        repos = [str(repo).strip() for repo in repos_raw if str(repo).strip()]
        if scope == "repo" and not repos:
            raise ValueError(f"managed_skills[{idx}] repo scope needs repos")
        if scope == "global":
            repos = []

        src = Path(source_path)
        if not src.is_absolute():
            src = (registry_dir.parent / src).resolve()
        if not (src / "SKILL.md").is_file():
            raise ValueError(f"source missing SKILL.md for {skill}: {src}")

        validated_managed.append(
            {
                "skill": skill,
                "origin": origin,
                "scope": scope,
                "repos": repos,
                "source_path": source_path,
                "source_abs": src,
                "upstream_ref": str(upstream_ref).strip() or "-",
            }
        )

    validated_unmanaged: list[dict[str, Any]] = []
    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ValueError(f"unmanaged_repo_local_skills[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", idx)
        skill = ensure_str(item.get("skill"), "skill", idx)
        validated_unmanaged.append({"repo": repo, "skill": skill})

    github_root_raw = data.get("paths", {}).get("github_root", "~/GitHub")
    if not isinstance(github_root_raw, str) or not github_root_raw.strip():
        raise ValueError("paths.github_root must be a non-empty string")
    github_root = expand_path(github_root_raw.strip(), home).resolve()

    return validated_managed, validated_unmanaged, github_root


def run_sync(
    managed: list[dict[str, Any]],
    root_dir: Path,
    github_root: Path,
    apply: bool,
) -> None:
    for item in managed:
        skill = item["skill"]
        src = item["source_abs"]
        if item["scope"] == "global":
            dst = root_dir / "skills" / skill
            sync_link(dst, src, apply)
            continue

        for repo in item["repos"]:
            dst = github_root / repo / ".agents" / "skills" / skill
            sync_link(dst, src, apply)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync skill symlinks from a canonical JSON registry and generate "
            "Obsidian Base artifacts."
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
        help="Skip generating registry.base and registry-items files.",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to canonical registry JSON file.",
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
        managed, unmanaged, github_root = validate_registry(data, registry_dir, home)
    except ValueError as exc:
        print(f"Registry validation failed: {exc}", file=sys.stderr)
        return 1

    if not args.no_generate:
        generate_registry_base(registry_dir)
        generate_registry_items(registry_dir, managed, unmanaged)
        print(f"Generated registry Base artifacts in {registry_dir}")

    run_sync(managed, root_dir, github_root, args.apply)

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute link changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
