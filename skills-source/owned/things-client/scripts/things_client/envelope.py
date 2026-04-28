from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .errors import ERROR_EXIT_CODES, ThingsError

SCHEMA_VERSION = "1.0"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def command_from_prog(prog: str) -> str:
    parts = prog.split()
    return f"things-client.{parts[1]}" if len(parts) > 1 else "things-client.cli"


def envelope(command: str, status: str, *, data: Any = None, error: dict[str, Any] | None = None, started: float | None = None) -> dict[str, Any]:
    started = started or time.perf_counter()
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data,
        "error": error,
        "meta": {
            "request_id": uuid.uuid4().hex,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "timestamp_utc": now_utc(),
        },
    }


def error_envelope(command: str, code: str, message: str, *, hint: str = "", retryable: bool = False) -> dict[str, Any]:
    return envelope(
        command,
        "error",
        error={"code": code, "message": message, "retryable": retryable, "hint": hint},
    )


def emit_json(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()
    if payload["status"] == "error":
        return ERROR_EXIT_CODES.get(payload["error"]["code"], 1)
    return 0


def emit_text(text: str) -> int:
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def error_payload(exc: ThingsError) -> dict[str, Any]:
    return {"code": exc.code, "message": exc.message, "retryable": exc.retryable, "hint": exc.hint}
