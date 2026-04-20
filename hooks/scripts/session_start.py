#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


VALID_RUNTIMES = {"codex", "claude"}
REPO_SESSION_START = Path("scripts/hooks/session-start.sh")
GIT_ROOT_TIMEOUT_SEC = 5
MAX_CONTEXT_CHARS = 12000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared SessionStart hook.")
    parser.add_argument("--runtime", choices=sorted(VALID_RUNTIMES), required=True)
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for non-interactive client compatibility; hooks never prompt.",
    )
    parser.add_argument("--debug", action="store_true", help="Write diagnostics to stderr.")
    return parser.parse_args()


def read_payload(debug: bool) -> tuple[dict[str, Any] | None, str]:
    raw = sys.stdin.read()
    if not raw.strip():
        return None, raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"session_start: invalid JSON payload: {exc}", file=sys.stderr)
        return None, raw
    if not isinstance(payload, dict):
        if debug:
            print("session_start: payload root is not an object", file=sys.stderr)
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


def run_repo_session_start(
    root: Path,
    raw_payload: str,
    *,
    runtime: str,
    debug: bool,
) -> int:
    script = root / REPO_SESSION_START
    if not script.is_file():
        return 0

    env = os.environ.copy()
    env.update(
        {
            "AGENT_HOOK_EVENT": "SessionStart",
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
            print(f"session_start: failed to run {script}: {exc}", file=sys.stderr)
        return 0

    if result.stdout:
        context = truncate_text(result.stdout, MAX_CONTEXT_CHARS)
        sys.stdout.write(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "additionalContext": context,
                        "hookEventName": "SessionStart",
                    }
                },
                sort_keys=True,
            )
        )
        sys.stdout.write("\n")
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n...[truncated]"
    return text[: max(0, limit - len(suffix))] + suffix


def main() -> int:
    args = parse_args()
    payload, raw_payload = read_payload(args.debug)
    cwd = str((payload or {}).get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if root is None:
        return 0
    return run_repo_session_start(root, raw_payload, runtime=args.runtime, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
