#!/usr/bin/env python3
"""Finalize stale Claude Code sessions for registered repos.

Twin of `finalize-stale-codex-threads.py`. Codex threads are listed via the
App Server; Claude sessions are discovered from transcript files under
`~/.claude/projects/<munged-repo-path>/<session-id>.jsonl`. A session is stale
when its transcript has not been touched for the cutoff window, it is not a
live CLI session, and it has not already been finalized (tracked in the
`finalize-claude-session` state file).

Each candidate is finalized through the global `finalize-claude-session.py`
primitive with reason `stale-cleanup`. For Dobby workspaces that runs one
remember-session turn per session (a real model call), so apply runs are
capped by `--max-sessions` per invocation; the remainder is reported and
picked up by later runs.

`--mark-only` records candidates as finalized WITHOUT running any remember
turn. Use it once at activation to absorb the pre-parity backlog so the
hourly loop only ever chews on recent sessions.

Dry-run by default. Follows the agent CLI contract: JSON envelope, stable
exit codes, `--no-input` accepted, exclusive lock against concurrent runs.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "finalize-stale-claude-sessions"
DEFAULT_OLDER_THAN_HOURS = 24.0
DEFAULT_MAX_SESSIONS = 10
DEFAULT_MAX_REPORT = 25
DEFAULT_FINALIZATION_TIMEOUT_SECONDS = 900.0
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT_DIR / "codex" / "config" / "repo-bootstrap.json"
FINALIZER_BIN = Path(__file__).resolve().parent / "finalize-claude-session.py"

STATE_ROOT = Path.home() / ".local/state/claude-control-plane"
DEFAULT_STATE_PATH = STATE_ROOT / "finalized-claude-sessions.json"
DEFAULT_LOCK_PATH = STATE_ROOT / "finalize-stale-claude-sessions.lock"
DEFAULT_PROJECTS_DIR = Path.home() / ".claude/projects"
RUNNING_HANDSHAKE_GLOB = str(Path.home() / ".claude/sessions/*.json")

SESSION_STEM_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@dataclass(frozen=True)
class Candidate:
    session_id: str
    transcript_path: str
    repo_path: str
    mtime_epoch: float


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def expand_path(raw: str) -> str:
    return str(Path(raw).expanduser().absolute())


def load_registry_repos(registry: Path) -> list[str]:
    data = json.loads(registry.read_text(encoding="utf-8"))
    entries = data.get("repos") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError(f"expected repo registry with a repos list: {registry}")
    repos: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        path = expand_path(raw_path.strip())
        if path not in seen:
            seen.add(path)
            repos.append(path)
    return repos


def munge_project_dir(repo_path: str) -> str:
    """Claude Code project dir name: every non-alphanumeric char becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", repo_path)


def projects_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR", str(DEFAULT_PROJECTS_DIR))).expanduser()


def state_path() -> Path:
    return Path(os.environ.get("CLAUDE_FINALIZE_STATE_PATH", str(DEFAULT_STATE_PATH))).expanduser()


def handshake_glob() -> str:
    return os.environ.get("CLAUDE_RUNNING_HANDSHAKE_GLOB", RUNNING_HANDSHAKE_GLOB)


def load_finalized_ids() -> set[str]:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    sessions = data.get("sessions") if isinstance(data, dict) else None
    return set(sessions) if isinstance(sessions, dict) else set()


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


def running_session_ids() -> set[str]:
    running: set[str] = set()
    glob_path = Path(handshake_glob())
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


def list_candidates(repos: list[str], cutoff_epoch: float) -> list[Candidate]:
    finalized = load_finalized_ids()
    running = running_session_ids()
    base = projects_dir()
    candidates: list[Candidate] = []
    for repo in repos:
        project_dir = base / munge_project_dir(repo)
        if not project_dir.is_dir():
            continue
        for transcript in project_dir.glob("*.jsonl"):
            stem = transcript.stem
            if not SESSION_STEM_RE.match(stem):
                continue
            if stem in finalized or stem in running:
                continue
            try:
                mtime = transcript.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff_epoch:
                continue
            candidates.append(
                Candidate(
                    session_id=stem,
                    transcript_path=str(transcript),
                    repo_path=repo,
                    mtime_epoch=mtime,
                )
            )
    return sorted(candidates, key=lambda c: c.mtime_epoch)


def mark_candidates(candidates: list[Candidate], reason: str) -> int:
    """Record candidates as finalized without running any remember turn."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {"schema_version": SCHEMA_VERSION, "sessions": {}}
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
            data = {"schema_version": SCHEMA_VERSION, "sessions": {}}
        marked = 0
        for candidate in candidates:
            if candidate.session_id in data["sessions"]:
                continue
            data["sessions"][candidate.session_id] = {
                "finalized_at": utc_now(),
                "reason": reason,
                "repo_root": candidate.repo_path,
                "transcript_path": candidate.transcript_path,
                "finalizer_status": "bootstrap-marked",
            }
            marked += 1
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
    return marked


def finalize_candidate(candidate: Candidate, *, reason: str, timeout_seconds: float) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(FINALIZER_BIN),
        "--session-id",
        candidate.session_id,
        "--reason",
        reason,
        "--apply",
        "--no-input",
        "--json",
        "--finalization-timeout-seconds",
        str(timeout_seconds),
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds + 120,
        )
    except subprocess.TimeoutExpired:
        return {"session_id": candidate.session_id, "status": "error", "error": "finalizer timed out"}
    except OSError as exc:
        return {"session_id": candidate.session_id, "status": "error", "error": f"failed to start finalizer: {exc}"}

    summary: dict[str, Any] = {
        "session_id": candidate.session_id,
        "repo_path": candidate.repo_path,
        "exit_code": result.returncode,
    }
    try:
        payload = json.loads(result.stdout)
        inner = (payload.get("data") or {}).get("result") or {}
        summary["status"] = payload.get("status")
        summary["finalized"] = inner.get("finalized")
        summary["finalizer_status"] = inner.get("finalizer_status")
        summary["skipped_reason"] = inner.get("skipped_reason")
        if inner.get("error"):
            summary["error"] = inner["error"]
    except json.JSONDecodeError:
        summary["status"] = "error" if result.returncode != 0 else "ok"
        tail = (result.stderr or result.stdout or "").strip()
        if tail and result.returncode != 0:
            summary["error"] = tail[-1000:]
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize stale Claude Code sessions for registered repos via finalize-claude-session."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Finalize candidates (runs remember turns for Dobby repos).")
    mode.add_argument("--dry-run", action="store_true", help="List candidates without finalizing (default).")
    mode.add_argument(
        "--mark-only",
        action="store_true",
        help="Record candidates as finalized without running remember turns (backlog bootstrap).",
    )
    age = parser.add_mutually_exclusive_group()
    age.add_argument(
        "--older-than-hours",
        type=float,
        default=DEFAULT_OLDER_THAN_HOURS,
        help=f"Finalize sessions whose transcript mtime is older than this many hours (default: {DEFAULT_OLDER_THAN_HOURS:g}).",
    )
    age.add_argument("--older-than-days", type=float, help="Cutoff in days.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=DEFAULT_MAX_SESSIONS,
        help=f"Maximum sessions to finalize per apply run; the rest wait for the next run (default: {DEFAULT_MAX_SESSIONS}).",
    )
    parser.add_argument("--max-report", type=int, default=DEFAULT_MAX_REPORT)
    parser.add_argument(
        "--finalization-timeout-seconds", type=float, default=DEFAULT_FINALIZATION_TIMEOUT_SECONDS
    )
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive callers; this command never prompts.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON (default).")
    parser.add_argument("--plain", action="store_true", help="Emit compact plain text for operator inspection.")
    return parser.parse_args()


def emit(payload: dict[str, Any], plain: bool) -> None:
    if not plain:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    data = payload.get("data") or {}
    print(
        f"{payload.get('status')} candidates={data.get('candidate_count')} "
        f"processed={len(data.get('results') or [])} deferred={data.get('deferred_count')} "
        f"marked={data.get('marked_count')}"
    )
    for line in (data.get("candidates") or [])[: data.get("max_report") or DEFAULT_MAX_REPORT]:
        print(f"  {line}")


def main() -> int:
    started_at = time.time()
    args = parse_args()
    plain = bool(args.plain)

    older_than_hours = args.older_than_hours
    if args.older_than_days is not None:
        older_than_hours = args.older_than_days * 24.0
    if older_than_hours <= 0:
        print("--older-than-hours must be positive", file=sys.stderr)
        return 2
    if args.max_sessions <= 0:
        print("--max-sessions must be positive", file=sys.stderr)
        return 2

    lock_path = Path(os.environ.get("CLAUDE_STALE_SCAN_LOCK_PATH", str(DEFAULT_LOCK_PATH))).expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("w")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another finalize-stale-claude-sessions run holds the lock", file=sys.stderr)
        return 6

    try:
        repos = load_registry_repos(args.registry.expanduser())
        cutoff_epoch = time.time() - older_than_hours * 3600.0
        candidates = list_candidates(repos, cutoff_epoch)

        data: dict[str, Any] = {
            "older_than_hours": older_than_hours,
            "candidate_count": len(candidates),
            "max_sessions": args.max_sessions,
            "max_report": args.max_report,
            "candidates": [
                f"{c.session_id} repo={c.repo_path} idle_since={datetime.fromtimestamp(c.mtime_epoch, UTC).isoformat(timespec='seconds')}"
                for c in candidates[: args.max_report]
            ],
            "results": [],
            "deferred_count": 0,
            "marked_count": 0,
        }

        status = "ok"
        if args.mark_only:
            data["marked_count"] = mark_candidates(candidates, "bootstrap-mark")
        elif args.apply:
            batch = candidates[: args.max_sessions]
            data["deferred_count"] = max(0, len(candidates) - len(batch))
            results = [
                finalize_candidate(c, reason="stale-cleanup", timeout_seconds=args.finalization_timeout_seconds)
                for c in batch
            ]
            data["results"] = results
            if any(r.get("status") != "ok" for r in results):
                status = "partial"

        payload = {
            "schema_version": SCHEMA_VERSION,
            "command": COMMAND,
            "status": status,
            "data": data,
            "error": None,
            "meta": {
                "timestamp_utc": utc_now(),
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        }
        emit(payload, plain)
        return 0 if status == "ok" else 3
    except Exception as exc:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "command": COMMAND,
            "status": "error",
            "data": None,
            "error": {
                "code": exc.__class__.__name__,
                "message": str(exc),
                "retryable": True,
                "hint": "Run with --dry-run --json and check the registry, projects dir, and state file.",
            },
            "meta": {
                "timestamp_utc": utc_now(),
                "duration_ms": int((time.time() - started_at) * 1000),
            },
        }
        emit(payload, plain)
        return 4
    finally:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
        finally:
            lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
