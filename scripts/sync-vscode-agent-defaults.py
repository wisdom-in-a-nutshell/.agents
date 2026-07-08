#!/usr/bin/env python3
"""Sync managed VS Code Chat/Agent permission defaults.

This is a distinct surface from sync-copilot.py: that script manages the
standalone terminal `copilot` CLI (~/.copilot/*). This script manages VS
Code's own Chat/Agent extension defaults so a fresh session in the VS Code
Agents window / Chat view (including Copilot CLI sessions hosted inside VS
Code, e.g. over Remote-SSH) starts fully autonomous instead of silently
falling back to VS Code's built-in "Default Approvals" + interactive mode.

Two independent, best-effort targets, each skipped (not failed) when its
machine doesn't have the relevant surface installed:

- agent-host-config.json: the Copilot-CLI-in-VS-Code "agent host" runtime
  config. Lives wherever `~/.vscode-server` exists, i.e. the machine acting
  as a Remote-SSH *host* for VS Code Chat sessions.
- VS Code user settings.json: the real client-side VS Code settings file
  for whichever machine's own local VS Code GUI is running (the Remote-SSH
  *client*). Controls what a brand-new session's permission level/mode
  default to.

Both files are plain JSON (no comments) written by VS Code itself; this
script merges only the managed keys and leaves everything else untouched.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


AGENTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OVERLAY = AGENTS_ROOT / "config" / "vscode-agent-defaults.json"


class SyncError(RuntimeError):
    pass


def expand(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    if raw == "~":
        return home
    return Path(raw)


def load_overlay(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as f:
        content = f.read().strip()
    if not content:
        return {}
    data = json.loads(content)
    if not isinstance(data, dict):
        raise SyncError(f"expected a JSON object in {path}, got {type(data).__name__}")
    return data


def merge_managed_keys(
    existing: dict[str, Any],
    managed: dict[str, Any],
    remove: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Overlay managed top-level keys onto existing (and drop removed keys), reporting changes."""
    desired = dict(existing)
    changed: list[str] = []
    for key, value in managed.items():
        if key not in desired or desired[key] != value:
            changed.append(key)
        desired[key] = value
    for key in remove or []:
        if key in desired:
            del desired[key]
            changed.append(f"-{key}")
    return desired, changed


def sync_target(
    *,
    label: str,
    path: Path,
    only_if_parent_exists: Path,
    managed_keys: dict[str, Any],
    keys_remove: list[str] | None = None,
    apply: bool,
    check: bool,
) -> bool:
    """Returns True if the target is in the desired state (or was skipped)."""
    if not only_if_parent_exists.exists():
        print(f"SKIP ({label}): surface not present on this machine: {only_if_parent_exists}")
        return True

    try:
        existing = load_json_file(path)
    except (json.JSONDecodeError, SyncError) as exc:
        raise SyncError(f"failed to read {label} at {path}: {exc}") from exc

    desired, changed = merge_managed_keys(existing, managed_keys, keys_remove)

    if check:
        if changed:
            print(f"FAIL ({label}): {path} missing/mismatched managed keys: {', '.join(changed)}")
            return False
        print(f"OK ({label}): {path} matches managed keys")
        return True

    if not changed:
        print(f"UNCHANGED ({label}): {path}")
        return True

    print(f"{'SYNC' if apply else 'WOULD SYNC'} ({label}): {path} -> {', '.join(changed)}")
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(desired, f, indent="\t")
            f.write("\n")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply managed keys.")
    mode.add_argument("--check", action="store_true", help="Validate managed keys, no writes.")
    mode.add_argument("--dry-run", action="store_true", help="Show writes without applying (default).")
    parser.add_argument("--overlay", default=str(DEFAULT_OVERLAY), help="Canonical settings overlay.")
    parser.add_argument("--home", default=str(Path.home()), help="Override home directory (testing).")
    args = parser.parse_args(argv)

    apply = bool(args.apply)
    check = bool(args.check)

    home = Path(args.home).expanduser()
    overlay = load_overlay(Path(args.overlay))

    ok = True

    agent_host = overlay.get("agentHostConfig", {})
    if agent_host:
        ok &= sync_target(
            label="vscode-agent-host-config",
            path=expand(agent_host["path"], home),
            only_if_parent_exists=expand(agent_host["onlyIfParentExists"], home),
            managed_keys=agent_host.get("keys", {}),
            keys_remove=agent_host.get("keysRemove", []),
            apply=apply,
            check=check,
        )

    user_settings = overlay.get("vscodeUserSettings", {})
    if user_settings:
        ok &= sync_target(
            label="vscode-user-settings",
            path=expand(user_settings["path"], home),
            only_if_parent_exists=expand(user_settings["onlyIfParentExists"], home),
            managed_keys=user_settings.get("keys", {}),
            keys_remove=user_settings.get("keysRemove", []),
            apply=apply,
            check=check,
        )

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
