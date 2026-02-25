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


@dataclass(frozen=True)
class UpstreamRef:
    repo: str
    path: str
    branch: str


@dataclass
class ExternalSkill:
    skill: str
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


def read_registry(registry_file: Path) -> tuple[Path, list[ExternalSkill]]:
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    managed = data.get("managed_skills", [])
    if not isinstance(managed, list):
        raise ValueError("managed_skills must be an array")

    registry_dir = registry_file.parent
    root_dir = registry_dir.parent
    external_root = (root_dir / "skills-source" / "external").resolve()

    skills: list[ExternalSkill] = []
    for idx, item in enumerate(managed):
        if not isinstance(item, dict):
            raise ValueError(f"managed_skills[{idx}] must be an object")
        if item.get("origin") != "external":
            continue

        skill = str(item.get("skill", "")).strip()
        source_path = str(item.get("source_path", "")).strip()
        upstream_ref = str(item.get("upstream_ref", "")).strip()
        if not skill or not source_path:
            raise ValueError(f"managed_skills[{idx}] missing skill/source_path")
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
                f"external skill source must live under skills-source/external: {skill} -> {src}"
            )

        skills.append(
            ExternalSkill(
                skill=skill,
                source_path=source_path,
                source_abs=src,
                upstream_ref=upstream_ref,
                upstream=upstream,
            )
        )

    return root_dir, skills


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh external skills from upstream_ref entries in skills/registry.json"
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
        "--skill",
        action="append",
        default=[],
        help="Only refresh this skill name (repeatable)",
    )
    parser.add_argument(
        "registry_file",
        nargs="?",
        default=str(Path.home() / ".agents" / "skills" / "registry.json"),
        help="Path to skills registry JSON (default: ~/.agents/skills/registry.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_file = Path(args.registry_file).expanduser().resolve()
    if not registry_file.is_file():
        print(f"Registry not found: {registry_file}", file=sys.stderr)
        return 1

    try:
        root_dir, skills = read_registry(registry_file)
    except Exception as exc:  # noqa: BLE001
        print(f"Registry parse failed: {exc}", file=sys.stderr)
        return 1

    skill_filter = {name.strip() for name in args.skill if name.strip()}
    if skill_filter:
        skills = [s for s in skills if s.skill in skill_filter]

    if not skills:
        print("No external skills with refreshable upstream_ref entries found.")
        return 0

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for skill in skills:
        key = (skill.upstream.repo, skill.upstream.branch)
        if key not in grouped:
            grouped[key] = {
                "upstream": skill.upstream,
                "paths": set(),
                "skills": [],
            }
        grouped[key]["paths"].add(skill.upstream.path)
        grouped[key]["skills"].append(skill)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Refreshing {len(skills)} external skill(s) from {len(grouped)} upstream repo+branch source(s).")

    updated = 0
    skipped_dirty = 0
    errors = 0

    with tempfile.TemporaryDirectory(prefix="agents-external-skills-") as tmp:
        tmp_root = Path(tmp)
        checkout_root = tmp_root / "checkouts"
        checkout_root.mkdir(parents=True, exist_ok=True)

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

            for skill in payload["skills"]:
                src = (checkout_dir / skill.upstream.path).resolve()
                dst = skill.source_abs
                rel_dst = rel_to(root_dir, dst)

                if not src.exists() or not src.is_dir():
                    errors += 1
                    print(
                        f"ERROR: upstream path missing for {skill.skill}: {skill.upstream_ref}",
                        file=sys.stderr,
                    )
                    continue

                if not args.force_dirty and git_path_dirty(root_dir, rel_dst):
                    skipped_dirty += 1
                    print(
                        f"[{mode}] SKIP DIRTY {skill.skill} ({rel_dst})",
                    )
                    continue

                if args.apply:
                    replace_tree(src, dst)
                print(f"[{mode}] {'SYNC' if args.apply else 'WOULD SYNC'} {skill.skill}: {skill.upstream_ref} -> {rel_dst}")
                updated += 1

    print(
        f"[{mode}] Summary: updated={updated} skipped_dirty={skipped_dirty} errors={errors}"
    )

    if errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
