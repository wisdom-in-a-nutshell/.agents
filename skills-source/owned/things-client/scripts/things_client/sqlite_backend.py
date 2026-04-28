from __future__ import annotations

import glob
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import DEFAULT_DATABASE_GLOBS, SQLITE_PATH_ENVS
from .errors import ThingsError

STATUS_OPEN = 0
STATUS_CANCELED = 2
STATUS_COMPLETED = 3
TYPE_TODO = 0
TYPE_PROJECT = 1
TYPE_HEADING = 2
START_INBOX = 0
START_ANYTIME = 1
START_SOMEDAY_OR_UPCOMING = 2


@dataclass(frozen=True)
class DatabaseInfo:
    path: Path

def configured_database_path() -> Path | None:
    for env_name in SQLITE_PATH_ENVS:
        configured = os.environ.get(env_name)
        if configured:
            path = Path(configured).expanduser()
            if not path.exists():
                raise ThingsError("E_NOT_FOUND", f"{env_name} points to a missing file: {path}")
            return path
    return None


def has_configured_database_path() -> bool:
    return any(bool(os.environ.get(env_name)) for env_name in SQLITE_PATH_ENVS)


def is_backup_database_path(path: Path) -> bool:
    return any(".bak" in part.lower() or "backup" in part.lower() for part in path.parts)


def discover_database_path() -> Path | None:
    candidates: list[Path] = []
    for pattern in DEFAULT_DATABASE_GLOBS:
        candidates.extend(Path(p) for p in glob.glob(os.path.expanduser(pattern)))
    candidates = [path for path in candidates if path.exists() and not is_backup_database_path(path)]
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def find_database() -> DatabaseInfo:
    path = configured_database_path()
    if path is None:
        path = discover_database_path()
    if path is None:
        raise ThingsError("E_NOT_FOUND", "Things SQLite database was not found.", hint="Open Things 3 or set THINGS_CLIENT_SQLITE_PATH.")
    return DatabaseInfo(path=path)


def connect_readonly() -> tuple[sqlite3.Connection, DatabaseInfo]:
    info = find_database()
    try:
        conn = sqlite3.connect(f"{info.path.as_uri()}?mode=ro", uri=True, timeout=1.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"failed to open Things SQLite database read-only: {exc}") from exc
    return conn, info

def thingsdate_to_iso(value: int | None) -> str | None:
    if not value:
        return None
    y = (int(value) & 0b111111111110000000000000000) >> 16
    m = (int(value) & 0b000000000001111000000000000) >> 12
    d = (int(value) & 0b000000000000000111110000000) >> 7
    if y <= 0 or not (1 <= m <= 12) or not (1 <= d <= 31):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}"


def thingsdate_from_iso(iso_date: str) -> int:
    y, m, d = (int(part) for part in iso_date.split("-"))
    return (y << 16) | (m << 12) | (d << 7)


def unix_to_iso(value: float | int | None) -> str | None:
    if value in (None, 0):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (OSError, ValueError):
        return None


def status_label(value: int | None) -> str:
    return {STATUS_OPEN: "open", STATUS_CANCELED: "canceled", STATUS_COMPLETED: "completed"}.get(value, "unknown")


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


def row_to_task(row: sqlite3.Row, *, verbose: bool, include_start: bool = False) -> dict[str, Any]:
    task: dict[str, Any] = {
        "id": row["uuid"],
        "name": row["title"] or "",
        "status": status_label(row["status"]),
        "tagNames": row["tagNames"] or "",
        "project": row["projectTitle"],
        "area": row["areaTitle"],
    }
    start_date = thingsdate_to_iso(row["startDate"])
    deadline = thingsdate_to_iso(row["deadline"])
    if include_start:
        task["startDate"] = start_date
    if deadline or verbose:
        task["dueDate"] = deadline
    if verbose:
        task.update(
            {
                "notes": row["notes"] or "",
                "creationDate": unix_to_iso(row["creationDate"]),
                "modificationDate": unix_to_iso(row["userModificationDate"]),
                "startDate": start_date,
                "stopDate": unix_to_iso(row["stopDate"]),
            }
        )
    return task


def row_to_project(row: sqlite3.Row, *, verbose: bool = True) -> dict[str, Any]:
    project: dict[str, Any] = {
        "id": row["uuid"],
        "name": row["title"] or "",
        "status": status_label(row["status"]),
        "area": row["areaTitle"],
        "tagNames": row["tagNames"] or "",
    }
    if verbose:
        project["notes"] = row["notes"] or ""
    return project


def row_to_area(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["uuid"], "name": row["title"] or "", "tagNames": row["tagNames"] or ""}


def row_to_tag(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["uuid"], "name": row["title"] or ""}


def tag_filter_clause(tag: str | None) -> tuple[str, list[Any]]:
    if not tag:
        return "", []
    return (
        """ AND EXISTS (
            SELECT 1
            FROM TMTaskTag FILTER_TASK_TAG
            JOIN TMTag FILTER_TAG ON FILTER_TAG.uuid = FILTER_TASK_TAG.tags
            WHERE FILTER_TASK_TAG.tasks = TASK.uuid
              AND lower(FILTER_TAG.title) = lower(?)
        )""",
        [tag],
    )


def fetch_tasks(
    where: str,
    params: Iterable[Any],
    *,
    verbose: bool,
    include_start: bool = False,
    limit: int = 0,
    order: str = 'TASK.userModificationDate DESC, TASK."index"',
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn, info = connect_readonly()
    limit_sql = " LIMIT ?" if limit > 0 else ""
    query_params = list(params)
    if limit > 0:
        query_params.append(limit)
    try:
        rows = conn.execute(
            f"{TASK_SELECT}\nWHERE {where}\nORDER BY {order}{limit_sql}",
            tuple(query_params),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
    finally:
        conn.close()
    return [row_to_task(row, verbose=verbose, include_start=include_start) for row in rows], {"name": "sqlite", "path": str(info.path)}


def list_tasks(*, tag: str | None, verbose: bool, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tag_sql, tag_params = tag_filter_clause(tag)
    return fetch_tasks(
        f"TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0{tag_sql}",
        [TYPE_TODO, STATUS_OPEN, *tag_params],
        verbose=verbose,
        include_start=verbose,
        limit=limit,
    )


def search_tasks(query: str, *, tag: str | None, include_completed: bool, verbose: bool, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tag_sql, tag_params = tag_filter_clause(tag)
    statuses = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
    placeholders = ",".join("?" for _ in statuses)
    needle = f"%{query.lower()}%"
    return fetch_tasks(
        f"""TASK.type = ? AND TASK.status IN ({placeholders}) AND TASK.trashed = 0
        AND (lower(COALESCE(TASK.title, '')) LIKE ? OR lower(COALESCE(TASK.notes, '')) LIKE ?){tag_sql}""",
        [TYPE_TODO, *statuses, needle, needle, *tag_params],
        verbose=verbose,
        include_start=verbose,
        limit=limit,
    )


def view_tasks(name: str, *, verbose: bool, limit: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        raise ThingsError("E_VALIDATION", f"unsupported Things view: {name}")
    return fetch_tasks(where, params, verbose=verbose, include_start=include_start, limit=limit, order=order)


def overdue_tasks(*, today_iso: str, verbose: bool, limit: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    today = thingsdate_from_iso(today_iso)
    return fetch_tasks(
        "TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0 AND TASK.deadline IS NOT NULL AND TASK.deadline < ?",
        [TYPE_TODO, STATUS_OPEN, today],
        verbose=verbose,
        include_start=True,
        limit=limit,
        order='TASK.deadline, TASK."index"',
    )


def snapshot_tasks(*, today_iso: str, verbose: bool, minimal: bool, limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
    today, backend = view_tasks("today", verbose=verbose)
    overdue, _ = overdue_tasks(today_iso=today_iso, verbose=verbose)
    inbox, _ = view_tasks("inbox", verbose=verbose)
    views = {"today": today, "overdue": overdue, "inbox": inbox}
    out: dict[str, Any] = {}
    for name, tasks in views.items():
        selected = tasks[:limit] if limit else tasks
        if minimal:
            if name == "overdue":
                minimal_tasks = [{"name": task.get("name", ""), "dueDate": task.get("dueDate")} for task in selected]
            else:
                minimal_tasks = [{"name": task.get("name", "")} for task in selected]
            out[name] = {"count": len(tasks), "tasks": minimal_tasks}
        else:
            out[name] = {"count": len(tasks), "tasks": selected}
    return out, backend


def list_projects() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn, info = connect_readonly()
    try:
        rows = conn.execute(
            f"""{TASK_SELECT}
            WHERE TASK.type = ? AND TASK.status = ? AND TASK.trashed = 0
            ORDER BY TASK."index" """,
            (TYPE_PROJECT, STATUS_OPEN),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
    finally:
        conn.close()
    return [row_to_project(row) for row in rows], {"name": "sqlite", "path": str(info.path)}


def list_areas() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn, info = connect_readonly()
    try:
        rows = conn.execute(
            f"""{AREA_SELECT}
            ORDER BY AREA.title """
        ).fetchall()
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
    finally:
        conn.close()
    return [row_to_area(row) for row in rows], {"name": "sqlite", "path": str(info.path)}


def list_tags() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn, info = connect_readonly()
    try:
        rows = conn.execute('SELECT uuid, title FROM TMTag ORDER BY "index"').fetchall()
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
    finally:
        conn.close()
    return [row_to_tag(row) for row in rows], {"name": "sqlite", "path": str(info.path)}


def inspect_task(target: str, *, include_completed: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    statuses = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
    placeholders = ",".join("?" for _ in statuses)
    target_like = f"{target}%"
    conn, info = connect_readonly()
    try:
        rows = conn.execute(
            f"""{TASK_SELECT}
            WHERE TASK.trashed = 0
              AND TASK.status IN ({placeholders})
              AND (TASK.uuid = ? OR TASK.uuid LIKE ? OR TASK.title = ?)
            ORDER BY CASE WHEN TASK.uuid = ? OR TASK.title = ? THEN 0 ELSE 1 END, TASK.userModificationDate DESC""",
            (*statuses, target, target_like, target, target, target),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
    finally:
        conn.close()
    backend = {"name": "sqlite", "path": str(info.path)}
    if not rows:
        raise ThingsError("E_NOT_FOUND", f"not found: {target}")
    row = rows[0]
    if len(rows) > 1 and not (row["uuid"] == target or row["title"] == target):
        raise ThingsError("E_VALIDATION", f"ambiguous target prefix: {target}")
    if row["type"] == TYPE_PROJECT:
        item_statuses = (STATUS_OPEN, STATUS_CANCELED, STATUS_COMPLETED) if include_completed else (STATUS_OPEN,)
        item_placeholders = ",".join("?" for _ in item_statuses)
        try:
            conn, _ = connect_readonly()
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
        except sqlite3.Error as exc:
            raise ThingsError("E_IO", f"Things SQLite query failed: {exc}") from exc
        finally:
            if "conn" in locals():
                conn.close()
        project = row_to_project(row, verbose=True)
        items = [row_to_task(item, verbose=True, include_start=True) for item in item_rows]
        return {"type": "project", "project": project, "items": items, "count": len(items)}, backend
    result_type = "heading" if row["type"] == TYPE_HEADING else "to-do"
    return {"type": result_type, "task": row_to_task(row, verbose=True, include_start=True)}, backend


