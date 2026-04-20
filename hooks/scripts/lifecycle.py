#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


VALID_EVENTS = {"SessionStart", "Stop"}
VALID_RUNTIMES = {"codex", "claude"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Shared no-op lifecycle hook runner for Codex and Claude."
    )
    parser.add_argument("--runtime", choices=sorted(VALID_RUNTIMES), required=True)
    parser.add_argument("--event", choices=sorted(VALID_EVENTS), required=True)
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for non-interactive client compatibility; hooks never prompt.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Write validation diagnostics to stderr without changing hook output.",
    )
    return parser.parse_args()


def _debug(enabled: bool, message: str) -> None:
    if enabled:
        print(f"hook lifecycle: {message}", file=sys.stderr)


def _read_payload(debug: bool) -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        _debug(debug, "empty stdin payload")
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        _debug(debug, f"invalid JSON payload: {exc}")
        return None
    if not isinstance(payload, dict):
        _debug(debug, "payload root is not an object")
        return None
    return payload


def main() -> int:
    args = parse_args()
    payload = _read_payload(args.debug)
    if payload is not None:
        actual_event = payload.get("hook_event_name")
        if isinstance(actual_event, str) and actual_event != args.event:
            _debug(
                args.debug,
                f"event mismatch: expected {args.event}, received {actual_event}",
            )

    # Hook stdout is part of the Codex/Claude hook protocol. V1 intentionally
    # emits no stdout so both SessionStart and Stop are successful no-ops.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
