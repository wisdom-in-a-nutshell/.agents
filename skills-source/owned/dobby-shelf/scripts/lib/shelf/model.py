"""Shelf v2 data model and validation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 2
DEFAULT_TIMEZONE = "Europe/Berlin"
ITEM_TYPES = {"do", "buy", "habit"}
SINGLE_TYPES = {"do", "buy"}
SINGLE_STATES = {"active", "completed", "dropped"}
HABIT_STATES = {"active", "paused", "dropped"}
SOURCE_TYPES = {"chat", "ui", "agent"}
CADENCES = {"daily", "weekly"}
DAYS_OF_WEEK = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VIEWS = {"today", "upcoming", "later", "open", "active", "archive", "completed", "done", "dropped", "all"}
SNAPSHOT_MODES = {"boot", "plan-day", "full"}
SECTION_ORDER = ("today", "upcoming", "later")
SNAPSHOT_LIMITS = {
    "boot": {"today": 8, "upcoming": 2, "later": 0},
    "plan-day": {"today": 12, "upcoming": 4, "later": 4},
    "full": {"today": -1, "upcoming": -1, "later": -1},
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
UTC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


class ShelfValidationError(ValueError):
    """Raised when a Shelf document or command payload is invalid."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def date_prefix(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = DATE_PREFIX_RE.match(value)
    return match.group(1) if match else None


def require_record(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ShelfValidationError(f"{label} must be an object")
    return value


def require_non_empty_string(record: dict[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ShelfValidationError(f"{label}: {field} must be a non-empty string")
    return value


def optional_string(record: dict[str, Any], field: str, label: str) -> None:
    if field in record and record[field] is not None and not isinstance(record[field], str):
        raise ShelfValidationError(f"{label}: {field} must be a string when present")


def validate_date(value: Any, label: str) -> str:
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ShelfValidationError(f"{label} must be a date string YYYY-MM-DD")
    return value


def validate_optional_date(record: dict[str, Any], field: str, label: str) -> None:
    if field in record and record[field] is not None:
        validate_date(record[field], f"{label}: {field}")


def validate_source(value: Any, label: str) -> None:
    if value is None:
        return
    source = require_record(value, f"{label}: source")
    if source.get("type") not in SOURCE_TYPES:
        raise ShelfValidationError(f"{label}: source.type must be one of {sorted(SOURCE_TYPES)}")
    if "ref" in source and not isinstance(source["ref"], str):
        raise ShelfValidationError(f"{label}: source.ref must be a string when present")


def validate_common_item(item: dict[str, Any], label: str) -> None:
    for field in ("id", "title", "createdAt", "updatedAt"):
        require_non_empty_string(item, field, label)
    for field in ("clientMutationId", "note", "lastDeferredAt", "completedAt", "droppedAt", "dropReason"):
        optional_string(item, field, label)
    validate_source(item.get("source"), label)
    for forbidden in ("kind", "status", "isNow", "showAt", "dueAt"):
        if forbidden in item:
            raise ShelfValidationError(f"{label}: v1 field {forbidden!r} is not allowed in schemaVersion 2")


def validate_single_item(item: dict[str, Any], label: str) -> None:
    validate_common_item(item, label)
    if item.get("type") not in SINGLE_TYPES:
        raise ShelfValidationError(f"{label}: type must be one of {sorted(SINGLE_TYPES)}")
    if item.get("state") not in SINGLE_STATES:
        raise ShelfValidationError(f"{label}: state must be one of {sorted(SINGLE_STATES)}")
    if not isinstance(item.get("deferCount"), int) or item["deferCount"] < 0:
        raise ShelfValidationError(f"{label}: deferCount must be a non-negative integer")
    validate_optional_date(item, "showOn", label)
    validate_optional_date(item, "dueOn", label)
    if item.get("state") == "completed" and not item.get("completedAt"):
        raise ShelfValidationError(f"{label}: completed items must have completedAt")
    if item.get("state") == "dropped" and not item.get("droppedAt"):
        raise ShelfValidationError(f"{label}: dropped items must have droppedAt")


def validate_schedule(schedule_value: Any, label: str) -> None:
    schedule = require_record(schedule_value, f"{label}: schedule")
    cadence = schedule.get("cadence")
    if cadence not in CADENCES:
        raise ShelfValidationError(f"{label}: schedule.cadence must be one of {sorted(CADENCES)}")
    validate_date(schedule.get("startOn"), f"{label}: schedule.startOn")
    if "endOn" in schedule and schedule["endOn"] is not None:
        end_on = validate_date(schedule["endOn"], f"{label}: schedule.endOn")
        if end_on < schedule["startOn"]:
            raise ShelfValidationError(f"{label}: schedule.endOn must be on or after startOn")
    if cadence == "weekly":
        days = schedule.get("daysOfWeek")
        if not isinstance(days, list) or not days:
            raise ShelfValidationError(f"{label}: weekly habits require non-empty schedule.daysOfWeek")
        for day in days:
            if day not in DAYS_OF_WEEK:
                raise ShelfValidationError(f"{label}: daysOfWeek values must be one of {sorted(DAYS_OF_WEEK)}")
    elif "daysOfWeek" in schedule:
        raise ShelfValidationError(f"{label}: daily habits must not set daysOfWeek")


def validate_completion(value: Any, label: str) -> None:
    completion = require_record(value, label)
    require_non_empty_string(completion, "occurrenceKey", label)
    require_non_empty_string(completion, "completedAt", label)


def validate_habit_item(item: dict[str, Any], label: str) -> None:
    validate_common_item(item, label)
    if item.get("type") != "habit":
        raise ShelfValidationError(f"{label}: type must be habit")
    if item.get("state") not in HABIT_STATES:
        raise ShelfValidationError(f"{label}: habit state must be one of {sorted(HABIT_STATES)}")
    validate_schedule(item.get("schedule"), label)
    completions = item.get("completions")
    if not isinstance(completions, list):
        raise ShelfValidationError(f"{label}: completions must be an array")
    seen: set[str] = set()
    for index, completion in enumerate(completions):
        validate_completion(completion, f"{label}: completions[{index}]")
        key = completion["occurrenceKey"]
        if key in seen:
            raise ShelfValidationError(f"{label}: duplicate occurrenceKey {key}")
        seen.add(key)
    if item.get("state") == "dropped" and not item.get("droppedAt"):
        raise ShelfValidationError(f"{label}: dropped habits must have droppedAt")
    if "deferCount" in item:
        raise ShelfValidationError(f"{label}: habits do not use deferCount")
    if "completedAt" in item:
        raise ShelfValidationError(f"{label}: habits are completed by occurrence, not completedAt")


def validate_item(item_value: Any, index: int) -> None:
    item = require_record(item_value, f"item[{index}]")
    item_type = item.get("type")
    label = f"item[{index}] {item.get('id', '<missing id>')}"
    if item_type in SINGLE_TYPES:
        validate_single_item(item, label)
    elif item_type == "habit":
        validate_habit_item(item, label)
    else:
        raise ShelfValidationError(f"{label}: type must be one of {sorted(ITEM_TYPES)}")


def validate_state(state_value: Any) -> dict[str, Any]:
    state = require_record(state_value, "Shelf state")
    if state.get("schemaVersion") != SCHEMA_VERSION:
        raise ShelfValidationError(f"schemaVersion must be {SCHEMA_VERSION}")
    if not isinstance(state.get("revision"), int) or state["revision"] < 0:
        raise ShelfValidationError("revision must be a non-negative integer")
    require_non_empty_string(state, "updatedAt", "Shelf state")
    require_non_empty_string(state, "timezone", "Shelf state")
    items = state.get("items")
    if not isinstance(items, list):
        raise ShelfValidationError("items must be an array")
    seen_ids: set[str] = set()
    seen_mutation_ids: set[str] = set()
    for index, item_value in enumerate(items):
        validate_item(item_value, index)
        item = item_value
        item_id = item["id"]
        if item_id in seen_ids:
            raise ShelfValidationError(f"duplicate item id: {item_id}")
        seen_ids.add(item_id)
        mutation_id = item.get("clientMutationId")
        if mutation_id:
            if mutation_id in seen_mutation_ids:
                raise ShelfValidationError(f"duplicate clientMutationId: {mutation_id}")
            seen_mutation_ids.add(mutation_id)
    return state


def default_state(timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "revision": 0,
        "timezone": timezone_name,
        "updatedAt": "1970-01-01T00:00:00.000Z",
        "items": [],
    }


@dataclass(frozen=True)
class CommandResult:
    state: dict[str, Any]
    item: dict[str, Any] | None = None
    card: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None
