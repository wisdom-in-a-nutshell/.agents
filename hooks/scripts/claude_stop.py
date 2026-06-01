#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


def load_stop_module() -> Any:
    stop_path = Path(__file__).with_name("stop.py")
    spec = importlib.util.spec_from_file_location("agents_stop_hook", stop_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load shared Stop hook: {stop_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_text": raw}
    return payload if isinstance(payload, dict) else {"raw_payload": payload}


def first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def cwd_from_payload(payload: dict[str, Any]) -> str:
    cwd = payload.get("cwd")
    transcript = payload.get("transcript_path") or payload.get("transcriptPath")
    transcript_dir = str(Path(transcript).parent) if isinstance(transcript, str) and transcript.strip() else None
    return first_string(
        cwd,
        payload.get("workingDirectory"),
        payload.get("workspace_dir"),
        payload.get("workspaceDir"),
        os.environ.get("AGENT_REPO_ROOT"),
        transcript_dir,
        os.getcwd(),
    ) or os.getcwd()


def normalize_payload(payload: dict[str, Any], cwd: str) -> dict[str, Any]:
    normalized = {
        "hook_event_name": "Stop",
        "cwd": cwd,
        "runtime": "claude",
        "raw_payload": payload,
    }
    for source_key, target_key in (
        ("session_id", "session_id"),
        ("sessionId", "session_id"),
        ("conversation_id", "session_id"),
        ("conversationId", "session_id"),
        ("transcript_path", "session_id"),
        ("model_provider", "model_provider"),
        ("modelProvider", "model_provider"),
    ):
        value = payload.get(source_key)
        if isinstance(value, str) and value.strip() and target_key not in normalized:
            normalized[target_key] = value.strip()
    return normalized


def main() -> int:
    payload = read_payload()
    cwd = cwd_from_payload(payload)
    normalized = normalize_payload(payload, cwd)
    stop = load_stop_module()

    try:
        output = stop.process_repo(cwd, normalized, runtime="claude")
    except Exception as exc:
        output = stop.warning(f"Claude Stop adapter failed: {exc}")

    if output:
        sys.stdout.write(json.dumps(output, sort_keys=True))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
