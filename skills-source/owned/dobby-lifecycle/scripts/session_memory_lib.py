#!/usr/bin/env python3
"""Dobby session-memory JSON helpers.

This module owns the agent-native session memory v1 contract used by Dobby
workspaces. Session memory is intentionally small: provenance plus a bootable
summary, optional deeper notes, and an optional plain-English changed-file
audit for durable writes made during finalization.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1
LOCAL_TIMEZONE = "Europe/Berlin"
RECENT_SESSION_DAYS = 7
RECENT_SESSION_MIN_COUNT = 3
RECENT_SESSION_MAX_COUNT = 10
RECENT_SESSION_RECORD_MAX_CHARS = 2500
RECENT_SESSIONS_BLOCK_MAX_CHARS = 12000


class SessionMemoryError(ValueError):
    """Validation or contract failure for session memory records."""


@dataclass(frozen=True)
class SessionMemoryEntry:
    stamp: datetime
    path: Path
    label: str
    content: str
    kind: str


def now_local() -> datetime:
    return datetime.now(ZoneInfo(LOCAL_TIMEZONE))


def iso_now_local() -> str:
    return now_local().isoformat(timespec="seconds")


def parse_created_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SessionMemoryError(f"createdAt must be ISO-8601: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(LOCAL_TIMEZONE))
    return parsed.astimezone(ZoneInfo(LOCAL_TIMEZONE))


def parse_session_path_datetime(path: Path) -> datetime | None:
    """Parse memory/sessions/YYYY/MM/DD-HHMMSS* as local time."""
    try:
        year = int(path.parent.parent.name)
        month = int(path.parent.name)
        match = re.match(
            r"^(?P<day>\d{2})-(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})",
            path.stem,
        )
        if not match:
            return None
        return datetime(
            year,
            month,
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second")),
            tzinfo=ZoneInfo(LOCAL_TIMEZONE),
        )
    except (OSError, ValueError):
        return None


def session_rel_path(created_at: str, *, suffix: str = ".json") -> Path:
    stamp = parse_created_at(created_at)
    return Path(
        "memory",
        "sessions",
        f"{stamp:%Y}",
        f"{stamp:%m}",
        f"{stamp:%d-%H%M%S}{suffix}",
    )


def next_session_path(workspace_root: Path, created_at: str) -> Path:
    rel = session_rel_path(created_at)
    path = workspace_root / rel
    if not path.exists():
        return path
    stem = path.stem
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise SessionMemoryError(f"could not find free session-memory path for {path}")


def clean_summary(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise SessionMemoryError("summary must be a non-empty array of strings")
    out = [str(value).strip() for value in values if str(value).strip()]
    if not out:
        raise SessionMemoryError("summary must contain at least one non-empty item")
    return out


def clean_changed_files(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        raise SessionMemoryError("changedFiles must be an array when present")
    out: list[dict[str, str]] = []
    for idx, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise SessionMemoryError(f"changedFiles[{idx}] must be an object")
        extra_keys = sorted(set(value) - {"path", "note"})
        if extra_keys:
            raise SessionMemoryError(f"changedFiles[{idx}] unsupported key(s): {', '.join(extra_keys)}")
        path = value.get("path")
        note = value.get("note")
        if not isinstance(path, str) or not path.strip():
            raise SessionMemoryError(f"changedFiles[{idx}].path is required")
        if not isinstance(note, str) or not note.strip():
            raise SessionMemoryError(f"changedFiles[{idx}].note is required")
        out.append({"path": path.strip(), "note": note.strip()})
    return out


def make_record(
    *,
    source: str,
    reason: str,
    thread_id: str | None,
    summary: list[str],
    notes: str | None = None,
    changed_files: Any | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    source = source.strip()
    reason = reason.strip()
    if not source:
        raise SessionMemoryError("source is required")
    if not reason:
        raise SessionMemoryError("reason is required")
    record: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": created_at or iso_now_local(),
        "source": source,
        "reason": reason,
        "threadId": thread_id.strip() if isinstance(thread_id, str) and thread_id.strip() else None,
        "summary": clean_summary(summary),
    }
    parse_created_at(str(record["createdAt"]))
    if notes is not None and notes.strip():
        record["notes"] = notes.strip()
    if changed_files is not None:
        cleaned_changed_files = clean_changed_files(changed_files)
        if cleaned_changed_files:
            record["changedFiles"] = cleaned_changed_files
    return record


def validate_record(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SessionMemoryError("record must be a JSON object")
    allowed_keys = {
        "schemaVersion",
        "createdAt",
        "source",
        "reason",
        "threadId",
        "summary",
        "notes",
        "changedFiles",
    }
    extra_keys = sorted(set(data) - allowed_keys)
    if extra_keys:
        raise SessionMemoryError(f"unsupported key(s): {', '.join(extra_keys)}")
    for key in ["schemaVersion", "createdAt", "source", "reason", "threadId", "summary"]:
        if key not in data:
            raise SessionMemoryError(f"{key} is required")
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise SessionMemoryError(f"schemaVersion must be {SCHEMA_VERSION}")
    created_at = data.get("createdAt")
    if not isinstance(created_at, str) or not created_at.strip():
        raise SessionMemoryError("createdAt is required")
    parse_created_at(created_at)
    for key in ("source", "reason"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SessionMemoryError(f"{key} is required")
    thread_id = data.get("threadId")
    if thread_id is not None and (not isinstance(thread_id, str) or not thread_id.strip()):
        raise SessionMemoryError("threadId must be a string or null")
    summary = clean_summary(data.get("summary"))
    notes = data.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise SessionMemoryError("notes must be a string when present")
    changed_files = data.get("changedFiles")
    cleaned_changed_files = None
    if changed_files is not None:
        cleaned_changed_files = clean_changed_files(changed_files)
    out = dict(data)
    out["summary"] = summary
    if thread_id is None:
        out["threadId"] = None
    if cleaned_changed_files:
        out["changedFiles"] = cleaned_changed_files
    else:
        out.pop("changedFiles", None)
    return out


def read_record(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionMemoryError(f"invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise SessionMemoryError(f"failed to read {path}: {exc}") from exc
    return validate_record(data)


def atomic_write_record(path: Path, record: dict[str, Any]) -> None:
    record = validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_record(workspace_root: Path, record: dict[str, Any]) -> Path:
    record = validate_record(record)
    path = next_session_path(workspace_root, str(record["createdAt"]))
    atomic_write_record(path, record)
    return path


def truncate_text(content: str, limit: int, label: str = "content") -> str:
    content = content.strip()
    if len(content) <= limit:
        return content
    suffix = f"\n...[{label} truncated]"
    return content[: max(0, limit - len(suffix))].rstrip() + suffix


def render_json_summary(record: dict[str, Any]) -> str:
    lines = [f"source={record['source']} reason={record['reason']} threadId={record.get('threadId') or 'null'}"]
    lines.extend(f"- {item}" for item in record["summary"])
    return "\n".join(lines)


def legacy_md_summary(content: str) -> list[str]:
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        lines.append(line.lstrip("- ").strip())
        if len(lines) >= 5:
            break
    return lines or ["Legacy session note migrated from Markdown; see notes for full context."]


def extract_legacy_thread_id(content: str) -> str | None:
    patterns = [
        r"Source thread [`'](?P<id>[^`']+)[`']",
        r"source thread id:\s*[`']?(?P<id>[A-Za-z0-9._:-]+)",
        r"thread(?:Id| id)?[`: ]+[`'](?P<id>[^`']+)[`']",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            value = match.group("id").strip()
            if value:
                return value
    return None


def record_from_legacy_md(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    stamp = parse_session_path_datetime(path) or now_local()
    return make_record(
        source="legacy-md",
        reason="migration",
        thread_id=extract_legacy_thread_id(content),
        summary=legacy_md_summary(content),
        notes=content,
        created_at=stamp.isoformat(timespec="seconds"),
    )


def collect_session_entries(sessions_dir: Path) -> list[SessionMemoryEntry]:
    entries: list[SessionMemoryEntry] = []
    if not sessions_dir.exists():
        return entries

    for path in sessions_dir.glob("*/*/*-*.json"):
        stamp = parse_session_path_datetime(path)
        if stamp is None:
            continue
        try:
            record = read_record(path)
        except SessionMemoryError:
            continue
        label = stamp.strftime("%Y-%m-%d %H:%M:%S %Z")
        entries.append(
            SessionMemoryEntry(
                stamp=stamp,
                path=path,
                label=label,
                content=render_json_summary(record),
                kind="json",
            )
        )

    return sorted(entries, key=lambda item: (item.stamp, str(item.path)))


def select_recent_entries(entries: list[SessionMemoryEntry]) -> list[SessionMemoryEntry]:
    if not entries:
        return []
    cutoff = now_local() - timedelta(days=RECENT_SESSION_DAYS)
    selected_paths = {entry.path for entry in entries[-RECENT_SESSION_MIN_COUNT:]}
    selected_paths.update(entry.path for entry in entries if entry.stamp >= cutoff)
    selected = [entry for entry in entries if entry.path in selected_paths]
    if len(selected) > RECENT_SESSION_MAX_COUNT:
        selected = selected[-RECENT_SESSION_MAX_COUNT:]
    return selected


def build_recent_session_entries(sessions_dir: Path) -> list[dict[str, Any]]:
    selected = select_recent_entries(collect_session_entries(sessions_dir))
    out: list[dict[str, Any]] = []
    total_chars = 0
    for entry in selected:
        content = truncate_text(entry.content, RECENT_SESSION_RECORD_MAX_CHARS, "session memory")
        block = f"## {entry.label}\n{content}\n"
        if total_chars + len(block) > RECENT_SESSIONS_BLOCK_MAX_CHARS:
            remaining = RECENT_SESSIONS_BLOCK_MAX_CHARS - total_chars
            if remaining <= 80:
                break
            content = truncate_text(content, max(0, remaining - len(f"## {entry.label}\n")), "session memory")
        out.append(
            {
                "label": entry.label,
                "content": content,
                "path": entry.path,
                "kind": entry.kind,
            }
        )
        total_chars += len(f"## {entry.label}\n{content}\n")
    return out
