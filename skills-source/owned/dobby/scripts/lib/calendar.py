"""Calendar commands for the Dobby CLI — macOS EventKit via `ical`.

This wrapper keeps Dobby's stable agent contract while using BRO3886/ical as
an EventKit backend. `ical` talks to the local macOS calendar store, including
Google calendars synced into Calendar.app, without the AppleScript broad-search
hangs we hit during birthday migration.

Design rules:
- JSON envelope by default for every calendar command; --plain is inspection.
- No interactive commands are exposed; --no-input is accepted and honored.
- Search is date-bounded by requirement.
- No delete/update commands in v1; writes are add/upsert only.
- Default calendar is required via DOBBY_CALENDAR_DEFAULT env var (no fallback).
  Commands that need a specific calendar fail fast when it is unset and
  --calendar is not passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta
from typing import Any

from lib.contract import Envelope, emit_json, emit_text

DEFAULT_CALENDAR = os.environ.get("DOBBY_CALENDAR_DEFAULT")  # None when unset — fail fast downstream

_CALENDAR_HELP = (
    f"Calendar name (default: {DEFAULT_CALENDAR})"
    if DEFAULT_CALENDAR
    else "Calendar name (required — set DOBBY_CALENDAR_DEFAULT or pass --calendar)"
)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


ICAL_TIMEOUT_SECS = _int_env("DOBBY_CALENDAR_TIMEOUT_SECS", 20)


class CalendarError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="calendar_cmd", required=True)

    p = sub.add_parser("doctor", help="Check ical/EventKit calendar connectivity")
    _fmt(p)
    p.set_defaults(handler=cmd_doctor)

    p = sub.add_parser("calendars", help="List calendars visible to EventKit")
    _fmt(p)
    p.set_defaults(handler=cmd_calendars)

    p = sub.add_parser("today", help="List today's events")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=cmd_today)

    p = sub.add_parser("upcoming", help="List upcoming events for N days")
    p.add_argument("--days", type=int, default=7, help="Number of days ahead (default: 7)")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=cmd_upcoming)

    p = sub.add_parser("week", help="List events for the next 7 days")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=lambda a: _cmd_upcoming_days(a, 7, "calendar.week"))

    p = sub.add_parser("month", help="List events for the next 30 days")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=lambda a: _cmd_upcoming_days(a, 30, "calendar.month"))

    p = sub.add_parser("list", help="List events in a required date range")
    p.add_argument("--from", dest="from_date", required=True, help="Start date/time, natural language or ISO")
    p.add_argument("--to", dest="to_date", required=True, help="End date/time, natural language or ISO")
    p.add_argument("--query", help="Optional title/location/notes substring")
    p.add_argument("--limit", type=int, help="Max events")
    p.add_argument("--no-recurring", action="store_true", help="Hide recurring events")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("search", help="Search events in a required date range")
    p.add_argument("query")
    p.add_argument("--from", dest="from_date", required=True, help="Start date/time, natural language or ISO")
    p.add_argument("--to", dest="to_date", required=True, help="End date/time, natural language or ISO")
    p.add_argument("--limit", type=int, help="Max events")
    p.add_argument("--no-recurring", action="store_true", help="Hide recurring events")
    _calendar_filter_flags(p)
    _fmt(p)
    p.set_defaults(handler=cmd_search)

    p = sub.add_parser("add-event", help="Create a calendar event")
    p.add_argument("--title", required=True)
    p.add_argument("--start", required=True, help="Start date/time, natural language or ISO")
    p.add_argument("--end", help="End date/time, natural language or ISO")
    p.add_argument("--calendar", default=DEFAULT_CALENDAR, help=_CALENDAR_HELP)
    p.add_argument("--all-day", action="store_true")
    p.add_argument("--location")
    p.add_argument("--notes")
    p.add_argument("--url")
    p.add_argument("--repeat", choices=["daily", "weekly", "monthly", "yearly"], help="Recurrence")
    p.add_argument("--repeat-until")
    p.add_argument("--no-alert", action="store_true", help="Suppress calendar default alerts")
    p.add_argument("--dry-run", action="store_true", help="Return planned operation without creating")
    _fmt(p)
    p.set_defaults(handler=cmd_add_event)

    p = sub.add_parser("upsert-event", help="Create event only if no exact title exists in match range")
    p.add_argument("--title", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end")
    p.add_argument("--calendar", default=DEFAULT_CALENDAR, help=_CALENDAR_HELP)
    p.add_argument("--match-from", required=True, help="Search start for duplicate detection")
    p.add_argument("--match-to", required=True, help="Search end for duplicate detection")
    p.add_argument("--all-day", action="store_true")
    p.add_argument("--location")
    p.add_argument("--notes")
    p.add_argument("--url")
    p.add_argument("--repeat", choices=["daily", "weekly", "monthly", "yearly"])
    p.add_argument("--repeat-until")
    p.add_argument("--no-alert", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    _fmt(p)
    p.set_defaults(handler=cmd_upsert_event)


def _fmt(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="Dobby JSON envelope (default)")
    g.add_argument("--plain", action="store_true", help="Compact plain text")
    p.add_argument("--no-input", action="store_true", help="Fail rather than prompt; calendar commands never prompt")


def _calendar_filter_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--calendar", default=DEFAULT_CALENDAR, help=_CALENDAR_HELP)
    p.add_argument("--all-calendars", action="store_true", help="Search/list all visible calendars instead of the default calendar")


# ---------------------------------------------------------------------------
# ical plumbing
# ---------------------------------------------------------------------------

def _run_ical(args: list[str], *, timeout: int = ICAL_TIMEOUT_SECS) -> Any:
    if shutil.which("ical") is None:
        raise CalendarError("ical is not installed. Install with: brew install BRO3886/tap/ical")
    cmd = ["ical", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CalendarError(f"ical timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError:
        raise CalendarError("ical executable not found")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        raise CalendarError(msg or f"ical exited {r.returncode}")
    out = r.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise CalendarError(f"ical returned invalid JSON: {e}: {out[:300]}")


def _parse_created_event_text(out: str) -> dict[str, Any]:
    """Parse `ical add` text output when the backend ignores JSON output.

    BRO3886/ical currently accepts `--output json` for `add` but may still
    return a human "Created:" block after successfully creating the event.
    Treat that as success and normalize the fields we can recover.
    """
    event: dict[str, Any] = {"raw": out}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if not value:
            continue
        if key == "created":
            event["title"] = value
        elif key == "calendar":
            event["calendar"] = value
        elif key == "when":
            event["when"] = value
        elif key == "id":
            event["id"] = value
    return event


def _run_ical_add(args: list[str], *, timeout: int = ICAL_TIMEOUT_SECS) -> Any:
    """Run `ical add`, accepting JSON or the backend's created-event text."""
    if shutil.which("ical") is None:
        raise CalendarError("ical is not installed. Install with: brew install BRO3886/tap/ical")
    cmd = ["ical", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CalendarError(f"ical timed out after {timeout}s: {' '.join(cmd)}")
    except FileNotFoundError:
        raise CalendarError("ical executable not found")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        raise CalendarError(msg or f"ical exited {r.returncode}")
    out = r.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        if out.startswith("Created:"):
            return _parse_created_event_text(out)
        raise CalendarError(f"ical returned invalid JSON for add: {out[:300]}")


def _run_ical_text(args: list[str], *, timeout: int = ICAL_TIMEOUT_SECS) -> str:
    if shutil.which("ical") is None:
        raise CalendarError("ical is not installed. Install with: brew install BRO3886/tap/ical")
    try:
        r = subprocess.run(["ical", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CalendarError(f"ical timed out after {timeout}s")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        raise CalendarError(msg or f"ical exited {r.returncode}")
    return r.stdout.strip()


def _err_code(e: CalendarError) -> str:
    msg = str(e).lower()
    if "not installed" in msg or "not found" in msg:
        return "E_DEPENDENCY"
    if "timed out" in msg:
        return "E_TIMEOUT"
    if "permission" in msg or "access" in msg or "not authorized" in msg or "denied" in msg:
        return "E_AUTH"
    if "no calendar configured" in msg or "required" in msg or "invalid json" in msg or "invalid" in msg:
        return "E_VALIDATION"
    return "E_RUNTIME"


def _emit(env: Envelope, data: Any, args: argparse.Namespace, *, plain: str | None = None) -> int:
    if getattr(args, "plain", False):
        return emit_text(plain if plain is not None else _plain_summary(data))
    return emit_json(env.ok(data))


def _plain_summary(data: Any) -> str:
    if data is None:
        return "(empty)"
    if isinstance(data, list):
        if not data:
            return "(empty)"
        lines = []
        for item in data:
            if isinstance(item, dict):
                title = item.get("title") or item.get("summary") or item.get("name") or item.get("id") or str(item)
                start = item.get("start_date") or item.get("start") or ""
                cal = item.get("calendar") or item.get("source") or ""
                suffix = ""
                if start:
                    suffix += f" · {start}"
                if cal:
                    suffix += f" · {cal}"
                lines.append(f"- {title}{suffix}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False)
    return str(data)


def _require_calendar(value: str | None) -> str:
    if not value:
        raise CalendarError(
            "no calendar configured: set DOBBY_CALENDAR_DEFAULT "
            "(via scripts/local/secrets/static_env_defaults.env + "
            "bootstrap_local_env_from_keyvault.sh) or pass --calendar explicitly"
        )
    return value


def _with_calendar(cmd: list[str], args: argparse.Namespace) -> list[str]:
    if getattr(args, "all_calendars", False):
        return cmd
    cmd.extend(["-c", _require_calendar(getattr(args, "calendar", None))])
    return cmd


def _event_args(args: argparse.Namespace) -> list[str]:
    if not args.title.strip():
        raise CalendarError("title is required")
    if not args.start.strip():
        raise CalendarError("start is required")
    calendar = _require_calendar(getattr(args, "calendar", None))
    cmd = ["-o", "json", "add", args.title, "-s", args.start, "-c", calendar]
    if args.end:
        cmd.extend(["-e", args.end])
    if args.all_day:
        cmd.append("--all-day")
    if args.location:
        cmd.extend(["-l", args.location])
    if args.notes:
        cmd.extend(["-n", args.notes])
    if args.url:
        cmd.extend(["-u", args.url])
    if args.repeat:
        cmd.extend(["--repeat", args.repeat])
    if args.repeat_until:
        cmd.extend(["--repeat-until", args.repeat_until])
    if args.no_alert:
        cmd.append("--no-alert")
    return cmd


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    env = Envelope("calendar.doctor")
    checks: list[dict[str, Any]] = []

    path = shutil.which("ical")
    checks.append({"name": "ical_installed", "ok": path is not None, "detail": path or "not found"})

    version = "skipped"
    if path:
        try:
            version = _run_ical_text(["version"])
            checks.append({"name": "ical_version", "ok": True, "detail": version})
        except CalendarError as e:
            checks.append({"name": "ical_version", "ok": False, "detail": str(e)})
    else:
        checks.append({"name": "ical_version", "ok": False, "detail": version})

    calendars: list[dict[str, Any]] = []
    if path:
        try:
            calendars = _run_ical(["calendars", "-o", "json"])
            checks.append({"name": "eventkit_calendars", "ok": isinstance(calendars, list), "detail": f"{len(calendars)} calendars"})
        except CalendarError as e:
            checks.append({"name": "eventkit_calendars", "ok": False, "detail": str(e)})
    else:
        checks.append({"name": "eventkit_calendars", "ok": False, "detail": "skipped"})

    if DEFAULT_CALENDAR is None:
        checks.append({
            "name": "default_calendar_writable",
            "ok": False,
            "detail": "DOBBY_CALENDAR_DEFAULT not set — configure via static_env_defaults.env",
        })
    else:
        default_matches = [c for c in calendars if c.get("title") == DEFAULT_CALENDAR]
        default_ok = bool(default_matches) and not default_matches[0].get("readOnly", True)
        checks.append({
            "name": "default_calendar_writable",
            "ok": default_ok,
            "detail": DEFAULT_CALENDAR if default_ok else f"{DEFAULT_CALENDAR} not found or read-only",
        })

    report = {
        "ok": all(c["ok"] for c in checks),
        "default_calendar": DEFAULT_CALENDAR,
        "checks": checks,
        "timeouts": {"ical_secs": ICAL_TIMEOUT_SECS},
    }
    if report["ok"]:
        return _emit(env, report, args, plain="calendar: OK")
    err = env.err("E_DEPENDENCY", "one or more calendar checks failed")
    err["data"] = report
    return emit_json(err)


def cmd_calendars(args: argparse.Namespace) -> int:
    env = Envelope("calendar.calendars")
    try:
        data = _run_ical(["calendars", "-o", "json"])
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"count": len(data), "calendars": data, "default_calendar": DEFAULT_CALENDAR}, args, plain=_plain_summary(data))


def cmd_today(args: argparse.Namespace) -> int:
    env = Envelope("calendar.today")
    cmd = _with_calendar(["today", "-o", "json"], args)
    try:
        data = _run_ical(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"count": len(data or []), "events": data or [], "calendar": None if args.all_calendars else args.calendar}, args, plain=_plain_summary(data))


def cmd_upcoming(args: argparse.Namespace) -> int:
    return _cmd_upcoming_days(args, args.days, "calendar.upcoming")


def _cmd_upcoming_days(args: argparse.Namespace, days: int, command: str) -> int:
    env = Envelope(command)
    if days < 1 or days > 366:
        return emit_json(env.err("E_VALIDATION", "--days must be between 1 and 366"))
    cmd = _with_calendar(["upcoming", "-d", str(days), "-o", "json"], args)
    try:
        data = _run_ical(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"count": len(data or []), "events": data or [], "days": days, "calendar": None if args.all_calendars else args.calendar}, args, plain=_plain_summary(data))


def cmd_list(args: argparse.Namespace) -> int:
    env = Envelope("calendar.list")
    cmd = ["list", "-f", args.from_date, "-t", args.to_date, "-o", "json"]
    if args.query:
        cmd.extend(["--search", args.query])
    if args.limit is not None:
        cmd.extend(["-n", str(args.limit)])
    if args.no_recurring:
        cmd.append("--no-recurring")
    cmd = _with_calendar(cmd, args)
    try:
        data = _run_ical(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"count": len(data or []), "events": data or [], "from": args.from_date, "to": args.to_date, "calendar": None if args.all_calendars else args.calendar}, args, plain=_plain_summary(data))


def cmd_search(args: argparse.Namespace) -> int:
    env = Envelope("calendar.search")
    if not args.query.strip():
        return emit_json(env.err("E_VALIDATION", "query cannot be empty"))
    cmd = ["search", args.query, "-f", args.from_date, "-t", args.to_date, "-o", "json"]
    if args.limit is not None:
        cmd.extend(["-n", str(args.limit)])
    if args.no_recurring:
        cmd.append("--no-recurring")
    cmd = _with_calendar(cmd, args)
    try:
        data = _run_ical(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"count": len(data or []), "events": data or [], "query": args.query, "from": args.from_date, "to": args.to_date, "calendar": None if args.all_calendars else args.calendar}, args, plain=_plain_summary(data))


def cmd_add_event(args: argparse.Namespace) -> int:
    env = Envelope("calendar.add-event")
    try:
        cmd = _event_args(args)
        planned = {"backend": "ical", "argv": cmd, "calendar": args.calendar, "title": args.title, "start": args.start, "end": args.end, "all_day": args.all_day}
        if args.dry_run:
            return _emit(env, {"created": False, "dry_run": True, "planned": planned}, args, plain=f"dry-run: {args.title}")
        data = _run_ical_add(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"created": True, "event": data, "calendar": args.calendar}, args, plain=f"created: {args.title}")


def cmd_upsert_event(args: argparse.Namespace) -> int:
    env = Envelope("calendar.upsert-event")
    try:
        search = _run_ical(["search", args.title, "-f", args.match_from, "-t", args.match_to, "-c", args.calendar, "-o", "json"])
        matches = [e for e in (search or []) if (e.get("title") or "") == args.title and (e.get("calendar") or "") == args.calendar]
        if matches:
            return _emit(env, {"created": False, "duplicate": True, "matches": matches, "calendar": args.calendar}, args, plain=f"exists: {args.title}")
        cmd = _event_args(args)
        planned = {"backend": "ical", "argv": cmd, "calendar": args.calendar, "title": args.title, "start": args.start, "end": args.end, "all_day": args.all_day}
        if args.dry_run:
            return _emit(env, {"created": False, "duplicate": False, "dry_run": True, "planned": planned}, args, plain=f"dry-run create: {args.title}")
        data = _run_ical_add(cmd)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e)))
    return _emit(env, {"created": True, "duplicate": False, "event": data, "calendar": args.calendar}, args, plain=f"created: {args.title}")
