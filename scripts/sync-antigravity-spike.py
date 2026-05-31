#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


# Temporary Antigravity experiment: this may be ripped out once the durable
# cross-runtime bootstrap model is clear.
DEFAULT_APP_DATA_DIR = Path.home() / ".gemini" / "antigravity-cli"
DEFAULT_SETTINGS = {"toolPermission": "always-proceed"}
ALLOWED_SCOPES = {"global", "repo", "dormant"}


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


def ensure_str(value: Any, field: str, label: str, idx: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}[{idx}] invalid {field}: {value!r}")
    return value.strip()


def load_registry(registry_file: Path) -> tuple[list[dict[str, Any]], Path]:
    if not registry_file.is_file():
        raise ValueError(f"registry not found: {registry_file}")
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {registry_file}: {exc}") from exc

    root_dir = registry_file.parent.parent
    items: list[dict[str, Any]] = []
    for label in ("managed_skills", "managed_plugin_skills"):
        raw_items = data.get(label, [])
        if not isinstance(raw_items, list):
            raise ValueError(f"{label} must be an array")
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                raise ValueError(f"{label}[{idx}] must be an object")
            skill = ensure_str(item.get("skill"), "skill", label, idx)
            scope = ensure_str(item.get("scope"), "scope", label, idx)
            source_path = ensure_str(item.get("source_path"), "source_path", label, idx)
            if scope not in ALLOWED_SCOPES:
                raise ValueError(f"{label}[{idx}] invalid scope: {scope}")
            if scope != "global":
                continue

            src = Path(source_path)
            if not src.is_absolute():
                src = (root_dir / src).resolve()
            if not (src / "SKILL.md").is_file():
                raise ValueError(f"source missing SKILL.md for {skill}: {src}")
            items.append({"skill": skill, "source_abs": src})

    seen: set[str] = set()
    duplicates = sorted(
        item["skill"] for item in items if item["skill"] in seen or seen.add(item["skill"])
    )
    if duplicates:
        raise ValueError(f"duplicate global skill entries: {', '.join(duplicates)}")
    return items, root_dir


def sync_link(dst: Path, src: Path, apply: bool) -> bool:
    rel = rel_link(dst, src)
    if dst.is_symlink() and resolved_target(dst) == src.resolve():
        print(f"UNCHANGED {dst}")
        return False

    print(f"SYNC {dst} -> {rel}")
    if not apply:
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    elif dst.exists():
        dst.unlink()
    dst.symlink_to(rel)
    return True


def prune_obsolete_links(
    skills_dir: Path,
    desired_links: dict[Path, Path],
    managed_source_roots: list[Path],
    apply: bool,
) -> None:
    if not skills_dir.exists():
        return
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        if not any(is_relative_to(target, root) for root in managed_source_roots):
            continue
        if entry in desired_links:
            continue
        print(f"PRUNE {entry}")
        if apply:
            entry.unlink()


def read_settings(settings_file: Path) -> dict[str, Any]:
    if not settings_file.exists():
        return {}
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {settings_file}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"settings file must contain a JSON object: {settings_file}")
    return data


def render_settings(settings_file: Path, apply: bool) -> None:
    data = read_settings(settings_file)
    desired = dict(data)
    desired.update(DEFAULT_SETTINGS)
    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return

    changed = ", ".join(sorted(DEFAULT_SETTINGS))
    print(f"SYNC {settings_file} ({changed})")
    if not apply:
        return

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(desired, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def run_sync(
    registry_file: Path,
    app_data_dir: Path,
    apply: bool,
    skip_yolo: bool,
) -> None:
    items, root_dir = load_registry(registry_file)
    skills_dir = app_data_dir / "skills"
    desired_links: dict[Path, Path] = {}
    for item in items:
        dst = skills_dir / item["skill"]
        src = item["source_abs"]
        desired_links[dst] = src
        sync_link(dst, src, apply)

    managed_source_roots = [
        (root_dir / "skills-source").resolve(),
        (root_dir / "plugins-source").resolve(),
    ]
    prune_obsolete_links(skills_dir, desired_links, managed_source_roots, apply)

    if not skip_yolo:
        render_settings(app_data_dir / "settings.json", apply)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Spike sync for Antigravity CLI global skills and always-proceed tool permissions."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run).",
    )
    parser.add_argument(
        "--app-data-dir",
        default=str(DEFAULT_APP_DATA_DIR),
        help="Antigravity CLI app data directory.",
    )
    parser.add_argument(
        "--skip-yolo",
        action="store_true",
        help="Do not render the always-proceed tool permission setting.",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to canonical skills registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    app_data_dir = Path(args.app_data_dir).expanduser().resolve()

    try:
        run_sync(registry_file, app_data_dir, args.apply, args.skip_yolo)
    except ValueError as exc:
        print(f"Antigravity spike sync failed: {exc}", file=sys.stderr)
        return 1

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute Antigravity changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
