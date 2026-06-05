#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
DEFAULT_REGISTRY_FILE = ROOT_DIR / "plugins" / "registry.json"

from plugins.derived import validate_plugin_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the canonical Codex plugin registry."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Accepted for consistency; plugin sync has no file materialization step.",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(DEFAULT_REGISTRY_FILE),
        help="Path to canonical plugin registry JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {registry_file}: {exc}", file=sys.stderr)
        return 1

    registry_dir = registry_file.parent
    root_dir = registry_dir.parent
    home = Path.home()

    try:
        managed, unmanaged, github_root = validate_plugin_registry(
            data,
            root_dir=root_dir,
            home=home,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Registry sync failed: {exc}", file=sys.stderr)
        return 1

    print("Plugin registry validated.")
    print(f"GitHub root: {github_root}")
    print(f"Managed plugins: {len(managed)}")
    print(f"Enabled plugins: {sum(1 for item in managed if item.enabled)}")
    print(f"Repo-local plugins: {len(unmanaged)}")
    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
