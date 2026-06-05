"""Calendar commands for the Dobby CLI — macOS EventKit via Dobby Calendar Bridge.

This wrapper keeps Dobby's stable agent contract while routing all calendar
operations through the native Dobby Calendar Bridge helper. The bridge talks to
the local macOS calendar store, including Google calendars synced into
Calendar.app, without AppleScript broad-search hangs or caller-specific macOS
Calendar permission drift.

Design rules:
- JSON envelope by default for every calendar command; --plain is inspection.
- No interactive commands are exposed; --no-input is accepted and honored.
- Search is date-bounded by requirement.
- No delete/update commands in v1; writes are add/upsert only.
- Default calendar is required via DOBBY_CALENDAR_DEFAULT env var.
  Commands that need a specific calendar fail fast when it is unset and
  --calendar is not passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
from datetime import date, datetime, timedelta
from pathlib import Path
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


BRIDGE_TIMEOUT_SECS = _int_env("DOBBY_CALENDAR_BRIDGE_TIMEOUT_SECS", 20)
BACKEND_ENV = "DOBBY_CALENDAR_BACKEND"
BRIDGE_BIN_ENV = "DOBBY_CALENDAR_BRIDGE_BIN"
BRIDGE_SOCKET_ENV = "DOBBY_CALENDAR_BRIDGE_SOCKET"
BACKENDS = ("auto", "bridge")


class CalendarError(RuntimeError):
    def __init__(self, message: str, *, code: str | None = None, hint: str = "", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint
        self.retryable = retryable


def _backend_preference() -> str:
    value = os.environ.get(BACKEND_ENV, "auto").strip().lower() or "auto"
    if value not in BACKENDS:
        raise CalendarError(
            f"invalid {BACKEND_ENV}: {value}",
            code="E_VALIDATION",
            hint=f"Use one of: {', '.join(BACKENDS)}",
        )
    return value


def _backend_order() -> list[str]:
    # `auto` remains accepted for existing environments, but it now resolves to
    # the only supported backend: the native Dobby Calendar Bridge.
    return ["bridge"]


def _bridge_candidates() -> list[Path]:
    configured = os.environ.get(BRIDGE_BIN_ENV)
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        Path.home() / "Applications/Dobby Calendar Bridge.app/Contents/MacOS/DobbyCalendarBridge",
        Path("/Applications/Dobby Calendar Bridge.app/Contents/MacOS/DobbyCalendarBridge"),
        Path.home() / "Library/Application Support/DobbyCalendarBridge/Dobby Calendar Bridge.app/Contents/MacOS/DobbyCalendarBridge",
    ])
    return candidates


def _find_bridge_bin() -> Path | None:
    for candidate in _bridge_candidates():
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _bridge_socket_path() -> Path:
    configured = os.environ.get(BRIDGE_SOCKET_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library/Application Support/DobbyCalendarBridge/bridge.sock"


def _bridge_install_hint() -> str:
    return (
        "Install/start the native helper with: "
        "~/GitHub/agents/skills-source/owned/dobby-calendar/scripts/dobby_calendar/bridge/install --request-access"
    )


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="calendar_cmd", required=True)

    p = sub.add_parser("doctor", help="Check Dobby Calendar Bridge/EventKit calendar connectivity")
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
# bridge plumbing
# ---------------------------------------------------------------------------

def _run_bridge(command: str, args: list[str] | None = None, *, timeout: int = BRIDGE_TIMEOUT_SECS) -> Any:
    socket_path = _bridge_socket_path()
    if not socket_path.exists():
        raise CalendarError(
            f"Dobby Calendar Bridge server socket is not available: {socket_path}",
            code="E_DEPENDENCY",
            hint=_bridge_install_hint(),
        )
    request_id = os.urandom(8).hex()
    request = {
        "schema_version": "1.0",
        "request_id": request_id,
        "command": command,
        "args": [*(args or []), "--no-input"],
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(socket_path))
            client.sendall(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
    except TimeoutError:
        raise CalendarError(
            f"Dobby Calendar Bridge timed out after {timeout}s",
            code="E_TIMEOUT",
            retryable=True,
            hint="Retry once; if it repeats, reinstall the bridge or check macOS Calendar privacy.",
        )
    except OSError as e:
        raise CalendarError(
            f"Dobby Calendar Bridge server is unavailable: {e}",
            code="E_DEPENDENCY",
            hint=_bridge_install_hint(),
        )

    try:
        envelope = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise CalendarError(
            f"Dobby Calendar Bridge returned invalid JSON: {e}: {raw[:300]}",
            code="E_RUNTIME",
            hint="Reinstall the bridge helper from ~/GitHub/scripts.",
        )

    if envelope.get("status") == "error":
        err = envelope.get("error") if isinstance(envelope, dict) else None
        if isinstance(err, dict):
            raise CalendarError(
                err.get("message") or "Dobby Calendar Bridge returned an error",
                code=err.get("code") or "E_RUNTIME",
                hint=err.get("hint") or "",
                retryable=bool(err.get("retryable", False)),
            )
        msg = (raw or "Dobby Calendar Bridge returned an error").strip()
        raise CalendarError(msg, code="E_RUNTIME")

    return envelope.get("data")


def _run_backend(
    op: str,
    bridge_call: Any,
    *,
    state_changing: bool = False,
) -> tuple[Any, str]:
    """Run a calendar operation through the Dobby Calendar Bridge."""
    del op, state_changing  # kept for call-site readability and future logging.
    return bridge_call(), "bridge"


def _err_code(e: CalendarError) -> str:
    if e.code:
        return e.code
    msg = str(e).lower()
    if "not installed" in msg or "not found" in msg:
        return "E_DEPENDENCY"
    if "timed out" in msg:
        return "E_TIMEOUT"
    if "permission" in msg or "access" in msg or "not authorized" in msg or "denied" in msg:
        return "E_AUTH"
    if "not found" in msg:
        return "E_NOT_FOUND"
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


def _decode_escapes(s: str | None) -> str | None:
    """Decode common shell-passed escape sequences in user-supplied free text.

    Agents and shell callers frequently pass ``\\n`` (literal backslash-n)
    when they mean a newline. Calendar.app then renders the literal escape
    in the notes field, which looks broken. We normalize the common cases
    (``\\n``, ``\\t``, ``\\r``) at the CLI boundary so the rest of the
    pipeline always sees real whitespace characters.
    """
    if not s:
        return s
    return s.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")


def _bridge_event_args(args: argparse.Namespace) -> list[str]:
    calendar = _require_calendar(getattr(args, "calendar", None))
    cmd = ["--title", args.title, "--start", args.start, "--calendar", calendar]
    if args.end:
        cmd.extend(["--end", args.end])
    if args.all_day:
        cmd.append("--all-day")
    if args.location:
        cmd.extend(["--location", args.location])
    if args.notes:
        cmd.extend(["--notes", _decode_escapes(args.notes)])
    if args.url:
        cmd.extend(["--url", args.url])
    if args.repeat:
        cmd.extend(["--repeat", args.repeat])
    if args.repeat_until:
        cmd.extend(["--repeat-until", args.repeat_until])
    if args.no_alert:
        cmd.append("--no-alert")
    return cmd


def _bridge_list_args(
    from_date: str,
    to_date: str,
    *,
    query: str | None = None,
    limit: int | None = None,
    no_recurring: bool = False,
    calendar_name: str | None = None,
    all_calendars: bool = False,
) -> list[str]:
    cmd = ["--from", from_date, "--to", to_date]
    if query:
        cmd.extend(["--query", query])
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    if no_recurring:
        cmd.append("--no-recurring")
    if all_calendars:
        cmd.append("--all-calendars")
    else:
        cmd.extend(["--calendar", _require_calendar(calendar_name)])
    return cmd


def _iso_date(d: date) -> str:
    return d.isoformat()


def _list_via_bridge(bridge_args: list[str]) -> tuple[list[dict[str, Any]], str]:
    data, backend = _run_backend(
        "list",
        lambda: (_run_bridge("list", bridge_args) or {}).get("events", []),
    )
    return data or [], backend


def _calendars_via_bridge() -> tuple[list[dict[str, Any]], str]:
    data, backend = _run_backend(
        "calendars",
        lambda: (_run_bridge("calendars") or {}).get("calendars", []),
    )
    return data or [], backend


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    env = Envelope("calendar.doctor")
    checks: list[dict[str, Any]] = []

    bridge_path = _find_bridge_bin()
    checks.append({
        "name": "eventkit_bridge_installed",
        "ok": bridge_path is not None,
        "detail": str(bridge_path) if bridge_path else "not found",
    })
    socket_path = _bridge_socket_path()
    checks.append({
        "name": "eventkit_bridge_socket",
        "ok": socket_path.exists(),
        "detail": str(socket_path) if socket_path.exists() else f"not found: {socket_path}",
    })

    bridge_calendars: list[dict[str, Any]] = []
    bridge_ok = False
    if bridge_path and socket_path.exists():
        try:
            bridge_report = _run_bridge("doctor")
            bridge_ok = bool((bridge_report or {}).get("ok"))
            checks.append({
                "name": "eventkit_bridge_access",
                "ok": bridge_ok,
                "detail": (bridge_report or {}).get("authorization_status", "unknown"),
            })
            if bridge_ok:
                bridge_calendars = (_run_bridge("calendars") or {}).get("calendars", [])
        except CalendarError as e:
            checks.append({"name": "eventkit_bridge_access", "ok": False, "detail": str(e)})
    else:
        checks.append({"name": "eventkit_bridge_access", "ok": False, "detail": _bridge_install_hint()})

    active_backend = "bridge" if bridge_ok else None
    calendars = bridge_calendars if bridge_ok else []

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
            "detail": DEFAULT_CALENDAR if default_ok else f"{DEFAULT_CALENDAR} not found or read-only via {active_backend or 'no backend'}",
        })

    report = {
        "ok": bool(active_backend) and any(c["name"] == "default_calendar_writable" and c["ok"] for c in checks),
        "backend": active_backend,
        "backend_preference": _backend_preference(),
        "default_calendar": DEFAULT_CALENDAR,
        "checks": checks,
        "timeouts": {"bridge_secs": BRIDGE_TIMEOUT_SECS},
    }
    if report["ok"]:
        return _emit(env, report, args, plain=f"calendar: OK ({active_backend})")
    error_code = "E_AUTH" if any((not c["ok"]) and ("access" in c["name"] or "calendar" in c["name"]) for c in checks) else "E_DEPENDENCY"
    err = env.err(error_code, "one or more calendar checks failed", hint=_bridge_install_hint())
    err["data"] = report
    return emit_json(err)


def cmd_calendars(args: argparse.Namespace) -> int:
    env = Envelope("calendar.calendars")
    try:
        data, backend = _calendars_via_bridge()
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"count": len(data), "calendars": data, "default_calendar": DEFAULT_CALENDAR, "backend": backend}, args, plain=_plain_summary(data))


def cmd_today(args: argparse.Namespace) -> int:
    env = Envelope("calendar.today")
    today = date.today()
    bridge_args = _bridge_list_args(
        _iso_date(today),
        _iso_date(today + timedelta(days=1)),
        calendar_name=args.calendar,
        all_calendars=args.all_calendars,
    )
    try:
        data, backend = _list_via_bridge(bridge_args)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"count": len(data or []), "events": data or [], "calendar": None if args.all_calendars else args.calendar, "backend": backend}, args, plain=_plain_summary(data))


def cmd_upcoming(args: argparse.Namespace) -> int:
    return _cmd_upcoming_days(args, args.days, "calendar.upcoming")


def _cmd_upcoming_days(args: argparse.Namespace, days: int, command: str) -> int:
    env = Envelope(command)
    if days < 1 or days > 366:
        return emit_json(env.err("E_VALIDATION", "--days must be between 1 and 366"))
    today = date.today()
    bridge_args = _bridge_list_args(
        _iso_date(today),
        _iso_date(today + timedelta(days=days)),
        calendar_name=args.calendar,
        all_calendars=args.all_calendars,
    )
    try:
        data, backend = _list_via_bridge(bridge_args)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"count": len(data or []), "events": data or [], "days": days, "calendar": None if args.all_calendars else args.calendar, "backend": backend}, args, plain=_plain_summary(data))


def cmd_list(args: argparse.Namespace) -> int:
    env = Envelope("calendar.list")
    bridge_args = _bridge_list_args(
        args.from_date,
        args.to_date,
        query=args.query,
        limit=args.limit,
        no_recurring=args.no_recurring,
        calendar_name=args.calendar,
        all_calendars=args.all_calendars,
    )
    try:
        data, backend = _list_via_bridge(bridge_args)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"count": len(data or []), "events": data or [], "from": args.from_date, "to": args.to_date, "calendar": None if args.all_calendars else args.calendar, "backend": backend}, args, plain=_plain_summary(data))


def cmd_search(args: argparse.Namespace) -> int:
    env = Envelope("calendar.search")
    if not args.query.strip():
        return emit_json(env.err("E_VALIDATION", "query cannot be empty"))
    bridge_args = _bridge_list_args(
        args.from_date,
        args.to_date,
        query=args.query,
        limit=args.limit,
        no_recurring=args.no_recurring,
        calendar_name=args.calendar,
        all_calendars=args.all_calendars,
    )
    try:
        data, backend = _list_via_bridge(bridge_args)
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"count": len(data or []), "events": data or [], "query": args.query, "from": args.from_date, "to": args.to_date, "calendar": None if args.all_calendars else args.calendar, "backend": backend}, args, plain=_plain_summary(data))


def cmd_add_event(args: argparse.Namespace) -> int:
    env = Envelope("calendar.add-event")
    try:
        bridge_cmd = _bridge_event_args(args)
        planned = {"backend": "bridge", "bridge_argv": bridge_cmd, "calendar": args.calendar, "title": args.title, "start": args.start, "end": args.end, "all_day": args.all_day}
        if args.dry_run:
            return _emit(env, {"created": False, "dry_run": True, "planned": planned}, args, plain=f"dry-run: {args.title}")
        data, backend = _run_backend(
            "add-event",
            lambda: _run_bridge("add", bridge_cmd),
            state_changing=True,
        )
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"created": True, "event": data, "calendar": args.calendar, "backend": backend}, args, plain=f"created: {args.title}")


def cmd_upsert_event(args: argparse.Namespace) -> int:
    env = Envelope("calendar.upsert-event")
    try:
        calendar = _require_calendar(args.calendar)
        search_bridge_args = _bridge_list_args(
            args.match_from,
            args.match_to,
            query=args.title,
            calendar_name=calendar,
        )
        search, search_backend = _run_backend(
            "upsert-search",
            lambda: (_run_bridge("list", search_bridge_args) or {}).get("events", []),
        )
        matches = [e for e in (search or []) if (e.get("title") or "") == args.title and (e.get("calendar") or "") == calendar]
        if matches:
            return _emit(env, {"created": False, "duplicate": True, "matches": matches, "calendar": calendar, "backend": search_backend}, args, plain=f"exists: {args.title}")
        bridge_cmd = _bridge_event_args(args)
        planned = {"backend": "bridge", "bridge_argv": bridge_cmd, "calendar": args.calendar, "title": args.title, "start": args.start, "end": args.end, "all_day": args.all_day}
        if args.dry_run:
            return _emit(env, {"created": False, "duplicate": False, "dry_run": True, "planned": planned}, args, plain=f"dry-run create: {args.title}")
        data, backend = _run_backend(
            "upsert-add",
            lambda: _run_bridge("add", bridge_cmd),
            state_changing=True,
        )
    except CalendarError as e:
        return emit_json(env.err(_err_code(e), str(e), retryable=e.retryable, hint=e.hint))
    return _emit(env, {"created": True, "duplicate": False, "event": data, "calendar": calendar, "backend": backend}, args, plain=f"created: {args.title}")
