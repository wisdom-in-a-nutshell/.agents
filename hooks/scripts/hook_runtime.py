from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hook_adapter import normalize_hook_payload


GIT_ROOT_TIMEOUT_SEC = 5
MAX_CONTEXT_TOKENS = 30000
APPROX_CHARS_PER_TOKEN = 4
MAX_CONTEXT_CHARS = MAX_CONTEXT_TOKENS * APPROX_CHARS_PER_TOKEN
MAX_LOG_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class RepoHookSpec:
    event: str
    repo_script: Path
    description: str
    valid_runtimes: frozenset[str]
    label: str
    forward_stdout_as_context: bool = False
    forward_stdout_raw: bool = False
    ignore_stdout_context_runtimes: frozenset[str] = field(
        default_factory=frozenset
    )
    ignore_mismatched_event_name: bool = False
    log_stdout: bool = False
    return_repo_exit_code: bool = True


def parse_args(spec: RepoHookSpec) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=spec.description)
    parser.add_argument("--runtime", choices=sorted(spec.valid_runtimes), required=True)
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for non-interactive client compatibility; hooks never prompt.",
    )
    parser.add_argument("--debug", action="store_true", help="Write diagnostics to stderr.")
    return parser.parse_args()


def read_payload(*, debug: bool, label: str) -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"{label}: invalid JSON payload: {exc}", file=sys.stderr)
        return None
    if not isinstance(payload, dict):
        if debug:
            print(f"{label}: payload root is not an object", file=sys.stderr)
        return None
    return payload


def resolve_repo_root(cwd: str) -> Path | None:
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


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n...[truncated]"
    return text[: max(0, limit - len(suffix))] + suffix


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_hook_message(message: str) -> None:
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


def write_context_output(*, event: str, stdout: str) -> None:
    context = truncate_text(stdout, MAX_CONTEXT_CHARS)
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "additionalContext": context,
                    "hookEventName": event,
                }
            },
            sort_keys=True,
        )
    )
    sys.stdout.write("\n")


def run_repo_hook(
    spec: RepoHookSpec,
    *,
    root: Path,
    payload: dict[str, Any] | None,
    cwd: str,
    runtime: str,
    debug: bool,
) -> int:
    script = root / spec.repo_script
    if not script.is_file():
        return 0

    env = os.environ.copy()
    env.update(
        {
            "AGENT_HOOK_EVENT": spec.event,
            "AGENT_HOOK_RUNTIME": runtime,
            "AGENT_REPO_ROOT": str(root),
            "AGENT_HOOK_SCHEMA_VERSION": "1.0",
        }
    )
    repo_payload = normalize_hook_payload(
        payload,
        event=spec.event,
        runtime=runtime,
        cwd=cwd,
        repo_root=root,
    )
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            env=env,
            input=json.dumps(repo_payload, sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        if debug:
            print(f"{spec.label}: failed to run {script}: {exc}", file=sys.stderr)
        return 0

    if result.stdout:
        if spec.forward_stdout_raw:
            sys.stdout.write(result.stdout)
        elif (
            spec.forward_stdout_as_context
            and runtime not in spec.ignore_stdout_context_runtimes
        ):
            write_context_output(event=spec.event, stdout=result.stdout)
        elif spec.log_stdout:
            log_hook_message(
                f"repo={root} runtime={runtime} stdout={result.stdout.strip()!r}"
            )

    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0 and spec.log_stdout:
        log_hook_message(f"repo={root} runtime={runtime} exit={result.returncode}")
    if spec.return_repo_exit_code:
        return result.returncode
    return 0


def run_lifecycle_hook(spec: RepoHookSpec) -> int:
    args = parse_args(spec)
    payload = read_payload(debug=args.debug, label=spec.label)
    if (
        spec.ignore_mismatched_event_name
        and (payload or {}).get("hook_event_name") not in {None, spec.event}
    ):
        return 0

    cwd = str((payload or {}).get("cwd") or os.getcwd())
    root = resolve_repo_root(cwd)
    if root is None:
        return 0
    return run_repo_hook(
        spec,
        root=root,
        payload=payload,
        cwd=cwd,
        runtime=args.runtime,
        debug=args.debug,
    )
