#!/usr/bin/env python3
"""Set Azure App Service app settings using reusable profiles or explicit targets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class Profile:
    name: str
    resource_group: str
    apps: List[str]
    env_file_hint: str
    notes: str


def _expand_home(path: str) -> str:
    if path == "~":
        return os.path.expanduser(path)
    if path.startswith("~/"):
        return os.path.expanduser(path)
    return path


def _parse_env_file(path: str) -> List[str]:
    settings: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                raise ValueError(f"Invalid env line (missing '='): {raw_line.rstrip()}")
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError(f"Invalid env line (empty key): {raw_line.rstrip()}")
            settings.append(f"{key}={value}")
    return settings


def _read_profiles(path: Path) -> Dict[str, Profile]:
    profiles: Dict[str, Profile] = {}
    if not path.exists():
        raise FileNotFoundError(f"Profiles file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = raw_line.split("\t")
        if len(parts) < 3:
            raise ValueError(
                "Invalid profile row (expected profile<TAB>resource_group<TAB>apps[...]): "
                f"{raw_line}"
            )

        name = parts[0].strip()
        if name == "profile":
            continue
        resource_group = parts[1].strip()
        apps_raw = parts[2].strip()
        env_file_hint = parts[3].strip() if len(parts) > 3 else ""
        notes = parts[4].strip() if len(parts) > 4 else ""

        if not name or not resource_group or not apps_raw:
            raise ValueError(f"Invalid profile row (missing required fields): {raw_line}")

        apps = [a.strip() for a in apps_raw.split(",") if a.strip()]
        if not apps:
            raise ValueError(f"Invalid profile row (no apps): {raw_line}")

        profiles[name] = Profile(
            name=name,
            resource_group=resource_group,
            apps=apps,
            env_file_hint=env_file_hint,
            notes=notes,
        )

    return profiles


def _collect_settings(args: argparse.Namespace) -> List[str]:
    settings: List[str] = []

    for pair in args.set:
        if "=" not in pair:
            raise ValueError(f"--set requires KEY=VALUE (got: {pair})")
        settings.append(pair)

    if args.env_file:
        settings.extend(_parse_env_file(args.env_file))

    # Preserve input order while deduping repeated keys by exact pair.
    deduped: List[str] = []
    seen = set()
    for pair in settings:
        if pair in seen:
            continue
        seen.add(pair)
        deduped.append(pair)
    return deduped


def _run(cmd: List[str], *, dry_run: bool) -> None:
    print("+", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _apply_settings(
    apps: Iterable[str],
    resource_group: str,
    settings: List[str],
    *,
    dry_run: bool,
) -> None:
    for app in apps:
        cmd = [
            "az",
            "webapp",
            "config",
            "appsettings",
            "set",
            "--name",
            app,
            "--resource-group",
            resource_group,
            "--settings",
            *settings,
            "--output",
            "none",
        ]
        _run(cmd, dry_run=dry_run)


def _restart_apps(apps: Iterable[str], resource_group: str, *, dry_run: bool) -> None:
    for app in apps:
        cmd = [
            "az",
            "webapp",
            "restart",
            "--name",
            app,
            "--resource-group",
            resource_group,
            "--output",
            "none",
        ]
        _run(cmd, dry_run=dry_run)


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    default_profiles = script_dir.parent / "references" / "profiles.tsv"

    parser = argparse.ArgumentParser(
        description="Set Azure Web App appsettings via shared profiles or explicit targets."
    )
    parser.add_argument(
        "--profile",
        help="Profile name from references/profiles.tsv.",
    )
    parser.add_argument(
        "--profiles-file",
        default=str(default_profiles),
        help=f"Profiles TSV path (default: {default_profiles})",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles and exit.",
    )
    parser.add_argument(
        "--app",
        action="append",
        default=[],
        help="Target app name (repeatable). Overrides profile apps when provided.",
    )
    parser.add_argument(
        "--resource-group",
        help="Azure resource group. Overrides profile resource group when provided.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        help="Setting to apply (KEY=VALUE). Repeatable.",
    )
    parser.add_argument(
        "--env-file",
        help="Path to .env-style file (KEY=VALUE per line).",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart target apps after setting appsettings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing.",
    )
    args = parser.parse_args()

    try:
        profiles = _read_profiles(Path(_expand_home(args.profiles_file)))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: failed to load profiles: {exc}", file=sys.stderr)
        return 2

    if args.list_profiles:
        print("Profiles:")
        for name in sorted(profiles):
            p = profiles[name]
            apps = ",".join(p.apps)
            hint = p.env_file_hint or "-"
            notes = p.notes or "-"
            print(
                f"  {p.name}\n"
                f"    resource_group: {p.resource_group}\n"
                f"    apps: {apps}\n"
                f"    env_file_hint: {hint}\n"
                f"    notes: {notes}"
            )
        return 0

    profile = None
    if args.profile:
        profile = profiles.get(args.profile)
        if profile is None:
            print(f"Error: unknown profile: {args.profile}", file=sys.stderr)
            return 2

    apps: List[str]
    if args.app:
        apps = [a.strip() for a in args.app if a.strip()]
    elif profile:
        apps = profile.apps
    else:
        apps = []

    resource_group = args.resource_group or (profile.resource_group if profile else "")

    if not apps:
        print(
            "Error: no target apps. Provide --app (repeatable) or --profile.",
            file=sys.stderr,
        )
        return 2

    if not resource_group:
        print(
            "Error: no resource group. Provide --resource-group or --profile.",
            file=sys.stderr,
        )
        return 2

    try:
        settings = _collect_settings(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not settings:
        print("Error: provide at least one --set or --env-file.", file=sys.stderr)
        return 2

    print(f"Target resource group: {resource_group}")
    print(f"Target apps: {', '.join(apps)}")
    if profile:
        print(f"Profile: {profile.name}")
        if profile.env_file_hint and not args.env_file:
            print(f"Hint: {profile.env_file_hint}")

    _apply_settings(apps, resource_group, settings, dry_run=args.dry_run)

    if args.restart:
        _restart_apps(apps, resource_group, dry_run=args.dry_run)
    else:
        print("Note: App Service may restart automatically on appsettings changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
