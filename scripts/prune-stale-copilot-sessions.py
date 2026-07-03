#!/usr/bin/env python3
"""Prune stale local GitHub Copilot session data by age.

GitHub documents `/session prune --older-than DAYS` as the supported local-only
cleanup path. That command is currently an interactive slash command, not a
top-level non-interactive `copilot session prune` subcommand. This tool gives the
control plane a guarded LaunchAgent-friendly equivalent for local data only:

- delete old rows from `~/.copilot/session-store.db`
- delete matching `~/.copilot/session-state/<session-id>` directories
- skip sessions with live `inuse.<pid>.lock` markers
- never delete synced GitHub.com data

Dry-run by default. Follows the repo CLI contract: structured JSON, `--plain`
for logs, `--no-input`, stable exit codes, exclusive lock, and backups before
apply writes.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "prune-stale-copilot-sessions"
DEFAULT_OLDER_THAN_HOURS = 24.0
DEFAULT_MAX_REPORT = 25
STATE_ROOT = Path.home() / ".local/state/copilot-control-plane"
DEFAULT_LOCK = STATE_ROOT / "prune-stale-copilot-sessions.lock"
DEFAULT_BACKUP_ROOT = STATE_ROOT / "prune-stale-copilot-sessions/backups"
DEFAULT_COPILOT_HOME = Path.home() / ".copilot"

REQUIRED_SESSION_COLUMNS = {"id", "updated_at"}
KNOWN_SESSION_REF_TABLES = {
    "checkpoints",
    "forge_trajectory_events",
    "session_files",
    "session_refs",
    "turns",
}


class ToolError(RuntimeError):
    code = "E_TOOL"
    exit_code = 1
    retryable = False
    hint = "Inspect the command inputs and retry after fixing the reported problem."


class UsageError(ToolError):
    code = "E_USAGE"
    exit_code = 2
    hint = "Run with --help and provide a valid non-interactive command."


class SchemaError(ToolError):
    code = "E_SCHEMA"
    exit_code = 2
    hint = "Copilot local session-store schema changed; no prune was applied."


class DependencyError(ToolError):
    code = "E_DEPENDENCY"
    exit_code = 4
    retryable = True
    hint = "Another prune run may be in progress; retry after it releases the lock."


@dataclass(frozen=True)
class SessionRef:
    session_id: str
    updated_at: str
    updated_epoch: float
    cwd: str | None
    repository: str | None
    branch: str | None
    state_dir: Path | None
    in_store: bool


@dataclass(frozen=True)
class Decision:
    session: SessionRef
    decision: str
    reason: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_timestamp(value: str, *, source: str) -> float:
    raw = value.strip()
    if not raw:
        raise SchemaError(f"{source} has an empty updated_at timestamp")
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SchemaError(f"{source} has invalid updated_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


def format_utc(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_plain(payload: dict[str, Any]) -> None:
    if payload["status"] != "ok":
        error = payload["error"] or {}
        print(f"error {error.get('code')}: {error.get('message')}", file=sys.stderr)
        if error.get("hint"):
            print(error["hint"], file=sys.stderr)
        return
    data = payload["data"]
    mode = "apply" if data["applied"] else "dry-run"
    print(
        f"ok mode={mode} cutoff={data['cutoff_utc']} scanned={data['scanned']} "
        f"pruned={data['pruned_count']} kept={data['kept_count']}"
    )
    for item in data["sessions"]:
        if item["decision"] != "prune":
            continue
        print(
            f"prune updated={item['updated_at']} id={item['session_id']} "
            f"repo={item['repository'] or ''} cwd={item['cwd'] or ''}"
        )


def finish(
    *,
    status: str,
    started_at: float,
    request_id: str,
    plain: bool,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    exit_code: int,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": status,
        "data": data or {},
        "error": error,
        "meta": {
            "request_id": request_id,
            "timestamp_utc": utc_now(),
            "duration_ms": int((time.time() - started_at) * 1000),
        },
    }
    if plain:
        emit_plain(payload)
    else:
        emit_json(payload)
    return exit_code


def acquire_lock(lock_path: Path) -> Any:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise DependencyError(f"another Copilot prune run already holds {lock_path}") from exc
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    return lock_file


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    ).fetchall()
    return {str(row[0]) for row in rows}


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({quote_identifier(table)})")}


def session_ref_tables(conn: sqlite3.Connection) -> list[str]:
    refs: set[str] = set()
    for table in table_names(conn):
        if table.startswith("sqlite_") or table.startswith("search_index_"):
            continue
        for row in conn.execute(f"PRAGMA foreign_key_list({quote_identifier(table)})"):
            target_table = str(row[2])
            from_column = str(row[3])
            to_column = str(row[4])
            if target_table == "sessions" and from_column == "session_id" and to_column == "id":
                refs.add(table)
    unknown = sorted(refs - KNOWN_SESSION_REF_TABLES)
    if unknown:
        raise SchemaError(
            "session-store has unknown tables referencing sessions: " + ", ".join(unknown)
        )
    return sorted(refs)


def validate_store_schema(conn: sqlite3.Connection) -> tuple[list[str], bool]:
    names = table_names(conn)
    if "sessions" not in names:
        raise SchemaError("session-store is missing sessions table")
    missing = sorted(REQUIRED_SESSION_COLUMNS - column_names(conn, "sessions"))
    if missing:
        raise SchemaError("session-store sessions table missing column(s): " + ", ".join(missing))
    refs = session_ref_tables(conn)
    has_search_index = "search_index" in names and "session_id" in column_names(conn, "search_index")
    return refs, has_search_index


def pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def live_inuse_pids(state_dir: Path | None) -> list[int]:
    if state_dir is None or not state_dir.is_dir():
        return []
    live: list[int] = []
    for lock in state_dir.glob("inuse.*.lock"):
        raw_pid = lock.name.removeprefix("inuse.").removesuffix(".lock")
        try:
            pid = int(raw_pid)
        except ValueError:
            continue
        if pid_is_alive(pid):
            live.append(pid)
    return sorted(live)


def read_workspace_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return data
    for line in text.splitlines():
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def iter_state_dirs(state_root: Path) -> list[Path]:
    if not state_root.is_dir():
        return []
    return sorted(path for path in state_root.iterdir() if path.is_dir())


def load_store_sessions(store_path: Path, state_root: Path) -> tuple[list[SessionRef], list[str], bool]:
    if not store_path.is_file():
        return [], [], False
    conn = connect_readonly(store_path)
    try:
        ref_tables, has_search_index = validate_store_schema(conn)
        rows = conn.execute(
            "SELECT id, updated_at, cwd, repository, branch FROM sessions ORDER BY updated_at"
        ).fetchall()
    finally:
        conn.close()
    sessions: list[SessionRef] = []
    for row in rows:
        session_id = str(row[0])
        updated_at = str(row[1])
        sessions.append(
            SessionRef(
                session_id=session_id,
                updated_at=updated_at,
                updated_epoch=parse_timestamp(updated_at, source=f"session-store row {session_id}"),
                cwd=row[2] if isinstance(row[2], str) else None,
                repository=row[3] if isinstance(row[3], str) else None,
                branch=row[4] if isinstance(row[4], str) else None,
                state_dir=state_root / session_id,
                in_store=True,
            )
        )
    return sessions, ref_tables, has_search_index


def load_unindexed_state_sessions(
    state_root: Path,
    indexed_ids: set[str],
) -> list[SessionRef]:
    sessions: list[SessionRef] = []
    for state_dir in iter_state_dirs(state_root):
        if state_dir.name in indexed_ids or state_dir.name.startswith("pending-session:"):
            continue
        metadata = read_workspace_yaml(state_dir / "workspace.yaml")
        updated_at = metadata.get("updated_at")
        if not updated_at:
            continue
        session_id = metadata.get("id") or state_dir.name
        sessions.append(
            SessionRef(
                session_id=session_id,
                updated_at=updated_at,
                updated_epoch=parse_timestamp(updated_at, source=f"{state_dir}/workspace.yaml"),
                cwd=metadata.get("cwd"),
                repository=metadata.get("repository"),
                branch=metadata.get("branch"),
                state_dir=state_dir,
                in_store=False,
            )
        )
    return sessions


def decide_sessions(
    sessions: list[SessionRef],
    *,
    cutoff_epoch: float,
    keep_sessions: set[str],
) -> list[Decision]:
    decisions: list[Decision] = []
    for session in sorted(sessions, key=lambda item: (item.updated_epoch, item.session_id)):
        if session.session_id in keep_sessions:
            decisions.append(Decision(session, "keep", "keep_session"))
        elif live_inuse_pids(session.state_dir):
            decisions.append(Decision(session, "keep", "running"))
        elif session.updated_epoch >= cutoff_epoch:
            decisions.append(Decision(session, "keep", "recent"))
        else:
            decisions.append(Decision(session, "prune", "older_than_cutoff"))
    return decisions


def backup_store(store_path: Path, backup_dir: Path) -> None:
    if not store_path.is_file():
        return
    target = backup_dir / "session-store.db"
    src = sqlite3.connect(str(store_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def backup_state_dir(state_dir: Path, backup_dir: Path, state_root: Path) -> None:
    if not state_dir.is_dir():
        return
    try:
        rel = state_dir.relative_to(state_root)
    except ValueError:
        rel = Path(state_dir.name)
    target = backup_dir / "session-state" / rel
    shutil.copytree(state_dir, target, copy_function=shutil.copy2, symlinks=True)


def delete_store_sessions(
    store_path: Path,
    session_ids: list[str],
    ref_tables: list[str],
    *,
    has_search_index: bool,
) -> None:
    if not session_ids or not store_path.is_file():
        return
    conn = sqlite3.connect(str(store_path), timeout=30.0)
    try:
        validate_store_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for session_id in session_ids:
                for table in ref_tables:
                    conn.execute(
                        f"DELETE FROM {quote_identifier(table)} WHERE session_id = ?",
                        (session_id,),
                    )
                if has_search_index:
                    conn.execute("DELETE FROM search_index WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


def session_output(decision: Decision) -> dict[str, Any]:
    session = decision.session
    live_pids = live_inuse_pids(session.state_dir)
    return {
        "session_id": session.session_id,
        "updated_at": session.updated_at,
        "updated_at_utc": format_utc(session.updated_epoch),
        "cwd": session.cwd,
        "repository": session.repository,
        "branch": session.branch,
        "state_dir": str(session.state_dir) if session.state_dir else None,
        "in_store": session.in_store,
        "live_inuse_pids": live_pids,
        "decision": decision.decision,
        "reason": decision.reason,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    older_than_hours = (
        args.older_than_hours if args.older_than_hours is not None else args.older_than_days * 24
    )
    if older_than_hours <= 0:
        raise UsageError("--older-than-hours/--older-than-days must be positive")
    if args.max_report < 0:
        raise UsageError("--max-report must be zero or positive")

    copilot_home = args.copilot_home.expanduser()
    store_path = args.session_store.expanduser() if args.session_store else copilot_home / "session-store.db"
    state_root = (
        args.session_state_dir.expanduser()
        if args.session_state_dir
        else copilot_home / "session-state"
    )
    keep_sessions = {sid for sid in args.keep_session}

    lock_file = acquire_lock(args.lock.expanduser())
    try:
        store_sessions, ref_tables, has_search_index = load_store_sessions(store_path, state_root)
        indexed_ids = {session.session_id for session in store_sessions}
        unindexed_sessions = (
            load_unindexed_state_sessions(state_root, indexed_ids)
            if args.include_unindexed
            else []
        )
        sessions = [*store_sessions, *unindexed_sessions]
        cutoff_epoch = time.time() - older_than_hours * 3600.0
        decisions = decide_sessions(sessions, cutoff_epoch=cutoff_epoch, keep_sessions=keep_sessions)
        to_prune = [decision for decision in decisions if decision.decision == "prune"]

        backup_dir: Path | None = None
        if args.apply and to_prune:
            backup_dir = args.backup_root.expanduser() / time.strftime("%Y%m%d-%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=False)
            backup_store(store_path, backup_dir)
            for decision in to_prune:
                if decision.session.state_dir is not None:
                    backup_state_dir(decision.session.state_dir, backup_dir, state_root)

            delete_store_sessions(
                store_path,
                [d.session.session_id for d in to_prune if d.session.in_store],
                ref_tables,
                has_search_index=has_search_index,
            )
            for decision in to_prune:
                state_dir = decision.session.state_dir
                if state_dir is not None and state_dir.is_dir():
                    shutil.rmtree(state_dir)

        report_items = decisions if args.max_report == 0 else decisions[: args.max_report]
        return {
            "applied": bool(args.apply),
            "copilot_home": str(copilot_home),
            "session_store": str(store_path),
            "session_state_dir": str(state_root),
            "older_than_hours": older_than_hours,
            "cutoff_utc": format_utc(cutoff_epoch),
            "scanned": len(decisions),
            "indexed_count": len(store_sessions),
            "unindexed_count": len(unindexed_sessions),
            "pruned_count": len(to_prune),
            "kept_count": sum(1 for decision in decisions if decision.decision == "keep"),
            "backup_dir": str(backup_dir) if backup_dir else None,
            "sessions": [session_output(decision) for decision in report_items],
            "omitted_session_count": max(0, len(decisions) - len(report_items)),
        }
    finally:
        lock_file.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prune stale local GitHub Copilot session data by age."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Delete stale local session data.")
    mode.add_argument("--dry-run", action="store_true", help="Report planned changes only (default).")
    age = parser.add_mutually_exclusive_group()
    age.add_argument("--older-than-hours", type=float, default=None)
    age.add_argument("--older-than-days", type=float, default=DEFAULT_OLDER_THAN_HOURS / 24)
    parser.add_argument("--copilot-home", type=Path, default=DEFAULT_COPILOT_HOME)
    parser.add_argument("--session-store", type=Path, default=None)
    parser.add_argument("--session-state-dir", type=Path, default=None)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--keep-session", action="append", default=[])
    parser.add_argument(
        "--include-unindexed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also prune stale session-state directories that are not indexed in session-store.db.",
    )
    parser.add_argument("--max-report", type=int, default=DEFAULT_MAX_REPORT)
    parser.add_argument("--no-input", action="store_true", help="Accepted for agent callers; never prompts.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON (default).")
    parser.add_argument("--plain", action="store_true", help="Emit compact plain text.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    started_at = time.time()
    request_id = f"{int(started_at)}-{os.getpid()}"
    args = parse_args(argv)
    plain = bool(args.plain and not args.json)
    try:
        data = run(args)
        return finish(
            status="ok",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            data=data,
            error=None,
            exit_code=0,
        )
    except ToolError as exc:
        return finish(
            status="error",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            error={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "hint": exc.hint,
            },
            exit_code=exc.exit_code,
        )
    except sqlite3.Error as exc:
        return finish(
            status="error",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            error={
                "code": "E_SQLITE",
                "message": str(exc),
                "retryable": True,
                "hint": "Close Copilot processes if the store is busy, then retry.",
            },
            exit_code=4,
        )
    except KeyboardInterrupt:
        return finish(
            status="error",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            error={
                "code": "E_TOOL",
                "message": "interrupted",
                "retryable": True,
                "hint": "Re-run when ready.",
            },
            exit_code=1,
        )


if __name__ == "__main__":
    raise SystemExit(main())
