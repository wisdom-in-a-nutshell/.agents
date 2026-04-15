#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ManagedPlugin:
    plugin_id: str
    plugin_name: str
    marketplace: str


def parse_plugin_id(plugin_id: str) -> tuple[str, str]:
    if "@" not in plugin_id:
        raise ValueError(f"plugin_id must look like <plugin-name>@<marketplace>: {plugin_id}")
    plugin_name, marketplace = plugin_id.rsplit("@", 1)
    plugin_name = plugin_name.strip()
    marketplace = marketplace.strip()
    if not plugin_name or not marketplace:
        raise ValueError(f"invalid plugin_id: {plugin_id!r}")
    return plugin_name, marketplace


def load_registry(registry_file: Path) -> list[ManagedPlugin]:
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    managed = data.get("managed_plugins", [])
    if not isinstance(managed, list):
        raise ValueError("managed_plugins must be an array")

    seen: set[str] = set()
    plugins: list[ManagedPlugin] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")
        plugin_id = str(item.get("plugin_id", "")).strip()
        if not plugin_id:
            raise ValueError(f"managed_plugins[{idx}] missing plugin_id")
        if plugin_id in seen:
            raise ValueError(f"duplicate managed plugin_id: {plugin_id}")
        seen.add(plugin_id)
        plugin_name, marketplace = parse_plugin_id(plugin_id)
        plugins.append(
            ManagedPlugin(
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                marketplace=marketplace,
            )
        )
    return plugins


class CodexAppServer:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            ["codex", "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._next_id = 1
        self._initialize()

    def _initialize(self) -> None:
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "managed-plugin-sync",
                    "title": "Managed Plugin Sync",
                    "version": "0.1.0",
                }
            },
        )
        self.notify("initialized", {})

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)

    def notify(self, method: str, params: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"method": method, "params": params}) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1
        assert self.proc.stdin is not None
        self.proc.stdin.write(
            json.dumps({"method": method, "id": req_id, "params": params}) + "\n"
        )
        self.proc.stdin.flush()

        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                stderr = ""
                if self.proc.stderr is not None:
                    stderr = self.proc.stderr.read().strip()
                raise RuntimeError(
                    f"codex app-server exited unexpectedly while waiting for {method}: "
                    + (stderr or "no stderr")
                )
            message = json.loads(line)
            if message.get("id") != req_id:
                continue
            if "error" in message and message["error"] is not None:
                raise RuntimeError(
                    f"{method} failed: {json.dumps(message['error'], ensure_ascii=True)}"
                )
            return message["result"]


def discover_plugins(
    client: CodexAppServer,
    *,
    force_remote_sync: bool,
) -> dict[str, dict[str, Any]]:
    result = client.request(
        "plugin/list",
        {
            "forceRemoteSync": force_remote_sync,
        },
    )
    discovered: dict[str, dict[str, Any]] = {}
    for marketplace in result.get("marketplaces", []):
        marketplace_name = marketplace.get("name")
        if not isinstance(marketplace_name, str):
            continue
        for plugin in marketplace.get("plugins", []):
            plugin_name = plugin.get("name")
            plugin_id = plugin.get("id")
            if not isinstance(plugin_name, str) or not isinstance(plugin_id, str):
                continue
            discovered[plugin_id] = {
                "marketplace_name": marketplace_name,
                "marketplace_path": marketplace.get("path"),
                "plugin_name": plugin_name,
                "installed": bool(plugin.get("installed")),
            }
    return discovered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure managed official Codex plugins are installed."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Install missing managed plugins. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without changing Codex.",
    )
    parser.add_argument(
        "--registry-file",
        default=str(Path.home() / ".agents" / "plugins" / "registry.json"),
        help="Path to plugins registry JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and args.dry_run:
        print("Choose either --apply or --dry-run, not both.", file=sys.stderr)
        return 1
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        plugins = load_registry(registry_file)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to load plugin registry: {exc}", file=sys.stderr)
        return 1

    if not plugins:
        print("No managed plugins declared.")
        return 0

    client = CodexAppServer()
    try:
        discovered = discover_plugins(client, force_remote_sync=False)
        missing_plugin_ids = [p.plugin_id for p in plugins if p.plugin_id not in discovered]
        if missing_plugin_ids:
            discovered = discover_plugins(client, force_remote_sync=True)

        missing_marketplace = False
        for plugin in plugins:
            info = discovered.get(plugin.plugin_id)
            if info is None:
                print(f"ERROR missing plugin in marketplaces: {plugin.plugin_id}", file=sys.stderr)
                missing_marketplace = True
                continue
            if info["marketplace_name"] != plugin.marketplace:
                print(
                    "ERROR marketplace mismatch for "
                    f"{plugin.plugin_id}: discovered={info['marketplace_name']}",
                    file=sys.stderr,
                )
                missing_marketplace = True
                continue

            if info["installed"]:
                print(f"UNCHANGED {plugin.plugin_id}")
                continue

            if not args.apply:
                print(f"INSTALL {plugin.plugin_id}")
                continue

            marketplace_path = info.get("marketplace_path")
            if not isinstance(marketplace_path, str) or not marketplace_path.strip():
                print(
                    f"ERROR missing marketplace path for {plugin.plugin_id}",
                    file=sys.stderr,
                )
                missing_marketplace = True
                continue
            client.request(
                "plugin/install",
                {
                    "marketplacePath": marketplace_path,
                    "pluginName": plugin.plugin_name,
                },
            )
            print(f"INSTALLED {plugin.plugin_id}")

        if missing_marketplace:
            return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
