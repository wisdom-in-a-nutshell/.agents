#!/usr/bin/env python3
"""Archive stale Claude Desktop sidebar sessions by age.

Claude Desktop renders its sidebar from per-session metadata files, each of which
carries an ``isArchived`` boolean. This tool flips ``isArchived`` to ``true`` for
sessions whose ``lastActivityAt`` is older than a cutoff, which is exactly what the
right-click "Archive" action does. Newly archived sessions leave the active list the
next time Claude Desktop is restarted (the app holds sessions in memory while running).

It deliberately does NOT touch transcripts under ``~/.claude/projects`` and never
archives a session that is currently running.

Follows docs/references/cli-interface-contract.md: dry-run by default, structured JSON
envelope (``--plain`` for operators), stable exit codes, and a guarded schema check that
refuses to write when the on-disk session shape is not recognized.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "claude-session-archiver"
DEFAULT_HOURS = 24.0
STATE_ROOT = Path.home() / ".local/state/claude-control-plane"
DEFAULT_LOCK = STATE_ROOT / "archive-stale-claude-sessions.lock"
DEFAULT_BACKUP_ROOT = STATE_ROOT / "archive-stale-claude-sessions/backups"

CLAUDE_SUPPORT_DIR = Path.home() / "Library/Application Support/Claude"
SESSION_DIR_NAMES = ("claude-code-sessions", "local-agent-mode-sessions")
RUNNING_HANDSHAKE_GLOB = str(Path.home() / ".claude/sessions/*.json")

# Keys every Claude session metadata file is expected to expose.
REQUIRED_SESSION_KEYS = ("sessionId", "isArchived", "lastActivityAt")


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
    hint = "Claude session metadata shape changed; no archive was applied."


class DependencyError(ToolError):
    code = "E_DEPENDENCY"
    exit_code = 4
    retryable = True
    hint = "Another archive run may be in progress; retry once it releases the lock."


@dataclass
class SessionRef:
    path: Path
    session_id: str
    cli_session_id: str | None
    title: str | None
    is_archived: bool
    last_activity_ms: int
    group: str


@dataclass
class Decision:
    session: SessionRef
    decision: str  # "archive" | "keep"
    reason: str


@dataclass
class RunResult:
    applied: bool
    older_than_hours: float
    cutoff_ms: int
    scanned: int
    decisions: list[Decision] = field(default_factory=list)
    backup_dir: str | None = None

    @property
    def archived(self) -> list[Decision]:
        return [d for d in self.decisions if d.decision == "archive"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_utc_ms(epoch_ms: int | None) -> str | None:
    if epoch_ms is None:
        return None
    return (
        datetime.fromtimestamp(epoch_ms / 1000, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


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
        f"ok mode={mode} cutoff={data['cutoff_utc']} "
        f"scanned={data['scanned']} archived={data['archived_count']} "
        f"kept={data['kept_count']}"
    )
    for item in data["sessions"]:
        if item["decision"] != "archive":
            continue
        print(
            f"archive group={item['group']} last={item['last_activity_utc'] or 'never'} "
            f"title={item['title'] or '(untitled)'} session={item['session_id']}"
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
        raise DependencyError(f"another archive run already holds {lock_path}") from exc
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    return lock_file


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


def running_cli_session_ids(handshake_glob: str) -> set[str]:
    """CLI session ids (== metadata cliSessionId) for live Claude processes."""
    running: set[str] = set()
    glob_path = Path(handshake_glob)
    for path in sorted(glob_path.parent.glob(glob_path.name)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("pid")
        session_id = data.get("sessionId")
        if not isinstance(pid, int) or not isinstance(session_id, str):
            continue
        if pid_is_alive(pid):
            running.add(session_id)
    return running


def load_session(path: Path) -> SessionRef | None:
    """Parse one session metadata file.

    Returns None when the file is not a session metadata object (missing sessionId),
    so unrelated files do not trip the schema guard. Raises SchemaError when a file
    looks like a session but is missing required fields.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SchemaError(f"could not read session metadata: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"session metadata is not valid JSON: {path}: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("sessionId"), str):
        return None

    missing = [key for key in REQUIRED_SESSION_KEYS if key not in raw]
    if missing:
        raise SchemaError(
            f"session metadata {path} missing key(s): {', '.join(missing)}"
        )
    if not isinstance(raw["isArchived"], bool):
        raise SchemaError(f"session metadata {path}: isArchived is not a boolean")
    if not isinstance(raw["lastActivityAt"], int):
        raise SchemaError(f"session metadata {path}: lastActivityAt is not an integer (epoch ms)")

    cli_session_id = raw.get("cliSessionId")
    title = raw.get("title")
    return SessionRef(
        path=path,
        session_id=raw["sessionId"],
        cli_session_id=cli_session_id if isinstance(cli_session_id, str) else None,
        title=title if isinstance(title, str) else None,
        is_archived=raw["isArchived"],
        last_activity_ms=raw["lastActivityAt"],
        group=path.parent.parent.parent.name,  # the <dir-name> level (session dir kind)
    )


def discover_sessions(support_dir: Path) -> list[SessionRef]:
    sessions: list[SessionRef] = []
    for dir_name in SESSION_DIR_NAMES:
        root = support_dir / dir_name
        if not root.is_dir():
            continue
        # Claude Desktop stores sidebar metadata as JSON files exactly two
        # levels below each session-store root. Some local-agent-mode sessions
        # also contain nested working copies with `.claude/sessions/*.json`
        # process handshakes; those are not sidebar metadata and must not be
        # schema-checked or archived.
        for path in sorted(root.glob("*/*/*.json")):
            if not path.is_file():
                continue
            ref = load_session(path)
            if ref is None:
                continue
            ref.group = dir_name
            sessions.append(ref)
    return sessions


def write_archived(path: Path) -> None:
    """Set isArchived=true in place, preserving the compact on-disk JSON shape."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["isArchived"] = True
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(
        json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def backup_session(path: Path, backup_dir: Path, support_dir: Path) -> None:
    try:
        relative = path.relative_to(support_dir)
    except ValueError:
        relative = Path(path.name)
    target = backup_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def session_output(decision: Decision) -> dict[str, Any]:
    s = decision.session
    return {
        "session_id": s.session_id,
        "cli_session_id": s.cli_session_id,
        "title": s.title,
        "group": s.group,
        "path": str(s.path),
        "is_archived": s.is_archived,
        "last_activity_ms": s.last_activity_ms,
        "last_activity_utc": format_utc_ms(s.last_activity_ms),
        "decision": decision.decision,
        "reason": decision.reason,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.older_than_hours is not None:
        older_than_hours = args.older_than_hours
    else:
        older_than_hours = args.older_than_days * 24
    if older_than_hours <= 0:
        raise UsageError("--older-than-hours/--older-than-days must be positive")

    support_dir = args.support_dir.expanduser()
    keep_sessions = {sid for sid in args.keep_session}
    running = running_cli_session_ids(args.handshake_glob)

    lock_file = acquire_lock(args.lock.expanduser())
    try:
        # Scan + plan first; a schema error here aborts before any write.
        sessions = discover_sessions(support_dir)
        now_ms = int(time.time() * 1000)
        cutoff_ms = int(now_ms - older_than_hours * 3600 * 1000)

        decisions: list[Decision] = []
        for s in sessions:
            if s.is_archived:
                decisions.append(Decision(s, "keep", "already_archived"))
                continue
            if s.session_id in keep_sessions:
                decisions.append(Decision(s, "keep", "keep_session"))
                continue
            if s.cli_session_id is not None and s.cli_session_id in running:
                decisions.append(Decision(s, "keep", "running"))
                continue
            if s.last_activity_ms >= cutoff_ms:
                decisions.append(Decision(s, "keep", "recent"))
                continue
            decisions.append(Decision(s, "archive", "older_than_cutoff"))

        to_archive = [d for d in decisions if d.decision == "archive"]

        backup_dir: Path | None = None
        if args.apply and to_archive:
            backup_dir = args.backup_root.expanduser() / time.strftime("%Y%m%d-%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=False)
            for decision in to_archive:
                backup_session(decision.session.path, backup_dir, support_dir)
                write_archived(decision.session.path)

        return {
            "applied": bool(args.apply),
            "support_dir": str(support_dir),
            "older_than_hours": older_than_hours,
            "cutoff_ms": cutoff_ms,
            "cutoff_utc": format_utc_ms(cutoff_ms),
            "running_session_count": len(running),
            "scanned": len(sessions),
            "archived_count": len(to_archive),
            "kept_count": sum(1 for d in decisions if d.decision == "keep"),
            "backup_dir": str(backup_dir) if backup_dir else None,
            "sessions": [session_output(d) for d in decisions],
        }
    finally:
        lock_file.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive stale Claude Desktop sidebar sessions by age (guarded local edits).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write isArchived=true to stale sessions.")
    mode.add_argument("--dry-run", action="store_true", help="Report planned changes only (default).")
    age = parser.add_mutually_exclusive_group()
    age.add_argument("--older-than-hours", type=float, default=None)
    age.add_argument("--older-than-days", type=float, default=DEFAULT_HOURS / 24)
    parser.add_argument(
        "--support-dir",
        type=Path,
        default=CLAUDE_SUPPORT_DIR,
        help="Claude Application Support directory (override for tests).",
    )
    parser.add_argument(
        "--handshake-glob",
        default=RUNNING_HANDSHAKE_GLOB,
        help="Glob for live-session handshake files used to skip running sessions.",
    )
    parser.add_argument(
        "--keep-session",
        action="append",
        default=[],
        help="sessionId to always keep (never archive). Repeatable.",
    )
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
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
