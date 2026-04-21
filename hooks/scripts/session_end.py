#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_RUNTIMES = {"claude", "copilot"}
HOOK_EVENT = "SessionEnd"
REPO_SESSION_END = Path("scripts/hooks/session-end.sh")
GIT_ROOT_TIMEOUT_SEC = 5
MAX_LOG_BYTES = 5 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared Claude SessionEnd hook.")
    parser.add_argument("--runtime", choices=sorted(VALID_RUNTIMES), required=True)
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for non-interactive client compatibility; hooks never prompt.",
    )
    parser.add_argument("--debug", action="store_true", help="Write diagnostics to stderr.")
    return parser.parse_args()


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    try:
        log_dir = Path.home() / ".local" / "state" / "agents-control-plane" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "hooks-session-end.log"
        if log_path.exists() and log_path.stat().st_size >= MAX_LOG_BYTES:
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - MAX_LOG_BYTES))
                tail = handle.read()
            newline = tail.find(b"\n")
            if newline != -1:
                tail = tail[newline + 1 :]
            log_path.write_bytes(tail)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now_iso_z()} {message}\n")
    except Exception:
        pass


def read_payload(debug: bool) -> tuple[dict[str, Any] | None, str]:
    raw = sys.stdin.read()
    if not raw.strip():
        return None, raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"session_end: invalid JSON payload: {exc}", file=sys.stderr)
        return None, raw
    if not isinstance(payload, dict):
        if debug:
            print("session_end: payload root is not an object", file=sys.stderr)
        return None, raw
    return payload, raw


def repo_root(cwd: str) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=GIT_ROOT_TIMEOUT_SEC,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    root = result.stdout.strip()
    if not root:
        return None
    return Path(root)


def run_repo_session_end(
    root: Path,
    raw_payload: str,
    *,
    runtime: str,
    debug: bool,
) -> int:
    script = root / REPO_SESSION_END
    if not script.is_file():
        return 0

    env = os.environ.copy()
    env.update(
        {
            "AGENT_HOOK_EVENT": HOOK_EVENT,
            "AGENT_HOOK_RUNTIME": runtime,
            "AGENT_REPO_ROOT": str(root),
        }
    )
    try:
        result = subprocess.run(
            ["bash", str(script)],
            cwd=str(root),
            env=env,
            input=raw_payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        if debug:
            print(f"session_end: failed to run {script}: {exc}", file=sys.stderr)
        return 0

    if result.stdout:
        log(f"repo={root} runtime={runtime} stdout={result.stdout.strip()!r}")
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        log(f"repo={root} runtime={runtime} exit={result.returncode}")
    return 0


def main() -> int:
    args = parse_args()
    payload, raw_payload = read_payload(args.debug)
    if (payload or {}).get("hook_event_name") not in {None, HOOK_EVENT}:
        return 0
    cwd = str((payload or {}).get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if root is None:
        return 0
    return run_repo_session_end(root, raw_payload, runtime=args.runtime, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
