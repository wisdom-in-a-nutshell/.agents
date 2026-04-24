"""Fast read-only Things 3 backend for Dobby task commands.

This module intentionally owns the fragile Things database details so the
agent-facing `dobby-tasks` perimeter can stay simple and stable.

Read path:
    SQLite database, opened read-only.

Write path:
    Stays in `tasks.py` via Things URL scheme / AppleScript.

Why this exists:
    AppleScript/JXA reads can hang even when Things 3 is open. For agent
    lookup, local read-only SQLite is faster and less brittle. The database
    path and date encoding are documented by Cultured Code's export docs and
    the things.py project:

    - ~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/
    - Things date integer: (year << 16) | (month << 12) | (day << 7)

Agent contract:
    Keep returned dicts compatible with the existing `dobby-tasks` JSON shape.
    Backend diagnostics are added by the command layer, not embedded here.
"""

from __future__ import annotations

import glob
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class ThingsReadError(RuntimeError):
    """Read-only Things backend failed."""


THINGS_SQLITE_PATH_ENV_VAR = "DOBBY_THINGS_SQLITE_PATH"

DEFAULT_FILEPATH_31616502 = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    "/ThingsData-*/Things Database.thingsdatabase/main.sqlite"
)
DEFAULT_FILEPATH_31516502 = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac"
    "/Things Database.thingsdatabase/main.sqlite"
)

STATUS_OPEN = 0
STATUS_CANCELED = 2
STATUS_COMPLETED = 3

TYPE_TODO = 0
TYPE_PROJECT = 1
TYPE_HEADING = 2

START_INBOX = 0
START_ANYTIME = 1
START_SOMEDAY_OR_UPCOMING = 2

THINGS_DATE_YEAR_MASK = 0b111111111110000000000000000
THINGS_DATE_MONTH_MASK = 0b000000000001111000000000000
THINGS_DATE_DAY_MASK = 0b000000000000000111110000000


@dataclass(frozen=True)
class DatabaseInfo:
    path: Path

    def as_meta(self) -> dict[str, Any]:
        return {"path": str(self.path)}


def find_database() -> DatabaseInfo:
    """Return the newest plausible Things 3 database path.

    Things now keeps data under `ThingsData-*`, but stale backup folders can
    also match that glob. Prefer non-backup candidates and then newest mtime.
    """
    configured = os.getenv(THINGS_SQLITE_PATH_ENV_VAR)
    if configured:
        path = Path(configured).expanduser()
        if not path.exists():
            raise ThingsReadError(f"{THINGS_SQLITE_PATH_ENV_VAR} points to missing file: {path}")
        return DatabaseInfo(path=path)

    patterns = [DEFAULT_FILEPATH_31616502, DEFAULT_FILEPATH_31516502]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(Path(p) for p in glob.glob(os.path.expanduser(pattern)))

    def is_backup(path: Path) -> bool:
        return any(".bak" in part.lower() or "backup" in part.lower() for part in path.parts)

    candidates = [p for p in candidates if p.exists() and not is_backup(p)]
    if not candidates:
        raise ThingsReadError("Things SQLite database not found")

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return DatabaseInfo(path=candidates[0])


def _connect() -> tuple[sqlite3.Connection, DatabaseInfo]:
    info = find_database()
    try:
        conn = sqlite3.connect(f"{info.path.as_uri()}?mode=ro", uri=True, timeout=1.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.Error as e:
        raise ThingsReadError(f"failed to open Things SQLite database read-only: {e}") from e
    return conn, info


def thingsdate_from_iso(iso_date: str) -> int:
    y, m, d = (int(part) for part in iso_date.split("-"))
    return (y << 16) | (m << 12) | (d << 7)


def thingsdate_to_iso(value: int | None) -> str | None:
    if not value:
        return None
    y = (int(value) & THINGS_DATE_YEAR_MASK) >> 16
    m = (int(value) & THINGS_DATE_MONTH_MASK) >> 12
    d = (int(value) & THINGS_DATE_DAY_MASK) >> 7
    if y <= 0 or not (1 <= m <= 12) or not (1 <= d <= 31):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def unix_to_iso(value: float | int | None) -> str | None:
    if value in (None, 0):
        return None
    try:
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OSError, ValueError):
        return None
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def _status_label(value: int | None) -> str:
    return {
        STATUS_OPEN: "open",
        STATUS_CANCELED: "canceled",
        STATUS_COMPLETED: "completed",
    }.get(value, "unknown")


def _row_to_task(row: sqlite3.Row, *, verbose: bool, include_start: bool = False) -> dict[str, Any]:
    start_date = thingsdate_to_iso(row["startDate"])
    deadline = thingsdate_to_iso(row["deadline"])

    task: dict[str, Any] = {
        "id": row["uuid"],
        "name": row["title"] or "",
        "status": _status_label(row["status"]),
        "tagNames": row["tagNames"] or "",
        "project": row["projectTitle"],
        "area": row["areaTitle"],
    }
    if include_start:
        task["startDate"] = start_date
    if deadline:
        # Existing JXA output used `dueDate`; keep that field name for
        # compatibility, but return the date-only value Things stores.
        task["dueDate"] = deadline
    elif include_start or verbose:
        task["dueDate"] = None

    if verbose:
        task.update({
            "notes": row["notes"] or "",
            "dueDate": deadline,
            "creationDate": unix_to_iso(row["creationDate"]),
            "modificationDate": unix_to_iso(row["userModificationDate"]),
            "startDate": start_date,
            "stopDate": unix_to_iso(row["stopDate"]),
        })
    return task


def _row_to_project(row: sqlite3.Row, *, verbose: bool = True) -> dict[str, Any]:
    project: dict[str, Any] = {
        "id": row["uuid"],
        "name": row["title"] or "",
        "status": _status_label(row["status"]),
        "area": row["areaTitle"],
        "tagNames": row["tagNames"] or "",
    }
    if verbose:
        project["notes"] = row["notes"] or ""
    return project


def _row_to_area(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["uuid"],
        "name": row["title"] or "",
        "tagNames": row["tagNames"] or "",
    }


def _row_to_tag(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["uuid"], "name": row["title"] or ""}


TASK_SELECT = """
SELECT
    TASK.uuid,
    TASK.title,
    TASK.notes,
    TASK.status,
    TASK.type,
    TASK.trashed,
    TASK.start,
    TASK.startDate,
    TASK.deadline,
    TASK.deadlineSuppressionDate,
    TASK.creationDate,
    TASK.userModificationDate,
    TASK.stopDate,
    TASK."index",
    TASK.todayIndex,
    COALESCE(PROJECT.uuid, PROJECT_OF_HEADING.uuid) AS projectUuid,
    COALESCE(PROJECT.title, PROJECT_OF_HEADING.title) AS projectTitle,
    COALESCE(AREA_DIRECT.uuid, AREA_PROJECT.uuid, AREA_HEADING_PROJECT.uuid) AS areaUuid,
    COALESCE(AREA_DIRECT.title, AREA_PROJECT.title, AREA_HEADING_PROJECT.title) AS areaTitle,
    (
        SELECT group_concat(title, ', ')
        FROM (
            SELECT TAG.title AS title
            FROM TMTaskTag TASK_TAG
            JOIN TMTag TAG ON TAG.uuid = TASK_TAG.tags
            WHERE TASK_TAG.tasks = TASK.uuid
            ORDER BY TAG."index"
        )
    ) AS tagNames
FROM TMTask TASK
LEFT JOIN TMTask PROJECT ON TASK.project = PROJECT.uuid
LEFT JOIN TMTask HEADING ON TASK.heading = HEADING.uuid
LEFT JOIN TMTask PROJECT_OF_HEADING ON HEADING.project = PROJECT_OF_HEADING.uuid
LEFT JOIN TMArea AREA_DIRECT ON TASK.area = AREA_DIRECT.uuid
LEFT JOIN TMArea AREA_PROJECT ON PROJECT.area = AREA_PROJECT.uuid
LEFT JOIN TMArea AREA_HEADING_PROJECT ON PROJECT_OF_HEADING.area = AREA_HEADING_PROJECT.uuid
"""


AREA_SELECT = """
SELECT
    AREA.uuid,
    AREA.title,
    AREA.visible,
    AREA."index",
    (
        SELECT group_concat(title, ', ')
        FROM (
            SELECT TAG.title AS title
            FROM TMAreaTag AREA_TAG
            JOIN TMTag TAG ON TAG.uuid = AREA_TAG.tags
            WHERE AREA_TAG.areas = AREA.uuid
            ORDER BY TAG."index"
        )
    ) AS tagNames
FROM TMArea AREA
"""


def _fetch_tasks(where: str, params: Iterable[Any] = (), *, order: str = 'TASK."index"', verbose: bool = False, include_start: bool = False) -> list[dict[str, Any]]:
    conn, _info = _connect()
    try:
        rows = conn.execute(f"{TASK_SELECT}\nWHERE {where}\nORDER BY {order}", tuple(params)).fetchall()
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()
    return [_row_to_task(row, verbose=verbose, include_start=include_start) for row in rows]


def list_view(name: str, *, verbose: bool = False) -> list[dict[str, Any]]:
    today = thingsdate_from_iso(date.today().isoformat())
    base = "TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0"
    params: list[Any] = [TYPE_TODO, STATUS_OPEN]
    include_start = False

    if name == "today":
        where = f"""{base} AND (
            (TASK.start = ? AND TASK.startDate IS NOT NULL AND TASK.startDate <= ?)
            OR (TASK.start = ? AND TASK.startDate IS NOT NULL AND TASK.startDate <= ?)
            OR (TASK.deadline IS NOT NULL AND TASK.deadline <= ? AND (TASK.deadlineSuppressionDate IS NULL OR TASK.deadlineSuppressionDate = 0))
        )"""
        params.extend([START_ANYTIME, today, START_SOMEDAY_OR_UPCOMING, today, today])
        order = "TASK.todayIndex, TASK.startDate, TASK.deadline, TASK.\"index\""
        include_start = True
    elif name == "inbox":
        where = f"{base} AND TASK.start = ?"
        params.append(START_INBOX)
        order = 'TASK."index"'
    elif name == "upcoming":
        where = f"{base} AND TASK.start = ? AND TASK.startDate IS NOT NULL AND TASK.startDate > ?"
        params.extend([START_SOMEDAY_OR_UPCOMING, today])
        order = 'TASK.startDate, TASK."index"'
        include_start = True
    elif name == "anytime":
        where = f"{base} AND TASK.start = ?"
        params.append(START_ANYTIME)
        order = 'TASK."index"'
    elif name == "someday":
        where = f"{base} AND TASK.start = ? AND TASK.startDate IS NULL"
        params.append(START_SOMEDAY_OR_UPCOMING)
        order = 'TASK."index"'
    elif name == "logbook":
        where = "TASK.type = ? AND TASK.status IN (?, ?) AND TASK.trashed = 0"
        params = [TYPE_TODO, STATUS_CANCELED, STATUS_COMPLETED]
        order = "TASK.stopDate DESC, TASK.userModificationDate DESC"
    else:
        raise ThingsReadError(f"unsupported Things list: {name}")

    return _fetch_tasks(where, params, order=order, verbose=verbose, include_start=include_start)


def overdue(*, today_iso: str, verbose: bool = False) -> list[dict[str, Any]]:
    today = thingsdate_from_iso(today_iso)
    return _fetch_tasks(
        "TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0 AND TASK.deadline IS NOT NULL AND TASK.deadline < ?",
        [TYPE_TODO, STATUS_OPEN, today],
        order='TASK.deadline, TASK."index"',
        verbose=verbose,
        include_start=True,
    )


def snapshot(*, today_iso: str, verbose: bool = False, minimal: bool = False, limit: int = 0) -> dict[str, Any]:
    views = {
        "today": list_view("today", verbose=verbose),
        "overdue": overdue(today_iso=today_iso, verbose=verbose),
        "inbox": list_view("inbox", verbose=verbose),
    }
    out: dict[str, Any] = {}
    for name, tasks in views.items():
        selected = tasks[:limit] if limit else tasks
        if minimal:
            if name == "overdue":
                minimal_tasks = [
                    {"name": task.get("name", ""), "dueDate": task.get("dueDate")}
                    for task in selected
                ]
            else:
                minimal_tasks = [{"name": task.get("name", "")} for task in selected]
            out[name] = {"count": len(tasks), "tasks": minimal_tasks}
        else:
            out[name] = {"count": len(tasks), "tasks": selected}
    return out


def search(query: str, *, include_completed: bool = False, verbose: bool = False) -> list[dict[str, Any]]:
    q = f"%{query.lower()}%"
    statuses: tuple[int, ...] = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
    placeholders = ",".join("?" for _ in statuses)
    return _fetch_tasks(
        f"""TASK.type = ? AND TASK.trashed = 0
        AND TASK.status IN ({placeholders})
        AND lower(COALESCE(TASK.title, '')) LIKE ?""",
        [TYPE_TODO, *statuses, q],
        order="TASK.status, TASK.todayIndex, TASK.userModificationDate DESC",
        verbose=verbose,
        include_start=verbose,
    )


def projects() -> list[dict[str, Any]]:
    conn, _info = _connect()
    try:
        rows = conn.execute(
            f"""{TASK_SELECT}
            WHERE TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0
            ORDER BY TASK."index" """,
            (TYPE_PROJECT, STATUS_OPEN),
        ).fetchall()
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()
    return [_row_to_project(row) for row in rows]


def areas() -> list[dict[str, Any]]:
    conn, _info = _connect()
    try:
        rows = conn.execute(
            f"""{AREA_SELECT}
            WHERE AREA.visible IS NULL OR AREA.visible != 0
            ORDER BY AREA."index" """
        ).fetchall()
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()
    return [_row_to_area(row) for row in rows]


def tags() -> list[dict[str, Any]]:
    conn, _info = _connect()
    try:
        rows = conn.execute('SELECT uuid, title FROM TMTag ORDER BY "index"').fetchall()
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()
    return [_row_to_tag(row) for row in rows]


def inspect(target: str, *, include_completed: bool = False, verbose: bool = True) -> dict[str, Any]:
    """Resolve a task/project by id prefix, id, or exact title.

    Projects include their open child to-dos by default. If
    `include_completed` is set, completed/canceled children are included too.
    """
    conn, _info = _connect()
    try:
        statuses: tuple[int, ...] = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
        placeholders = ",".join("?" for _ in statuses)
        target_like = f"{target}%"
        rows = conn.execute(
            f"""{TASK_SELECT}
            WHERE TASK.trashed = 0
              AND TASK.status IN ({placeholders})
              AND (TASK.uuid = ? OR TASK.uuid LIKE ? OR TASK.title = ?)
            ORDER BY CASE WHEN TASK.uuid = ? OR TASK.title = ? THEN 0 ELSE 1 END, TASK.userModificationDate DESC""",
            (*statuses, target, target_like, target, target, target),
        ).fetchall()
        if not rows:
            raise ThingsReadError(f"not found: {target}")
        row = rows[0]
        if len(rows) > 1 and not (row["uuid"] == target or row["title"] == target):
            raise ThingsReadError(f"ambiguous target prefix: {target}")

        if row["type"] == TYPE_PROJECT:
            item_statuses = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
            item_placeholders = ",".join("?" for _ in item_statuses)
            item_rows = conn.execute(
                f"""{TASK_SELECT}
                WHERE TASK.type = ?
                  AND TASK.trashed = 0
                  AND TASK.status IN ({item_placeholders})
                  AND (TASK.project = ? OR TASK.heading IN (
                      SELECT H.uuid FROM TMTask H WHERE H.project = ?
                  ))
                ORDER BY TASK.status, TASK."index", TASK.todayIndex""",
                (TYPE_TODO, *item_statuses, row["uuid"], row["uuid"]),
            ).fetchall()
            obj = _row_to_project(row, verbose=verbose)
            items = [_row_to_task(item, verbose=verbose, include_start=verbose) for item in item_rows]
            return {"type": "project", "project": obj, "items": items, "count": len(items)}

        task = _row_to_task(row, verbose=verbose, include_start=verbose)
        object_type = "to-do" if row["type"] == TYPE_TODO else "heading"
        return {"type": object_type, "task": task}
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()


def resolve_id(target: str) -> str:
    """Resolve exact task/project title or id prefix to a Things uuid."""
    conn, _info = _connect()
    try:
        target_like = f"{target}%"
        rows = conn.execute(
            """SELECT uuid, title FROM TMTask
            WHERE trashed = 0 AND status = ? AND (uuid = ? OR uuid LIKE ? OR title = ?)
            ORDER BY CASE WHEN uuid = ? OR title = ? THEN 0 ELSE 1 END, userModificationDate DESC""",
            (STATUS_OPEN, target, target_like, target, target, target),
        ).fetchall()
    except sqlite3.Error as e:
        raise ThingsReadError(f"Things SQLite query failed: {e}") from e
    finally:
        conn.close()

    if not rows:
        raise ThingsReadError(f"not found: {target}")
    if len(rows) > 1 and not (rows[0]["uuid"] == target or rows[0]["title"] == target):
        raise ThingsReadError(f"ambiguous target prefix: {target}")
    return str(rows[0]["uuid"])

