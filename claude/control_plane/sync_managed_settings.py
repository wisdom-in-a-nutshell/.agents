"""Render the canonical Claude managed-settings policy file into the OS-level path.

The macOS path `/Library/Application Support/ClaudeCode/managed-settings.json` is
the system-wide policy file Claude Code consults at startup (the "policySettings"
source). Anything in `enabledPlugins` here LOCKS the plugin name: when a daemon
session like the Claude.ai app's Code/Chat/Cowork tabs spawns ccd-cli with
`--plugin-dir <bundled-plugin>`, the daemon refuses to load the plugin if its
name appears in this lock list.

This sync runs the file install with sudo because the path is root-owned by
convention and we don't want to weaken the system permissions.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import (
    ControlPlaneError,
    claude_root,
    json_files_equal,
    load_json_file,
    main_guard,
    render_json,
    show_diff,
)


DEFAULT_MACOS_TARGET = "/Library/Application Support/ClaudeCode/managed-settings.json"
DEFAULT_LINUX_TARGET = "/etc/claude-code/managed-settings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the canonical Claude managed-settings policy file into the OS-level "
            "policy path (e.g. /Library/Application Support/ClaudeCode/managed-settings.json)."
        )
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show diffs only (default)",
    )
    parser.set_defaults(apply=False)

    default_target = (
        DEFAULT_MACOS_TARGET if sys.platform == "darwin" else DEFAULT_LINUX_TARGET
    )
    parser.add_argument(
        "--policy-target",
        default=default_target,
        help=f"Override the OS-level managed-settings.json target (default: {default_target})",
    )
    parser.add_argument(
        "--canonical-policy",
        default=str(claude_root() / "config" / "managed-settings.json"),
        help="Override canonical managed-settings source",
    )
    return parser.parse_args()


def policy_files_match(left: Path, right: Path) -> bool:
    if not left.exists():
        return False
    return json_files_equal(left, right)


def _sudo_available_noninteractive() -> bool:
    """Return True iff `sudo -n true` succeeds, i.e. sudo is cached/passwordless."""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def _has_tty() -> bool:
    """Return True iff the current process can prompt the user on a TTY."""
    try:
        return sys.stdin.isatty() and sys.stderr.isatty()
    except Exception:
        return False


def _claude_runtime_present() -> bool:
    """Return True when this machine appears to have a Claude runtime installed."""
    if shutil.which("claude"):
        return True
    if sys.platform == "darwin":
        for app_path in (
            Path("/Applications/Claude.app"),
            Path.home() / "Applications/Claude.app",
            Path("/Applications/Claude Code.app"),
            Path.home() / "Applications/Claude Code.app",
        ):
            if app_path.exists():
                return True
    return False


def install_with_sudo(rendered: Path, target: Path) -> None:
    """Install rendered file at the policy path using sudo.

    Refuses to run if sudo is not cached AND no TTY is attached, to avoid
    hanging the bootstrap chain in cron / auto-apply contexts.
    """
    if not _sudo_available_noninteractive() and not _has_tty():
        raise ControlPlaneError(
            f"Writing {target} requires sudo, but sudo is not cached and no TTY is "
            f"attached. Re-run interactively (e.g. "
            f"`bash claude/scripts/sync-managed-settings.sh --apply`) once to cache "
            f"sudo credentials, or pre-warm sudo before invoking the auto-apply chain."
        )

    target_str = str(target)
    target_parent = str(target.parent)

    subprocess.run(
        ["sudo", "/usr/bin/install", "-d", "-m", "0755", target_parent],
        check=True,
    )
    subprocess.run(
        ["sudo", "/usr/bin/install", "-m", "0644", str(rendered), target_str],
        check=True,
    )


def main() -> int:
    args = parse_args()
    policy_target = Path(args.policy_target)
    canonical_policy = Path(args.canonical_policy).expanduser().resolve()
    default_target = Path(
        DEFAULT_MACOS_TARGET if sys.platform == "darwin" else DEFAULT_LINUX_TARGET
    )

    if not str(args.policy_target).startswith("/"):
        raise ControlPlaneError("--policy-target must be an absolute path")
    if not Path(args.canonical_policy).is_absolute():
        raise ControlPlaneError("--canonical-policy must be an absolute path")
    if not canonical_policy.is_file():
        raise ControlPlaneError(f"Missing canonical policy file: {canonical_policy}")

    data = load_json_file(canonical_policy, label="canonical managed-settings file")
    if not isinstance(data, dict):
        raise ControlPlaneError(f"managed-settings root must be an object: {canonical_policy}")

    with tempfile.TemporaryDirectory() as temp_dir:
        rendered = Path(temp_dir) / "managed-settings.json"
        rendered.write_text(render_json(data), encoding="utf-8")

        print("=== Claude Managed Settings ===")
        if (
            policy_target == default_target
            and not policy_target.exists()
            and not _claude_runtime_present()
            and os.environ.get("CLAUDE_MANAGED_SETTINGS_REQUIRED") != "1"
        ):
            print(
                "SKIP: Claude runtime is not installed and the OS-level policy file "
                f"is absent: {policy_target}"
            )
            return 0

        show_diff(policy_target, rendered)

        if not args.apply:
            return 0

        if policy_files_match(policy_target, rendered):
            print(f"No change: {policy_target}")
            return 0

        # Try direct write first; fall back to sudo if permission denied.
        try:
            policy_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rendered, policy_target)
            os.chmod(policy_target, 0o644)
            print(f"Updated: {policy_target}")
        except PermissionError:
            install_with_sudo(rendered, policy_target)
            print(f"Updated (via sudo): {policy_target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
