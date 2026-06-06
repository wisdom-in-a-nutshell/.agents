"""Shelf v2 argparse handlers."""
from __future__ import annotations

import argparse
from typing import Any

from lib.contract import Envelope, emit_json, emit_text

from . import service
from .migrate import migrate
from .model import ITEM_TYPES, SNAPSHOT_MODES, VIEWS
from .views import format_snapshot_plain


def fmt(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit JSON envelope (default)")
    group.add_argument("--plain", action="store_true", help="Emit plain text for operator inspection")
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive agent contract")


def emit_result(env: Envelope, data: Any, plain: str, args: argparse.Namespace) -> int:
    if getattr(args, "plain", False):
        return emit_text(plain)
    return emit_json(env.ok(data))


def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="shelf_cmd", required=True)

    p = sub.add_parser("snapshot", help="Curated Shelf v2 decision surface")
    p.add_argument("--mode", choices=sorted(SNAPSHOT_MODES), default="plan-day")
    fmt(p)
    p.set_defaults(handler=cmd_snapshot)

    p = sub.add_parser("list", help="List Shelf v2 cards/items")
    p.add_argument("--view", choices=sorted(VIEWS), default="active")
    p.add_argument("--type", choices=sorted(ITEM_TYPES), dest="item_type")
    fmt(p)
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("add", help="Add a do/buy Shelf item")
    p.add_argument("--title", required=True)
    p.add_argument("--type", choices=["do", "buy"], default="do", dest="item_type")
    p.add_argument("--show-on")
    p.add_argument("--due-on")
    p.add_argument("--note")
    p.add_argument("--id")
    p.add_argument("--client-mutation-id")
    p.add_argument("--source-ref", default="dobby-shelf-cli")
    fmt(p)
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("habit", help="Habit operations")
    habit_sub = p.add_subparsers(dest="habit_cmd", required=True)
    hp = habit_sub.add_parser("add", help="Add a recurring habit")
    hp.add_argument("--title", required=True)
    hp.add_argument("--cadence", choices=["daily", "weekly"], default="daily")
    hp.add_argument("--start-on", required=True)
    hp.add_argument("--end-on")
    hp.add_argument("--days", help="Comma-separated days for weekly habits, e.g. mon,thu")
    hp.add_argument("--note")
    hp.add_argument("--id")
    hp.add_argument("--client-mutation-id")
    hp.add_argument("--source-ref", default="dobby-shelf-cli")
    fmt(hp)
    hp.set_defaults(handler=cmd_habit_add)

    p = sub.add_parser("complete", help="Complete a visible card or one-off item")
    p.add_argument("selector")
    fmt(p)
    p.set_defaults(handler=cmd_complete)

    p = sub.add_parser("drop", help="Drop a Shelf item")
    p.add_argument("selector")
    p.add_argument("--reason", default="")
    fmt(p)
    p.set_defaults(handler=cmd_drop)

    p = sub.add_parser("defer", help="Defer a do/buy item")
    p.add_argument("selector")
    p.add_argument("--show-on", required=True)
    fmt(p)
    p.set_defaults(handler=cmd_defer)

    p = sub.add_parser("note", help="Set, append to, or clear a Shelf item note")
    p.add_argument("selector")
    note = p.add_mutually_exclusive_group(required=True)
    note.add_argument("--set", dest="set_note")
    note.add_argument("--append", dest="append_note")
    note.add_argument("--clear", action="store_true")
    fmt(p)
    p.set_defaults(handler=cmd_note)

    p = sub.add_parser("migrate-v2", help="One-shot v1 to v2 migration")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    fmt(p)
    p.set_defaults(handler=cmd_migrate)


def cmd_snapshot(args: argparse.Namespace) -> int:
    env = Envelope("shelf.snapshot")
    data = service.read_snapshot(args.mode)
    return emit_result(env, data, format_snapshot_plain(data), args)


def cmd_list(args: argparse.Namespace) -> int:
    env = Envelope("shelf.list")
    data = service.list_cards(args.view, args.item_type)
    plain = "\n".join(f"- {card.get('itemId')}: {card.get('title')} ({card.get('type')}, {card.get('state')})" for card in data["cards"]) or "(empty)"
    return emit_result(env, data, plain, args)


def cmd_add(args: argparse.Namespace) -> int:
    env = Envelope("shelf.add")
    result = service.add_single(title=args.title, item_type=args.item_type, show_on=args.show_on, due_on=args.due_on, note=args.note, item_id=args.id, source_ref=args.source_ref, client_mutation_id=args.client_mutation_id)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"added {result.item['id']}: {result.item['title']}", args)


def cmd_habit_add(args: argparse.Namespace) -> int:
    env = Envelope("shelf.habit.add")
    days = [day.strip().lower() for day in args.days.split(",") if day.strip()] if args.days else None
    result = service.add_habit(title=args.title, cadence=args.cadence, start_on=args.start_on, end_on=args.end_on, days_of_week=days, note=args.note, item_id=args.id, source_ref=args.source_ref, client_mutation_id=args.client_mutation_id)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"added habit {result.item['id']}: {result.item['title']}", args)


def cmd_complete(args: argparse.Namespace) -> int:
    env = Envelope("shelf.complete")
    result = service.complete(args.selector)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"completed {result.item['id']}: {result.item['title']}", args)


def cmd_drop(args: argparse.Namespace) -> int:
    env = Envelope("shelf.drop")
    result = service.drop(args.selector, args.reason or None)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"dropped {result.item['id']}: {result.item['title']}", args)


def cmd_defer(args: argparse.Namespace) -> int:
    env = Envelope("shelf.defer")
    result = service.defer(args.selector, args.show_on)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"deferred {result.item['id']}: {result.item['title']}", args)


def cmd_note(args: argparse.Namespace) -> int:
    env = Envelope("shelf.note")
    result = service.update_note(args.selector, set_note=args.set_note, append_note=args.append_note, clear=args.clear)
    data = {"item": result.item, "revision": result.state.get("revision"), "updatedAt": result.state.get("updatedAt")}
    return emit_result(env, data, f"updated note {result.item['id']}: {result.item['title']}", args)


def cmd_migrate(args: argparse.Namespace) -> int:
    env = Envelope("shelf.migrate-v2")
    data = migrate(apply=args.apply, backup=not args.no_backup)
    state = data.get("state") or {}
    plain = f"migrate-v2 applied={data['applied']} revision={state.get('revision')} converted={data['report']['converted']} habits={len(data['report']['habits'])} backup={data.get('backupPath') or '-'}"
    return emit_result(env, data, plain, args)
