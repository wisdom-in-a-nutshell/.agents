"""Workspace resolution for Dobby skill scripts.

Dobby's executable scripts live inside the `dobby` skill, but operate on a
Dobby workspace repo (for Adi: `/Users/adi/GitHub/adi`). Resolve that workspace
from DOBBY_WORKSPACE first, then from the current working directory.
"""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_MARKERS = ("soul.md", "memory", "journal")


class WorkspaceError(RuntimeError):
    pass


def is_workspace(path: Path) -> bool:
    return all((path / marker).exists() for marker in WORKSPACE_MARKERS)


def find_workspace(start: Path | None = None) -> Path:
    env = os.environ.get("DOBBY_WORKSPACE", "").strip()
    if env:
        path = Path(env).expanduser().resolve()
        if not is_workspace(path):
            raise WorkspaceError(
                f"DOBBY_WORKSPACE does not look like a Dobby workspace: {path}. "
                "Expected soul.md, memory/, and journal/."
            )
        return path

    cur = (start or Path.cwd()).resolve()
    candidates = [cur, *cur.parents]
    for candidate in candidates:
        if is_workspace(candidate):
            return candidate

    raise WorkspaceError(
        "Could not find a Dobby workspace. Run from a repo containing soul.md, "
        "memory/, and journal/, or set DOBBY_WORKSPACE=/path/to/workspace."
    )


def workspace_root() -> Path:
    return find_workspace()
