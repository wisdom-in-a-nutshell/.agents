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

# The shared hook control plane lives in this repo; make it importable so Claude
# per-repo hooks render from the same registry Codex uses.
_AGENTS_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENTS_ROOT))

from hooks.control_plane import (  # noqa: E402
    load_hooks_registry,
    render_claude_hooks,
)
from hooks.scripts.stop import register_current_codex_transaction_paths  # noqa: E402
from mcp.control_plane import claude_server_from_preset, load_mcp_catalog  # noqa: E402


# Durable Claude Code control-plane sync: renders global instructions, skills,
# settings/hooks, the launcher, and per-repo agent preview configs from the
# canonical sources in this agents control-plane repo.
DEFAULT_CLAUDE_HOME = Path.home() / ".claude"
DEFAULT_GITHUB_ROOT = Path.home() / "GitHub"
DEFAULT_GLOBAL_CONTEXT_SOURCE = _AGENTS_ROOT / "config" / "global.agents.md"
DEFAULT_GLOBAL_CONTEXT_TARGET = Path.home() / ".claude" / "CLAUDE.md"
DEFAULT_CLAUDE_SETTINGS_OVERLAY = _AGENTS_ROOT / "config" / "claude-settings.json"
DEFAULT_CLAUDE_DESKTOP_CONFIG = Path.home() / "Library/Application Support/Claude/config.json"
DEFAULT_LAUNCHER_TARGET = Path.home() / "bin" / "claude"
DEFAULT_REAL_CLI_PATH = Path.home() / ".local/bin/claude"
DEFAULT_DEV_SERVERS_REGISTRY = _AGENTS_ROOT / "dev-servers" / "registry.json"
DEFAULT_MCP_PRESETS_REGISTRY = _AGENTS_ROOT / "mcp" / "config" / "presets.json"
DEFAULT_HOOKS_REGISTRY = _AGENTS_ROOT / "hooks" / "registry.json"
DEFAULT_REPO_REGISTRY = _AGENTS_ROOT / "codex" / "config" / "repo-bootstrap.json"
DEFAULT_PREVIEW_RUNNER = _AGENTS_ROOT / "scripts" / "run-agent-preview-server.py"
LAUNCH_CONFIG_VERSION = "0.0.1"
CLAUDE_STOP_COMMAND = 'python3 "$HOME/GitHub/agents/hooks/scripts/claude_stop.py"'
LEGACY_CLAUDE_STOP_COMMANDS = (
    "python3 ~/.agents/hooks/scripts/claude_stop.py",
    "python3 $HOME/.agents/hooks/scripts/claude_stop.py",
)
REPO_CLAUDE_IMPORT = "@../AGENTS.md"
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
    "Workflow",
    "Write",
]
# Top-level "max YOLO" acceptance flags. The launcher already passes
# --dangerously-skip-permissions, but that flag does not pre-accept the one-time
# confirmation dialogs below (bypass-mode dialog, auto-mode opt-in, the
# multi-agent Workflow usage warning), so set them durably here. The result is a
# fully autonomous agent that is never blocked on a permission/usage prompt.
YOLO_ACCEPTANCE_FLAGS = {
    "skipDangerousModePermissionPrompt": True,
    "skipAutoPermissionPrompt": True,
    "skipWorkflowUsageWarning": True,
    "enableAllProjectMcpServers": True,
}
DEFAULT_CLAUDE_SCALAR_SETTINGS = {
    "effortLevel": "high",
}
# Managed dict-valued keys from config/claude-settings.json that are deep-merged
# (overlay wins per key) into the global ~/.claude/settings.json. Keys not listed
# here are ignored so the overlay can never clobber permissions/hooks/yolo state.
CLAUDE_SETTINGS_DICT_OVERLAY_KEYS = ("enabledPlugins", "skillOverrides")
CLAUDE_SETTINGS_LIST_BY_ID_OVERLAY_KEYS = ("sshConfigs",)
CLAUDE_SSH_CONFIG_REQUIRED_STRING_KEYS = ("id", "name", "sshHost")
CLAUDE_SSH_CONFIG_OPTIONAL_STRING_KEYS = ("sshIdentityFile", "startDirectory")
CLAUDE_SSH_CONFIG_OPTIONAL_KEYS = {
    *CLAUDE_SSH_CONFIG_REQUIRED_STRING_KEYS,
    *CLAUDE_SSH_CONFIG_OPTIONAL_STRING_KEYS,
    "sshPort",
}
CLAUDE_DESKTOP_PREFERENCE_KEYS: dict[str, type] = {"chromeExtensionEnabled": bool}
# Allowed values for skillOverrides per the Claude Code settings schema
# (https://code.claude.com/docs/en/settings.md): hide or collapse a bundled skill
# without editing its SKILL.md. Does not apply to plugin skills.
VALID_SKILL_OVERRIDE_VALUES = {"on", "name-only", "user-invocable-only", "off"}
# Managed per-repo settings keys from config/claude-settings.json repoSettings
# (repo name -> settings), written into <repo>/.claude/settings.json next to
# the managed hooks block. Value is the required JSON type. Keys a repo does
# not declare are preserved untouched, mirroring the global overlay semantics
# (e.g. autoMemoryEnabled false for Dobby workspaces, whose memory lives in the
# workspace itself rather than in Claude's per-project auto-memory).
CLAUDE_REPO_SETTINGS_KEYS: dict[str, type] = {"autoMemoryEnabled": bool}


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


def expand_home_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_home_path(repo, home).resolve()
    return (github_root / repo).resolve()


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
            if scope == "dormant":
                continue
            repos_raw = item.get("repos", [])
            if not isinstance(repos_raw, list):
                raise ValueError(f"{label}[{idx}] repos must be an array")
            repos = [str(repo).strip() for repo in repos_raw if str(repo).strip()]
            if scope == "repo" and not repos:
                raise ValueError(f"{label}[{idx}] repo scope needs repos")
            if scope == "global":
                repos = []
            src = Path(source_path)
            if not src.is_absolute():
                src = (root_dir / src).resolve()
            if not (src / "SKILL.md").is_file():
                raise ValueError(f"source missing SKILL.md for {skill}: {src}")
            items.append({"skill": skill, "scope": scope, "repos": repos, "source_abs": src})

    seen: set[str] = set()
    duplicates = sorted(
        f"{item['skill']}/{item['scope']}"
        for item in items
        if f"{item['skill']}/{item['scope']}" in seen or seen.add(f"{item['skill']}/{item['scope']}")
    )
    if duplicates:
        raise ValueError(f"duplicate skill+scope entries: {', '.join(duplicates)}")
    return items, root_dir


def load_repo_registry_entries(registry_file: Path) -> list[dict[str, Any]]:
    data = read_json_object(registry_file)
    raw_items = data.get("repos", [])
    if not isinstance(raw_items, list):
        raise ValueError("repo registry repos must be an array")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{idx}] must be an object")
        raw_path = ensure_str(item.get("path"), "path", "repos", idx)
        if raw_path in seen:
            raise ValueError(f"duplicate repo path: {raw_path}")
        seen.add(raw_path)
        instructions = item.get("model_instructions_file")
        if instructions is not None and (not isinstance(instructions, str) or not instructions.strip()):
            raise ValueError(f"repos[{idx}].model_instructions_file must be a non-empty string")
        identity_clients = item.get("model_instructions_clients")
        if identity_clients is None:
            identity_clients = ["codex", "claude", "copilot"] if instructions else []
        if (
            not isinstance(identity_clients, list)
            or not all(isinstance(client, str) for client in identity_clients)
        ):
            raise ValueError(f"repos[{idx}].model_instructions_clients must be an array of strings")
        entries.append(
            {
                "path": raw_path,
                "model_instructions_file": instructions,
                "model_instructions_clients": identity_clients,
            }
        )
    return entries


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
) -> set[Path]:
    touched_links: set[Path] = set()
    if not skills_dir.exists():
        return touched_links
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        if entry in desired_links or not any(is_relative_to(target, root) for root in managed_source_roots):
            continue
        print(f"PRUNE {entry}")
        if apply:
            entry.unlink()
        touched_links.add(entry)
    return touched_links


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


def repo_git_root(repo_root: Path) -> Path | None:
    if not repo_root.exists() or not repo_root.is_dir():
        return None
    return git_root_for(repo_root)


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


def discover_github_workspace_roots(github_root: Path) -> list[Path]:
    """Workspace paths Claude should trust under the local GitHub root.

    Claude's trust prompt is keyed to the selected project path, not just Git
    roots. Trust the GitHub root itself plus direct child directories so new or
    non-git workspaces do not prompt, and keep recursive Git repo discovery for
    nested repos.
    """
    if not github_root.is_dir():
        return []
    desired: set[Path] = {github_root.resolve()}
    for child in github_root.iterdir():
        if child.name in PRUNED_REPO_DIR_NAMES:
            continue
        if child.is_dir():
            desired.add(child.resolve())
    desired.update(discover_git_repo_roots(github_root))
    return sorted(desired, key=lambda path: str(path))


def repo_skill_dirs_for_prune(root_dir: Path, github_root: Path, repo_filters: set[Path]) -> set[Path]:
    dirs: set[Path] = set()
    if not repo_filters or root_dir.resolve() in repo_filters:
        dirs.add(root_dir / ".claude" / "skills")
    if github_root.is_dir():
        for repo_root in github_root.iterdir():
            actual_repo = repo_git_root(repo_root)
            if actual_repo is None:
                continue
            if repo_filters and actual_repo not in repo_filters:
                continue
            dirs.add(actual_repo / ".claude" / "skills")
    return dirs


def render_skills(
    items: list[dict[str, Any]],
    root_dir: Path,
    claude_home: Path,
    github_root: Path,
    repo_filters: set[Path],
    apply: bool,
) -> None:
    home = Path.home()
    managed_source_roots = [
        (root_dir / "skills-source").resolve(),
        (root_dir / "plugins-source").resolve(),
    ]
    desired_global_links: dict[Path, Path] = {}
    desired_repo_links: dict[Path, Path] = {}
    touched_links: set[Path] = set()

    for item in items:
        skill = item["skill"]
        src = item["source_abs"]
        if item["scope"] == "global":
            dst = claude_home / "skills" / skill
            desired_global_links[dst] = src
            if sync_link(dst, src, apply):
                touched_links.add(dst)
            continue

        for repo in item["repos"]:
            repo_root = resolve_repo_root(repo, github_root, home)
            if repo_filters and repo_root not in repo_filters:
                continue
            actual_repo = repo_git_root(repo_root)
            if actual_repo is None:
                if repo_root.exists():
                    print(f"WARNING: skipping existing non-git path: {repo_root}", file=sys.stderr)
                continue
            if repo_filters and actual_repo not in repo_filters:
                continue
            dst = actual_repo / ".claude" / "skills" / skill
            desired_repo_links[dst] = src
            if sync_link(dst, src, apply):
                touched_links.add(dst)

    touched_links.update(
        prune_obsolete_links(
            claude_home / "skills",
            desired_global_links,
            managed_source_roots,
            apply,
        )
    )
    repo_skill_dirs = repo_skill_dirs_for_prune(root_dir, github_root, repo_filters)
    repo_skill_dirs.update(path.parent for path in desired_repo_links)
    for skills_dir in sorted(repo_skill_dirs):
        touched_links.update(
            prune_obsolete_links(
                skills_dir,
                desired_repo_links,
                managed_source_roots,
                apply,
            )
        )
    if apply:
        registered = register_current_codex_transaction_paths(touched_links)
        for git_root, item in sorted(registered.items()):
            print(f"REGISTER CODEX STOP {git_root}: {' '.join(sorted(item.paths))}")


def trusted_workspaces(root_dir: Path, github_root: Path, extra: list[Path]) -> list[str]:
    desired: set[Path] = set()
    control_plane_repo = git_root_for(root_dir)
    if control_plane_repo is not None:
        desired.add(control_plane_repo)
    desired.update(discover_github_workspace_roots(github_root))
    desired.update(path.resolve() for path in extra if path.exists())
    return [str(path) for path in sorted(desired, key=lambda item: str(item))]


def merge_string_list(existing: Any, desired: list[str], *, prune: set[str] | None = None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    prune = prune or set()
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, str) or not item.strip():
                continue
            value = str(Path(item).expanduser().resolve())
            if value in prune or value in seen:
                continue
            seen.add(value)
            merged.append(value)
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


def remove_hook_commands(hooks: dict[str, Any], event_name: str, commands: list[str]) -> None:
    current = hooks.get(event_name)
    if not isinstance(current, list):
        return
    filtered: list[Any] = []
    for entry in current:
        if not isinstance(entry, dict):
            filtered.append(entry)
            continue
        entry_hooks = entry.get("hooks")
        if not isinstance(entry_hooks, list):
            filtered.append(entry)
            continue
        next_hooks = [
            hook
            for hook in entry_hooks
            if not (isinstance(hook, dict) and hook.get("command") in commands)
        ]
        if next_hooks:
            filtered.append({**entry, "hooks": next_hooks})
    if filtered:
        hooks[event_name] = filtered
    else:
        hooks.pop(event_name, None)


UNWANTED_CLAUDE_HOOK_COMMAND_SUBSTRINGS = ("herdr", "herdr-agent-state.sh")


def remove_hook_commands_containing(
    hooks: dict[str, Any],
    substrings: tuple[str, ...],
) -> None:
    lowered = tuple(item.lower() for item in substrings)
    for event_name, current in list(hooks.items()):
        if not isinstance(current, list):
            continue
        filtered_entries: list[Any] = []
        for entry in current:
            if not isinstance(entry, dict):
                filtered_entries.append(entry)
                continue
            entry_hooks = entry.get("hooks")
            if not isinstance(entry_hooks, list):
                filtered_entries.append(entry)
                continue
            filtered_hooks = []
            for hook in entry_hooks:
                command = hook.get("command") if isinstance(hook, dict) else None
                command_lower = command.lower() if isinstance(command, str) else ""
                if command_lower and any(item in command_lower for item in lowered):
                    continue
                filtered_hooks.append(hook)
            if filtered_hooks:
                filtered_entries.append({**entry, "hooks": filtered_hooks})
        if filtered_entries:
            hooks[event_name] = filtered_entries
        else:
            hooks.pop(event_name, None)


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


def repo_claude_guidance_content(repo_root: Path, model_instructions_file: str | None) -> str:
    """Build the managed .claude/CLAUDE.md body.

    The identity prompt (Codex `model_instructions_file`, relative to `.codex/`) is imported
    first so Claude sees it before the operational router, mirroring Codex's system-prompt
    then AGENTS.md order. The import path is relative to `.claude/CLAUDE.md`.
    """
    lines: list[str] = []
    if model_instructions_file:
        source = (repo_root / ".codex" / model_instructions_file).resolve()
        if not source.is_file():
            raise ValueError(f"model_instructions_file for {repo_root} does not exist: {source}")
        rel = os.path.relpath(str(source), str(repo_root / ".claude"))
        lines.append(f"@{rel}")
    lines.append(REPO_CLAUDE_IMPORT)
    return "\n".join(lines) + "\n"


def is_managed_claude_guidance(content: str) -> bool:
    stripped = [line.strip() for line in content.splitlines() if line.strip()]
    return bool(stripped) and all(line.startswith("@../") for line in stripped)


def render_repo_claude_guidance(
    repo_root: Path,
    apply: bool,
    model_instructions_file: str | None = None,
) -> None:
    agents_file = repo_root / "AGENTS.md"
    if not agents_file.is_file():
        print(f"SKIP {repo_root} (.claude/CLAUDE.md: no AGENTS.md)")
        return

    target = repo_root / ".claude" / "CLAUDE.md"
    desired = repo_claude_guidance_content(repo_root, model_instructions_file)
    label = "imports ../AGENTS.md" + (" + identity prompt" if model_instructions_file else "")
    if target.is_symlink() and resolved_target(target) == agents_file.resolve():
        if model_instructions_file:
            print(
                f"WARNING: {target} is a symlink to AGENTS.md and cannot carry the identity import; "
                "replace it with a managed import file",
                file=sys.stderr,
            )
            return
        print(f"UNCHANGED {target} (symlink to AGENTS.md)")
        return
    if target.is_file():
        current = target.read_text(encoding="utf-8")
        if current == desired:
            print(f"UNCHANGED {target} ({label})")
            return
        if not is_managed_claude_guidance(current):
            print(
                f"WARNING: skipping existing Claude guidance without {REPO_CLAUDE_IMPORT}: {target}",
                file=sys.stderr,
            )
            return
    elif target.exists() or target.is_symlink():
        print(f"WARNING: skipping unsupported Claude guidance path: {target}", file=sys.stderr)
        return

    print(f"SYNC {target} ({label})")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desired, encoding="utf-8")


def render_repo_claude_guidance_files(
    repos: list[dict[str, Any]],
    github_root: Path,
    repo_filters: set[Path],
    apply: bool,
) -> None:
    home = Path.home()
    for entry in repos:
        repo_root = resolve_repo_root(entry["path"], github_root, home)
        if repo_filters and repo_root not in repo_filters:
            continue
        actual_repo = repo_git_root(repo_root)
        if actual_repo is None:
            if repo_root.exists():
                print(f"WARNING: skipping existing non-git path: {repo_root}", file=sys.stderr)
            continue
        if repo_filters and actual_repo not in repo_filters:
            continue
        instructions = (
            entry.get("model_instructions_file")
            if "claude" in entry.get("model_instructions_clients", [])
            else None
        )
        render_repo_claude_guidance(actual_repo, apply, instructions)


def load_claude_settings_overlay(overlay_file: Path) -> dict[str, Any]:
    """Load and validate the managed global Claude settings overlay.

    Returns a mapping of overlay key -> validated value. A missing file yields an
    empty overlay so the renderer is a no-op when nothing is managed. Validation
    is strict and actionable so a malformed overlay fails the bootstrap instead
    of silently shipping bad settings.
    """
    if not overlay_file.exists():
        return {}
    data = read_json_object(overlay_file)
    overlay: dict[str, Any] = {}
    label = overlay_file

    enabled = data.get("enabledPlugins")
    if enabled is not None:
        if not isinstance(enabled, dict):
            raise ValueError(f"{label}: enabledPlugins must be an object")
        for key, value in enabled.items():
            if not isinstance(value, bool):
                raise ValueError(
                    f"{label}: enabledPlugins[{key!r}] must be a boolean (got {type(value).__name__})"
                )
        overlay["enabledPlugins"] = dict(enabled)

    overrides = data.get("skillOverrides")
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise ValueError(f"{label}: skillOverrides must be an object")
        for key, value in overrides.items():
            if value not in VALID_SKILL_OVERRIDE_VALUES:
                raise ValueError(
                    f"{label}: skillOverrides[{key!r}] must be one of "
                    f"{sorted(VALID_SKILL_OVERRIDE_VALUES)} (got {value!r})"
                )
        overlay["skillOverrides"] = dict(overrides)

    repo_settings = data.get("repoSettings")
    if repo_settings is not None:
        if not isinstance(repo_settings, dict):
            raise ValueError(f"{label}: repoSettings must be an object")
        validated: dict[str, Any] = {}
        for repo_name, repo_keys in repo_settings.items():
            if not isinstance(repo_keys, dict):
                raise ValueError(f"{label}: repoSettings[{repo_name!r}] must be an object")
            for key, value in repo_keys.items():
                expected = CLAUDE_REPO_SETTINGS_KEYS.get(key)
                if expected is None:
                    raise ValueError(
                        f"{label}: repoSettings[{repo_name!r}][{key!r}] is not a managed key "
                        f"(allowed: {sorted(CLAUDE_REPO_SETTINGS_KEYS)})"
                    )
                if not isinstance(value, expected):
                    raise ValueError(
                        f"{label}: repoSettings[{repo_name!r}][{key!r}] must be "
                        f"{expected.__name__} (got {type(value).__name__})"
                    )
            validated[repo_name] = dict(repo_keys)
        overlay["repoSettings"] = validated

    desktop_preferences = data.get("desktopPreferences")
    if desktop_preferences is not None:
        if not isinstance(desktop_preferences, dict):
            raise ValueError(f"{label}: desktopPreferences must be an object")
        validated_preferences: dict[str, Any] = {}
        for key, value in desktop_preferences.items():
            expected = CLAUDE_DESKTOP_PREFERENCE_KEYS.get(key)
            if expected is None:
                raise ValueError(
                    f"{label}: desktopPreferences[{key!r}] is not a managed key "
                    f"(allowed: {sorted(CLAUDE_DESKTOP_PREFERENCE_KEYS)})"
                )
            if not isinstance(value, expected):
                raise ValueError(
                    f"{label}: desktopPreferences[{key!r}] must be "
                    f"{expected.__name__} (got {type(value).__name__})"
                )
            validated_preferences[key] = value
        overlay["desktopPreferences"] = validated_preferences

    ssh_configs = data.get("sshConfigs")
    if ssh_configs is not None:
        if not isinstance(ssh_configs, list):
            raise ValueError(f"{label}: sshConfigs must be an array")
        validated_configs: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for idx, item in enumerate(ssh_configs):
            if not isinstance(item, dict):
                raise ValueError(f"{label}: sshConfigs[{idx}] must be an object")
            unknown = sorted(set(item) - CLAUDE_SSH_CONFIG_OPTIONAL_KEYS)
            if unknown:
                raise ValueError(f"{label}: sshConfigs[{idx}] has unmanaged key(s): {unknown}")
            config: dict[str, Any] = {}
            for key in CLAUDE_SSH_CONFIG_REQUIRED_STRING_KEYS:
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{label}: sshConfigs[{idx}][{key!r}] must be a non-empty string")
                config[key] = value.strip()
            for key in CLAUDE_SSH_CONFIG_OPTIONAL_STRING_KEYS:
                if key not in item:
                    continue
                value = item[key]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{label}: sshConfigs[{idx}][{key!r}] must be a non-empty string")
                config[key] = value.strip()
            if "sshPort" in item:
                value = item["sshPort"]
                if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 65535:
                    raise ValueError(f"{label}: sshConfigs[{idx}]['sshPort'] must be an integer from 1 to 65535")
                config["sshPort"] = value
            config_id = config["id"]
            if config_id in seen_ids:
                raise ValueError(f"{label}: duplicate sshConfigs id: {config_id}")
            seen_ids.add(config_id)
            validated_configs.append(config)
        overlay["sshConfigs"] = validated_configs

    return overlay


def merge_object_list_by_id(existing: Any, managed: list[dict[str, Any]]) -> list[Any]:
    """Merge settings arrays where entries are keyed by an ``id`` field.

    Existing user entries are preserved. If a managed entry shares an id with an
    existing entry, the managed entry replaces it in place so bootstrap repairs
    drift without reordering unrelated manual SSH connections.
    """
    managed_by_id = {entry["id"]: entry for entry in managed}
    emitted_managed_ids: set[str] = set()
    merged: list[Any] = []

    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                item_id = item["id"]
                if item_id in managed_by_id:
                    merged.append(managed_by_id[item_id])
                    emitted_managed_ids.add(item_id)
                    continue
            merged.append(item)

    for item in managed:
        item_id = item["id"]
        if item_id not in emitted_managed_ids:
            merged.append(item)
            emitted_managed_ids.add(item_id)

    return merged


def apply_settings_overlay(desired: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Deep-merge managed overlay dict-keys into ``desired`` settings in place.

    For each managed key the overlay declares, existing entries are preserved and
    overlay entries win per sub-key, so a fresh machine renders exactly the
    overlay while machines with extra manual entries keep them. Keys that merge to
    an empty object are not written, avoiding noise keys like ``skillOverrides: {}``.
    """
    for key in CLAUDE_SETTINGS_DICT_OVERLAY_KEYS:
        managed = overlay.get(key)
        if not managed:
            continue
        existing = desired.get(key)
        existing = dict(existing) if isinstance(existing, dict) else {}
        existing.update(managed)
        if existing:
            desired[key] = existing

    for key in CLAUDE_SETTINGS_LIST_BY_ID_OVERLAY_KEYS:
        managed = overlay.get(key)
        if not managed:
            continue
        desired[key] = merge_object_list_by_id(desired.get(key), managed)


def build_settings(
    data: dict[str, Any],
    trusted: list[str],
    skip_yolo: bool,
    overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    desired = dict(data)
    desired.setdefault("$schema", "https://json.schemastore.org/claude-code-settings.json")
    for key, value in DEFAULT_CLAUDE_SCALAR_SETTINGS.items():
        desired.setdefault(key, value)

    permissions = desired.get("permissions")
    permissions = dict(permissions) if isinstance(permissions, dict) else {}
    allow = merge_literal_string_list(permissions.get("allow"), DEFAULT_ALLOW_RULES)
    permissions["allow"] = allow
    legacy_control_plane_dirs = {str((Path.home() / ".agents").resolve())}
    permissions["additionalDirectories"] = merge_string_list(
        permissions.get("additionalDirectories"),
        trusted,
        prune=legacy_control_plane_dirs,
    )
    if not skip_yolo:
        permissions["defaultMode"] = "bypassPermissions"
        permissions["skipDangerousModePermissionPrompt"] = True
    desired["permissions"] = permissions

    if not skip_yolo:
        for flag, value in YOLO_ACCEPTANCE_FLAGS.items():
            desired[flag] = value

    # Always strip Claude Code's built-in commit/PR workflow instructions and the
    # git-status snapshot from the system prompt: this machine auto-commits,
    # rebases, and pushes via the Stop hook and its guidance forbids manual git, so
    # the defaults only mislead the agent.
    # https://code.claude.com/docs/en/settings (includeGitInstructions)
    desired["includeGitInstructions"] = False

    hooks = desired.get("hooks")
    hooks = dict(hooks) if isinstance(hooks, dict) else {}
    legacy_pre_tool_command = (
        "printf '%s\\n' "
        "'{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\","
        "\"permissionDecisionReason\":\"YOLO mode\"}}'"
    )
    legacy_permission_command = (
        "printf '%s\\n' "
        "'{\"hookSpecificOutput\":{\"hookEventName\":\"PermissionRequest\",\"decision\":{\"behavior\":\"allow\"}}}'"
    )
    remove_hook_commands(hooks, "PreToolUse", [legacy_pre_tool_command])
    remove_hook_commands(hooks, "PermissionRequest", [legacy_permission_command])
    remove_hook_commands_containing(hooks, UNWANTED_CLAUDE_HOOK_COMMAND_SUBSTRINGS)
    entries = {
        "Stop": {"hooks": [{"type": "command", "command": CLAUDE_STOP_COMMAND, "timeout": 900}]},
    }
    for event_name, entry in entries.items():
        current = hooks.get(event_name)
        current_entries = current if isinstance(current, list) else []
        command = entry["hooks"][0]["command"]
        hooks[event_name] = current_entries
        remove_hook_commands(hooks, event_name, [command, *LEGACY_CLAUDE_STOP_COMMANDS])
        current = hooks.get(event_name)
        current_entries = current if isinstance(current, list) else []
        hooks[event_name] = current_entries + [entry]
    desired["hooks"] = hooks

    apply_settings_overlay(desired, overlay or {})
    return desired


def render_settings(
    settings_file: Path,
    trusted: list[str],
    apply: bool,
    skip_yolo: bool,
    overlay: dict[str, Any] | None = None,
) -> None:
    data = read_json_object(settings_file)
    desired = build_settings(data, trusted, skip_yolo, overlay)

    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return
    print(f"SYNC {settings_file} (permissions, hooks, plugins)")
    if not apply:
        return
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def render_desktop_config(config_file: Path, overlay: dict[str, Any], apply: bool) -> None:
    preferences_overlay = overlay.get("desktopPreferences")
    if not preferences_overlay:
        print(f"UNCHANGED {config_file} (desktop preferences)")
        return

    data = read_json_object(config_file)
    desired = dict(data)
    preferences = desired.get("preferences")
    preferences = dict(preferences) if isinstance(preferences, dict) else {}
    preferences.update(preferences_overlay)
    desired["preferences"] = preferences

    if desired == data:
        print(f"UNCHANGED {config_file} (desktop preferences)")
        return
    print(f"SYNC {config_file} (desktop preferences)")
    if not apply:
        return
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(desired, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# Events whose Claude hooks are rendered per-repo from the shared hook registry.
CLAUDE_REPO_HOOK_EVENTS = ("SessionStart", "UserPromptSubmit")


def claude_hook_repos(hooks_registry: dict[str, Any]) -> list[str]:
    """Repos that have at least one claude-enabled, repo-scoped managed hook."""
    repos: list[str] = []
    seen: set[str] = set()
    for hook in hooks_registry.get("managed_hooks", []):
        if not isinstance(hook, dict) or hook.get("scope") != "repo":
            continue
        if "claude" not in (hook.get("runtimes") or []):
            continue
        for repo in hook.get("repos", []):
            name = str(repo).strip()
            if name and name not in seen:
                seen.add(name)
                repos.append(name)
    return repos


def _is_managed_claude_hook(hook: Any) -> bool:
    return (
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and (
            "/.agents/hooks/scripts/" in hook["command"]
            or "/GitHub/agents/hooks/scripts/" in hook["command"]
        )
        and "--runtime claude" in hook["command"]
    )


def render_repo_hook_settings(
    repo_root: Path,
    hooks_registry: dict[str, Any],
    apply: bool,
    repo_settings: dict[str, Any] | None = None,
) -> None:
    """Merge rendered Claude hooks into ``<repo>/.claude/settings.json``.

    Mirrors how Codex writes ``<repo>/.codex/hooks.json``, but as a hooks block
    inside the project settings the Claude Agent SDK loads when run with
    ``cwd = repo`` and ``settingSources`` including ``project`` (the mobile-gateway
    Claude runtime, and interactive Claude Code in that repo).

    ``repo_settings`` is the overlay's ``repoSettings`` mapping; the entry for
    this repo's name (validated managed keys only) is written alongside the
    hooks so per-repo Claude behavior stays reproducible from the control plane.
    """
    rendered = render_claude_hooks(hooks_registry, repo_name=repo_root.name).get(
        "hooks", {}
    )
    settings_file = repo_root / ".claude" / "settings.json"
    data = read_json_object(settings_file)
    desired = dict(data)
    desired.setdefault(
        "$schema", "https://json.schemastore.org/claude-code-settings.json"
    )

    hooks = desired.get("hooks")
    hooks = dict(hooks) if isinstance(hooks, dict) else {}

    # Idempotent + prune: drop any previously-managed Claude lifecycle hooks from
    # the events we own, then add the freshly rendered entries. Other hooks and
    # settings keys in the file are preserved untouched.
    for event_name in CLAUDE_REPO_HOOK_EVENTS:
        current = hooks.get(event_name)
        current = current if isinstance(current, list) else []
        pruned: list[Any] = []
        for entry in current:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                pruned.append(entry)
                continue
            kept = [h for h in entry["hooks"] if not _is_managed_claude_hook(h)]
            if kept:
                pruned.append({**entry, "hooks": kept})
        if pruned:
            hooks[event_name] = pruned
        else:
            hooks.pop(event_name, None)

    for event_name, entries in rendered.items():
        existing = hooks.get(event_name)
        existing = existing if isinstance(existing, list) else []
        hooks[event_name] = existing + list(entries)

    if hooks:
        desired["hooks"] = hooks
    else:
        desired.pop("hooks", None)

    for key, value in ((repo_settings or {}).get(repo_root.name) or {}).items():
        desired[key] = value

    if desired == data:
        print(f"UNCHANGED {settings_file}")
        return
    print(f"SYNC {settings_file} (claude hooks, settings)")
    if not apply:
        return
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def render_repo_hooks(
    hooks_registry_file: Path,
    github_root: Path,
    repo_filters: set[Path],
    apply: bool,
    repo_settings: dict[str, Any] | None = None,
) -> None:
    if not hooks_registry_file.is_file():
        print(
            f"WARNING: hooks registry missing, skipping per-repo Claude hooks: {hooks_registry_file}",
            file=sys.stderr,
        )
        return
    hooks_registry = load_hooks_registry(hooks_registry_file)
    home = Path.home()
    # Union of hook-managed repos and repoSettings repos, so a managed settings
    # key still renders for a repo that has no managed hooks.
    repos = list(claude_hook_repos(hooks_registry))
    repos.extend(name for name in sorted(repo_settings or {}) if name not in repos)
    for repo in repos:
        repo_root = resolve_repo_root(repo, github_root, home)
        actual_repo = repo_git_root(repo_root)
        if actual_repo is None:
            if repo_root.exists():
                print(
                    f"WARNING: skipping existing non-git path: {repo_root}",
                    file=sys.stderr,
                )
            continue
        if repo_filters and actual_repo not in repo_filters:
            continue
        render_repo_hook_settings(actual_repo, hooks_registry, apply, repo_settings)


def render_workspace_trust(claude_json_file: Path, trusted: list[str], apply: bool) -> None:
    """Reconcile Claude's mutable runtime state without replacing its file.

    This pre-accepts managed workspaces and disables Claude's independent
    automatic installer so guarded package maintenance remains the only
    unattended update lane. Claude owns ~/.claude.json, so merge in place and
    never create it from scratch.
    """
    if not claude_json_file.exists():
        print(f"SKIP workspace trust: {claude_json_file} missing (start Claude once first)")
        return
    data = read_json_object(claude_json_file)
    projects = data.get("projects")
    projects = dict(projects) if isinstance(projects, dict) else {}

    seeded: list[str] = []
    for path in trusted:
        entry = projects.get(path)
        entry = dict(entry) if isinstance(entry, dict) else {}
        already = entry.get("hasTrustDialogAccepted") is True and entry.get("hasCompletedProjectOnboarding") is True
        if already:
            continue
        entry["hasTrustDialogAccepted"] = True
        entry["hasCompletedProjectOnboarding"] = True
        projects[path] = entry
        seeded.append(path)

    auto_updates_changed = data.get("autoUpdates") is not False
    if auto_updates_changed:
        data["autoUpdates"] = False

    if not seeded and not auto_updates_changed:
        print(f"UNCHANGED {claude_json_file} (workspace trust and auto-updates)")
        return
    print(
        f"SYNC {claude_json_file} "
        f"(workspace trust: {len(seeded)} workspace(s), autoUpdates=false)"
    )
    if not apply:
        return
    data["projects"] = projects
    claude_json_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def launcher_text(real_cli_path: Path) -> str:
    real_cli = shlex.quote(str(real_cli_path))
    return f"""#!/usr/bin/env bash
set -euo pipefail

default_real_cli={real_cli}
real_cli="${{CLAUDE_REAL_BIN:-$default_real_cli}}"
export DISABLE_AUTOUPDATER="${{DISABLE_AUTOUPDATER:-1}}"
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


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _shell_command(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def shell_home_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(Path.home().resolve())
    except ValueError:
        return str(path)
    return "${HOME}/" + rel.as_posix()


def shell_quote_command_part(part: str) -> str:
    if part.startswith("${HOME}/"):
        return '"' + part.replace('"', '\\"') + '"'
    return shlex.quote(part)


def shell_command_preserving_home(parts: list[str]) -> str:
    return " ".join(shell_quote_command_part(part) for part in parts)


def expand_dev_server_runtime_value(value: str, github_root: Path, repo_root: Path) -> str:
    github_root_value = shell_home_path(github_root)
    repo_root_value = shell_home_path(repo_root)
    return (
        value.replace("{github_root}", github_root_value)
        .replace("{repo_root}", repo_root_value)
    )


def preview_command_parts(
    server: dict[str, Any],
    preview_runner: Path,
    github_root: Path,
    repo_root: Path,
) -> list[str]:
    wrapped = [
        "python3",
        shell_home_path(preview_runner),
        "--host",
        server["host"],
        "--port",
        str(server["port"]),
        "--",
        expand_dev_server_runtime_value(server["runtimeExecutable"], github_root, repo_root),
        *[
            expand_dev_server_runtime_value(arg, github_root, repo_root)
            for arg in server["runtimeArgs"]
        ],
    ]
    return ["/bin/bash", "-lc", shell_command_preserving_home(wrapped)]


def render_claude_preview_config(
    server: dict[str, Any],
    preview_runner: Path,
    github_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    command_parts = preview_command_parts(server, preview_runner, github_root, repo_root)
    return {
        "name": server["name"],
        "runtimeExecutable": command_parts[0],
        "runtimeArgs": command_parts[1:],
        "port": server["port"],
        "autoPort": False,
    }


def load_dev_servers(registry_file: Path) -> list[dict[str, Any]]:
    data = read_json_object(registry_file)
    raw_items = data.get("managed_dev_servers", [])
    if not isinstance(raw_items, list):
        raise ValueError("managed_dev_servers must be an array")
    entries: list[dict[str, Any]] = []
    seen_ports: dict[int, str] = {}
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise ValueError(f"managed_dev_servers[{idx}] must be an object")
        repo = ensure_str(item.get("repo"), "repo", "managed_dev_servers", idx)
        servers_raw = item.get("servers", [])
        if not isinstance(servers_raw, list) or not servers_raw:
            raise ValueError(f"managed_dev_servers[{idx}] needs a non-empty servers array")
        if len(servers_raw) != 1:
            raise ValueError(
                f"managed_dev_servers[{idx}] must define exactly one agent preview server"
            )
        servers: list[dict[str, Any]] = []
        label = f"managed_dev_servers[{idx}].servers"
        for sidx, server in enumerate(servers_raw):
            if not isinstance(server, dict):
                raise ValueError(f"{label}[{sidx}] must be an object")
            name = ensure_str(server.get("name"), "name", label, sidx)
            runtime = ensure_str(server.get("runtimeExecutable"), "runtimeExecutable", label, sidx)
            host = str(server.get("host", "127.0.0.1")).strip() or "127.0.0.1"
            args_raw = server.get("runtimeArgs", [])
            if not isinstance(args_raw, list) or not all(isinstance(arg, str) for arg in args_raw):
                raise ValueError(f"{label}[{sidx}] runtimeArgs must be an array of strings")
            port = server.get("port")
            if not isinstance(port, int) or isinstance(port, bool):
                raise ValueError(f"{label}[{sidx}] port must be an integer")
            if port in seen_ports:
                raise ValueError(f"{label}[{sidx}] port {port} duplicates {seen_ports[port]}")
            seen_ports[port] = f"{repo}/{name}"
            # The `port`/`host` fields are the single source of truth. The dev command
            # must reference them through {port}/{host} placeholders instead of hardcoding
            # the literal, so the wrapper's reuse check and the server's actual bind can
            # never drift apart. Reject a hardcoded port literal to keep that guarantee.
            port_token = str(port)
            for arg in args_raw:
                if port_token in arg and "{port}" not in arg:
                    raise ValueError(
                        f"{label}[{sidx}] hardcodes port {port} in runtimeArgs; "
                        "use the {port} placeholder so the port stays single-source"
                    )
            runtime_args = [
                arg.replace("{port}", port_token).replace("{host}", host) for arg in args_raw
            ]
            config: dict[str, Any] = {
                "name": name,
                "host": host,
                "runtimeExecutable": runtime,
                "runtimeArgs": runtime_args,
                "port": port,
                "autoPort": False,
            }
            if "autoPort" in server:
                auto_port = server.get("autoPort")
                if not isinstance(auto_port, bool):
                    raise ValueError(f"{label}[{sidx}] autoPort must be a boolean")
                if auto_port:
                    raise ValueError(
                        f"{label}[{sidx}] autoPort must be false for shared agent previews"
                    )
            servers.append(config)
        entries.append({"repo": repo, "servers": servers})

    seen: set[str] = set()
    duplicates = sorted(
        entry["repo"] for entry in entries if entry["repo"] in seen or seen.add(entry["repo"])
    )
    if duplicates:
        raise ValueError(f"duplicate dev-server repo entries: {', '.join(duplicates)}")
    return entries


def render_launch_config(target: Path, desired: dict[str, Any], apply: bool) -> None:
    existing = read_json_object(target)
    if existing == desired:
        print(f"UNCHANGED {target}")
        return
    print(f"SYNC {target} (dev-server launch config)")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def render_launch_configs(
    entries: list[dict[str, Any]],
    github_root: Path,
    repo_filters: set[Path],
    preview_runner: Path,
    apply: bool,
) -> None:
    home = Path.home()
    for entry in entries:
        repo_root = resolve_repo_root(entry["repo"], github_root, home)
        if repo_filters and repo_root not in repo_filters:
            continue
        actual_repo = repo_git_root(repo_root)
        if actual_repo is None:
            if repo_root.exists():
                print(f"WARNING: skipping existing non-git path: {repo_root}", file=sys.stderr)
            continue
        if repo_filters and actual_repo not in repo_filters:
            continue
        desired = {
            "version": LAUNCH_CONFIG_VERSION,
            "configurations": [
                render_claude_preview_config(server, preview_runner, github_root, actual_repo)
                for server in entry["servers"]
            ],
        }
        target = actual_repo / ".claude" / "launch.json"
        render_launch_config(target, desired, apply)


def codex_environment_text(
    entry: dict[str, Any],
    preview_runner: Path,
    github_root: Path,
    repo_root: Path,
) -> str:
    actions: list[str] = []
    for server in entry["servers"]:
        command = _shell_command(
            preview_command_parts(server, preview_runner, github_root, repo_root)
        )
        actions.append(
            "\n".join(
                [
                    "[[actions]]",
                    f"name = {_toml_string(server['name'])}",
                    'icon = "run"',
                    f"command = {_toml_string(command)}",
                ]
            )
        )

    return "\n".join(
        [
            "# THIS IS AUTOGENERATED. DO NOT EDIT MANUALLY",
            "version = 1",
            f"name = {_toml_string(entry['repo'])}",
            "",
            "[setup]",
            'script = ""',
            "",
            "\n\n".join(actions),
            "",
        ]
    )


def render_codex_environment_config(target: Path, desired: str, apply: bool) -> None:
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    if existing == desired:
        print(f"UNCHANGED {target}")
        return
    print(f"SYNC {target} (Codex agent preview environment)")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desired, encoding="utf-8")


def render_codex_environment_configs(
    entries: list[dict[str, Any]],
    github_root: Path,
    repo_filters: set[Path],
    preview_runner: Path,
    apply: bool,
) -> None:
    home = Path.home()
    for entry in entries:
        repo_root = resolve_repo_root(entry["repo"], github_root, home)
        if repo_filters and repo_root not in repo_filters:
            continue
        actual_repo = repo_git_root(repo_root)
        if actual_repo is None:
            if repo_root.exists():
                print(f"WARNING: skipping existing non-git path: {repo_root}", file=sys.stderr)
            continue
        if repo_filters and actual_repo not in repo_filters:
            continue
        target = actual_repo / ".codex" / "environments" / "environment.toml"
        render_codex_environment_config(
            target,
            codex_environment_text(entry, preview_runner, github_root, actual_repo),
            apply,
        )


def load_repo_mcp_entries(repo_registry_file: Path) -> list[dict[str, Any]]:
    """Load the managed repo inventory used by the canonical MCP target matrix."""
    data = read_json_object(repo_registry_file)
    repos_raw = data.get("repos", [])
    if not isinstance(repos_raw, list):
        raise ValueError("repo registry repos must be an array")
    for idx, item in enumerate(repos_raw):
        if not isinstance(item, dict):
            raise ValueError(f"repos[{idx}] must be an object")
        ensure_str(item.get("path"), "path", "repos", idx)
    return repos_raw


def render_mcp_config(target: Path, desired: dict[str, Any], apply: bool) -> None:
    existing = read_json_object(target)
    if existing == desired:
        print(f"UNCHANGED {target}")
        return
    print(f"SYNC {target} (project MCP servers)")
    if not apply:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(desired, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def remove_mcp_config(target: Path, apply: bool) -> None:
    if not target.exists() and not target.is_symlink():
        return
    print(f"REMOVE {target} (project MCP servers)")
    if apply:
        target.unlink()


def render_mcp_configs(
    repo_entries: list[dict[str, Any]],
    mcp_registry_file: Path,
    github_root: Path,
    repo_filters: set[Path],
    apply: bool,
) -> None:
    catalog = load_mcp_catalog(mcp_registry_file, repo_entries)
    home = Path.home()
    for entry in repo_entries:
        repo_ref = str(entry["path"])
        repo_root = resolve_repo_root(repo_ref, github_root, home)
        if repo_filters and repo_root not in repo_filters:
            continue
        actual_repo = repo_git_root(repo_root)
        if actual_repo is None:
            if repo_root.exists():
                print(f"WARNING: skipping existing non-git path: {repo_root}", file=sys.stderr)
            continue
        if repo_filters and actual_repo not in repo_filters:
            continue
        servers = {
            name: claude_server_from_preset(name, preset)
            for name, preset in catalog.presets_for(repo_ref, "claude")
        }
        target = actual_repo / ".mcp.json"
        if not servers:
            remove_mcp_config(target, apply)
            continue
        desired = {"mcpServers": servers}
        render_mcp_config(target, desired, apply)


def run_sync(args: argparse.Namespace) -> None:
    registry_file = absolute_path(Path(args.registry_file).expanduser()).resolve()
    claude_home = absolute_path(Path(args.claude_home).expanduser()).resolve()
    github_root = absolute_path(Path(args.github_root).expanduser()).resolve()
    global_context_source = absolute_path(Path(args.global_context_source).expanduser()).resolve()
    global_context_target = output_path(Path(args.global_context_target).expanduser())
    claude_desktop_config = output_path(Path(args.claude_desktop_config).expanduser())
    launcher_target = output_path(Path(args.launcher_target).expanduser())
    real_cli_path = absolute_path(Path(args.real_cli_path).expanduser())
    preview_runner = absolute_path(Path(args.preview_runner).expanduser()).resolve()
    extra_trusted_workspaces = [Path(raw).expanduser().resolve() for raw in args.trusted_workspace if raw.strip()]

    items, root_dir = load_registry(registry_file)
    repo_filters = {
        resolve_repo_root(raw.strip(), github_root, Path.home())
        for raw in args.repo
        if raw.strip()
    }
    if not args.skip_skills:
        render_skills(
            items,
            root_dir,
            claude_home,
            github_root,
            repo_filters,
            args.apply,
        )

    trusted = trusted_workspaces(root_dir, github_root, extra_trusted_workspaces)
    if not args.skip_global_context:
        render_global_context(global_context_source, global_context_target, args.apply)
    overlay_file = absolute_path(Path(args.claude_settings_overlay).expanduser()).resolve()
    overlay = load_claude_settings_overlay(overlay_file)
    if not args.skip_desktop_config:
        render_desktop_config(claude_desktop_config, overlay, args.apply)
    if not args.skip_settings:
        render_settings(
            claude_home / "settings.json",
            trusted,
            args.apply,
            args.skip_yolo,
            overlay,
        )
    if not args.skip_repo_hooks:
        hooks_registry_file = absolute_path(
            Path(args.hooks_registry).expanduser()
        ).resolve()
        render_repo_hooks(
            hooks_registry_file,
            github_root,
            repo_filters,
            args.apply,
            overlay.get("repoSettings", {}),
        )
    if not args.skip_repo_guidance:
        repo_registry_file = absolute_path(Path(args.repo_registry).expanduser()).resolve()
        render_repo_claude_guidance_files(
            load_repo_registry_entries(repo_registry_file),
            github_root,
            repo_filters,
            args.apply,
        )
    if not args.skip_workspace_trust:
        if args.claude_json:
            claude_json = absolute_path(Path(args.claude_json).expanduser()).resolve()
        else:
            # ~/.claude.json sits beside the ~/.claude home; deriving it from
            # claude_home keeps tests isolated automatically (temp/.claude.json).
            claude_json = claude_home.parent / ".claude.json"
        render_workspace_trust(claude_json, trusted, args.apply)
    if not args.skip_launcher:
        render_launcher(launcher_target, real_cli_path, args.apply)
    if not args.skip_launch_configs:
        dev_servers_registry = absolute_path(Path(args.dev_servers_registry).expanduser()).resolve()
        dev_server_entries = load_dev_servers(dev_servers_registry)
        render_launch_configs(
            dev_server_entries,
            github_root,
            repo_filters,
            preview_runner,
            args.apply,
        )
        if not args.skip_codex_environments:
            render_codex_environment_configs(
                dev_server_entries,
                github_root,
                repo_filters,
                preview_runner,
                args.apply,
            )
    elif not args.skip_codex_environments:
        dev_servers_registry = absolute_path(Path(args.dev_servers_registry).expanduser()).resolve()
        render_codex_environment_configs(
            load_dev_servers(dev_servers_registry),
            github_root,
            repo_filters,
            preview_runner,
            args.apply,
        )
    if not args.skip_mcp_configs:
        mcp_presets_registry = absolute_path(Path(args.mcp_presets_registry).expanduser()).resolve()
        repo_registry_file = absolute_path(Path(args.repo_registry).expanduser()).resolve()
        render_mcp_configs(
            load_repo_mcp_entries(repo_registry_file),
            mcp_presets_registry,
            github_root,
            repo_filters,
            args.apply,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Claude Code global instructions, skills, settings/hooks, launcher, and per-repo agent preview configs."
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run).")
    parser.add_argument("--claude-home", default=str(DEFAULT_CLAUDE_HOME), help="Claude Code user directory.")
    parser.add_argument("--github-root", default=str(DEFAULT_GITHUB_ROOT), help="GitHub root to scan for trusted Git workspaces.")
    parser.add_argument("--trusted-workspace", action="append", default=[], help="Additional workspace path to trust.")
    parser.add_argument("--repo", action="append", default=[], help="Limit repo-local Claude skill sync to an exact repo path or repo name.")
    parser.add_argument("--global-context-source", default=str(DEFAULT_GLOBAL_CONTEXT_SOURCE), help="Source markdown file for global CLAUDE.md.")
    parser.add_argument("--global-context-target", default=str(DEFAULT_GLOBAL_CONTEXT_TARGET), help="Claude global CLAUDE.md target.")
    parser.add_argument("--claude-desktop-config", default=str(DEFAULT_CLAUDE_DESKTOP_CONFIG), help="Claude Desktop app config JSON target.")
    parser.add_argument("--launcher-target", default=str(DEFAULT_LAUNCHER_TARGET), help="Claude YOLO launcher target.")
    parser.add_argument("--real-cli-path", default=str(DEFAULT_REAL_CLI_PATH), help="Real Claude CLI binary path wrapped by launcher.")
    parser.add_argument("--skip-yolo", action="store_true", help="Do not render bypass-permission defaults.")
    parser.add_argument("--claude-json", default=None, help="Claude Code runtime config used to pre-accept workspace trust (defaults to <claude-home>/../.claude.json).")
    parser.add_argument("--skip-workspace-trust", action="store_true", help="Do not pre-accept the per-folder trust dialog for managed workspaces.")
    parser.add_argument("--skip-global-context", action="store_true", help="Do not render global CLAUDE.md.")
    parser.add_argument("--skip-desktop-config", action="store_true", help="Do not render Claude Desktop app config preferences.")
    parser.add_argument("--skip-settings", action="store_true", help="Do not render Claude settings.")
    parser.add_argument(
        "--claude-settings-overlay",
        default=str(DEFAULT_CLAUDE_SETTINGS_OVERLAY),
        help="Managed overlay JSON of Claude settings: global keys (enabledPlugins, skillOverrides, sshConfigs) merged into ~/.claude/settings.json, desktopPreferences merged into Claude Desktop config.json, plus repoSettings merged into <repo>/.claude/settings.json.",
    )
    parser.add_argument("--skip-launcher", action="store_true", help="Do not render Claude launcher.")
    parser.add_argument("--skip-skills", action="store_true", help="Do not render Claude skill links.")
    parser.add_argument(
        "--repo-registry",
        default=str(DEFAULT_REPO_REGISTRY),
        help="Canonical managed repo registry JSON for per-repo Claude guidance bridges.",
    )
    parser.add_argument(
        "--skip-repo-guidance",
        action="store_true",
        help="Do not render per-repo .claude/CLAUDE.md files that import AGENTS.md and, when the repo declares model_instructions_file, the identity prompt.",
    )
    parser.add_argument(
        "--hooks-registry",
        default=str(DEFAULT_HOOKS_REGISTRY),
        help="Canonical hook registry JSON for per-repo Claude lifecycle hooks.",
    )
    parser.add_argument(
        "--skip-repo-hooks",
        action="store_true",
        help="Do not render per-repo Claude lifecycle hooks (.claude/settings.json).",
    )
    parser.add_argument(
        "--dev-servers-registry",
        default=str(DEFAULT_DEV_SERVERS_REGISTRY),
        help="Canonical dev-server registry JSON for per-repo agent preview configs.",
    )
    parser.add_argument(
        "--preview-runner",
        default=str(DEFAULT_PREVIEW_RUNNER),
        help="Shared runner that starts a preview only when its fixed port is free.",
    )
    parser.add_argument(
        "--skip-launch-configs",
        action="store_true",
        help="Do not render per-repo dev-server launch configs (.claude/launch.json).",
    )
    parser.add_argument(
        "--skip-codex-environments",
        action="store_true",
        help="Do not render per-repo Codex environment action configs (.codex/environments/environment.toml).",
    )
    parser.add_argument(
        "--mcp-presets-registry",
        default=str(DEFAULT_MCP_PRESETS_REGISTRY),
        help="Canonical MCP target catalog rendered into per-repo Claude .mcp.json.",
    )
    parser.add_argument(
        "--skip-mcp-configs",
        action="store_true",
        help="Do not render per-repo Claude project MCP configs (.mcp.json).",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(_AGENTS_ROOT / "skills" / "registry.json"),
        help="Path to canonical skills registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_sync(args)
    except ValueError as exc:
        print(f"Claude sync failed: {exc}", file=sys.stderr)
        return 1
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute Claude changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
