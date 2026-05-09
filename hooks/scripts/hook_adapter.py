from __future__ import annotations

from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


def _first_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _source_thread_id(raw_payload: dict[str, Any]) -> str | None:
    return _first_text(
        raw_payload,
        "source_thread_id",
        "sourceThreadId",
        "thread_id",
        "threadId",
        # Runtime hook payloads may still call the active Codex/App Server
        # thread a session. Keep that name at the boundary only.
        "session_id",
        "sessionId",
    )


def _source_turn_id(raw_payload: dict[str, Any]) -> str | None:
    return _first_text(
        raw_payload,
        "source_turn_id",
        "sourceTurnId",
        "turn_id",
        "turnId",
    )


def _transcript_format(
    payload: dict[str, Any],
    *,
    runtime: str,
    transcript_path: str | None,
) -> str | None:
    explicit = _first_text(payload, "transcript_format", "transcriptFormat")
    if explicit:
        return explicit
    if not transcript_path:
        return None
    if runtime == "claude":
        return "claude-jsonl"
    if runtime == "copilot":
        return "copilot-gateway-jsonl"
    return "unknown"


def normalize_hook_payload(
    payload: dict[str, Any] | None,
    *,
    event: str,
    runtime: str,
    cwd: str,
    repo_root: Path,
) -> dict[str, Any]:
    raw_payload = payload or {}
    transcript_path = _first_text(raw_payload, "transcript_path", "transcriptPath")

    return {
        "schema_version": SCHEMA_VERSION,
        "hook_event_name": event,
        "runtime": runtime,
        "cwd": cwd,
        "repo_root": str(repo_root),
        "source_thread_id": _source_thread_id(raw_payload),
        "source_turn_id": _source_turn_id(raw_payload),
        "session_id": _first_text(raw_payload, "session_id", "sessionId"),
        "turn_id": _first_text(raw_payload, "turn_id", "turnId"),
        "model": _first_text(raw_payload, "model"),
        "timestamp": raw_payload.get("timestamp"),
        "source": _first_text(raw_payload, "source"),
        "reason": _first_text(raw_payload, "reason"),
        "prompt": _first_text(raw_payload, "prompt"),
        "initial_prompt": _first_text(raw_payload, "initial_prompt", "initialPrompt"),
        "final_message": _first_text(raw_payload, "final_message", "finalMessage"),
        "error": raw_payload.get("error"),
        "transcript_path": transcript_path,
        "transcript_format": _transcript_format(
            raw_payload,
            runtime=runtime,
            transcript_path=transcript_path,
        ),
        "raw_payload": raw_payload,
    }
