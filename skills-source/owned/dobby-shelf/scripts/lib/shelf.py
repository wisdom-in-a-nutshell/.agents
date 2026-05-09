"""Dobby Shelf commands.

Local-first client for `state/shelf.json`. The CLI keeps JSON mutation rules in
one deterministic place so agents do not hand-edit Shelf state for ordinary
operations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lib.contract import Envelope, emit_json, emit_text
from lib.workspace import workspace_root

VALID_KINDS = {"do", "buy", "remember"}
VALID_STATUSES = {"open", "done", "dropped"}
VIEWS = {"open", "now", "today", "upcoming", "later", "done", "dropped", "all"}
LOCAL_TIMEZONE = os.environ.get("DOBBY_LOCAL_TIMEZONE", "Europe/Berlin")


class ShelfError(RuntimeError):
    def __init__(self, command: str, code: str, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.command = command
        self.code = code
        self.hint = hint


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def today_local() -> str:
    return datetime.now(ZoneInfo(LOCAL_TIMEZONE)).date().isoformat()


def shelf_path() -> Path:
    return workspace_root() / "state" / "shelf.json"


def default_state() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "revision": 0,
        "updatedAt": "1970-01-01T00:00:00.000Z",
        "items": [],
    }


def read_state(command: str) -> dict[str, Any]:
    path = shelf_path()
    if not path.exists():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ShelfError(command, "E_IO", f"invalid Shelf JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ShelfError(command, "E_VALIDATION", "invalid Shelf shape", hint="Expected object with items array.")
    if data.get("schemaVersion") != 1:
        raise ShelfError(command, "E_VALIDATION", f"unsupported Shelf schemaVersion: {data.get('schemaVersion')}")
    return data


def write_state(data: dict[str, Any], command: str) -> None:
    path = shelf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["revision"] = int(data.get("revision") or 0) + 1
    data["updatedAt"] = utc_now_iso()
    payload = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
    except OSError as exc:
        raise ShelfError(command, "E_IO", f"failed to write Shelf: {exc}") from exc


def show_date(item: dict[str, Any]) -> str | None:
    value = item.get("showAt")
    if not isinstance(value, str):
        return None
    match = re.match(r"^\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else None


def item_view(item: dict[str, Any], today: str | None = None) -> str:
    today = today or today_local()
    status = item.get("status")
    if status == "done":
        return "done"
    if status == "dropped":
        return "dropped"
    if status != "open":
        return "all"
    if item.get("isNow") is True:
        return "now"
    date = show_date(item)
    if date is None:
        return "later"
    if date <= today:
        return "today"
    return "upcoming"


def open_items(items: list[Any]) -> list[dict[str, Any]]:
    return [item for item in items if isinstance(item, dict) and item.get("status") == "open"]


def counts(items: list[Any]) -> dict[str, int]:
    dicts = [item for item in items if isinstance(item, dict)]
    today = today_local()
    return {
        "total": len(dicts),
        "open": sum(1 for item in dicts if item.get("status") == "open"),
        "now": sum(1 for item in dicts if item_view(item, today) == "now"),
        "today": sum(1 for item in dicts if item_view(item, today) == "today"),
        "upcoming": sum(1 for item in dicts if item_view(item, today) == "upcoming"),
        "later": sum(1 for item in dicts if item_view(item, today) == "later"),
        "done": sum(1 for item in dicts if item.get("status") == "done"),
        "dropped": sum(1 for item in dicts if item.get("status") == "dropped"),
    }


def filter_items(items: list[Any], view: str) -> list[dict[str, Any]]:
    dicts = [item for item in items if isinstance(item, dict)]
    if view == "all":
        return dicts
    if view == "open":
        return [item for item in dicts if item.get("status") == "open"]
    today = today_local()
    return [item for item in dicts if item_view(item, today) == view]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60].strip("-") or "item"


def unique_id(title: str, items: list[Any], requested: str | None = None) -> str:
    existing = {item.get("id") for item in items if isinstance(item, dict)}
    base = slugify(requested or title)
    candidate = base
    n = 2
    while candidate in existing:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def resolve_item(items: list[Any], selector: str, command: str) -> dict[str, Any]:
    dicts = [item for item in items if isinstance(item, dict)]
    exact_id = [item for item in dicts if item.get("id") == selector]
    if len(exact_id) == 1:
        return exact_id[0]
    prefix = [item for item in dicts if isinstance(item.get("id"), str) and item["id"].startswith(selector)]
    if len(prefix) == 1:
        return prefix[0]
    title = [item for item in dicts if str(item.get("title", "")).casefold() == selector.casefold()]
    if len(title) == 1:
        return title[0]
    if len(prefix) > 1 or len(title) > 1:
        raise ShelfError(command, "E_VALIDATION", f"ambiguous Shelf item selector: {selector}", hint="Use the full item id.")
    raise ShelfError(command, "E_NOT_FOUND", f"Shelf item not found: {selector}")


def public_item(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item)


def format_items_plain(view: str, state: dict[str, Any], items: list[dict[str, Any]]) -> str:
    c = counts(state.get("items", []))
    lines = [
        f"revision={state.get('revision', 0)} open={c['open']} now={c['now']} today={c['today']} upcoming={c['upcoming']} later={c['later']}",
        f"view={view} count={len(items)}",
    ]
    for item in items:
        bits: list[str] = []
        if item.get("kind") and item.get("kind") != "do":
            bits.append(str(item["kind"]))
        if item.get("showAt"):
            bits.append(f"showAt={item['showAt']}")
        if item.get("dueAt"):
            bits.append(f"dueAt={item['dueAt']}")
        if item.get("isNow") is True:
            bits.append("now")
        if item.get("deferCount"):
            bits.append(f"deferred={item['deferCount']}x")
        suffix = f" ({', '.join(bits)})" if bits else ""
        lines.append(f"- {item.get('id')}: {item.get('title')}{suffix}")
    return "\n".join(lines)


def fmt(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit JSON envelope (default)")
    group.add_argument("--plain", action="store_true", help="Emit plain text for operator inspection")
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive agent contract")


def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="shelf_cmd", required=True)

    p = sub.add_parser("list", help="List Shelf items")
    p.add_argument("--view", choices=sorted(VIEWS), default="open", help="Shelf view to list (default: open)")
    p.add_argument("--limit", type=int, default=50, help="Maximum items to return (default: 50; <=0 means no limit)")
    fmt(p)
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("add", help="Add a Shelf item")
    p.add_argument("--title", required=True, help="Short item title")
    p.add_argument("--kind", choices=sorted(VALID_KINDS), default="do", help="Item kind")
    p.add_argument("--show-at", help="Date/time when the item should surface")
    p.add_argument("--due-at", help="Real deadline only")
    p.add_argument("--note", help="Optional note")
    p.add_argument("--id", help="Optional explicit id")
    p.add_argument("--now", action="store_true", help="Mark as Now/focus")
    p.add_argument("--source-ref", default="dobby-shelf-cli", help="Source ref metadata")
    fmt(p)
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("done", help="Mark a Shelf item done")
    p.add_argument("selector", help="Item id, unique id prefix, or exact title")
    fmt(p)
    p.set_defaults(handler=cmd_done)

    p = sub.add_parser("drop", help="Drop a Shelf item")
    p.add_argument("selector", help="Item id, unique id prefix, or exact title")
    p.add_argument("--reason", default="", help="Optional drop reason")
    fmt(p)
    p.set_defaults(handler=cmd_drop)

    p = sub.add_parser("defer", help="Defer a Shelf item to a future showAt")
    p.add_argument("selector", help="Item id, unique id prefix, or exact title")
    p.add_argument("--show-at", required=True, help="New showAt date/time")
    fmt(p)
    p.set_defaults(handler=cmd_defer)

    p = sub.add_parser("focus", help="Set or clear the Now/focus flag")
    p.add_argument("selector", help="Item id, unique id prefix, or exact title")
    focus = p.add_mutually_exclusive_group(required=True)
    focus.add_argument("--on", action="store_true", help="Set isNow true")
    focus.add_argument("--off", action="store_true", help="Remove isNow")
    fmt(p)
    p.set_defaults(handler=cmd_focus)


def emit_result(env: Envelope, data: dict[str, Any], plain: str, args: argparse.Namespace) -> int:
    if getattr(args, "plain", False):
        return emit_text(plain)
    return emit_json(env.ok(data))


def cmd_list(args: argparse.Namespace) -> int:
    env = Envelope("shelf.list")
    state = read_state("shelf.list")
    items = filter_items(state.get("items", []), args.view)
    if args.limit > 0:
        items = items[: args.limit]
    data = {
        "path": str(shelf_path().relative_to(workspace_root())),
        "revision": state.get("revision", 0),
        "updatedAt": state.get("updatedAt"),
        "view": args.view,
        "counts": counts(state.get("items", [])),
        "items": [public_item(item) for item in items],
    }
    return emit_result(env, data, format_items_plain(args.view, state, items), args)


def cmd_add(args: argparse.Namespace) -> int:
    env = Envelope("shelf.add")
    state = read_state("shelf.add")
    items = state.setdefault("items", [])
    now = utc_now_iso()
    item: dict[str, Any] = {
        "id": unique_id(args.title, items, args.id),
        "title": args.title.strip(),
        "kind": args.kind,
        "status": "open",
        "source": {"type": "agent", "ref": args.source_ref},
        "deferCount": 0,
        "createdAt": now,
        "updatedAt": now,
    }
    if not item["title"]:
        raise ShelfError("shelf.add", "E_VALIDATION", "title must not be empty")
    if args.show_at:
        item["showAt"] = args.show_at
    if args.due_at:
        item["dueAt"] = args.due_at
    if args.note:
        item["note"] = args.note
    if args.now:
        item["isNow"] = True
    items.append(item)
    write_state(state, "shelf.add")
    data = {"item": public_item(item), "revision": state.get("revision"), "updatedAt": state.get("updatedAt")}
    return emit_result(env, data, f"added {item['id']}: {item['title']}", args)


def mutate_item(args: argparse.Namespace, command: str, mutator) -> int:
    env = Envelope(command)
    state = read_state(command)
    item = resolve_item(state.get("items", []), args.selector, command)
    mutator(item)
    item["updatedAt"] = utc_now_iso()
    write_state(state, command)
    data = {"item": public_item(item), "revision": state.get("revision"), "updatedAt": state.get("updatedAt")}
    return emit_result(env, data, f"{command.split('.')[1]} {item.get('id')}: {item.get('title')}", args)


def cmd_done(args: argparse.Namespace) -> int:
    stamp = utc_now_iso()
    def apply(item: dict[str, Any]) -> None:
        item["status"] = "done"
        item["completedAt"] = stamp
    return mutate_item(args, "shelf.done", apply)


def cmd_drop(args: argparse.Namespace) -> int:
    stamp = utc_now_iso()
    def apply(item: dict[str, Any]) -> None:
        item["status"] = "dropped"
        item["droppedAt"] = stamp
        if args.reason:
            item["dropReason"] = args.reason
    return mutate_item(args, "shelf.drop", apply)


def cmd_defer(args: argparse.Namespace) -> int:
    stamp = utc_now_iso()
    def apply(item: dict[str, Any]) -> None:
        item["status"] = "open"
        item["showAt"] = args.show_at
        item["deferCount"] = int(item.get("deferCount") or 0) + 1
        item["lastDeferredAt"] = stamp
    return mutate_item(args, "shelf.defer", apply)


def cmd_focus(args: argparse.Namespace) -> int:
    def apply(item: dict[str, Any]) -> None:
        item["status"] = "open"
        if args.on:
            item["isNow"] = True
        else:
            item.pop("isNow", None)
    return mutate_item(args, "shelf.focus", apply)
