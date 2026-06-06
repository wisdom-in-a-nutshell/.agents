"""One-shot Shelf v1 -> v2 migration."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .model import DEFAULT_TIMEZONE, date_prefix, utc_now_iso, validate_state
from .store import shelf_lock, shelf_path, write_state

HABIT_IDS = {
    "keep-a-water-bottle-on-the-desk": {"cadence": "daily", "startOn": "2026-05-21"},
    "night-device-cutoff-4-week-habit-loop": {"cadence": "daily", "startOn": "2026-05-23", "endOn": "2026-06-20"},
    "no-coffee-1-month-sleep-addiction-experiment-2026-06-06": {"cadence": "daily", "startOn": "2026-06-06", "endOn": "2026-07-06"},
}


def read_raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict) and value.get("type") in {"chat", "ui", "agent"}:
        out = {"type": str(value["type"])}
        if isinstance(value.get("ref"), str):
            out["ref"] = value["ref"]
        return out
    return None


def convert_single(item: dict[str, Any], item_type: str) -> dict[str, Any]:
    old_status = item.get("status")
    state = {"open": "active", "done": "completed", "dropped": "dropped"}.get(old_status, "active")
    out: dict[str, Any] = {
        "id": item["id"],
        **({"clientMutationId": item["clientMutationId"]} if item.get("clientMutationId") else {}),
        "type": item_type,
        "title": item["title"],
        "state": state,
        "deferCount": int(item.get("deferCount") or 0),
        "createdAt": item.get("createdAt") or utc_now_iso(),
        "updatedAt": item.get("updatedAt") or utc_now_iso(),
    }
    if (show := date_prefix(item.get("showAt"))):
        out["showOn"] = show
    if (due := date_prefix(item.get("dueAt"))):
        out["dueOn"] = due
    for field in ("note", "lastDeferredAt", "completedAt", "droppedAt", "dropReason"):
        if isinstance(item.get(field), str) and item[field].strip():
            out[field] = item[field]
    if state == "completed" and not out.get("completedAt"):
        out["completedAt"] = out["updatedAt"]
    if state == "dropped" and not out.get("droppedAt"):
        out["droppedAt"] = out["updatedAt"]
    if (src := source(item.get("source"))):
        out["source"] = src
    return out


def convert_habit(item: dict[str, Any], schedule: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": item["id"],
        **({"clientMutationId": item["clientMutationId"]} if item.get("clientMutationId") else {}),
        "type": "habit",
        "title": item["title"],
        "state": "active" if item.get("status") != "dropped" else "dropped",
        "schedule": dict(schedule),
        "completions": [],
        "createdAt": item.get("createdAt") or utc_now_iso(),
        "updatedAt": item.get("updatedAt") or utc_now_iso(),
    }
    for field in ("note", "droppedAt", "dropReason"):
        if isinstance(item.get(field), str) and item[field].strip():
            out[field] = item[field]
    if out["state"] == "dropped" and not out.get("droppedAt"):
        out["droppedAt"] = out["updatedAt"]
    if (src := source(item.get("source"))):
        out["source"] = src
    return out


def transform_v1_to_v2(v1: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if v1.get("schemaVersion") != 1:
        raise ValueError(f"expected schemaVersion 1, got {v1.get('schemaVersion')}")
    now = utc_now_iso()
    report = {"converted": 0, "habits": [], "rememberToDo": [], "removedIsNow": [], "warnings": []}
    items: list[dict[str, Any]] = []
    for item in v1.get("items", []):
        item_id = item.get("id")
        if item.get("isNow") is True:
            report["removedIsNow"].append(item_id)
        kind = item.get("kind")
        if item_id in HABIT_IDS and item.get("status") == "open":
            items.append(convert_habit(item, HABIT_IDS[item_id]))
            report["habits"].append(item_id)
        elif kind == "buy":
            items.append(convert_single(item, "buy"))
        else:
            if kind == "remember":
                report["rememberToDo"].append(item_id)
            items.append(convert_single(item, "do"))
        report["converted"] += 1
    v2 = {
        "schemaVersion": 2,
        "revision": int(v1.get("revision") or 0) + 1,
        "timezone": DEFAULT_TIMEZONE,
        "updatedAt": now,
        "items": items,
    }
    validate_state(v2)
    return v2, report


def migrate(*, apply: bool, backup: bool = True) -> dict[str, Any]:
    path = shelf_path()
    with shelf_lock():
        v1 = read_raw(path)
        v2, report = transform_v1_to_v2(v1)
        backup_path = None
        if apply:
            if backup:
                stamp = utc_now_iso().replace(":", "").replace("-", "").replace(".", "")
                backup_path = path.with_name(f"shelf.v1-backup-{stamp}.json")
                shutil.copy2(path, backup_path)
            write_state(v2)
        return {"applied": apply, "backupPath": str(backup_path) if backup_path else None, "report": report, "state": v2}
