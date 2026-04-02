#!/usr/bin/env bash
set -euo pipefail

APPLY=0
REGISTRY_FILE=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"
DEFAULT_REGISTRY_FILE="${ROOT_DIR}/skills/registry.json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Sync Claude global and repo-local skill links from the canonical skills registry.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show actions only (default)
  --registry <path>      Override skills registry path
  --repo <path>          Limit repo-local sync to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/.agents/claude/scripts/sync-skills.sh
  ~/.agents/claude/scripts/sync-skills.sh --apply
  ~/.agents/claude/scripts/sync-skills.sh --apply --repo ~/.agents
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --repo)
      REPO_FILTERS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ -z "$REGISTRY_FILE" ]]; then
  REGISTRY_FILE="$DEFAULT_REGISTRY_FILE"
fi

[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"

python3 - "$REGISTRY_FILE" "$APPLY" "${REPO_FILTERS[@]}" <<'PY'
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ALLOWED_ORIGINS = {"external", "owned"}
ALLOWED_SCOPES = {"global", "repo"}


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def rel_link(dst: Path, src: Path) -> str:
    return os.path.relpath(str(src), str(dst.parent))


def resolved_target(link_path: Path) -> Path:
    cur = os.readlink(link_path)
    if os.path.isabs(cur):
        return Path(cur).resolve()
    return (link_path.parent / cur).resolve()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_repo_root(repo: str, github_root: Path, home: Path) -> Path:
    if repo.startswith("~/") or repo.startswith("/"):
        return expand_path(repo, home).resolve()
    return (github_root / repo).resolve()


def normalize_repo(repo: str) -> str:
    return str(Path(repo).expanduser().resolve())


def git_repo_root(path: Path) -> Path | None:
    try:
        actual_repo = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    return Path(actual_repo).resolve()


def sync_link(dst: Path, src: Path, apply: bool) -> None:
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
    managed_source_root: Path,
    repo_local_source_root: Path | None,
    apply: bool,
) -> None:
    if not skills_dir.exists():
        return
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_symlink():
            continue
        target = resolved_target(entry)
        managed_target = is_relative_to(target, managed_source_root)
        repo_local_target = repo_local_source_root is not None and is_relative_to(target, repo_local_source_root)
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


registry_path = Path(sys.argv[1]).expanduser().resolve()
apply = bool(int(sys.argv[2]))
filters = {normalize_repo(path) for path in sys.argv[3:] if path.strip()}

data = json.loads(registry_path.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    raise SystemExit(f"ERROR: registry root must be an object: {registry_path}")

managed = data.get("managed_skills", [])
unmanaged = data.get("unmanaged_repo_local_skills", [])
paths = data.get("paths", {})
if not isinstance(managed, list):
    raise SystemExit("ERROR: managed_skills must be an array")
if not isinstance(unmanaged, list):
    raise SystemExit("ERROR: unmanaged_repo_local_skills must be an array")
if not isinstance(paths, dict):
    raise SystemExit("ERROR: paths must be an object")

root_dir = registry_path.parent.parent
home = Path.home()
github_root = expand_path(str(paths.get("github_root", "~/GitHub")), home).resolve()
managed_source_root = (root_dir / "skills-source").resolve()
global_skills_dir = home / ".claude" / "skills"

desired_links: dict[Path, Path] = {}
repo_dirs_to_prune: dict[Path, dict[Path, Path]] = {}

for idx, item in enumerate(managed):
    if not isinstance(item, dict):
        raise SystemExit(f"ERROR: managed_skills[{idx}] must be an object")

    skill = str(item.get("skill", "")).strip()
    origin = str(item.get("origin", "")).strip()
    scope = str(item.get("scope", "")).strip()
    source_path = str(item.get("source_path", "")).strip()
    repos = item.get("repos", [])

    if not skill:
      raise SystemExit(f"ERROR: managed_skills[{idx}] missing skill")
    if origin not in ALLOWED_ORIGINS:
      raise SystemExit(f"ERROR: managed_skills[{idx}] invalid origin: {origin!r}")
    if scope not in ALLOWED_SCOPES:
      raise SystemExit(f"ERROR: managed_skills[{idx}] invalid scope: {scope!r}")
    if not source_path:
      raise SystemExit(f"ERROR: managed_skills[{idx}] missing source_path")
    if not isinstance(repos, list):
      raise SystemExit(f"ERROR: managed_skills[{idx}] repos must be an array")

    src = Path(source_path)
    if not src.is_absolute():
        src = (root_dir / src).resolve()
    if not ensure_skill_source(src, label=f"managed skill {skill}"):
        continue

    if scope == "global":
        dst = global_skills_dir / skill
        if dst in desired_links and desired_links[dst] != src:
            raise SystemExit(f"ERROR: conflicting Claude skill targets for {dst}")
        desired_links[dst] = src
        sync_link(dst, src, apply)
        continue

    for repo in repos:
        repo_root = resolve_repo_root(str(repo), github_root, home)
        actual_repo = git_repo_root(repo_root)
        if actual_repo is None:
            print(f"WARNING: skipping non-git path: {repo_root}", file=sys.stderr)
            continue
        actual_repo_str = str(actual_repo)
        if filters and actual_repo_str not in filters:
            continue
        skills_dir = actual_repo / ".claude" / "skills"
        dst = skills_dir / skill
        if dst in desired_links and desired_links[dst] != src:
            raise SystemExit(f"ERROR: conflicting Claude skill targets for {dst}")
        desired_links[dst] = src
        repo_dirs_to_prune.setdefault(actual_repo, {})[dst] = src
        sync_link(dst, src, apply)

for idx, item in enumerate(unmanaged):
    if not isinstance(item, dict):
        raise SystemExit(f"ERROR: unmanaged_repo_local_skills[{idx}] must be an object")
    repo = str(item.get("repo", "")).strip()
    skill = str(item.get("skill", "")).strip()
    if not repo or not skill:
        raise SystemExit(f"ERROR: unmanaged_repo_local_skills[{idx}] must define repo and skill")

    repo_root = resolve_repo_root(repo, github_root, home)
    actual_repo = git_repo_root(repo_root)
    if actual_repo is None:
        print(f"WARNING: skipping non-git path: {repo_root}", file=sys.stderr)
        continue
    actual_repo_str = str(actual_repo)
    if filters and actual_repo_str not in filters:
        continue

    src = actual_repo / ".agents" / "skills" / skill
    if not ensure_skill_source(src, label=f"repo-local skill {skill} in {actual_repo}"):
        continue

    skills_dir = actual_repo / ".claude" / "skills"
    dst = skills_dir / skill
    if dst in desired_links and desired_links[dst] != src:
        raise SystemExit(f"ERROR: conflicting Claude skill targets for {dst}")
    desired_links[dst] = src
    repo_dirs_to_prune.setdefault(actual_repo, {})[dst] = src
    sync_link(dst, src, apply)

prune_dir(
    global_skills_dir,
    {path: src for path, src in desired_links.items() if path.parent == global_skills_dir},
    managed_source_root=managed_source_root,
    repo_local_source_root=None,
    apply=apply,
)

for repo_root, repo_desired in sorted(repo_dirs_to_prune.items()):
    prune_dir(
        repo_root / ".claude" / "skills",
        repo_desired,
        managed_source_root=managed_source_root,
        repo_local_source_root=repo_root / ".agents" / "skills",
        apply=apply,
    )

if apply:
    print("Apply complete.")
else:
    print("Dry run complete. Re-run with --apply to execute link changes.")
PY
