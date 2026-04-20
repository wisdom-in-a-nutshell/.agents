from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .common import (
    ControlPlaneError,
    expand_path,
    git_repo_root,
    is_relative_to,
    main_guard,
    rel_link,
    repo_root,
    resolved_target,
)

ALLOWED_ORIGINS = {"external", "owned"}
ALLOWED_SCOPES = {"global", "repo", "dormant"}


def sync_link(dst: Path, src: Path, *, apply: bool) -> None:
    rel = rel_link(dst, src)
    if dst.is_symlink() and resolved_target(dst) == src.resolve():
        print(f"UNCHANGED {dst}")
        return

    print(f"SYNC {dst} -> {rel}")
    if not apply:
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    elif dst.exists():
        dst.unlink()
    dst.symlink_to(rel)


def prune_dir(
    skills_dir: Path,
    desired: dict[Path, Path],
    *,
    managed_source_roots: tuple[Path, ...],
    repo_local_source_root: Path | None,
    apply: bool,
) -> None:
    if not skills_dir.exists():
        return
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        managed_target = any(is_relative_to(target, root) for root in managed_source_roots)
        repo_local_target = (
            repo_local_source_root is not None
            and is_relative_to(target, repo_local_source_root)
        )
        if not managed_target and not repo_local_target:
            continue
        if entry in desired:
            continue
        print(f"PRUNE {entry}")
        if apply:
            entry.unlink()


def ensure_skill_source(path: Path, *, label: str) -> bool:
    if (path / "SKILL.md").is_file():
        return True
    print(f"WARNING: skipping {label}; missing SKILL.md at {path}", file=sys.stderr)
    return False


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_path(repo, home).resolve()
    return (github_root / repo).resolve()


def normalize_repo(repo: str) -> str:
    return str(Path(repo).expanduser().resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Claude global and repo-local skill links from the canonical skills registry."
    )
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply changes")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Show actions only (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--registry",
        default=str(repo_root() / "skills" / "registry.json"),
        help="Override skills registry path",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Limit repo-local sync to an exact repo path (repeatable)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_path = Path(args.registry).expanduser().resolve()
    if not registry_path.is_file():
        raise ControlPlaneError(f"Missing registry file: {registry_path}")

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ControlPlaneError(f"registry root must be an object: {registry_path}")

    managed = data.get("managed_skills", [])
    managed_plugin_skills = data.get("managed_plugin_skills", [])
    unmanaged = data.get("unmanaged_repo_local_skills", [])
    paths = data.get("paths", {})
    if not isinstance(managed, list):
        raise ControlPlaneError("managed_skills must be an array")
    if not isinstance(managed_plugin_skills, list):
        raise ControlPlaneError("managed_plugin_skills must be an array")
    if not isinstance(unmanaged, list):
        raise ControlPlaneError("unmanaged_repo_local_skills must be an array")
    if not isinstance(paths, dict):
        raise ControlPlaneError("paths must be an object")

    root_dir = registry_path.parent.parent
    home = Path.home().resolve()
    github_root = expand_path(str(paths.get("github_root", "~/GitHub")), home).resolve()
    managed_source_roots = (
        (root_dir / "skills-source").resolve(),
        (root_dir / "plugins-source").resolve(),
    )
    global_skills_dir = home / ".claude" / "skills"
    filters = {normalize_repo(path) for path in args.repo if path.strip()}

    desired_links: dict[Path, Path] = {}
    repo_dirs_to_prune: dict[Path, dict[Path, Path]] = {}

    for label, items in (
        ("managed_skills", managed),
        ("managed_plugin_skills", managed_plugin_skills),
    ):
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ControlPlaneError(f"{label}[{idx}] must be an object")

            skill = str(item.get("skill", "")).strip()
            origin = str(item.get("origin", "")).strip()
            scope = str(item.get("scope", "")).strip()
            source_path = str(item.get("source_path", "")).strip()
            repos = item.get("repos", [])

            if not skill:
                raise ControlPlaneError(f"{label}[{idx}] missing skill")
            if origin not in ALLOWED_ORIGINS:
                raise ControlPlaneError(f"{label}[{idx}] invalid origin: {origin!r}")
            if scope not in ALLOWED_SCOPES:
                raise ControlPlaneError(f"{label}[{idx}] invalid scope: {scope!r}")
            if not source_path:
                raise ControlPlaneError(f"{label}[{idx}] missing source_path")
            if not isinstance(repos, list):
                raise ControlPlaneError(f"{label}[{idx}] repos must be an array")

            src = Path(source_path)
            if not src.is_absolute():
                src = (root_dir / src).resolve()
            if not ensure_skill_source(src, label=f"managed skill {skill}"):
                continue

            if scope == "global":
                dst = global_skills_dir / skill
                if dst in desired_links and desired_links[dst] != src:
                    raise ControlPlaneError(f"conflicting Claude skill targets for {dst}")
                desired_links[dst] = src
                sync_link(dst, src, apply=args.apply)
                continue
            if scope == "dormant":
                continue

            for repo in repos:
                repo_root_path = resolve_repo_root(str(repo), github_root, home)
                actual_repo = git_repo_root(repo_root_path)
                if actual_repo is None:
                    print(f"WARNING: skipping non-git path: {repo_root_path}", file=sys.stderr)
                    continue
                actual_repo_str = str(actual_repo)
                if filters and actual_repo_str not in filters:
                    continue
                skills_dir = actual_repo / ".claude" / "skills"
                dst = skills_dir / skill
                if dst in desired_links and desired_links[dst] != src:
                    raise ControlPlaneError(f"conflicting Claude skill targets for {dst}")
                desired_links[dst] = src
                repo_dirs_to_prune.setdefault(actual_repo, {})[dst] = src
                sync_link(dst, src, apply=args.apply)

    for idx, item in enumerate(unmanaged):
        if not isinstance(item, dict):
            raise ControlPlaneError(f"unmanaged_repo_local_skills[{idx}] must be an object")
        repo = str(item.get("repo", "")).strip()
        skill = str(item.get("skill", "")).strip()
        if not repo or not skill:
            raise ControlPlaneError(
                f"unmanaged_repo_local_skills[{idx}] must define repo and skill"
            )

        repo_root_path = resolve_repo_root(repo, github_root, home)
        actual_repo = git_repo_root(repo_root_path)
        if actual_repo is None:
            print(f"WARNING: skipping non-git path: {repo_root_path}", file=sys.stderr)
            continue
        actual_repo_str = str(actual_repo)
        if filters and actual_repo_str not in filters:
            continue

        repo_dirs_to_prune.setdefault(actual_repo, {})
        src = actual_repo / ".agents" / "skills" / skill
        if not ensure_skill_source(src, label=f"repo-local skill {skill} in {actual_repo}"):
            continue

        skills_dir = actual_repo / ".claude" / "skills"
        dst = skills_dir / skill
        if dst in desired_links and desired_links[dst] != src:
            raise ControlPlaneError(f"conflicting Claude skill targets for {dst}")
        desired_links[dst] = src
        repo_dirs_to_prune[actual_repo][dst] = src
        sync_link(dst, src, apply=args.apply)

    prune_dir(
        global_skills_dir,
        {path: src for path, src in desired_links.items() if path.parent == global_skills_dir},
        managed_source_roots=managed_source_roots,
        repo_local_source_root=None,
        apply=args.apply,
    )

    for repo_root_path, repo_desired in sorted(repo_dirs_to_prune.items()):
        prune_dir(
            repo_root_path / ".claude" / "skills",
            repo_desired,
            managed_source_roots=managed_source_roots,
            repo_local_source_root=repo_root_path / ".agents" / "skills",
            apply=args.apply,
        )

    if args.apply:
        print("Apply complete.")
    else:
        print("Dry run complete. Re-run with --apply to execute link changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
