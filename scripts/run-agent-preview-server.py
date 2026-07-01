#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path


def is_port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def listener_pids(port: int) -> list[int]:
    proc = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    pids: list[int] = []
    for line in proc.stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pids.append(int(line[1:]))
    return sorted(set(pids))


def cwd_for_pid(pid: int) -> Path | None:
    proc = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("n/"):
            return Path(line[1:])
    return None


def expected_dir(command: list[str]) -> Path | None:
    """Best-effort `cd <path>` target parsed from the wrapped command string."""
    for token in command:
        match = re.search(r"(?:^|&&|;)\s*cd\s+([^\s&;]+)", token)
        if match:
            return Path(expand_shell_path_token(match.group(1))).expanduser()
    return None


def expand_shell_path_token(token: str) -> str:
    token = token.strip("\"'")
    home = os.environ.get("HOME", str(Path.home()))

    match = re.match(r"^\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)\}(.*)$", token)
    if match:
        name, fallback, suffix = match.groups()
        value = os.environ.get(name) or fallback
        token = value + suffix

    return token.replace("${HOME}", home).replace("$HOME", home)


def terminate(pid: int, grace_seconds: float = 5.0) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return True


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


def reclaim_or_classify(args: argparse.Namespace) -> str:
    """Decide what to do with a busy port: 'free', 'reuse', or exit with a message.

    A listener whose working directory no longer exists is a stale orphan
    (e.g. a dev server that outlived its checkout): kill it and take the port.
    A live listener in the wrong directory is NOT reused silently — a preview
    pointing at the wrong app is worse than an error.
    """
    if not is_port_listening(args.host, args.port):
        return "free"

    pids = listener_pids(args.port)
    want = expected_dir(args.command)
    reclaimed = False
    for pid in pids:
        cwd = cwd_for_pid(pid)
        if cwd is not None and not cwd.exists():
            print(
                f"Reclaiming port {args.port}: stale listener pid={pid} "
                f"(working directory deleted: {cwd})"
            )
            if not terminate(pid):
                raise SystemExit(f"ERROR: could not terminate stale listener pid={pid}")
            reclaimed = True
            continue
        if want is not None and cwd is not None and cwd.exists():
            try:
                cwd.resolve().relative_to(want.resolve())
            except ValueError:
                raise SystemExit(
                    f"ERROR: port {args.port} is held by pid={pid} running in {cwd}, "
                    f"but this preview expects a server from {want}. Refusing to reuse "
                    f"a mismatched server; stop pid={pid} or fix the launch config."
                )

    if reclaimed:
        time.sleep(0.5)
    return "free" if not is_port_listening(args.host, args.port) else "reuse"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    url = f"http://{args.host}:{args.port}/"

    state = reclaim_or_classify(args)
    if state == "reuse":
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
