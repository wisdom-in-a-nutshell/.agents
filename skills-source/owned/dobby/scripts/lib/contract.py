"""Stable CLI contract for the Dobby CLI.

Follows `client-interface-guidelines`:
- JSON envelope with schema_version, command, status, data, error, meta
- Stable error codes mapped to stable exit codes
- stdout = machine result; stderr = diagnostics
- Non-interactive, deterministic, TTY-insensitive
- No secrets in any output

Every command goes through `Envelope` for timing and shaping.
Content commands (memory boot, memory read) default to markdown on stdout
because I (the primary consumer) am a language model and markdown is natively
machine-readable. Operation commands (memory write, tasks add, etc.) default
to the JSON envelope. Every command honors `--json` and `--plain` overrides.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = "1.0"

# Stable error codes and their mapped exit codes.
# Keep both the codes and the mapping append-only — downstream tests and agents
# depend on this being stable across releases.
ERROR_EXIT_CODES: dict[str, int] = {
    "E_VALIDATION": 2,  # bad input, missing args, unknown section
    "E_NOT_FOUND": 1,   # resource (file, section, task id) does not exist
    "E_IO": 1,          # file read/write failure
    "E_RUNTIME": 1,     # generic runtime error
    "E_DEPENDENCY": 4,  # external tool missing, network unavailable
    "E_AUTH": 3,        # authentication failure (Things Cloud, etc.)
    "E_TIMEOUT": 5,     # remote call timed out
}


def now_utc_iso() -> str:
    """UTC timestamp in stable ISO-8601 form with seconds precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Envelope:
    """Builds stable JSON envelopes for a single command invocation.

    Usage:
        env = Envelope("memory.boot")
        try:
            data = do_work()
            return emit_json(env.ok(data))
        except SomeError as e:
            return emit_json(env.err("E_IO", str(e), hint="..."))
    """

    def __init__(self, command: str) -> None:
        self.command = command
        self._started = time.perf_counter()
        self.request_id = uuid.uuid4().hex

    def _meta(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "duration_ms": int((time.perf_counter() - self._started) * 1000),
            "timestamp_utc": now_utc_iso(),
        }

    def ok(self, data: Any) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "status": "ok",
            "data": data,
            "error": None,
            "meta": self._meta(),
        }

    def err(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        hint: str = "",
    ) -> dict[str, Any]:
        if code not in ERROR_EXIT_CODES:
            # Unknown error code is itself a contract bug; surface it explicitly
            # rather than silently mapping to a generic exit code.
            log_stderr(f"contract bug: unknown error code {code!r}")
            code = "E_RUNTIME"
        return {
            "schema_version": SCHEMA_VERSION,
            "command": self.command,
            "status": "error",
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "hint": hint,
            },
            "meta": self._meta(),
        }


def emit_json(envelope: dict[str, Any]) -> int:
    """Serialize envelope to stdout and return the mapped exit code.

    Always writes a single JSON object followed by a newline.
    """
    sys.stdout.write(json.dumps(envelope, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
    if envelope["status"] == "error":
        return ERROR_EXIT_CODES.get(envelope["error"]["code"], 1)
    return 0


def emit_text(content: str, *, ensure_newline: bool = True) -> int:
    """Print content (markdown, plain text, git diff, etc.) to stdout.

    Used for content commands defaulting to a non-envelope shape. The primary
    machine consumer (a language model) reads this natively — no parsing step.
    """
    sys.stdout.write(content)
    if ensure_newline and not content.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def log_stderr(msg: str) -> None:
    """Write a diagnostic line to stderr. Never touches stdout."""
    sys.stderr.write(msg)
    if not msg.endswith("\n"):
        sys.stderr.write("\n")
    sys.stderr.flush()


def err_envelope(command: str, code: str, message: str, *, hint: str = "") -> dict[str, Any]:
    """Shortcut for tests and top-level error reporting without a live Envelope."""
    env = Envelope(command)
    return env.err(code, message, hint=hint)
