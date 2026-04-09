from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class ControlPlaneError(RuntimeError):
    """User-facing control-plane failure."""


@dataclass(frozen=True)
class RenderAction:
    scope: str
    kind: str
    target: Path
    data: Path | str | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def claude_root() -> Path:
    return repo_root() / "claude"


def main_guard(entrypoint: Callable[[], int]) -> int:
    try:
        return entrypoint()
    except ControlPlaneError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def expand_path(raw: str, home: Path) -> Path:
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def normalize_path(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def ordered_unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def rel_link(dst: Path, src: Path) -> str:
    return os.path.relpath(str(src), str(dst.parent))


def resolved_target(link_path: Path) -> Path:
    current = os.readlink(link_path)
    if os.path.isabs(current):
        return Path(current).resolve()
    return (link_path.parent / current).resolve()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json_file(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlPlaneError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ControlPlaneError(f"Invalid JSON in {path}: {exc}") from exc


def json_files_equal(left: Path, right: Path) -> bool:
    try:
        left_data = json.loads(left.read_text(encoding="utf-8"))
        right_data = json.loads(right.read_text(encoding="utf-8"))
    except Exception:
        return False
    return left_data == right_data


def show_diff(original: Path, rendered: Path) -> None:
    if (
        original.is_file()
        and not original.is_symlink()
        and original.suffix == ".json"
        and json_files_equal(original, rendered)
    ):
        return
    if original.exists() or original.is_symlink():
        subprocess.run(["diff", "-u", str(original), str(rendered)], check=False)
    else:
        subprocess.run(["diff", "-u", "/dev/null", str(rendered)], check=False)


def install_rendered_file(rendered: Path, target: Path, *, log: Callable[[str], None]) -> None:
    if target.is_file() and not target.is_symlink() and rendered.read_bytes() == target.read_bytes():
        log(f"No change: {target}")
        return

    if (
        target.is_file()
        and not target.is_symlink()
        and target.suffix == ".json"
        and json_files_equal(target, rendered)
    ):
        log(f"No change: {target}")
        return

    mode = 0o600
    if target.is_file() and not target.is_symlink():
        mode = stat.S_IMODE(target.stat().st_mode)

    if target.is_symlink():
        target.unlink()

    ensure_parent_dir(target)
    shutil.copyfile(rendered, target)
    os.chmod(target, mode)
    log(f"Updated: {target}")


def remove_managed_file(target: Path, *, apply: bool, log: Callable[[str], None]) -> None:
    if not target.exists() and not target.is_symlink():
        log(f"No managed file to remove: {target}")
        return

    if not apply:
        log(f"Would remove file: {target}")
        return

    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink()
    log(f"Removed file: {target}")


def sync_relative_symlink(
    target: Path,
    link_to: str,
    *,
    apply: bool,
    log: Callable[[str], None],
) -> None:
    if target.is_symlink() and os.readlink(target) == link_to:
        log(f"No change: {target} -> {link_to}")
        return

    if not apply:
        if target.is_symlink():
            log(f"Would replace symlink: {target} -> {os.readlink(target)}")
        elif target.exists():
            log(f"Would replace file: {target}")
        else:
            log(f"Would create symlink: {target}")
        log(f"Would point to: {link_to}")
        return

    ensure_parent_dir(target)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(link_to)
    log(f"Linked {target} -> {link_to}")


def remove_managed_symlink(
    target: Path,
    link_to: str,
    *,
    apply: bool,
    log: Callable[[str], None],
) -> None:
    if target.is_symlink() and os.readlink(target) == link_to:
        if not apply:
            log(f"Would remove managed symlink: {target} -> {link_to}")
            return
        target.unlink()
        log(f"Removed managed symlink: {target}")
        return

    log(f"No managed symlink to remove: {target}")


def render_json(value: dict[str, Any], *, sort_keys: bool = True) -> str:
    return json.dumps(value, indent=2, sort_keys=sort_keys) + "\n"
