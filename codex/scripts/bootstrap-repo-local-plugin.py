#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PluginRef:
    plugin_name: str
    marketplace: str

    @property
    def plugin_id(self) -> str:
        return f"{self.plugin_name}@{self.marketplace}"


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
                    "name": "repo-local-plugin-bootstrap",
                    "title": "Repo Local Plugin Bootstrap",
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


def parse_plugin_ref(raw: str) -> PluginRef:
    raw = raw.strip()
    if not raw:
        raise ValueError("plugin ref must not be empty")
    if "@" not in raw:
        return PluginRef(plugin_name=raw, marketplace="openai-curated")
    plugin_name, marketplace = raw.rsplit("@", 1)
    plugin_name = plugin_name.strip()
    marketplace = marketplace.strip()
    if not plugin_name or not marketplace:
        raise ValueError(f"invalid plugin ref: {raw!r}")
    return PluginRef(plugin_name=plugin_name, marketplace=marketplace)


def latest_cached_bundle(home: Path, plugin: PluginRef) -> Path:
    cache_root = home / ".codex" / "plugins" / "cache" / plugin.marketplace / plugin.plugin_name
    if not cache_root.is_dir():
        raise FileNotFoundError(
            f"plugin cache not found: {cache_root}. Install {plugin.plugin_id} once in Codex first."
        )
    versions = [path for path in cache_root.iterdir() if path.is_dir()]
    if not versions:
        raise FileNotFoundError(
            f"no cached versions found under {cache_root}. Install {plugin.plugin_id} once in Codex first."
        )
    return max(versions, key=lambda path: path.stat().st_mtime)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def patch_local_manifest(manifest_path: Path, *, repo_name: str) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    interface = manifest.setdefault("interface", {})
    display_name = str(interface.get("displayName", manifest.get("name", "Plugin"))).strip()
    suffix = f" ({repo_name})"
    if not display_name.endswith(suffix):
        interface["displayName"] = f"{display_name}{suffix}"
    short_description = str(interface.get("shortDescription", "")).strip()
    if short_description and repo_name not in short_description:
        interface["shortDescription"] = f"{short_description} Repo-local copy for {repo_name}."
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def discover_plugin(
    client: CodexAppServer,
    *,
    cwd: Path,
    marketplace_name: str,
    plugin_name: str,
) -> tuple[str, dict[str, Any]]:
    result = client.request(
        "plugin/list",
        {
            "cwds": [str(cwd)],
            "forceRemoteSync": False,
        },
    )
    for marketplace in result.get("marketplaces", []):
        if marketplace.get("name") != marketplace_name:
            continue
        for plugin in marketplace.get("plugins", []):
            if plugin.get("name") != plugin_name:
                continue
            marketplace_path = marketplace.get("path")
            if not isinstance(marketplace_path, str) or not marketplace_path:
                raise RuntimeError(f"missing marketplace path for {marketplace_name}")
            return marketplace_path, plugin
    raise RuntimeError(
        f"plugin {plugin_name}@{marketplace_name} was not discovered for cwd={cwd}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy an installed Codex plugin bundle into a repo-local marketplace and install it."
        )
    )
    parser.add_argument(
        "plugin_ref",
        help="Plugin id like build-ios-apps@openai-curated or a bare plugin name.",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Absolute repo path or a path relative to ~/GitHub.",
    )
    parser.add_argument(
        "--source-path",
        help="Optional explicit source plugin bundle path. Defaults to the latest installed cache entry.",
    )
    parser.add_argument(
        "--marketplace-name",
        help="Override the repo-local marketplace name. Defaults to <repo-name>-local-plugins.",
    )
    parser.add_argument(
        "--marketplace-display-name",
        help="Override the repo-local marketplace title. Defaults to <RepoName> Local Plugins.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the copy/install. Default is dry-run.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Emit concise plain-text output.",
    )
    return parser.parse_args()


def emit(payload: dict[str, Any], *, plain: bool) -> None:
    if not plain:
        print(json.dumps(payload, indent=2))
        return
    print(f"repo={payload['repo_root']}")
    print(f"source_bundle={payload['source_bundle']}")
    print(f"local_plugin_dir={payload['local_plugin_dir']}")
    print(f"marketplace_file={payload['marketplace_file']}")
    print(f"local_plugin_id={payload['local_plugin_id']}")
    print(f"repo_visible={payload['repo_visible']}")
    print(f"outside_visible={payload['outside_visible']}")
    print(f"installed={payload['installed']}")
    for action in payload["actions"]:
        print(action)


def main() -> int:
    args = parse_args()
    home = Path.home()
    plugin = parse_plugin_ref(args.plugin_ref)

    repo_root = Path(args.repo).expanduser()
    if not repo_root.is_absolute():
        repo_root = (home / "GitHub" / repo_root).resolve()
    else:
        repo_root = repo_root.resolve()

    if not repo_root.is_dir():
        print(f"repo not found: {repo_root}", file=sys.stderr)
        return 1

    marketplace_name = args.marketplace_name or f"{repo_root.name}-local-plugins"
    marketplace_display_name = (
        args.marketplace_display_name or f"{repo_root.name} Local Plugins"
    )

    source_bundle = (
        Path(args.source_path).expanduser().resolve()
        if args.source_path
        else latest_cached_bundle(home, plugin)
    )
    if not source_bundle.is_dir():
        print(f"source bundle not found: {source_bundle}", file=sys.stderr)
        return 1

    local_plugin_dir = repo_root / "plugins" / plugin.plugin_name
    local_manifest_path = local_plugin_dir / ".codex-plugin" / "plugin.json"
    marketplace_file = repo_root / ".agents" / "plugins" / "marketplace.json"
    actions: list[str] = []

    if args.apply:
        if local_plugin_dir.exists():
            shutil.rmtree(local_plugin_dir)
            actions.append(f"removed existing {local_plugin_dir}")
        shutil.copytree(source_bundle, local_plugin_dir)
        actions.append(f"copied {source_bundle} -> {local_plugin_dir}")
        patched_manifest = patch_local_manifest(local_manifest_path, repo_name=repo_root.name)
        category = (
            patched_manifest.get("interface", {}).get("category")
            or "Coding"
        )
        write_json(
            marketplace_file,
            {
                "name": marketplace_name,
                "interface": {
                    "displayName": marketplace_display_name,
                },
                "plugins": [
                    {
                        "name": plugin.plugin_name,
                        "source": {
                            "source": "local",
                            "path": f"./plugins/{plugin.plugin_name}",
                        },
                        "policy": {
                            "installation": "INSTALLED_BY_DEFAULT",
                            "authentication": "ON_INSTALL",
                        },
                        "category": category,
                    }
                ],
            },
        )
        actions.append(f"wrote {marketplace_file}")
    else:
        actions.append(f"would copy {source_bundle} -> {local_plugin_dir}")
        actions.append(f"would write {marketplace_file}")

    if not args.apply and (not marketplace_file.exists() or not local_plugin_dir.exists()):
        emit(
            {
                "repo_root": str(repo_root),
                "source_bundle": str(source_bundle),
                "local_plugin_dir": str(local_plugin_dir),
                "marketplace_file": str(marketplace_file),
                "local_plugin_id": f"{plugin.plugin_name}@{marketplace_name}",
                "repo_visible": False,
                "outside_visible": False,
                "installed": False,
                "actions": actions,
            },
            plain=args.plain,
        )
        return 0

    client = CodexAppServer()
    try:
        repo_marketplace_path, repo_plugin = discover_plugin(
            client,
            cwd=repo_root,
            marketplace_name=marketplace_name,
            plugin_name=plugin.plugin_name,
        )
        if args.apply and not bool(repo_plugin.get("installed")):
            client.request(
                "plugin/install",
                {
                    "marketplacePath": repo_marketplace_path,
                    "pluginName": plugin.plugin_name,
                },
            )
            actions.append(f"installed {plugin.plugin_name}@{marketplace_name}")
            _, repo_plugin = discover_plugin(
                client,
                cwd=repo_root,
                marketplace_name=marketplace_name,
                plugin_name=plugin.plugin_name,
            )
        elif args.apply:
            actions.append(f"left installed {plugin.plugin_name}@{marketplace_name} unchanged")

        repo_visible = True
        outside_visible = False
        outside_result = client.request(
            "plugin/list",
            {
                "cwds": [str(home / ".agents")],
                "forceRemoteSync": False,
            },
        )
        for marketplace in outside_result.get("marketplaces", []):
            if marketplace.get("name") != marketplace_name:
                continue
            for candidate in marketplace.get("plugins", []):
                if candidate.get("name") == plugin.plugin_name:
                    outside_visible = True
    finally:
        client.close()

    emit(
        {
            "repo_root": str(repo_root),
            "source_bundle": str(source_bundle),
            "local_plugin_dir": str(local_plugin_dir),
            "marketplace_file": str(marketplace_file),
            "local_plugin_id": f"{plugin.plugin_name}@{marketplace_name}",
            "repo_visible": repo_visible,
            "outside_visible": outside_visible,
            "installed": bool(repo_plugin.get("installed")),
            "actions": actions,
        },
        plain=args.plain,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
