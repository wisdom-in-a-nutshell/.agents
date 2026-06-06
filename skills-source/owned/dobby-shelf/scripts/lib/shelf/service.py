"""Shelf v2 mutation service."""
from __future__ import annotations

import re
from typing import Any

from .model import CommandResult, ShelfValidationError, date_prefix, utc_now_iso, validate_date
from .store import mutate, read_state
from .views import build_snapshot, habit_occurrence, local_date


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


def resolve_item(items: list[Any], selector: str) -> dict[str, Any]:
    dicts = [item for item in items if isinstance(item, dict)]
    exact = [item for item in dicts if item.get("id") == selector]
    if len(exact) == 1:
        return exact[0]
    prefix = [item for item in dicts if isinstance(item.get("id"), str) and item["id"].startswith(selector)]
    if len(prefix) == 1:
        return prefix[0]
    title = [item for item in dicts if str(item.get("title", "")).casefold() == selector.casefold()]
    if len(title) == 1:
        return title[0]
    if len(prefix) > 1 or len(title) > 1:
        raise ShelfValidationError(f"ambiguous Shelf item selector: {selector}; use the full item id")
    raise KeyError(selector)


def resolve_card(state: dict[str, Any], selector: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    snapshot = build_snapshot(state, "full")
    for cards in snapshot["views"].values():
        for card in cards:
            if card.get("cardId") == selector:
                return resolve_item(state["items"], card["itemId"]), card
    return resolve_item(state["items"], selector), None


def source_object(source_ref: str | None, source_type: str = "agent") -> dict[str, str]:
    source = {"type": source_type}
    if source_ref:
        source["ref"] = source_ref
    return source


def add_single(
    *,
    title: str,
    item_type: str = "do",
    show_on: str | None = None,
    due_on: str | None = None,
    note: str | None = None,
    item_id: str | None = None,
    source_ref: str | None = "dobby-shelf-cli",
    source_type: str = "agent",
    client_mutation_id: str | None = None,
) -> CommandResult:
    title = title.strip()
    if not title:
        raise ShelfValidationError("title must not be empty")
    if item_type not in {"do", "buy"}:
        raise ShelfValidationError("single items must have type do or buy")
    if show_on:
        validate_date(show_on, "showOn")
    if due_on:
        validate_date(due_on, "dueOn")

    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        items = state.setdefault("items", [])
        if client_mutation_id:
            for item in items:
                if item.get("clientMutationId") == client_mutation_id:
                    return item
        item: dict[str, Any] = {
            "id": unique_id(title, items, item_id),
            **({"clientMutationId": client_mutation_id} if client_mutation_id else {}),
            "type": item_type,
            "title": title,
            "state": "active",
            "deferCount": 0,
            "createdAt": now,
            "updatedAt": now,
            "source": source_object(source_ref, source_type),
        }
        if show_on:
            item["showOn"] = show_on
        if due_on:
            item["dueOn"] = due_on
        if note:
            item["note"] = note.strip()
        items.append(item)
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def add_habit(
    *,
    title: str,
    cadence: str = "daily",
    start_on: str,
    end_on: str | None = None,
    days_of_week: list[str] | None = None,
    note: str | None = None,
    item_id: str | None = None,
    source_ref: str | None = "dobby-shelf-cli",
    source_type: str = "agent",
    client_mutation_id: str | None = None,
) -> CommandResult:
    title = title.strip()
    if not title:
        raise ShelfValidationError("title must not be empty")
    validate_date(start_on, "startOn")
    if end_on:
        validate_date(end_on, "endOn")
    if cadence not in {"daily", "weekly"}:
        raise ShelfValidationError("cadence must be daily or weekly")

    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        items = state.setdefault("items", [])
        if client_mutation_id:
            for item in items:
                if item.get("clientMutationId") == client_mutation_id:
                    return item
        schedule: dict[str, Any] = {"cadence": cadence, "startOn": start_on}
        if end_on:
            schedule["endOn"] = end_on
        if cadence == "weekly":
            if not days_of_week:
                raise ShelfValidationError("weekly habits require --days")
            schedule["daysOfWeek"] = days_of_week
        item: dict[str, Any] = {
            "id": unique_id(title, items, item_id),
            **({"clientMutationId": client_mutation_id} if client_mutation_id else {}),
            "type": "habit",
            "title": title,
            "state": "active",
            "schedule": schedule,
            "completions": [],
            "createdAt": now,
            "updatedAt": now,
            "source": source_object(source_ref, source_type),
        }
        if note:
            item["note"] = note.strip()
        items.append(item)
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def complete(selector: str) -> CommandResult:
    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        item, card = resolve_card(state, selector)
        if item.get("type") == "habit":
            today = local_date(state.get("timezone", "Europe/Berlin"))
            occurrence = card or habit_occurrence(item, today)
            if not occurrence:
                raise ShelfValidationError("habit has no active occurrence to complete")
            key = occurrence["occurrenceKey"]
            completions = item.setdefault("completions", [])
            if not any(c.get("occurrenceKey") == key for c in completions if isinstance(c, dict)):
                completions.append({"occurrenceKey": key, "completedAt": now})
            item["updatedAt"] = now
            return item
        if item.get("state") == "dropped":
            raise ShelfValidationError("dropped items cannot be completed")
        item["state"] = "completed"
        item["completedAt"] = now
        item.pop("droppedAt", None)
        item.pop("dropReason", None)
        item["updatedAt"] = now
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def drop(selector: str, reason: str | None = None) -> CommandResult:
    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        item = resolve_item(state.get("items", []), selector)
        item["state"] = "dropped"
        item["droppedAt"] = now
        if reason:
            item["dropReason"] = reason.strip()
        else:
            item.pop("dropReason", None)
        if item.get("type") in {"do", "buy"}:
            item.pop("completedAt", None)
        item["updatedAt"] = now
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def defer(selector: str, show_on: str) -> CommandResult:
    validate_date(show_on, "showOn")

    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        item = resolve_item(state.get("items", []), selector)
        if item.get("type") == "habit":
            raise ShelfValidationError("habits cannot be deferred; pause/drop or edit the schedule instead")
        if item.get("state") == "dropped":
            raise ShelfValidationError("dropped items cannot be deferred")
        item["state"] = "active"
        item["showOn"] = show_on
        item["deferCount"] = int(item.get("deferCount") or 0) + 1
        item["lastDeferredAt"] = now
        item.pop("completedAt", None)
        item["updatedAt"] = now
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def update_note(selector: str, *, set_note: str | None = None, append_note: str | None = None, clear: bool = False) -> CommandResult:
    def clean(value: str | None, mode: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ShelfValidationError(f"{mode} note text must not be empty")
        return text

    def apply(state: dict[str, Any], now: str) -> dict[str, Any]:
        item = resolve_item(state.get("items", []), selector)
        if clear:
            item.pop("note", None)
        elif set_note is not None:
            item["note"] = clean(set_note, "set")
        else:
            addition = clean(append_note, "append")
            existing = str(item.get("note") or "").strip()
            item["note"] = f"{existing}\n\n{addition}" if existing else addition
        item["updatedAt"] = now
        return item

    state, item = mutate(apply)
    return CommandResult(state, item=item)


def read_snapshot(mode: str = "plan-day") -> dict[str, Any]:
    return build_snapshot(read_state(), mode)


def list_cards(view: str = "active", item_type: str | None = None) -> dict[str, Any]:
    state = read_state()
    snapshot = build_snapshot(state, "full")
    if view in {"today", "upcoming", "later"}:
        cards = snapshot["views"][view]
    elif view in {"active", "open"}:
        cards = [card for name in ("today", "upcoming", "later") for card in snapshot["views"][name]]
    elif view in {"completed", "done", "dropped", "archive", "all"}:
        cards = []
        for item in state.get("items", []):
            if view == "all" or (view in {"completed", "done"} and item.get("state") == "completed") or (view == "dropped" and item.get("state") == "dropped") or (view == "archive" and item.get("state") in {"completed", "dropped", "paused"}):
                cards.append({"itemId": item.get("id"), "type": item.get("type"), "title": item.get("title"), "state": item.get("state"), "updatedAt": item.get("updatedAt")})
    else:
        raise ShelfValidationError(f"unknown view: {view}")
    if item_type:
        cards = [card for card in cards if card.get("type") == item_type]
    return {"revision": state.get("revision"), "updatedAt": state.get("updatedAt"), "view": view, "cards": cards, "counts": snapshot["counts"]}
