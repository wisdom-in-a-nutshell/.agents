"""Shelf v2 derived views and card projection."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .model import SECTION_ORDER, SNAPSHOT_LIMITS

DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
INDEX_DAY = {v: k for k, v in DAY_INDEX.items()}


def local_date(timezone_name: str) -> str:
    from datetime import datetime
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def completion_keys(item: dict[str, Any]) -> set[str]:
    return {str(c.get("occurrenceKey")) for c in item.get("completions", []) if isinstance(c, dict)}


def daily_occurrence(schedule: dict[str, Any], today: str) -> tuple[str, str, str] | None:
    start = schedule["startOn"]
    end = schedule.get("endOn")
    if end and today > end:
        return None
    if start > today:
        return (start, start, "upcoming")
    return (today, today, "today")


def weekly_occurrence(schedule: dict[str, Any], today: str) -> tuple[str, str, str] | None:
    start = parse_day(schedule["startOn"])
    end = parse_day(schedule["endOn"]) if schedule.get("endOn") else None
    today_date = parse_day(today)
    if end and today_date > end:
        return None
    days = sorted(DAY_INDEX[day] for day in schedule.get("daysOfWeek") or [INDEX_DAY[start.weekday()]])
    search = max(today_date, start)
    for offset in range(0, 15):
        candidate = search + timedelta(days=offset)
        if end and candidate > end:
            return None
        if candidate < start:
            continue
        if candidate.weekday() in days:
            occurrence_date = candidate.isoformat()
            day = INDEX_DAY[candidate.weekday()]
            key = f"{candidate.isocalendar().year}-W{candidate.isocalendar().week:02d}-{day}"
            view = "today" if candidate == today_date else "upcoming"
            return (key, occurrence_date, view)
    return None


def habit_occurrence(item: dict[str, Any], today: str) -> dict[str, Any] | None:
    if item.get("state") != "active":
        return None
    schedule = item["schedule"]
    if schedule["cadence"] == "daily":
        raw = daily_occurrence(schedule, today)
    else:
        raw = weekly_occurrence(schedule, today)
    if raw is None:
        return None
    occurrence_key, occurrence_on, view = raw
    if view == "today" and occurrence_key in completion_keys(item):
        return None
    return {
        "occurrenceKey": occurrence_key,
        "occurrenceOn": occurrence_on,
        "view": view,
        "cadence": schedule["cadence"],
        "completed": occurrence_key in completion_keys(item),
    }


def single_view(item: dict[str, Any], today: str) -> str | None:
    if item.get("state") != "active":
        return None
    show_on = item.get("showOn")
    if not show_on:
        return "later"
    if show_on <= today:
        return "today"
    return "upcoming"


def due_state(due_on: str | None, today: str) -> str | None:
    if not due_on:
        return None
    if due_on < today:
        return "overdue"
    if due_on == today:
        return "today"
    return "future"


def note_preview(note: str | None) -> str | None:
    if not note:
        return None
    text = " ".join(note.split())
    return text[:157].rstrip() + "…" if len(text) > 160 else text


def single_card(item: dict[str, Any], view: str, today: str) -> dict[str, Any]:
    due = due_state(item.get("dueOn"), today)
    badges: list[str] = []
    if due == "overdue":
        badges.append("overdue")
    return {
        "cardId": f"{item['type']}:{item['id']}",
        "itemId": item["id"],
        "type": item["type"],
        "title": item["title"],
        "state": item["state"],
        "view": view,
        **({"showOn": item["showOn"]} if item.get("showOn") else {}),
        **({"dueOn": item["dueOn"]} if item.get("dueOn") else {}),
        **({"note": item["note"]} if item.get("note") else {}),
        **({"notePreview": note_preview(item.get("note"))} if item.get("note") else {}),
        **({"deferCount": item["deferCount"]} if item.get("deferCount") else {}),
        **({"lastDeferredAt": item["lastDeferredAt"]} if item.get("lastDeferredAt") else {}),
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
        **({"completedAt": item["completedAt"]} if item.get("completedAt") else {}),
        **({"droppedAt": item["droppedAt"]} if item.get("droppedAt") else {}),
        **({"dropReason": item["dropReason"]} if item.get("dropReason") else {}),
        **({"source": item["source"]} if item.get("source") else {}),
        "badges": badges,
        "meta": {"due": due} if due else {},
    }


def habit_card(item: dict[str, Any], occurrence: dict[str, Any]) -> dict[str, Any]:
    return {
        "cardId": f"habit:{item['id']}:{occurrence['occurrenceKey']}",
        "itemId": item["id"],
        "type": "habit",
        "title": item["title"],
        "state": item["state"],
        "view": occurrence["view"],
        "occurrenceKey": occurrence["occurrenceKey"],
        "occurrenceOn": occurrence["occurrenceOn"],
        "cadence": occurrence["cadence"],
        "completed": occurrence["completed"],
        **({"note": item["note"]} if item.get("note") else {}),
        **({"notePreview": note_preview(item.get("note"))} if item.get("note") else {}),
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
        **({"source": item["source"]} if item.get("source") else {}),
        "badges": [],
        "meta": {},
    }


def build_cards(state: dict[str, Any], today: str | None = None) -> dict[str, list[dict[str, Any]]]:
    today = today or local_date(state.get("timezone", "Europe/Berlin"))
    views: dict[str, list[dict[str, Any]]] = {name: [] for name in SECTION_ORDER}
    for item in state.get("items", []):
        if item.get("type") in {"do", "buy"}:
            view = single_view(item, today)
            if view:
                views[view].append(single_card(item, view, today))
        elif item.get("type") == "habit":
            occurrence = habit_occurrence(item, today)
            if occurrence:
                views[occurrence["view"]].append(habit_card(item, occurrence))
    for name, cards in views.items():
        cards.sort(key=lambda card: card_sort_key(name, card))
    return views


def card_sort_key(section: str, card: dict[str, Any]) -> tuple[str, str, str, str]:
    title = str(card.get("title") or "").casefold()
    created = str(card.get("createdAt") or "")
    due = str(card.get("dueOn") or "9999-99-99")
    show = str(card.get("showOn") or card.get("occurrenceOn") or "9999-99-99")
    if section == "today":
        return (due, show, created, title)
    if section == "upcoming":
        return (show, due, created, title)
    return (created, title, show, due)


def archive_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in state.get("items", []):
        if item.get("type") in {"do", "buy"} and item.get("state") in {"completed", "dropped"}:
            view = "completed" if item.get("state") == "completed" else "dropped"
            out.append(single_card(item, view, local_date(state.get("timezone", "Europe/Berlin"))))
        elif item.get("type") == "habit" and item.get("state") in {"paused", "dropped"}:
            out.append({
                "cardId": f"habit:{item['id']}",
                "itemId": item["id"],
                "type": "habit",
                "title": item["title"],
                "state": item["state"],
                "view": item["state"],
                "createdAt": item["createdAt"],
                "updatedAt": item["updatedAt"],
            })
    out.sort(key=lambda card: str(card.get("updatedAt") or ""), reverse=True)
    return out


def counts(state: dict[str, Any], sections: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, int]:
    sections = sections or build_cards(state)
    items = state.get("items", [])
    return {
        "total": len(items),
        "active": sum(1 for item in items if item.get("state") == "active"),
        "today": len(sections["today"]),
        "upcoming": len(sections["upcoming"]),
        "later": len(sections["later"]),
        "completed": sum(1 for item in items if item.get("state") == "completed"),
        "dropped": sum(1 for item in items if item.get("state") == "dropped"),
        "habits": sum(1 for item in items if item.get("type") == "habit"),
    }


def signals(sections: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "todayOverload": len(sections["today"]) > 9,
        "overdueCount": sum(1 for card in sections["today"] if "overdue" in card.get("badges", [])),
        "laterBacklogCount": len(sections["later"]),
    }


def build_snapshot(state: dict[str, Any], mode: str = "plan-day") -> dict[str, Any]:
    today = local_date(state.get("timezone", "Europe/Berlin"))
    raw_views = build_cards(state, today)
    limits = SNAPSHOT_LIMITS[mode]
    visible_views: dict[str, list[dict[str, Any]]] = {}
    hidden: dict[str, int] = {}
    for name in SECTION_ORDER:
        raw = raw_views[name]
        limit = limits[name]
        visible = raw if limit < 0 else raw[:limit]
        visible_views[name] = visible
        hidden[name] = max(0, len(raw) - len(visible))
    return {
        "schemaVersion": 2,
        "path": "state/shelf.json",
        "revision": state.get("revision", 0),
        "updatedAt": state.get("updatedAt"),
        "timezone": state.get("timezone", "Europe/Berlin"),
        "localDate": today,
        "mode": mode,
        "views": visible_views,
        "viewCounts": {name: len(raw_views[name]) for name in SECTION_ORDER},
        "viewLimits": limits,
        "hiddenCounts": hidden,
        "counts": counts(state, raw_views),
        "signals": signals(raw_views),
    }


def format_snapshot_plain(data: dict[str, Any]) -> str:
    c = data["counts"]
    lines = [
        f"Shelf snapshot v2 mode={data['mode']} revision={data.get('revision', 0)} active={c['active']} today={c['today']} upcoming={c['upcoming']} later={c['later']} habits={c['habits']}"
    ]
    sig = data.get("signals") or {}
    signal_bits = [f"overdue={sig.get('overdueCount', 0)}", f"later_backlog={sig.get('laterBacklogCount', 0)}"]
    if sig.get("todayOverload"):
        signal_bits.append("today_overload=true")
    lines.append("signals: " + " ".join(signal_bits))
    labels = {"today": "Today", "upcoming": "Upcoming", "later": "Later"}
    for name in SECTION_ORDER:
        cards = data.get("views", {}).get(name) or []
        hidden = int((data.get("hiddenCounts") or {}).get(name) or 0)
        if not cards and hidden == 0:
            continue
        lines.append("")
        lines.append(f"## {labels[name]}")
        for card in cards:
            bits: list[str] = [str(card.get("type"))]
            if card.get("dueOn"):
                bits.append(f"dueOn={card['dueOn']}")
            if card.get("showOn"):
                bits.append(f"showOn={card['showOn']}")
            if card.get("occurrenceKey"):
                bits.append(f"occurrence={card['occurrenceKey']}")
            if "overdue" in card.get("badges", []):
                bits.append("overdue")
            suffix = f" ({', '.join(bits)})" if bits else ""
            lines.append(f"- {card.get('itemId')}: {card.get('title')}{suffix}")
        if hidden:
            lines.append(f"- … {hidden} more hidden")
    if len(lines) == 2:
        lines.append("")
        lines.append("(empty)")
    return "\n".join(lines)
