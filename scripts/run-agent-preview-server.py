#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
from collections.abc import Sequence


def is_port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a repo preview server only when its fixed local port is free."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Preview bind host.")
    parser.add_argument("--port", required=True, type=int, help="Preview bind port.")
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to exec after --, for example: -- npm run dev",
    )
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing command after --")
    if args.port <= 0 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    url = f"http://{args.host}:{args.port}/"

    if is_port_listening(args.host, args.port):
        print(f"Agent preview already running: {url}")
        print("Reusing the existing local server; no new process started.")
        return 0

    print(f"Starting agent preview: {url}")
    print("+ " + " ".join(args.command))
    sys.stdout.flush()
    try:
        completed = subprocess.run(args.command, env=os.environ.copy(), check=False)
    except FileNotFoundError:
        print(f"ERROR: command not found: {args.command[0]}", file=sys.stderr)
        return 127
    if completed.returncode < 0:
        return 128 + abs(completed.returncode)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
