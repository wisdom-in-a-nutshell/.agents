#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKIP_UPSTREAM_REFS = {"", "-", "local-import"}
DEFAULT_REGISTRY_FILE = Path(__file__).resolve().parent.parent / "plugins" / "registry.json"
PRESERVE_RELATIVE_PATHS = ("agents/openai.yaml",)


@dataclass(frozen=True)
class UpstreamRef:
    repo: str
    path: str
    branch: str


@dataclass
class ExternalPlugin:
    plugin: str
    source_path: str
    source_abs: Path
    upstream_ref: str
    upstream: UpstreamRef


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _safe_slug(value: str) -> str:
    out = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out.append(ch)
        else:
            out.append("-")
    return "".join(out).strip("-")


def parse_upstream_ref(raw: str) -> UpstreamRef:
    if raw in SKIP_UPSTREAM_REFS:
        raise ValueError("non-refreshable upstream_ref")

    try:
        repo_and_path, branch = raw.rsplit("@", 1)
        repo, path = repo_and_path.split(":", 1)
    except ValueError as exc:
        raise ValueError(f"invalid upstream_ref format: {raw}") from exc

    repo = repo.strip()
    path = path.strip().strip("/")
    branch = branch.strip()
    if not repo or "/" not in repo:
        raise ValueError(f"invalid repo in upstream_ref: {raw}")
    if not path:
        raise ValueError(f"invalid path in upstream_ref: {raw}")
    if not branch:
        raise ValueError(f"invalid branch in upstream_ref: {raw}")

    return UpstreamRef(repo=repo, path=path, branch=branch)


def rel_to(base: Path, target: Path) -> str:
    return os.path.relpath(str(target), str(base))


def inside_dir(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def read_registry(registry_file: Path) -> tuple[Path, list[ExternalPlugin]]:
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    managed = data.get("managed_plugins", [])
    if not isinstance(managed, list):
        raise ValueError("managed_plugins must be an array")

    registry_dir = registry_file.parent
    root_dir = registry_dir.parent
    external_root = (root_dir / "plugins-source" / "external").resolve()

    plugins: list[ExternalPlugin] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_plugins[{idx}] must be an object")
        if item.get("origin") != "external":
            continue

        plugin = str(item.get("plugin", "")).strip()
        source_path = str(item.get("source_path", "")).strip()
        upstream_ref = str(item.get("upstream_ref", "")).strip()
        if not plugin or not source_path:
            raise ValueError(f"managed_plugins[{idx}] missing plugin/source_path")
        if upstream_ref in SKIP_UPSTREAM_REFS:
            continue

        upstream = parse_upstream_ref(upstream_ref)

        src = Path(source_path)
        if not src.is_absolute():
            src = (root_dir / src).resolve()
        else:
            src = src.resolve()

        if not inside_dir(src, external_root):
            raise ValueError(
                f"external plugin source must live under plugins-source/external: {plugin} -> {src}"
            )

        plugins.append(
            ExternalPlugin(
                plugin=plugin,
                source_path=source_path,
                source_abs=src,
                upstream_ref=upstream_ref,
                upstream=upstream,
            )
        )

    return root_dir, plugins


def git_path_dirty(repo_root: Path, rel_path: str) -> bool:
    proc = _run(["git", "-C", str(repo_root), "status", "--porcelain", "--", rel_path])
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def sparse_checkout_repo(checkout_root: Path, ref: UpstreamRef, paths: list[str]) -> Path:
    repo_url = f"https://github.com/{ref.repo}.git"
    checkout_dir = checkout_root / f"{_safe_slug(ref.repo)}--{_safe_slug(ref.branch)}"

    proc = _run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "--branch",
            ref.branch,
            repo_url,
            str(checkout_dir),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"clone failed for {ref.repo}@{ref.branch}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    proc = _run(
        ["git", "-C", str(checkout_dir), "sparse-checkout", "set", "--no-cone", *sorted(set(paths))]
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"sparse-checkout failed for {ref.repo}@{ref.branch}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    return checkout_dir


def replace_tree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    elif dst.exists():
        dst.unlink()
    shutil.copytree(src, dst, symlinks=True)


def path_lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def copy_path(src: Path, dst: Path) -> None:
    if src.is_symlink():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(os.readlink(src))
        return
    if src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
        return
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    raise ValueError(f"unsupported path type for copy: {src}")


def backup_preserved_paths(plugin: str, dst: Path, backup_root: Path) -> list[str]:
    preserved: list[str] = []
    for rel in PRESERVE_RELATIVE_PATHS:
        src = dst / rel
        if not path_lexists(src):
            continue
        backup_path = backup_root / plugin / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        copy_path(src, backup_path)
        preserved.append(rel)
    return preserved


def restore_preserved_paths(plugin: str, dst: Path, backup_root: Path, preserved: list[str]) -> None:
    for rel in preserved:
        restore_src = backup_root / plugin / rel
        restore_dst = dst / rel
        if path_lexists(restore_dst):
            remove_path(restore_dst)
        copy_path(restore_src, restore_dst)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh external plugins from upstream_ref entries in plugins/registry.json"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (default is dry-run)",
    )
    parser.add_argument(
        "--force-dirty",
        action="store_true",
        help="Overwrite destination paths even if local git changes exist under source_path",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Only refresh this plugin name (repeatable)",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(DEFAULT_REGISTRY_FILE),
        help="Path to plugins registry JSON (default: <control-plane>/plugins/registry.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        root_dir, plugins = read_registry(registry_file)
    except Exception as exc:  # noqa: BLE001
        print(f"Registry parse failed: {exc}", file=sys.stderr)
        return 1

    plugin_filter = {name.strip() for name in args.plugin if name.strip()}
    if plugin_filter:
        plugins = [p for p in plugins if p.plugin in plugin_filter]

    if not plugins:
        print("No external plugins with refreshable upstream_ref entries found.")
        return 0

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for plugin in plugins:
        key = (plugin.upstream.repo, plugin.upstream.branch)
        if key not in grouped:
            grouped[key] = {
                "upstream": plugin.upstream,
                "paths": set(),
                "plugins": [],
            }
        grouped[key]["paths"].add(plugin.upstream.path)
        grouped[key]["plugins"].append(plugin)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"[{mode}] Refreshing {len(plugins)} external plugin(s) from {len(grouped)} upstream repo+branch source(s)."
    )

    updated = 0
    skipped_dirty = 0
    errors = 0

    with tempfile.TemporaryDirectory(prefix="agents-external-plugins-") as tmp:
        tmp_root = Path(tmp)
        checkout_root = tmp_root / "checkouts"
        preserve_root = tmp_root / "preserved"
        checkout_root.mkdir(parents=True, exist_ok=True)
        preserve_root.mkdir(parents=True, exist_ok=True)

        for (_, _), payload in grouped.items():
            upstream: UpstreamRef = payload["upstream"]
            paths: list[str] = sorted(payload["paths"])
            print(f"[{mode}] FETCH {upstream.repo}@{upstream.branch} paths={','.join(paths)}")

            try:
                checkout_dir = sparse_checkout_repo(checkout_root, upstream, paths)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"ERROR: {exc}", file=sys.stderr)
                continue

            for plugin in payload["plugins"]:
                src = (checkout_dir / plugin.upstream.path).resolve()
                dst = plugin.source_abs
                rel_dst = rel_to(root_dir, dst)

                if not src.exists() or not src.is_dir():
                    errors += 1
                    print(
                        f"ERROR: upstream path missing for {plugin.plugin}: {plugin.upstream_ref}",
                        file=sys.stderr,
                    )
                    continue

                if not args.force_dirty and git_path_dirty(root_dir, rel_dst):
                    skipped_dirty += 1
                    print(
                        f"[{mode}] SKIP DIRTY {plugin.plugin} ({rel_dst})",
                    )
                    continue

                preserved = [rel for rel in PRESERVE_RELATIVE_PATHS if path_lexists(dst / rel)]
                if args.apply:
                    preserved = backup_preserved_paths(plugin.plugin, dst, preserve_root)
                    replace_tree(src, dst)
                    restore_preserved_paths(plugin.plugin, dst, preserve_root, preserved)
                preserve_suffix = (
                    f" (preserved: {','.join(preserved)})" if preserved else ""
                )
                print(
                    f"[{mode}] {'SYNC' if args.apply else 'WOULD SYNC'} "
                    f"{plugin.plugin}: {plugin.upstream_ref} -> {rel_dst}{preserve_suffix}"
                )
                updated += 1

    print(
        f"[{mode}] Summary: updated={updated} skipped_dirty={skipped_dirty} errors={errors}"
    )

    if errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
