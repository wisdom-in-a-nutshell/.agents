#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


VALID_RUNTIMES = {"codex", "claude"}


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


def read_payload(debug: bool) -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"session_start: invalid JSON payload: {exc}", file=sys.stderr)
        return None
    if not isinstance(payload, dict):
        if debug:
            print("session_start: payload root is not an object", file=sys.stderr)
        return None
    return payload


def main() -> int:
    args = parse_args()
    _ = read_payload(args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
