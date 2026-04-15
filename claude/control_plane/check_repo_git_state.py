from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .common import ControlPlaneError, git_repo_root, main_guard, normalize_path


TRACKED_SURFACES = (
    ".claude/skills",
    ".claude/agents",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check managed repo-local Claude generated surfaces for untracked files in "
            "repos that already track those surfaces."
        )
    )
    parser.add_argument("--registry", required=True)
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Limit checks to an exact repo path (repeatable)",
    )
    return parser.parse_args()


def _git_output(repo_root_path: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _tracked_surface_entries(repo_root_path: Path, surface: str) -> list[str]:
    return _git_output(repo_root_path, "ls-files", "--", surface)


def _untracked_surface_entries(repo_root_path: Path, surface: str) -> list[str]:
    lines = _git_output(
        repo_root_path,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        surface,
    )
    untracked: list[str] = []
    prefix = "?? "
    for line in lines:
        if line.startswith(prefix):
            untracked.append(line[len(prefix) :].strip())
    return untracked


def main() -> int:
    args = parse_args()
    registry_path = Path(args.registry).expanduser().resolve()
    if not registry_path.is_file():
        raise ControlPlaneError(f"missing required file: {registry_path}")

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ControlPlaneError(f"repo bootstrap root must be an object: {registry_path}")

    repos = data.get("repos", [])
    if not isinstance(repos, list):
        raise ControlPlaneError(f"repos must be an array in {registry_path}")

    filters = {normalize_path(path) for path in args.repo if path.strip()}
    failures: list[str] = []

    for idx, item in enumerate(repos):
        if not isinstance(item, dict):
            raise ControlPlaneError(f"repos[{idx}] must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ControlPlaneError(f"repos[{idx}].path must be a non-empty string")

        declared_repo_path = Path(normalize_path(raw_path))
        actual_repo_path = git_repo_root(declared_repo_path)
        if actual_repo_path is None:
            continue
        actual_repo = str(actual_repo_path)
        if filters and actual_repo not in filters:
            continue

        for surface in TRACKED_SURFACES:
            tracked_entries = _tracked_surface_entries(actual_repo_path, surface)
            if not tracked_entries:
                continue

            untracked_entries = _untracked_surface_entries(actual_repo_path, surface)
            if not untracked_entries:
                continue

            failures.append(
                "\n".join(
                    [
                        f"repo: {actual_repo}",
                        f"surface: {surface}",
                        "untracked generated Claude files:",
                        *[f"  - {entry}" for entry in untracked_entries],
                        "These files were rendered into a repo surface that is already tracked.",
                        "Add or ignore them intentionally instead of leaving the repo in a mixed state.",
                    ]
                )
            )

    if failures:
        raise ControlPlaneError(
            "Managed repo-local Claude files need git attention:\n\n" + "\n\n".join(failures)
        )

    print("OK: no untracked generated Claude repo files in tracked repo-local surfaces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_guard(main))
