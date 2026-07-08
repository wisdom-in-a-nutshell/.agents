#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any


AGENTS_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = AGENTS_ROOT / "config/grok-config.toml"
DEFAULT_TARGET = Path.home() / ".grok/config.toml"


def read_toml_object(path: Path, *, missing_ok: bool = False) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        if missing_ok:
            return {}
        raise ValueError(f"missing managed Grok config source: {path}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"TOML root must be a table: {path}")
    return data


def merge_overlay(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    desired = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(desired.get(key), dict):
            desired[key] = merge_overlay(desired[key], value)
        else:
            desired[key] = value
    return desired


def toml_quote(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return toml_quote(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list) and all(not isinstance(item, dict) for item in value):
        return "[" + ", ".join(render_scalar(item) for item in value) + "]"
    raise ValueError(f"unsupported TOML value: {value!r}")


def render_table(lines: list[str], prefix: tuple[str, ...], data: dict[str, Any]) -> None:
    scalar_items = [
        (key, value)
        for key, value in data.items()
        if not isinstance(value, dict)
        and not (isinstance(value, list) and any(isinstance(item, dict) for item in value))
    ]
    for key, value in scalar_items:
        lines.append(f"{key} = {render_scalar(value)}")

    table_items = [(key, value) for key, value in data.items() if isinstance(value, dict)]
    array_table_items = [
        (key, value)
        for key, value in data.items()
        if isinstance(value, list) and any(isinstance(item, dict) for item in value)
    ]

    for key, value in table_items:
        child_prefix = (*prefix, key)
        has_direct_values = any(
            not isinstance(child_value, dict)
            for child_value in value.values()
        )
        if has_direct_values:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"[{'.'.join(child_prefix)}]")
        render_table(lines, child_prefix, value)

    for key, value in array_table_items:
        for item in value:
            if not isinstance(item, dict):
                raise ValueError(f"mixed scalar/object arrays are not supported for {key}")
            if lines and lines[-1] != "":
                lines.append("")
            child_prefix = (*prefix, key)
            lines.append(f"[[{'.'.join(child_prefix)}]]")
            render_table(lines, child_prefix, item)


def render_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    render_table(lines, (), data)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


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
    overlay = read_toml_object(source)

    if should_skip_for_absent_runtime(target, skip_if_uninstalled):
        print(f"SKIP {target} (grok not installed and runtime home absent)")
        return 0

    current_data = read_toml_object(target, missing_ok=True)
    desired = render_toml(merge_overlay(current_data, overlay))
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
        description="Sync Grok Build config from the agents control plane."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply changes.")
    mode.add_argument("--dry-run", action="store_true", help="Show changes only.")
    mode.add_argument("--check", action="store_true", help="Fail if target is out of sync.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Canonical managed Grok config overlay TOML.",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help="Target ~/.grok/config.toml path.",
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
