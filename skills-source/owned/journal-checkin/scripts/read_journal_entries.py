#!/usr/bin/env python3

"""Read and format journal entries for agent consumption.

Outputs markdown (default) or JSON. Designed for deterministic,
non-interactive use by any agent.

Exit codes:
  0  success (entries found and printed to stdout)
  1  error (bad arguments, I/O failure — message on stderr)
  2  no entries found matching the query
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


VALID_KINDS = {"morning", "night", "general", "all"}


# ── workspace detection (mirrors write_journal_entry.py) ─────────────

def detect_workspace_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in [cwd, *cwd.parents]:
        if (path / "AGENTS.md").is_file():
            return path
    return cwd


# ── argument parsing ─────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read journal entries and output markdown or JSON.",
    )
    parser.add_argument(
        "--from", dest="from_date",
        help="Start date inclusive (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to", dest="to_date",
        help="End date inclusive (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--last", type=int,
        help="Shorthand: last N days (alternative to --from/--to).",
    )
    parser.add_argument(
        "--kind", default="all", choices=sorted(VALID_KINDS),
        help="Filter by entry type. Default: all.",
    )
    parser.add_argument(
        "--format", dest="fmt", default="markdown",
        choices=["markdown", "json"],
        help="Output format. Default: markdown.",
    )
    parser.add_argument(
        "--workspace-root",
        help="Workspace root. Auto-detects if omitted.",
    )
    return parser.parse_args()


def resolve_date_range(args: argparse.Namespace) -> tuple[date, date]:
    today = date.today()

    if args.last is not None:
        if args.last < 1:
            print("--last must be >= 1", file=sys.stderr)
            sys.exit(1)
        return today - timedelta(days=args.last - 1), today

    if args.from_date is None and args.to_date is None:
        return today - timedelta(days=6), today

    try:
        start = date.fromisoformat(args.from_date) if args.from_date else today - timedelta(days=6)
        end = date.fromisoformat(args.to_date) if args.to_date else today
    except ValueError as exc:
        print(f"Invalid date: {exc}", file=sys.stderr)
        sys.exit(1)

    if start > end:
        print("--from date must be <= --to date", file=sys.stderr)
        sys.exit(1)

    return start, end


# ── entry loading ────────────────────────────────────────────────────

def load_json_entry(path: Path, entry_date: str, kind: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    data.setdefault("date", entry_date)
    data.setdefault("kind", kind)
    return data


def load_general_entry(path: Path, entry_date: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    if not text:
        return None
    return {"date": entry_date, "kind": "general", "content": text}


def collect_entries(
    entries_dir: Path,
    start: date,
    end: date,
    kind_filter: str,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current = start
    while current <= end:
        day_str = current.isoformat()
        day_dir = entries_dir / day_str

        if day_dir.is_dir():
            if kind_filter in ("all", "morning"):
                entry = load_json_entry(day_dir / "morning.json", day_str, "morning")
                if entry:
                    entries.append(entry)

            if kind_filter in ("all", "night"):
                entry = load_json_entry(day_dir / "night.json", day_str, "night")
                if entry:
                    entries.append(entry)

            if kind_filter in ("all", "general"):
                entry = load_general_entry(day_dir / "general.md", day_str)
                if entry:
                    entries.append(entry)

        current += timedelta(days=1)
    return entries


# ── markdown rendering ───────────────────────────────────────────────

def _score_line(label: str, state: dict[str, Any]) -> str:
    score = state.get("score_10", "?")
    notes = state.get("notes", "")
    if notes:
        return f"- {label}: {score}/10 — {notes}"
    return f"- {label}: {score}/10"


def render_morning_md(entry: dict[str, Any]) -> list[str]:
    lines = ["## Morning", ""]
    for field in ("sleep", "energy", "mood"):
        val = entry.get(field)
        if isinstance(val, dict):
            lines.append(_score_line(field.capitalize(), val))
    grateful = entry.get("grateful")
    if isinstance(grateful, list) and grateful:
        lines.append(f"- Grateful: {'; '.join(str(g) for g in grateful)}")
    otm = entry.get("one_thing_that_matters")
    if otm:
        lines.append(f"- One thing that matters: {otm}")
    show_up = entry.get("show_up_as")
    if show_up:
        lines.append(f"- Show up as: {show_up}")
    lines.append("")
    return lines


def render_night_md(entry: dict[str, Any]) -> list[str]:
    lines = ["## Night", ""]
    for field in ("mood", "energy"):
        val = entry.get(field)
        if isinstance(val, dict):
            lines.append(_score_line(field.capitalize(), val))
    for field, label in [
        ("went_well", "Went well"),
        ("could_have_been_improved", "Could improve"),
        ("actions_to_improve_tomorrow", "Tomorrow"),
    ]:
        val = entry.get(field)
        if val:
            lines.append(f"- {label}: {val}")
    lines.append("")
    return lines


def render_general_md(entry: dict[str, Any]) -> list[str]:
    content = entry.get("content", "")
    lines = ["## General", ""]
    for line in content.splitlines():
        lines.append(line)
    lines.append("")
    return lines


def entries_to_markdown(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return ""

    # Group entries by date
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        d = entry["date"]
        grouped.setdefault(d, []).append(entry)

    output_lines: list[str] = []
    for day_date in sorted(grouped.keys(), reverse=True):
        if output_lines:
            output_lines.append("---")
            output_lines.append("")
        output_lines.append(f"# Journal: {day_date}")
        output_lines.append("")
        for entry in grouped[day_date]:
            kind = entry.get("kind", "")
            if kind == "morning":
                output_lines.extend(render_morning_md(entry))
            elif kind == "night":
                output_lines.extend(render_night_md(entry))
            elif kind == "general":
                output_lines.extend(render_general_md(entry))

    return "\n".join(output_lines).rstrip() + "\n"


# ── JSON rendering ───────────────────────────────────────────────────

def entries_to_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, indent=2, ensure_ascii=False)


# ── main ─────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()

    workspace_root = (
        Path(args.workspace_root).resolve()
        if args.workspace_root
        else detect_workspace_root()
    )
    entries_dir = workspace_root / "journal" / "daily"

    if not entries_dir.is_dir():
        print(f"Journal daily directory not found: {entries_dir}", file=sys.stderr)
        return 1

    start, end = resolve_date_range(args)
    entries = collect_entries(entries_dir, start, end, args.kind)

    if not entries:
        print(
            f"No entries found from {start.isoformat()} to {end.isoformat()}"
            + (f" (kind={args.kind})" if args.kind != "all" else ""),
            file=sys.stderr,
        )
        return 2

    if args.fmt == "json":
        sys.stdout.write(entries_to_json(entries) + "\n")
    else:
        sys.stdout.write(entries_to_markdown(entries))

    return 0


if __name__ == "__main__":
    sys.exit(main())
