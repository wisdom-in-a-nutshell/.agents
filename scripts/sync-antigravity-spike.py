#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Temporary Antigravity experiment: this may be ripped out once the durable
# cross-runtime bootstrap model is clear.
DEFAULT_APP_DATA_DIR = Path.home() / ".gemini" / "antigravity-cli"
DEFAULT_GITHUB_ROOT = Path.home() / "GitHub"
DEFAULT_GLOBAL_CONTEXT_SOURCE = Path.home() / ".agents" / "codex" / "config" / "global.agents.md"
DEFAULT_GLOBAL_CONTEXT_TARGET = Path.home() / ".gemini" / "GEMINI.md"
DEFAULT_HOOKS_FILE = Path.home() / ".gemini" / "config" / "hooks.json"
ANTIGRAVITY_STOP_COMMAND = "python3 ~/.agents/hooks/scripts/antigravity_stop.py"
DEFAULT_SETTINGS = {"toolPermission": "always-proceed"}
ALLOWED_SCOPES = {"global", "repo", "dormant"}
PRUNED_REPO_DIR_NAMES = {
    ".cache",
    ".direnv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".tox",
    ".venv",
    "__pycache__",
    "DerivedData",
    "node_modules",
    "temp",
    "tmp",
    "vendor",
    "venv",
}


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


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def git_root_for(path: Path) -> Path | None:
    if not path.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    return Path(raw).resolve()


def discover_git_repo_roots(root: Path) -> list[Path]:
    if not root.is_dir():
        return []

    seen: set[Path] = set()
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in PRUNED_REPO_DIR_NAMES
        ]
        has_git = ".git" in dirnames or ".git" in filenames
        if ".git" in dirnames:
            dirnames.remove(".git")
        if not has_git:
            continue

        repo_root = git_root_for(Path(dirpath))
        if repo_root is None or repo_root in seen:
            continue
        seen.add(repo_root)
        repos.append(repo_root)
    return sorted(repos, key=lambda path: str(path))


def trusted_workspaces(root_dir: Path, github_root: Path, extra: list[Path]) -> list[str]:
    desired: set[Path] = set()
    control_plane_repo = git_root_for(root_dir)
    if control_plane_repo is not None:
        desired.add(control_plane_repo)
    desired.update(discover_git_repo_roots(github_root))
    desired.update(path.resolve() for path in extra if path.exists())
    return [str(path) for path in sorted(desired, key=lambda item: str(item))]


def merge_string_list(existing: Any, desired: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, str) or not item.strip():
                continue
            value = str(Path(item).expanduser().resolve())
            if value not in seen:
                seen.add(value)
                merged.append(value)
    for item in desired:
        value = str(Path(item).expanduser().resolve())
        if value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


def render_settings(
    settings_file: Path,
    trusted: list[str],
    apply: bool,
    skip_yolo: bool,
    skip_workspace_trust: bool,
) -> None:
    data = read_settings(settings_file)
    desired = dict(data)
    if not skip_yolo:
        desired.update(DEFAULT_SETTINGS)
    if not skip_workspace_trust:
        desired["trustedWorkspaces"] = merge_string_list(
            data.get("trustedWorkspaces"),
            trusted,
        )
    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return

    changed = ", ".join(sorted(key for key in desired if desired.get(key) != data.get(key)))
    print(f"SYNC {settings_file} ({changed})")
    if not apply:
        return

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(desired, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def render_global_context(source: Path, target: Path, apply: bool) -> None:
    if not source.is_file():
        raise ValueError(f"global context source missing: {source}")
    if target.is_symlink() and resolved_target(target) == source.resolve():
        print(f"UNCHANGED {target}")
        return

    print(f"SYNC {target} -> {rel_link(target, source)}")
    if not apply:
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
    target.symlink_to(rel_link(target, source))


def is_antigravity_stop_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    for hook in hooks:
        if isinstance(hook, dict) and hook.get("command") == ANTIGRAVITY_STOP_COMMAND:
            return True
    return False


def render_hooks(hooks_file: Path, apply: bool) -> None:
    data = read_json_object(hooks_file)
    desired = dict(data)
    hooks = desired.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    else:
        hooks = dict(hooks)

    stop_entries = hooks.get("Stop")
    if not isinstance(stop_entries, list):
        stop_entries = []
    stop_entries = [entry for entry in stop_entries if not is_antigravity_stop_entry(entry)]
    stop_entries.append(
        {
            "hooks": [
                {
                    "command": ANTIGRAVITY_STOP_COMMAND,
                    "timeout": 900,
                    "type": "command",
                }
            ]
        }
    )
    hooks["Stop"] = stop_entries
    desired["hooks"] = hooks

    if desired == data:
        print(f"UNCHANGED {hooks_file}")
        return

    print(f"SYNC {hooks_file} (Stop)")
    if not apply:
        return

    hooks_file.parent.mkdir(parents=True, exist_ok=True)
    hooks_file.write_text(
        json.dumps(desired, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_sync(
    registry_file: Path,
    app_data_dir: Path,
    github_root: Path,
    extra_trusted_workspaces: list[Path],
    global_context_source: Path,
    global_context_target: Path,
    hooks_file: Path,
    apply: bool,
    skip_yolo: bool,
    skip_workspace_trust: bool,
    skip_global_context: bool,
    skip_hooks: bool,
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

    render_settings(
        app_data_dir / "settings.json",
        trusted_workspaces(root_dir, github_root, extra_trusted_workspaces),
        apply,
        skip_yolo,
        skip_workspace_trust,
    )
    if not skip_global_context:
        render_global_context(global_context_source, global_context_target, apply)
    if not skip_hooks:
        render_hooks(hooks_file, apply)


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
        "--github-root",
        default=str(DEFAULT_GITHUB_ROOT),
        help="GitHub root to scan for trusted Git workspaces.",
    )
    parser.add_argument(
        "--trusted-workspace",
        action="append",
        default=[],
        help="Additional workspace path to trust (repeatable).",
    )
    parser.add_argument(
        "--global-context-source",
        default=str(DEFAULT_GLOBAL_CONTEXT_SOURCE),
        help="Source markdown file for Antigravity global GEMINI.md.",
    )
    parser.add_argument(
        "--global-context-target",
        default=str(DEFAULT_GLOBAL_CONTEXT_TARGET),
        help="Antigravity global GEMINI.md target.",
    )
    parser.add_argument(
        "--hooks-file",
        default=str(DEFAULT_HOOKS_FILE),
        help="Antigravity global hooks.json target.",
    )
    parser.add_argument(
        "--skip-yolo",
        action="store_true",
        help="Do not render the always-proceed tool permission setting.",
    )
    parser.add_argument(
        "--skip-workspace-trust",
        action="store_true",
        help="Do not render Antigravity trustedWorkspaces.",
    )
    parser.add_argument(
        "--skip-global-context",
        action="store_true",
        help="Do not render Antigravity global GEMINI.md.",
    )
    parser.add_argument(
        "--skip-hooks",
        action="store_true",
        help="Do not render Antigravity global hooks.json.",
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
    github_root = Path(args.github_root).expanduser().resolve()
    global_context_source = Path(args.global_context_source).expanduser().resolve()
    global_context_target = Path(args.global_context_target).expanduser().resolve()
    hooks_file = Path(args.hooks_file).expanduser().resolve()
    extra_trusted_workspaces = [
        Path(raw).expanduser().resolve()
        for raw in args.trusted_workspace
        if raw.strip()
    ]

    try:
        run_sync(
            registry_file,
            app_data_dir,
            github_root,
            extra_trusted_workspaces,
            global_context_source,
            global_context_target,
            hooks_file,
            args.apply,
            args.skip_yolo,
            args.skip_workspace_trust,
            args.skip_global_context,
            args.skip_hooks,
        )
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
