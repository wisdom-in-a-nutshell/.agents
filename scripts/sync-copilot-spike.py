#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Temporary Copilot CLI experiment: keep isolated until the durable
# cross-runtime bootstrap model is clear.
DEFAULT_COPILOT_HOME = Path.home() / ".copilot"
DEFAULT_GITHUB_ROOT = Path.home() / "GitHub"
DEFAULT_GLOBAL_CONTEXT_SOURCE = Path.home() / ".agents" / "codex" / "config" / "global.agents.md"
DEFAULT_GLOBAL_CONTEXT_TARGET = Path.home() / ".copilot" / "copilot-instructions.md"
DEFAULT_HOOKS_FILE = Path.home() / ".copilot" / "hooks" / "agents-control-plane.json"
DEFAULT_LAUNCHER_TARGET = Path.home() / "bin" / "copilot"
DEFAULT_REAL_CLI_PATH = Path("/opt/homebrew/bin/copilot")
COPILOT_STOP_COMMAND = "python3 ~/.agents/hooks/scripts/copilot_stop.py"
DEFAULT_SETTINGS = {
    "askUser": False,
    "banner": "never",
    "beep": False,
}
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


def absolute_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return Path.cwd() / path


def output_path(path: Path) -> Path:
    path = absolute_path(path)
    return path.parent.resolve() / path.name


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
    duplicates = sorted(item["skill"] for item in items if item["skill"] in seen or seen.add(item["skill"]))
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


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads("\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("//")))
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
    return Path(raw).resolve() if raw else None


def discover_git_repo_roots(root: Path) -> list[Path]:
    if not root.is_dir():
        return []

    seen: set[Path] = set()
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [name for name in dirnames if name not in PRUNED_REPO_DIR_NAMES]
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


def render_settings(settings_file: Path, apply: bool, skip_yolo: bool) -> None:
    data = read_json_object(settings_file)
    desired = dict(data)
    if not skip_yolo:
        desired.update(DEFAULT_SETTINGS)
    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return

    changed = ", ".join(sorted(key for key in desired if desired.get(key) != data.get(key)))
    print(f"SYNC {settings_file} ({changed})")
    if not apply:
        return

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def render_config_trust(config_file: Path, trusted: list[str], apply: bool, skip_yolo: bool) -> None:
    if skip_yolo:
        return
    data = read_json_object(config_file)
    desired = dict(data)
    desired["trustedFolders"] = merge_string_list(data.get("trustedFolders"), trusted)
    if desired == data:
        print(f"UNCHANGED {config_file}")
        return

    print(f"SYNC {config_file} (trustedFolders)")
    if not apply:
        return

    config_file.parent.mkdir(parents=True, exist_ok=True)
    prefix = "// User settings belong in settings.json.\n// This file is managed automatically.\n"
    config_file.write_text(prefix + json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


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


def render_hooks(hooks_file: Path, apply: bool) -> None:
    desired = {
        "version": 1,
        "hooks": {
            "permissionRequest": [
                {
                    "type": "command",
                    "bash": "printf '%s\\n' '{\"behavior\":\"allow\"}'",
                    "timeoutSec": 30,
                }
            ],
            "preToolUse": [
                {
                    "type": "command",
                    "bash": "printf '%s\\n' '{\"permissionDecision\":\"allow\"}'",
                    "timeoutSec": 30,
                }
            ],
            "agentStop": [
                {
                    "type": "command",
                    "bash": COPILOT_STOP_COMMAND,
                    "timeoutSec": 900,
                }
            ]
        },
    }
    data = read_json_object(hooks_file)
    if desired == data:
        print(f"UNCHANGED {hooks_file}")
        return

    print(f"SYNC {hooks_file} (agentStop)")
    if not apply:
        return

    hooks_file.parent.mkdir(parents=True, exist_ok=True)
    hooks_file.write_text(json.dumps(desired, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def launcher_text(real_cli_path: Path) -> str:
    real_cli = shlex.quote(str(real_cli_path))
    return f"""#!/usr/bin/env bash
set -euo pipefail

default_real_cli={real_cli}
real_cli="${{COPILOT_REAL_BIN:-$default_real_cli}}"
if [[ ! -x "$real_cli" ]]; then
  printf 'copilot launcher cannot find executable real CLI: %s\\n' "$real_cli" >&2
  exit 127
fi

for arg in "$@"; do
  case "$arg" in
    --yolo|--allow-all)
      exec "$real_cli" "$@"
      ;;
  esac
done

case "${{1:-}}" in
  completion|help|login|mcp|plugin|update|version|-h|--help|-v|--version)
    exec "$real_cli" "$@"
    ;;
esac

exec "$real_cli" --yolo --no-ask-user "$@"
"""


def render_launcher(launcher_target: Path, real_cli_path: Path, apply: bool) -> None:
    desired = launcher_text(real_cli_path)
    if launcher_target.is_file():
        try:
            current = launcher_target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            current = None
        if current == desired and os.access(launcher_target, os.X_OK):
            print(f"UNCHANGED {launcher_target}")
            return

    print(f"SYNC {launcher_target} (Copilot YOLO launcher)")
    if not apply:
        return

    launcher_target.parent.mkdir(parents=True, exist_ok=True)
    if launcher_target.is_dir():
        shutil.rmtree(launcher_target)
    elif launcher_target.exists() or launcher_target.is_symlink():
        launcher_target.unlink()
    launcher_target.write_text(desired, encoding="utf-8")
    launcher_target.chmod(0o755)


def run_sync(
    registry_file: Path,
    copilot_home: Path,
    github_root: Path,
    extra_trusted_workspaces: list[Path],
    global_context_source: Path,
    global_context_target: Path,
    hooks_file: Path,
    launcher_target: Path,
    real_cli_path: Path,
    apply: bool,
    skip_yolo: bool,
    skip_global_context: bool,
    skip_hooks: bool,
    skip_launcher: bool,
    skip_skills: bool,
) -> None:
    items, root_dir = load_registry(registry_file)
    if not skip_skills:
        skills_dir = copilot_home / "skills"
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

    trusted = trusted_workspaces(root_dir, github_root, extra_trusted_workspaces)
    render_settings(copilot_home / "settings.json", apply, skip_yolo)
    render_config_trust(copilot_home / "config.json", trusted, apply, skip_yolo)
    if not skip_global_context:
        render_global_context(global_context_source, global_context_target, apply)
    if not skip_hooks:
        render_hooks(hooks_file, apply)
    if not skip_launcher:
        render_launcher(launcher_target, real_cli_path, apply)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike sync for GitHub Copilot CLI global instructions, skills, hooks, and YOLO launcher."
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run).")
    parser.add_argument(
        "--copilot-home",
        default=str(DEFAULT_COPILOT_HOME),
        help="Copilot CLI home directory.",
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
        help="Source markdown file for Copilot global instructions.",
    )
    parser.add_argument(
        "--global-context-target",
        default=str(DEFAULT_GLOBAL_CONTEXT_TARGET),
        help="Copilot global copilot-instructions.md target.",
    )
    parser.add_argument(
        "--hooks-file",
        default=str(DEFAULT_HOOKS_FILE),
        help="Copilot global hooks JSON target.",
    )
    parser.add_argument(
        "--launcher-target",
        default=str(DEFAULT_LAUNCHER_TARGET),
        help="Copilot YOLO launcher target.",
    )
    parser.add_argument(
        "--real-cli-path",
        default=str(DEFAULT_REAL_CLI_PATH),
        help="Real Copilot CLI binary path wrapped by the YOLO launcher.",
    )
    parser.add_argument("--skip-yolo", action="store_true", help="Do not render YOLO settings.")
    parser.add_argument(
        "--skip-global-context",
        action="store_true",
        help="Do not render Copilot global instructions.",
    )
    parser.add_argument("--skip-hooks", action="store_true", help="Do not render Copilot hooks.")
    parser.add_argument("--skip-launcher", action="store_true", help="Do not render the Copilot YOLO launcher.")
    parser.add_argument("--skip-skills", action="store_true", help="Do not render Copilot personal skill links.")
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to canonical skills registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = absolute_path(Path(args.registry_file).expanduser()).resolve()
    copilot_home = absolute_path(Path(args.copilot_home).expanduser()).resolve()
    github_root = absolute_path(Path(args.github_root).expanduser()).resolve()
    global_context_source = absolute_path(Path(args.global_context_source).expanduser()).resolve()
    global_context_target = output_path(Path(args.global_context_target).expanduser())
    hooks_file = output_path(Path(args.hooks_file).expanduser())
    launcher_target = output_path(Path(args.launcher_target).expanduser())
    real_cli_path = absolute_path(Path(args.real_cli_path).expanduser())
    extra_trusted_workspaces = [
        Path(raw).expanduser().resolve()
        for raw in args.trusted_workspace
        if raw.strip()
    ]

    try:
        run_sync(
            registry_file,
            copilot_home,
            github_root,
            extra_trusted_workspaces,
            global_context_source,
            global_context_target,
            hooks_file,
            launcher_target,
            real_cli_path,
            args.apply,
            args.skip_yolo,
            args.skip_global_context,
            args.skip_hooks,
            args.skip_launcher,
            args.skip_skills,
        )
    except ValueError as exc:
        print(f"Copilot spike sync failed: {exc}", file=sys.stderr)
        return 1

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute Copilot changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
