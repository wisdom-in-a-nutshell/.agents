#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from plugins.derived import validate_plugin_registry


DEFAULT_REGISTRY_FILE = ROOT_DIR / "plugins" / "registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def installed_plugin_ids(home: Path) -> set[str]:
    cache_root = home / ".codex" / "plugins" / "cache"
    if not cache_root.is_dir():
        return set()

    ids: set[str] = set()
    for manifest in cache_root.glob("*/*/*/.codex-plugin/plugin.json"):
        version_dir = manifest.parent.parent
        plugin_dir = version_dir.parent
        marketplace_dir = plugin_dir.parent
        try:
            metadata = load_json(manifest)
        except Exception:
            continue
        name = metadata.get("name") if isinstance(metadata.get("name"), str) else plugin_dir.name
        ids.add(f"{name}@{marketplace_dir.name}")
    return ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install enabled managed Codex plugin packages missing from the local runtime cache."
    )
    parser.add_argument("--apply", action="store_true", help="Install missing plugin packages.")
    parser.add_argument(
        "--registry-file",
        default=str(DEFAULT_REGISTRY_FILE),
        help="Path to canonical plugins registry JSON file.",
    )
    parser.add_argument("--home", default=str(Path.home()), help="Home directory containing .codex.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable to invoke.")
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive callers.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    home = Path(args.home).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        registry = load_json(registry_file)
        managed, _unmanaged, _github_root = validate_plugin_registry(
            registry,
            root_dir=registry_file.parent.parent,
            home=home,
        )
    except Exception as exc:
        print(f"Plugin install sync failed: {exc}", file=sys.stderr)
        return 1

    installed = installed_plugin_ids(home)
    required = [
        plugin
        for plugin in managed
        if plugin.enabled and plugin.scope in {"global", "repo"} and plugin.marketplace != "openai-bundled"
    ]
    missing = [plugin for plugin in required if plugin.plugin_id not in installed]

    print(f"Required non-bundled Codex plugins: {len(required)}")
    print(f"Missing non-bundled Codex plugins: {len(missing)}")

    for plugin in missing:
        if not args.apply:
            print(f"WOULD INSTALL {plugin.plugin_id}")
            continue
        print(f"INSTALL {plugin.plugin_id}")
        completed = subprocess.run(
            [args.codex_bin, "plugin", "add", plugin.plugin_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)
        if completed.returncode != 0:
            print(
                f"Failed to install {plugin.plugin_id} with `{args.codex_bin} plugin add`",
                file=sys.stderr,
            )
            return completed.returncode

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
