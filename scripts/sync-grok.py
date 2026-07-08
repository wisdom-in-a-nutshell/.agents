#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import tomllib
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = AGENTS_ROOT / "config/grok-managed-config.toml"
DEFAULT_TARGET = Path.home() / ".grok/managed_config.toml"


def read_valid_toml(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"missing managed Grok config source: {path}") from exc
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return text if text.endswith("\n") else f"{text}\n"


def should_skip_for_absent_runtime(target: Path, skip_if_uninstalled: bool) -> bool:
    if not skip_if_uninstalled:
        return False
    if target.parent.exists():
        return False
    return shutil.which("grok") is None


def sync_managed_config(
    source: Path,
    target: Path,
    *,
    apply: bool,
    check: bool,
    skip_if_uninstalled: bool,
) -> int:
    desired = read_valid_toml(source)

    if should_skip_for_absent_runtime(target, skip_if_uninstalled):
        print(f"SKIP {target} (grok not installed and runtime home absent)")
        return 0

    existing = target.read_text(encoding="utf-8") if target.exists() else None
    if existing == desired:
        print(f"UNCHANGED {target}")
        return 0

    if check:
        print(f"OUT-OF-SYNC {target}", file=sys.stderr)
        return 1

    print(f"SYNC {target} <- {source}")
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync Grok Build managed config from the agents control plane."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    mode.add_argument("--dry-run", action="store_true", help="Show changes only.")
    mode.add_argument("--check", action="store_true", help="Fail if target is out of sync.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Canonical managed Grok config TOML.",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help="Target ~/.grok/managed_config.toml path.",
    )
    parser.add_argument(
        "--no-skip-if-uninstalled",
        action="store_true",
        help="Do not skip when grok is absent and the runtime home does not exist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return sync_managed_config(
            Path(args.source).expanduser(),
            Path(args.target).expanduser(),
            apply=args.apply,
            check=args.check,
            skip_if_uninstalled=not args.no_skip_if_uninstalled,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
