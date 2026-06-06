"""Shelf v2 storage with cross-process locking and atomic writes."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from lib.workspace import workspace_root

from .model import ShelfValidationError, default_state, utc_now_iso, validate_state


class ShelfStoreError(RuntimeError):
    pass


def shelf_path() -> Path:
    return workspace_root() / "state" / "shelf.json"


def lock_path() -> Path:
    return workspace_root() / "tmp" / "shelf.lock"


@contextmanager
def shelf_lock() -> Iterator[None]:
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ShelfStoreError(f"invalid Shelf JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ShelfValidationError("Shelf state must be an object")
    return data


def read_state(*, validate: bool = True) -> dict[str, Any]:
    data = read_json_file(shelf_path())
    return validate_state(data) if validate else data


def fsync_dir(path: Path) -> None:
    try:
        dir_fd = os.open(str(path), os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def write_state(state: dict[str, Any]) -> None:
    path = shelf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    fd = None
    tmp_name = ""
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".shelf.", suffix=".tmp", dir=str(path.parent), text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        fsync_dir(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def mutate(mutator: Callable[[dict[str, Any], str], Any]) -> tuple[dict[str, Any], Any]:
    with shelf_lock():
        state = read_state(validate=True)
        now = utc_now_iso()
        result = mutator(state, now)
        state["revision"] = int(state.get("revision") or 0) + 1
        state["updatedAt"] = now
        validate_state(state)
        write_state(state)
        return state, result
