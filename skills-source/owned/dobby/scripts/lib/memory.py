"""Memory commands for the Dobby CLI.

Commands:
- read: loads a specific section by dot-notation path
- write: appends to a section from stdin, timestamped
- diff: wraps `git log -p memory/ --since <ref>`

Section routing (dot notation):
    now                -> memory/now.md
    area.<name>        -> memory/areas/<name>/  (concat all .md)
    area.<name>.<file> -> memory/areas/<name>/<file>.md

Adi's durable identity lives in `soul.md` under `## About Adi` and is loaded
via the wrapper-composed system prompt. It is intentionally not served by
this CLI — editing soul.md is a manual `Edit` operation.

Boot-time loading is handled by the repo's SessionStart hook
(`scripts/hooks/session_start.py`) which reads memory files directly via
file I/O. This CLI no longer exposes a `boot` command.

Every command defaults to the Dobby JSON envelope for agent reliability.
`--plain` prints markdown/raw text for operator inspection when needed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from lib.contract import Envelope, emit_json, emit_text
from lib.workspace import WorkspaceError, workspace_root

_REPO_ROOT: Path | None = None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


GIT_TIMEOUT_SECS = _int_env("DOBBY_MEMORY_GIT_TIMEOUT_SECS", 15)


def repo_root() -> Path:
    """Return the active Dobby workspace root.

    The scripts live inside the skill, while the workspace is whichever repo
    contains `soul.md`, `memory/`, and `journal/` (or DOBBY_WORKSPACE). Resolve
    lazily so `dobby-memory --help` works even outside a workspace.
    """
    global _REPO_ROOT
    if _REPO_ROOT is None:
        _REPO_ROOT = workspace_root()
    return _REPO_ROOT


def memory_dir() -> Path:
    return repo_root() / "memory"


def relpath(path: Path) -> str:
    return path.relative_to(repo_root()).as_posix()


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------

def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="memory_cmd", required=True)

    p_read = sub.add_parser("read", help="Read a memory section")
    p_read.add_argument(
        "--section",
        required=True,
        help="Section path: now | area.<name> | area.<name>.<file>",
    )
    _add_format_flags(p_read)
    p_read.set_defaults(handler=cmd_read)

    p_write = sub.add_parser(
        "write",
        help="Append to a memory section (content from stdin)",
    )
    p_write.add_argument(
        "--section",
        required=True,
        help="Section path. Must resolve to a file (not a directory).",
    )
    p_write.add_argument(
        "--message",
        default=None,
        help="Optional one-line label stamped in the append header",
    )
    _add_format_flags(p_write)
    p_write.set_defaults(handler=cmd_write)

    p_diff = sub.add_parser(
        "diff",
        help="Show recent memory/ changes via git log -p",
    )
    p_diff.add_argument(
        "--since",
        default="1 week ago",
        help='git log --since expression (default: "1 week ago")',
    )
    _add_format_flags(p_diff)
    p_diff.set_defaults(handler=cmd_diff)


def _add_format_flags(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="Output the full JSON envelope (default)")
    g.add_argument("--plain", action="store_true", help="Output plain text / minimal form")
    p.add_argument("--no-input", action="store_true", help="Fail rather than prompt; Dobby memory commands never prompt")


# ---------------------------------------------------------------------------
# section routing
# ---------------------------------------------------------------------------

class SectionError(ValueError):
    pass


def resolve_section(section: str) -> Path:
    """Map a dot-notation section path to a filesystem path.

    Raises SectionError on unknown paths. Does not check existence.
    """
    if not section:
        raise SectionError("empty section path")
    parts = section.split(".")
    head = parts[0]

    if head == "now":
        if len(parts) != 1:
            raise SectionError(f"now takes no subsections: {section!r}")
        return memory_dir() / "now.md"

    if head == "area":
        if len(parts) == 2:
            return memory_dir() / "areas" / parts[1]
        if len(parts) == 3:
            return memory_dir() / "areas" / parts[1] / f"{parts[2]}.md"
        raise SectionError(
            f"area path must be area.<name> or area.<name>.<file>: {section!r}"
        )

    raise SectionError(f"unknown section root: {head!r}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{relpath(path)} does not exist")
    return path.read_text(encoding="utf-8")


def _read_dir_concat(path: Path) -> str:
    """Read every .md in a directory as a single concatenated markdown blob."""
    if not path.exists():
        raise FileNotFoundError(f"{relpath(path)} does not exist")
    parts: list[str] = []
    for md in sorted(path.glob("*.md")):
        parts.append(f"## {md.stem}\n\n{md.read_text(encoding='utf-8').rstrip()}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_read(args: argparse.Namespace) -> int:
    env = Envelope("memory.read")
    try:
        target = resolve_section(args.section)
    except SectionError as e:
        return emit_json(
            env.err(
                "E_VALIDATION",
                str(e),
                hint="Use: now | area.<name> | area.<name>.<file>",
            )
        )

    try:
        if target.is_dir():
            content = _read_dir_concat(target)
        else:
            content = _read_file(target)
    except FileNotFoundError as e:
        return emit_json(env.err("E_NOT_FOUND", str(e)))
    except OSError as e:
        return emit_json(env.err("E_IO", str(e)))

    payload = {
        "section": args.section,
        "path": relpath(target),
        "content": content,
        "bytes": len(content.encode("utf-8")),
    }
    if args.plain:
        return emit_text(content)
    return emit_json(env.ok(payload))


def cmd_write(args: argparse.Namespace) -> int:
    env = Envelope("memory.write")

    try:
        target = resolve_section(args.section)
    except SectionError as e:
        return emit_json(
            env.err(
                "E_VALIDATION",
                str(e),
                hint="Use: now | area.<name>.<file>",
            )
        )

    if target.exists() and target.is_dir():
        return emit_json(
            env.err(
                "E_VALIDATION",
                f"cannot write to directory {relpath(target)}",
                hint="Specify a file: area.<name>.<file>",
            )
        )
    if not target.exists():
        return emit_json(
            env.err(
                "E_NOT_FOUND",
                f"{relpath(target)} does not exist",
                hint="Phase 1 does not auto-create; create the file first",
            )
        )

    # Read content from stdin (never from flags — keeps the door open for
    # secret-bearing content and avoids shell quoting footguns for multiline).
    if sys.stdin.isatty():
        return emit_json(
            env.err(
                "E_VALIDATION",
                "content must be piped on stdin",
                hint="Pipe content into `dobby-memory write`",
            )
        )
    content = sys.stdin.read()
    if not content.strip():
        return emit_json(
            env.err(
                "E_VALIDATION",
                "empty input on stdin",
                hint="Pipe content into `dobby-memory write`",
            )
        )

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header_bits = [f"dobby write {stamp}"]
    if args.message:
        header_bits.append(args.message)
    header = "\n\n<!-- " + " — ".join(header_bits) + " -->\n"
    block = header + content.rstrip() + "\n"

    try:
        before = target.stat().st_size
        with target.open("a", encoding="utf-8") as f:
            f.write(block)
        after = target.stat().st_size
    except OSError as e:
        return emit_json(env.err("E_IO", str(e)))

    payload = {
        "section": args.section,
        "path": relpath(target),
        "bytes_appended": after - before,
        "timestamp_local": stamp,
        "message": args.message,
    }

    if args.plain:
        return emit_text(
            f"wrote {after - before} bytes to {payload['path']} at {stamp}",
        )
    return emit_json(env.ok(payload))


def cmd_diff(args: argparse.Namespace) -> int:
    env = Envelope("memory.diff")
    cmd = [
        "git",
        "-C",
        str(repo_root()),
        "log",
        f"--since={args.since}",
        "-p",
        "--",
        "memory/",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        return emit_json(
            env.err("E_TIMEOUT", f"git log timed out after {GIT_TIMEOUT_SECS}s", hint="Reduce --since range or set DOBBY_MEMORY_GIT_TIMEOUT_SECS")
        )
    except FileNotFoundError:
        return emit_json(
            env.err("E_DEPENDENCY", "git binary not found on PATH")
        )

    if result.returncode != 0:
        return emit_json(
            env.err(
                "E_RUNTIME",
                f"git log exited {result.returncode}: {result.stderr.strip()}",
            )
        )

    payload = {
        "since": args.since,
        "diff": result.stdout,
        "is_empty": not result.stdout.strip(),
        "bytes": len(result.stdout.encode("utf-8")),
        "timeout_secs": GIT_TIMEOUT_SECS,
    }
    if args.plain:
        return emit_text(result.stdout, ensure_newline=False)
    return emit_json(env.ok(payload))
