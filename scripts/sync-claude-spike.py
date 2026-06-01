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


# Temporary Claude Code experiment: keep isolated until the durable
# cross-runtime bootstrap model is clear.
DEFAULT_CLAUDE_HOME = Path.home() / ".claude"
DEFAULT_GITHUB_ROOT = Path.home() / "GitHub"
DEFAULT_GLOBAL_CONTEXT_SOURCE = Path.home() / ".agents" / "codex" / "config" / "global.agents.md"
DEFAULT_GLOBAL_CONTEXT_TARGET = Path.home() / ".claude" / "CLAUDE.md"
DEFAULT_LAUNCHER_TARGET = Path.home() / "bin" / "claude"
DEFAULT_REAL_CLI_PATH = Path("/opt/homebrew/bin/claude")
CLAUDE_STOP_COMMAND = "python3 ~/.agents/hooks/scripts/claude_stop.py"
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
DEFAULT_ALLOW_RULES = [
    "Agent",
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "LS",
    "MultiEdit",
    "NotebookEdit",
    "Read",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
]


def rel_link(dst: Path, src: Path) -> str:
    return os.path.relpath(str(src), str(dst.parent))


def resolved_target(link_path: Path) -> Path:
    cur = os.readlink(link_path)
    if os.path.isabs(cur):
        return Path(cur).resolve()
    return (link_path.parent / cur).resolve()


def absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


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


def load_registry(registry_file: Path) -> tuple[list[dict[str, Any]], Path]:
    data = read_json_object(registry_file)
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


def prune_obsolete_links(skills_dir: Path, desired_links: dict[Path, Path], managed_source_roots: list[Path], apply: bool) -> None:
    if not skills_dir.exists():
        return
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        if entry in desired_links or not any(is_relative_to(target, root) for root in managed_source_roots):
            continue
        print(f"PRUNE {entry}")
        if apply:
            entry.unlink()


def git_root_for(path: Path) -> Path | None:
    if not path.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    raw = result.stdout.strip()
    return Path(raw).resolve() if result.returncode == 0 and raw else None


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
        if repo_root is not None and repo_root not in seen:
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
            if isinstance(item, str) and item.strip() and item not in seen:
                seen.add(item)
                merged.append(item)
    for item in desired:
        value = str(Path(item).expanduser().resolve())
        if value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


def merge_literal_string_list(existing: Any, desired: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item.strip() and item not in seen:
                seen.add(item)
                merged.append(item)
    for item in desired:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def managed_hook_command(entry: Any, command: str) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(isinstance(hook, dict) and hook.get("command") == command for hook in hooks)


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


def render_settings(settings_file: Path, trusted: list[str], apply: bool, skip_yolo: bool) -> None:
    data = read_json_object(settings_file)
    desired = dict(data)
    desired.setdefault("$schema", "https://json.schemastore.org/claude-code-settings.json")

    permissions = desired.get("permissions")
    permissions = dict(permissions) if isinstance(permissions, dict) else {}
    allow = merge_literal_string_list(permissions.get("allow"), DEFAULT_ALLOW_RULES)
    permissions["allow"] = allow
    permissions["additionalDirectories"] = merge_string_list(permissions.get("additionalDirectories"), trusted)
    if not skip_yolo:
        permissions["defaultMode"] = "bypassPermissions"
        permissions["skipDangerousModePermissionPrompt"] = True
    desired["permissions"] = permissions

    hooks = desired.get("hooks")
    hooks = dict(hooks) if isinstance(hooks, dict) else {}
    pre_tool_command = (
        "printf '%s\\n' "
        "'{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\","
        "\"permissionDecisionReason\":\"YOLO mode\"}}'"
    )
    permission_command = (
        "printf '%s\\n' "
        "'{\"hookSpecificOutput\":{\"hookEventName\":\"PermissionRequest\",\"decision\":{\"behavior\":\"allow\"}}}'"
    )
    entries = {
        "PreToolUse": {"matcher": "*", "hooks": [{"type": "command", "command": pre_tool_command, "timeout": 30}]},
        "PermissionRequest": {"matcher": "*", "hooks": [{"type": "command", "command": permission_command, "timeout": 30}]},
        "Stop": {"hooks": [{"type": "command", "command": CLAUDE_STOP_COMMAND, "timeout": 900}]},
    }
    for event_name, entry in entries.items():
        current = hooks.get(event_name)
        current_entries = current if isinstance(current, list) else []
        command = entry["hooks"][0]["command"]
        hooks[event_name] = [item for item in current_entries if not managed_hook_command(item, command)] + [entry]
    desired["hooks"] = hooks

    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return
    print(f"SYNC {settings_file} (permissions, hooks)")
    if not apply:
        return
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def launcher_text(real_cli_path: Path) -> str:
    real_cli = shlex.quote(str(real_cli_path))
    return f"""#!/usr/bin/env bash
set -euo pipefail

default_real_cli={real_cli}
real_cli="${{CLAUDE_REAL_BIN:-$default_real_cli}}"
secret_env="${{CLAUDE_SECRET_ENV:-$HOME/.secrets/anthropic/env}}"
if [[ -f "$secret_env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$secret_env"
  set +a
fi
if [[ ! -x "$real_cli" ]]; then
  printf 'claude launcher cannot find executable real CLI: %s\\n' "$real_cli" >&2
  exit 127
fi

for arg in "$@"; do
  if [[ "$arg" == "--dangerously-skip-permissions" ]]; then
    exec "$real_cli" "$@"
  fi
done

case "${{1:-}}" in
  auth|doctor|install|mcp|plugin|plugins|project|setup-token|update|upgrade|-h|--help|-v|--version)
    exec "$real_cli" "$@"
    ;;
esac

exec "$real_cli" --dangerously-skip-permissions "$@"
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
    print(f"SYNC {launcher_target} (Claude YOLO launcher)")
    if not apply:
        return
    launcher_target.parent.mkdir(parents=True, exist_ok=True)
    if launcher_target.is_dir():
        shutil.rmtree(launcher_target)
    elif launcher_target.exists() or launcher_target.is_symlink():
        launcher_target.unlink()
    launcher_target.write_text(desired, encoding="utf-8")
    launcher_target.chmod(0o755)


def run_sync(args: argparse.Namespace) -> None:
    registry_file = absolute_path(Path(args.registry_file).expanduser()).resolve()
    claude_home = absolute_path(Path(args.claude_home).expanduser()).resolve()
    github_root = absolute_path(Path(args.github_root).expanduser()).resolve()
    global_context_source = absolute_path(Path(args.global_context_source).expanduser()).resolve()
    global_context_target = output_path(Path(args.global_context_target).expanduser())
    launcher_target = output_path(Path(args.launcher_target).expanduser())
    real_cli_path = absolute_path(Path(args.real_cli_path).expanduser())
    extra_trusted_workspaces = [Path(raw).expanduser().resolve() for raw in args.trusted_workspace if raw.strip()]

    items, root_dir = load_registry(registry_file)
    if not args.skip_skills:
        skills_dir = claude_home / "skills"
        desired_links: dict[Path, Path] = {}
        for item in items:
            dst = skills_dir / item["skill"]
            src = item["source_abs"]
            desired_links[dst] = src
            sync_link(dst, src, args.apply)
        prune_obsolete_links(
            skills_dir,
            desired_links,
            [(root_dir / "skills-source").resolve(), (root_dir / "plugins-source").resolve()],
            args.apply,
        )

    trusted = trusted_workspaces(root_dir, github_root, extra_trusted_workspaces)
    if not args.skip_global_context:
        render_global_context(global_context_source, global_context_target, args.apply)
    if not args.skip_settings:
        render_settings(claude_home / "settings.json", trusted, args.apply, args.skip_yolo)
    if not args.skip_launcher:
        render_launcher(launcher_target, real_cli_path, args.apply)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spike sync for Claude Code global instructions, skills, hooks, and YOLO launcher."
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run).")
    parser.add_argument("--claude-home", default=str(DEFAULT_CLAUDE_HOME), help="Claude Code user directory.")
    parser.add_argument("--github-root", default=str(DEFAULT_GITHUB_ROOT), help="GitHub root to scan for trusted Git workspaces.")
    parser.add_argument("--trusted-workspace", action="append", default=[], help="Additional workspace path to trust.")
    parser.add_argument("--global-context-source", default=str(DEFAULT_GLOBAL_CONTEXT_SOURCE), help="Source markdown file for global CLAUDE.md.")
    parser.add_argument("--global-context-target", default=str(DEFAULT_GLOBAL_CONTEXT_TARGET), help="Claude global CLAUDE.md target.")
    parser.add_argument("--launcher-target", default=str(DEFAULT_LAUNCHER_TARGET), help="Claude YOLO launcher target.")
    parser.add_argument("--real-cli-path", default=str(DEFAULT_REAL_CLI_PATH), help="Real Claude CLI binary path wrapped by launcher.")
    parser.add_argument("--skip-yolo", action="store_true", help="Do not render bypass-permission defaults.")
    parser.add_argument("--skip-global-context", action="store_true", help="Do not render global CLAUDE.md.")
    parser.add_argument("--skip-settings", action="store_true", help="Do not render Claude settings.")
    parser.add_argument("--skip-launcher", action="store_true", help="Do not render Claude launcher.")
    parser.add_argument("--skip-skills", action="store_true", help="Do not render Claude skill links.")
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to canonical skills registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_sync(args)
    except ValueError as exc:
        print(f"Claude spike sync failed: {exc}", file=sys.stderr)
        return 1
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute Claude changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
