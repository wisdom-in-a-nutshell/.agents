#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_FILE = ROOT_DIR / "codex" / "config" / "repo-bootstrap.json"


@dataclass(frozen=True)
class RepoCandidate:
    declared_path: Path
    repo_root: Path


def expand_path(raw: str, home: Path) -> Path:
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def display_path(path: Path, home: Path) -> str:
    try:
        rel = path.resolve().relative_to(home)
    except ValueError:
        return str(path.resolve())
    if not rel.parts:
        return "~"
    return f"~/{rel.as_posix()}"


def git_repo_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    if not root:
        return None
    return Path(root).resolve()


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: registry root must be an object")
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        raise ValueError(f"{path}: repos must be an array")
    for idx, item in enumerate(repos):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: repos[{idx}] must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{path}: repos[{idx}].path must be a non-empty string")
    return data


def discover_direct_child_git_repos(github_root: Path) -> list[RepoCandidate]:
    if not github_root.is_dir():
        raise ValueError(f"GitHub root is not a directory: {github_root}")

    discovered: list[RepoCandidate] = []
    for child in sorted(github_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        repo_root = git_repo_root(child)
        if repo_root is None:
            continue
        if repo_root != child.resolve():
            continue
        discovered.append(RepoCandidate(declared_path=child, repo_root=repo_root))
    return discovered


def existing_repo_roots(repos: list[dict[str, Any]], home: Path) -> set[Path]:
    roots: set[Path] = set()
    for item in repos:
        raw_path = str(item["path"]).strip()
        expanded = expand_path(raw_path, home).resolve()
        roots.add(git_repo_root(expanded) or expanded)
    return roots


def repo_sort_key(item: dict[str, Any], home: Path) -> str:
    raw_path = str(item.get("path", "")).strip()
    return str(expand_path(raw_path, home).resolve())


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enroll every direct child Git repo under ~/GitHub into the shared "
            "agent repo bootstrap registry."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Write registry changes")
    parser.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Report changes without writing (default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--github-root",
        default=str(Path.home() / "GitHub"),
        help="Top-level GitHub workspace root to scan (default: ~/GitHub)",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY_FILE),
        help="Repo bootstrap registry path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = Path.home().resolve()
    github_root = expand_path(str(args.github_root), home).resolve()
    registry_path = expand_path(str(args.registry), home).resolve()
    if not registry_path.is_file():
        print(f"Registry not found: {registry_path}", file=sys.stderr)
        return 1

    try:
        data = load_registry(registry_path)
        repos = data["repos"]
        discovered = discover_direct_child_git_repos(github_root)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    enrolled_roots = existing_repo_roots(repos, home)
    missing = [
        candidate
        for candidate in discovered
        if candidate.repo_root not in enrolled_roots
    ]

    print(f"Discovered {len(discovered)} direct child Git repo(s) under {github_root}.")
    if not missing:
        print("OK: all discovered repos are already enrolled.")
        return 0

    for candidate in missing:
        print(f"ADD {display_path(candidate.declared_path, home)}")

    if not args.apply:
        print("Dry run complete. Re-run with --apply to update the registry.")
        return 0

    repos.extend(
        {"path": display_path(candidate.declared_path, home)}
        for candidate in missing
    )
    repos.sort(key=lambda item: repo_sort_key(item, home))
    write_json(registry_path, data)
    print(f"Updated: {registry_path}")

    print("Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
