#!/usr/bin/env python3
"""Finalize a Claude Code session: run repo memory policy, then mark it done.

Twin of `finalize-codex-thread.py` for the Claude runtime. Codex threads live
in the App Server (read → repo hook → archive); Claude sessions live as
transcripts under `~/.claude/projects/<munged-cwd>/<session-id>.jsonl`. This
command derives the workspace from the transcript, runs the repo-local hook
`scripts/hooks/finalize_claude_session.py` when present (for Dobby workspaces
that hook runs `remember-claude-session`), and records the session id in a
local finalized-state file so scans never finalize the same session twice.

There is no archive step: Claude Desktop sidebar tidying is owned by the
separate `archive-stale-claude-sessions.py` job and never touches memory.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "finalize-claude-session"
HOOK_EVENT = "FinalizeClaudeSession"
DEFAULT_FINALIZATION_TIMEOUT_SECONDS = 900.0
MAX_OUTPUT_CHARS = 12_000
REPO_FINALIZER = Path("scripts/hooks/finalize_claude_session.py")

STATE_ROOT = Path.home() / ".local/state/claude-control-plane"
DEFAULT_STATE_PATH = STATE_ROOT / "finalized-claude-sessions.json"
DEFAULT_PROJECTS_DIR = Path.home() / ".claude/projects"
RUNNING_HANDSHAKE_GLOB = str(Path.home() / ".claude/sessions/*.json")


@dataclass(frozen=True)
class FinalizeResult:
    session_id: str
    transcript_path: str | None
    cwd: str | None
    repo_root: str | None
    finalizer_path: str | None
    finalizer_status: str
    finalized: bool
    skipped_reason: str | None
    error: str | None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def truncate_text(value: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    suffix = "\n...[truncated]"
    return text[: max(0, limit - len(suffix))] + suffix


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_plain(payload: dict[str, Any]) -> None:
    status = payload["status"]
    data = payload.get("data") or {}
    result = data.get("result") or {}
    if status == "ok":
        action = "finalized" if result.get("finalized") else f"skipped ({result.get('skipped_reason')})"
        print(
            f"ok {action} id={result.get('session_id')} "
            f"cwd={result.get('cwd') or 'unknown'} "
            f"repo_hook={result.get('finalizer_status')}"
        )
        return

    error = payload.get("error") or {}
    print(f"error {error.get('code', 'error')}: {error.get('message', status)}", file=sys.stderr)
    if error.get("hint"):
        print(error["hint"], file=sys.stderr)


def finish(
    *,
    status: str,
    started_at: float,
    plain: bool,
    result: FinalizeResult | None = None,
    error: dict[str, Any] | None = None,
    exit_code: int,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": status,
        "data": {"result": asdict(result) if result else None},
        "error": error,
        "meta": {
            "timestamp_utc": utc_now(),
            "duration_ms": int((time.time() - started_at) * 1000),
        },
    }
    if plain:
        emit_plain(payload)
    else:
        emit_json(payload)
    return exit_code


def projects_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR", str(DEFAULT_PROJECTS_DIR))).expanduser()


def state_path() -> Path:
    return Path(os.environ.get("CLAUDE_FINALIZE_STATE_PATH", str(DEFAULT_STATE_PATH))).expanduser()


def handshake_glob() -> str:
    return os.environ.get("CLAUDE_RUNNING_HANDSHAKE_GLOB", RUNNING_HANDSHAKE_GLOB)


def find_transcript(session_id: str) -> Path | None:
    candidates = sorted(
        projects_dir().glob(f"*/{session_id}.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def transcript_cwd(path: Path) -> str | None:
    """Last `cwd` recorded in the transcript; lines are independent JSON objects."""
    cwd: str | None = None
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if '"cwd"' not in line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                value = data.get("cwd") if isinstance(data, dict) else None
                if isinstance(value, str) and value.strip():
                    cwd = value.strip()
    except OSError:
        return None
    return cwd


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


def session_is_running(session_id: str) -> bool:
    glob_path = Path(handshake_glob())
    for path in sorted(glob_path.parent.glob(glob_path.name)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("pid")
        handshake_session = data.get("sessionId")
        if not isinstance(pid, int) or handshake_session != session_id:
            continue
        if pid_is_alive(pid):
            return True
    return False


class FinalizedState:
    """Locked JSON map of finalized session ids."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._lock_handle: Any = None

    def __enter__(self) -> "FinalizedState":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_handle = self.lock_path.open("w")
        fcntl.flock(self._lock_handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._lock_handle is not None:
            fcntl.flock(self._lock_handle, fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": SCHEMA_VERSION, "sessions": {}}
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
            return {"schema_version": SCHEMA_VERSION, "sessions": {}}
        return data

    def is_finalized(self, session_id: str) -> bool:
        return session_id in self.load()["sessions"]

    def mark(self, session_id: str, info: dict[str, Any]) -> None:
        data = self.load()
        data["sessions"][session_id] = info
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)


def repo_root_for_cwd(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return str(Path(cwd).expanduser().resolve())
    if result.returncode != 0 or not result.stdout.strip():
        return str(Path(cwd).expanduser().resolve())
    return str(Path(result.stdout.strip()).expanduser().resolve())


def run_repo_finalizer(
    *,
    finalizer_path: Path,
    repo_root: str,
    session_id: str,
    reason: str,
    finalization_timeout_seconds: float,
) -> tuple[bool, str | None, str | None]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "hook_event_name": HOOK_EVENT,
        "session_id": session_id,
        "reason": reason,
    }
    env = os.environ.copy()
    try:
        result = subprocess.run(
            [sys.executable, str(finalizer_path)],
            cwd=repo_root,
            env=env,
            input=json.dumps(payload, sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=finalization_timeout_seconds + 60,
        )
    except subprocess.TimeoutExpired as exc:
        return False, None, f"repo finalizer timed out after {exc.timeout}s"
    except OSError as exc:
        return False, None, f"repo finalizer failed to start: {exc}"

    if result.returncode == 0:
        return True, result.stdout.strip() or None, None
    output = "\n".join(part for part in [result.stderr, result.stdout] if part.strip())
    message = output.strip() or f"repo finalizer exited {result.returncode}"
    return False, None, truncate_text(message)


def skip(result_kwargs: dict[str, Any], reason: str, *, error: str | None = None) -> FinalizeResult:
    return FinalizeResult(
        **result_kwargs,
        finalizer_status="not_run",
        finalized=False,
        skipped_reason=reason,
        error=error,
    )


def finalize_session(
    *,
    session_id: str,
    reason: str,
    dry_run: bool,
    force: bool,
    finalization_timeout_seconds: float,
) -> FinalizeResult:
    base: dict[str, Any] = {
        "session_id": session_id,
        "transcript_path": None,
        "cwd": None,
        "repo_root": None,
        "finalizer_path": None,
    }

    transcript = find_transcript(session_id)
    if transcript is None:
        return skip(base, "missing_transcript", error=f"no transcript found for session {session_id}")
    base["transcript_path"] = str(transcript)

    cwd = transcript_cwd(transcript)
    if not cwd:
        # Empty or cwd-less transcripts are aborted sessions with nothing to
        # remember. Mark them finalized so scans stop retrying them forever.
        if not dry_run:
            with FinalizedState(state_path()) as state:
                state.mark(
                    session_id,
                    {
                        "finalized_at": utc_now(),
                        "reason": reason,
                        "repo_root": None,
                        "transcript_path": str(transcript),
                        "finalizer_status": "skipped-empty-transcript",
                    },
                )
        return skip(base, "empty_transcript")
    base["cwd"] = cwd

    repo_root = repo_root_for_cwd(cwd)
    base["repo_root"] = repo_root
    finalizer_path = Path(repo_root) / REPO_FINALIZER
    finalizer_path_str = str(finalizer_path) if finalizer_path.is_file() else None
    base["finalizer_path"] = finalizer_path_str

    if session_is_running(session_id):
        return skip(base, "session_running")

    with FinalizedState(state_path()) as state:
        if not force and state.is_finalized(session_id):
            return skip(base, "already_finalized")

    if dry_run:
        return FinalizeResult(
            **base,
            finalizer_status="would_run" if finalizer_path_str else "not_found",
            finalized=False,
            skipped_reason="dry_run",
            error=None,
        )

    finalizer_status = "not_found"
    if finalizer_path_str:
        ok, output, error = run_repo_finalizer(
            finalizer_path=finalizer_path,
            repo_root=repo_root,
            session_id=session_id,
            reason=reason,
            finalization_timeout_seconds=finalization_timeout_seconds,
        )
        if not ok:
            return FinalizeResult(
                **base,
                finalizer_status="failed",
                finalized=False,
                skipped_reason="finalizer_failed",
                error=error,
            )
        finalizer_status = "completed"
        if output:
            print(
                f"[finalize-claude-session] repo finalizer output: {truncate_text(output, 1000)}",
                file=sys.stderr,
            )

    with FinalizedState(state_path()) as state:
        state.mark(
            session_id,
            {
                "finalized_at": utc_now(),
                "reason": reason,
                "repo_root": repo_root,
                "transcript_path": str(transcript),
                "finalizer_status": finalizer_status,
            },
        )

    return FinalizeResult(
        **base,
        finalizer_status=finalizer_status,
        finalized=True,
        skipped_reason=None,
        error=None,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize a Claude Code session by deriving the workspace from its transcript, "
            "running an optional repo finalizer, then recording it as finalized."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Run finalization and record the session as finalized.")
    mode.add_argument("--dry-run", action="store_true", help="Resolve repo policy without running finalization (default).")
    parser.add_argument("--session-id", required=True, help="Claude Code session id to finalize.")
    parser.add_argument("--reason", default="manual", help="Reason label passed to repo finalizers.")
    parser.add_argument("--force", action="store_true", help="Finalize even if the session is already recorded as finalized.")
    parser.add_argument(
        "--finalization-timeout-seconds", type=float, default=DEFAULT_FINALIZATION_TIMEOUT_SECONDS
    )
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive callers; this command never prompts.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    parser.add_argument("--plain", action="store_true", help="Emit compact plain text for operator inspection.")
    return parser.parse_args()


def main() -> int:
    started_at = time.time()
    args = parse_args()
    plain = bool(args.plain)
    dry_run = not bool(args.apply)

    try:
        if args.finalization_timeout_seconds <= 0:
            raise ValueError("--finalization-timeout-seconds must be positive")
        result = finalize_session(
            session_id=args.session_id,
            reason=args.reason,
            dry_run=dry_run,
            force=bool(args.force),
            finalization_timeout_seconds=args.finalization_timeout_seconds,
        )
        ok_skips = {"dry_run", "already_finalized", "session_running", "empty_transcript"}
        status = "ok" if result.error is None and (result.finalized or result.skipped_reason in ok_skips) else "error"
        exit_code = 0
        if status != "ok":
            exit_code = 5 if "timed out" in (result.error or "") else 4
        return finish(
            status=status,
            started_at=started_at,
            plain=plain,
            result=result,
            error=None
            if status == "ok"
            else {
                "code": "FinalizeFailed",
                "message": result.error or result.skipped_reason or "session finalization failed",
                "hint": "Check the repo finalizer, the claude CLI, and the session transcript path.",
            },
            exit_code=exit_code,
        )
    except ValueError as exc:
        return finish(
            status="error",
            started_at=started_at,
            plain=plain,
            error={
                "code": "InvalidUsage",
                "message": str(exc),
                "retryable": False,
                "hint": "Fix the command arguments and retry.",
            },
            exit_code=2,
        )
    except Exception as exc:
        return finish(
            status="error",
            started_at=started_at,
            plain=plain,
            error={
                "code": exc.__class__.__name__,
                "message": str(exc),
                "retryable": True,
                "hint": "Run with --dry-run --json, then check the transcript and repo hook.",
            },
            exit_code=4,
        )


if __name__ == "__main__":
    raise SystemExit(main())
