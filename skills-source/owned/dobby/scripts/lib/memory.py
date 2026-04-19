"""Memory commands for the Dobby CLI.

Commands:
- boot: loads profile + now + becoming + area manifest (with mtimes, no content)
- read: loads a specific section by dot-notation path
- write: appends to a section from stdin, timestamped
- diff: wraps `git log -p memory/ --since <ref>`

Section routing (dot notation):
    profile            -> memory/profile.md
    now                -> memory/now.md
    becoming           -> memory/becoming.md
    area.<name>        -> memory/areas/<name>/  (concat all .md)
    area.<name>.<file> -> memory/areas/<name>/<file>.md

Content commands (boot, read, diff) default to text/markdown on stdout so a
language-model consumer reads them natively. --json flips to the envelope.
Operation commands (write) default to the JSON envelope. --plain prints a
minimal confirmation message instead.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.contract import Envelope, emit_json, emit_text, log_stderr
from lib.workspace import WorkspaceError, workspace_root

_REPO_ROOT: Path | None = None


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

    p_boot = sub.add_parser("boot", help="Load profile + now + becoming + area manifest")
    _add_format_flags(p_boot)
    p_boot.set_defaults(handler=cmd_boot)

    p_read = sub.add_parser("read", help="Read a memory section")
    p_read.add_argument(
        "--section",
        required=True,
        help="Section path: profile | now | becoming | area.<name> | area.<name>.<file>",
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
    g.add_argument("--json", action="store_true", help="Output the full JSON envelope")
    g.add_argument("--plain", action="store_true", help="Output plain text / minimal form")


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

    if head == "profile":
        if len(parts) != 1:
            raise SectionError(f"profile takes no subsections: {section!r}")
        return memory_dir() / "profile.md"

    if head == "now":
        if len(parts) != 1:
            raise SectionError(f"now takes no subsections: {section!r}")
        return memory_dir() / "now.md"

    if head == "becoming":
        if len(parts) != 1:
            raise SectionError(f"becoming takes no subsections: {section!r}")
        return memory_dir() / "becoming.md"

    if head == "area":
        if len(parts) == 2:
            return memory_dir() / "areas" / parts[1]
        if len(parts) == 3:
            return memory_dir() / "areas" / parts[1] / f"{parts[2]}.md"
        raise SectionError(
            f"area path must be area.<name> or area.<name>.<file>: {section!r}"
        )

    raise SectionError(f"unknown section root: {head!r}")


def area_manifest() -> list[dict[str, Any]]:
    """Build the lazy manifest of area files with mtimes.

    Returns a list of {area, files[]} with file metadata (name, path,
    size_bytes, mtime_date, mtime_iso). Content is NOT included.
    """
    areas_dir = memory_dir() / "areas"
    if not areas_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for area_dir in sorted(d for d in areas_dir.iterdir() if d.is_dir()):
        files: list[dict[str, Any]] = []
        for md in sorted(area_dir.glob("*.md")):
            stat = md.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            files.append({
                "name": md.stem,
                "path": relpath(md),
                "size_bytes": stat.st_size,
                "mtime_date": mtime.strftime("%Y-%m-%d"),
                "mtime_iso": mtime.isoformat(timespec="seconds"),
            })
        out.append({"area": area_dir.name, "files": files})
    return out


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


def _render_boot_markdown(
    profile: str,
    now: str,
    becoming: str,
    manifest: list[dict[str, Any]],
) -> str:
    """Render boot payload as markdown with HTML-comment section markers.

    HTML comments are invisible in rendered markdown but give a language-model
    consumer clear, unambiguous section boundaries in the raw text — and they
    don't collide with the files' own `#` headings (which is what happens if
    we wrap them in our own H1s).
    """
    lines: list[str] = []
    lines.append("<!-- dobby memory boot: profile (memory/profile.md) -->")
    lines.append("")
    lines.append(profile.rstrip())
    lines.append("")
    lines.append("<!-- dobby memory boot: now (memory/now.md) -->")
    lines.append("")
    lines.append(now.rstrip())
    lines.append("")
    lines.append("<!-- dobby memory boot: becoming (memory/becoming.md) -->")
    lines.append("")
    lines.append(becoming.rstrip())
    lines.append("")
    lines.append(
        "<!-- dobby memory boot: areas (lazy manifest — "
        "read content via `dobby-memory read --section area.<name>`) -->"
    )
    lines.append("")
    if not manifest:
        lines.append("_no area files found_")
        lines.append("")
    for d in manifest:
        lines.append(f"### {d['area']}")
        lines.append("")
        for f in d["files"]:
            lines.append(
                f"- `{f['path']}` — {f['mtime_date']} ({f['size_bytes']}B)"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_boot(args: argparse.Namespace) -> int:
    env = Envelope("memory.boot")
    try:
        root_memory = memory_dir()
        profile = _read_file(root_memory / "profile.md")
        now = _read_file(root_memory / "now.md")
        becoming_path = root_memory / "becoming.md"
        becoming = becoming_path.read_text(encoding="utf-8") if becoming_path.exists() else ""
        manifest = area_manifest()
    except WorkspaceError as e:
        return emit_json(env.err("E_VALIDATION", str(e)))
    except FileNotFoundError as e:
        return emit_json(
            env.err(
                "E_NOT_FOUND",
                str(e),
                hint="Ensure memory/profile.md and memory/now.md exist",
            )
        )
    except OSError as e:
        return emit_json(env.err("E_IO", str(e)))
    except Exception as e:  # pragma: no cover - defensive
        return emit_json(env.err("E_RUNTIME", f"{type(e).__name__}: {e}"))

    if args.json:
        return emit_json(
            env.ok(
                {
                    "profile": profile,
                    "now": now,
                    "becoming": becoming,
                    "areas": manifest,
                    "counts": {
                        "profile_bytes": len(profile.encode("utf-8")),
                        "now_bytes": len(now.encode("utf-8")),
                        "becoming_bytes": len(becoming.encode("utf-8")),
                        "area_files": sum(len(d["files"]) for d in manifest),
                    },
                }
            )
        )

    return emit_text(
        _render_boot_markdown(profile, now, becoming, manifest),
        ensure_newline=False,
    )


def cmd_read(args: argparse.Namespace) -> int:
    env = Envelope("memory.read")
    try:
        target = resolve_section(args.section)
    except SectionError as e:
        return emit_json(
            env.err(
                "E_VALIDATION",
                str(e),
                hint="Use: profile | now | becoming | area.<name> | area.<name>.<file>",
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

    if args.json:
        return emit_json(
            env.ok(
                {
                    "section": args.section,
                    "path": relpath(target),
                    "content": content,
                    "bytes": len(content.encode("utf-8")),
                }
            )
        )
    return emit_text(content)


def cmd_write(args: argparse.Namespace) -> int:
    env = Envelope("memory.write")

    try:
        target = resolve_section(args.section)
    except SectionError as e:
        return emit_json(
            env.err(
                "E_VALIDATION",
                str(e),
                hint="Use: profile | now | becoming | area.<name>.<file>",
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

    if args.json:
        return emit_json(env.ok(payload))
    # default: concise one-liner
    return emit_text(
        f"wrote {after - before} bytes to {payload['path']} at {stamp}",
    )


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
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return emit_json(
            env.err("E_TIMEOUT", "git log timed out", hint="Reduce --since range")
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

    if args.json:
        return emit_json(
            env.ok(
                {
                    "since": args.since,
                    "diff": result.stdout,
                    "is_empty": not result.stdout.strip(),
                    "bytes": len(result.stdout.encode("utf-8")),
                }
            )
        )
    # plain default for diff — users and agents typically want raw git output
    return emit_text(result.stdout, ensure_newline=False)
