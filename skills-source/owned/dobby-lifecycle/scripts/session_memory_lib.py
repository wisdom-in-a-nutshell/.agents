#!/usr/bin/env python3
"""Dobby session-memory helpers.

This module owns the agent-native session-memory v4 contract used by Dobby
workspaces. Each session is a folder under memory/sessions/YYYY/MM/DD-HHMMSS/:

- meta.json     machine facts (schemaVersion, createdAt, threadId, runtime,
                trigger, cwd, tldr)
- summary.md    human/agent-readable continuity index (# title, summary body,
                "## Workspace changes" section)
- raw.jsonl     untouched runtime transcript, copied at finalize time
- dialogue.md   normalized human<->agent transcript rendered from raw.jsonl

meta.json and summary.md are written by this module. raw.jsonl and dialogue.md
are owned by transcript_lib / session-transcript and may be absent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 4
RUNTIMES = ("codex", "claude")
LOCAL_TIMEZONE = "Europe/Berlin"
RECENT_SESSION_DAYS = 7
RECENT_SESSION_MIN_COUNT = 3
RECENT_SESSION_MAX_COUNT = 10
RECENT_SESSION_FULL_COUNT = 3
RECENT_SESSION_FULL_ENTRY_MAX_CHARS = 2000
RECENT_SESSIONS_BLOCK_MAX_CHARS = 8000
TITLE_MAX_CHARS = 120
TLDR_MAX_CHARS = 240

META_FILENAME = "meta.json"
SUMMARY_FILENAME = "summary.md"
DIALOGUE_FILENAME = "dialogue.md"
RAW_FILENAME = "raw.jsonl"
WORKSPACE_CHANGES_HEADING = "## Workspace changes"

META_KEYS = ("schemaVersion", "createdAt", "threadId", "runtime", "trigger", "cwd", "tldr")


class SessionMemoryError(ValueError):
    """Validation or contract failure for session memory records."""


@dataclass(frozen=True)
class SessionMemoryEntry:
    stamp: datetime
    path: Path
    label: str
    title: str
    summary: str
    tldr: str
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
    """Parse memory/sessions/YYYY/MM/DD-HHMMSS* (folder or file) as local time."""
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


def session_dir_rel_path(created_at: str) -> Path:
    stamp = parse_created_at(created_at)
    return Path(
        "memory",
        "sessions",
        f"{stamp:%Y}",
        f"{stamp:%m}",
        f"{stamp:%d-%H%M%S}",
    )


def next_session_dir(workspace_root: Path, created_at: str) -> Path:
    path = workspace_root / session_dir_rel_path(created_at)
    if not path.exists():
        return path
    for idx in range(2, 1000):
        candidate = path.with_name(f"{path.name}-{idx}")
        if not candidate.exists():
            return candidate
    raise SessionMemoryError(f"could not find free session-memory dir for {path}")


def clean_text(value: Any, field: str, *, max_chars: int | None = None) -> str:
    if not isinstance(value, str):
        raise SessionMemoryError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise SessionMemoryError(f"{field} is required")
    if max_chars is not None and len(text) > max_chars:
        raise SessionMemoryError(f"{field} must be at most {max_chars} characters")
    return text


def clean_thread_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SessionMemoryError("threadId must be a string or null")
    return value.strip()


def clean_runtime(value: Any) -> str:
    if not isinstance(value, str) or value.strip() not in RUNTIMES:
        raise SessionMemoryError(f"runtime must be one of {', '.join(RUNTIMES)}")
    return value.strip()


def clean_cwd(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SessionMemoryError("cwd must be a string or null")
    return value.strip()


def truncate_text(content: str, limit: int, label: str = "content") -> str:
    content = content.strip()
    if len(content) <= limit:
        return content
    suffix = f"\n...[{label} truncated]"
    return content[: max(0, limit - len(suffix))].rstrip() + suffix


def truncate_single_line(content: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", content).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def first_meaningful_line(content: str) -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        cleaned = re.sub(r"^[-*]\s+", "", line).strip()
        if cleaned:
            return cleaned
    return "Legacy session memory"


def clean_tldr(value: Any, *, summary: str) -> str:
    if isinstance(value, str) and value.strip():
        source = value
    else:
        source = first_meaningful_line(summary)
    text = truncate_single_line(source, TLDR_MAX_CHARS)
    if not text:
        raise SessionMemoryError("tldr is required")
    return text


def make_record(
    *,
    trigger: str,
    title: str,
    summary: str,
    workspace_changes: str,
    thread_id: str | None,
    runtime: str,
    created_at: str | None = None,
    cwd: str | None = None,
    tldr: str | None = None,
) -> dict[str, Any]:
    cleaned_summary = clean_text(summary, "summary")
    record: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": created_at or iso_now_local(),
        "threadId": clean_thread_id(thread_id),
        "runtime": clean_runtime(runtime),
        "trigger": clean_text(trigger, "trigger"),
        "cwd": clean_cwd(cwd),
        "tldr": clean_tldr(tldr, summary=cleaned_summary),
        "title": clean_text(title, "title", max_chars=TITLE_MAX_CHARS),
        "summary": cleaned_summary,
        "workspaceChanges": clean_text(workspace_changes, "workspaceChanges"),
    }
    parse_created_at(str(record["createdAt"]))
    return record


def validate_record(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SessionMemoryError("record must be a JSON object")
    allowed_keys = set(META_KEYS) | {"title", "summary", "workspaceChanges"}
    extra_keys = sorted(set(data) - allowed_keys)
    if extra_keys:
        raise SessionMemoryError(f"unsupported key(s): {', '.join(extra_keys)}")
    for key in [
        "schemaVersion",
        "createdAt",
        "threadId",
        "runtime",
        "trigger",
        "cwd",
        "tldr",
        "title",
        "summary",
        "workspaceChanges",
    ]:
        if key not in data:
            raise SessionMemoryError(f"{key} is required")
    if data.get("schemaVersion") != SCHEMA_VERSION:
        raise SessionMemoryError(f"schemaVersion must be {SCHEMA_VERSION}")
    created_at = data.get("createdAt")
    if not isinstance(created_at, str) or not created_at.strip():
        raise SessionMemoryError("createdAt is required")
    parse_created_at(created_at)
    out = dict(data)
    out["threadId"] = clean_thread_id(data.get("threadId"))
    out["runtime"] = clean_runtime(data.get("runtime"))
    out["trigger"] = clean_text(data.get("trigger"), "trigger")
    out["cwd"] = clean_cwd(data.get("cwd"))
    out["title"] = clean_text(data.get("title"), "title", max_chars=TITLE_MAX_CHARS)
    out["summary"] = clean_text(data.get("summary"), "summary")
    out["workspaceChanges"] = clean_text(data.get("workspaceChanges"), "workspaceChanges")
    out["tldr"] = clean_tldr(data.get("tldr"), summary=out["summary"])
    return out


def upgrade_flat_record(data: Any) -> dict[str, Any]:
    """Upgrade a flat v2/v3 card to the v4 record shape for migration commands."""
    if not isinstance(data, dict):
        raise SessionMemoryError("record must be a JSON object")
    if data.get("schemaVersion") not in (2, 3, SCHEMA_VERSION):
        raise SessionMemoryError(f"cannot upgrade schemaVersion {data.get('schemaVersion')!r}")
    upgraded = dict(data)
    upgraded["schemaVersion"] = SCHEMA_VERSION
    upgraded.setdefault("runtime", "codex")
    upgraded.setdefault("cwd", None)
    if "tldr" not in upgraded:
        upgraded["tldr"] = first_meaningful_line(str(upgraded.get("summary") or ""))
    return validate_record(upgraded)


def split_record(record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Split a validated record into (meta dict, summary.md text)."""
    record = validate_record(record)
    meta = {key: record.get(key) for key in META_KEYS}
    summary_md = "\n".join(
        [
            f"# {record['title']}",
            "",
            str(record["summary"]).strip(),
            "",
            WORKSPACE_CHANGES_HEADING,
            "",
            str(record["workspaceChanges"]).strip(),
            "",
        ]
    )
    return meta, summary_md


def parse_summary_md(text: str, *, source: str = "summary.md") -> dict[str, str]:
    if text.startswith("\ufeff"):
        raise SessionMemoryError(f"{source} must not start with a BOM")
    lines = text.replace("\r\n", "\n").split("\n")
    title: str | None = None
    title_idx = -1
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            title_idx = idx
        break
    if title is None:
        raise SessionMemoryError(f"{source} must start with a '# <title>' heading")
    if not (1 <= len(title) <= TITLE_MAX_CHARS):
        raise SessionMemoryError(f"{source} title must be 1-{TITLE_MAX_CHARS} chars")
    heading_idx = -1
    in_fence = False
    for idx in range(len(lines) - 1, title_idx, -1):
        line = lines[idx]
        # Reverse fence tracking is not reliable; instead require exact final
        # heading text. Session summaries should not end inside a code fence.
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.strip() == WORKSPACE_CHANGES_HEADING:
            heading_idx = idx
            break
    if heading_idx < 0:
        raise SessionMemoryError(f"{source} must contain a '{WORKSPACE_CHANGES_HEADING}' section")
    summary = "\n".join(lines[title_idx + 1 : heading_idx]).strip()
    workspace_changes = "\n".join(lines[heading_idx + 1 :]).strip()
    if not summary:
        raise SessionMemoryError(f"{source} summary body is required")
    if not workspace_changes:
        raise SessionMemoryError(f"{source} workspace changes body is required")
    return {"title": title, "summary": summary, "workspaceChanges": workspace_changes}


def resolve_session_dir(path: Path) -> Path:
    """Accept a session folder or any file inside it; return the folder."""
    if path.is_dir():
        return path
    if path.name in {META_FILENAME, SUMMARY_FILENAME, DIALOGUE_FILENAME, RAW_FILENAME}:
        return path.parent
    raise SessionMemoryError(f"not a session folder or session file: {path}")


def read_meta(session_dir: Path) -> dict[str, Any]:
    meta_path = session_dir / META_FILENAME
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionMemoryError(f"invalid JSON in {meta_path}: {exc}") from exc
    except OSError as exc:
        raise SessionMemoryError(f"failed to read {meta_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SessionMemoryError(f"{meta_path} must hold a JSON object")
    return data


def read_record(path: Path) -> dict[str, Any]:
    session_dir = resolve_session_dir(path)
    meta = read_meta(session_dir)
    summary_path = session_dir / SUMMARY_FILENAME
    try:
        summary_text = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SessionMemoryError(f"failed to read {summary_path}: {exc}") from exc
    parts = parse_summary_md(summary_text, source=str(summary_path))
    return validate_record({**meta, **parts})


def _atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_record_files(session_dir: Path, record: dict[str, Any]) -> dict[str, Path]:
    meta, summary_md = split_record(record)
    session_dir.mkdir(parents=True, exist_ok=True)
    # Summary first, meta last. Selection requires meta.json, so a crash mid-write
    # never creates a half-readable record.
    _atomic_write_text(session_dir / SUMMARY_FILENAME, summary_md)
    _atomic_write_text(session_dir / META_FILENAME, json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return {"meta": session_dir / META_FILENAME, "summary": session_dir / SUMMARY_FILENAME}


def write_record(workspace_root: Path, record: dict[str, Any]) -> Path:
    record = validate_record(record)
    session_dir = next_session_dir(workspace_root, str(record["createdAt"]))
    write_record_files(session_dir, record)
    return session_dir


def update_meta(session_dir: Path, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into meta.json (used by transcript capture to add cwd)."""
    record = read_record(session_dir)
    merged = validate_record({**record, **updates})
    write_record_files(session_dir, merged)
    return merged


def title_from_text(content: str) -> str:
    title = re.sub(r"[`*_#]", "", first_meaningful_line(content))
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) <= TITLE_MAX_CHARS:
        return title
    return title[: TITLE_MAX_CHARS - 1].rstrip() + "…"


def strip_legacy_markdown_noise(content: str) -> str:
    skip_prefixes = (
        "source thread ",
        "source: ",
        "preserve only ",
        "useful delta only",
        "useful continuity preserved elsewhere",
    )
    kept: list[str] = []
    previous_blank = False
    for raw_line in content.replace("\r\n", "\n").split("\n"):
        line = raw_line.rstrip()
        stripped = line.strip()
        lower = stripped.lower()
        if stripped.startswith("# Session continuity"):
            continue
        if any(lower.startswith(prefix) for prefix in skip_prefixes):
            continue
        if not stripped:
            if kept and not previous_blank:
                kept.append("")
            previous_blank = True
            continue
        kept.append(line)
        previous_blank = False
    return "\n".join(kept).strip() or first_meaningful_line(content)


def extract_legacy_thread_id(content: str) -> str | None:
    patterns = [
        r"Source thread [`'](?P<id>[^`']+)[`']",
        r"source thread id:\s*[`']?(?P<id>[A-Za-z0-9._:-]+)",
        r"thread(?:Id| id)?[`: ]+[`'](?P<id>[^`']+)[`']",
        r"Source:\s*`[^`]+`\s*/\s*`(?P<id>[^`']+)`",
        r"Source:\s*`[^`]+`\s*\((?P<id>[A-Za-z0-9._:-]+)\)",
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
    summary = strip_legacy_markdown_noise(content)
    return make_record(
        trigger="migration",
        thread_id=extract_legacy_thread_id(content),
        runtime="codex",
        title=title_from_text(summary),
        summary=summary,
        workspace_changes="No separate workspace-change note existed in the legacy record.",
        created_at=stamp.isoformat(timespec="seconds"),
        cwd=None,
        tldr=first_meaningful_line(summary),
    )


def iter_session_dirs(sessions_dir: Path) -> list[Path]:
    if not sessions_dir.exists():
        return []
    out = [
        path
        for path in sessions_dir.glob("*/*/*-*")
        if path.is_dir() and (path / META_FILENAME).is_file()
    ]
    return sorted(out)


def collect_session_entries(sessions_dir: Path) -> list[SessionMemoryEntry]:
    entries: list[SessionMemoryEntry] = []
    for path in iter_session_dirs(sessions_dir):
        stamp = parse_session_path_datetime(path)
        if stamp is None:
            continue
        try:
            record = read_record(path)
        except SessionMemoryError:
            continue
        label = f"{stamp:%d-%H:%M} local — {record['title']}"
        entries.append(
            SessionMemoryEntry(
                stamp=stamp,
                path=path,
                label=label,
                title=str(record["title"]),
                summary=str(record["summary"]),
                tldr=str(record["tldr"]),
                kind="folder",
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
    return list(reversed(selected))  # newest first for rendering and cap behavior


def render_full_entry(entry: SessionMemoryEntry) -> str:
    return truncate_text(entry.summary, RECENT_SESSION_FULL_ENTRY_MAX_CHARS, "session memory")


def render_brief_lines(entries: list[SessionMemoryEntry]) -> str:
    return "\n".join(f"- {entry.stamp:%m-%d %H:%M} — {entry.tldr}" for entry in entries).strip()


def blocks_length(fulls: list[SessionMemoryEntry], briefs: list[SessionMemoryEntry]) -> int:
    total = 0
    for entry in fulls:
        total += len(f"## {entry.label}\n{render_full_entry(entry)}\n\n")
    if briefs:
        total += len(f"## earlier this week\n{render_brief_lines(briefs)}\n")
    return total


def build_recent_session_entries(sessions_dir: Path) -> list[dict[str, Any]]:
    selected = select_recent_entries(collect_session_entries(sessions_dir))
    if not selected:
        return []
    fulls = selected[:RECENT_SESSION_FULL_COUNT]
    briefs = selected[RECENT_SESSION_FULL_COUNT:]

    # Degrade gracefully until the block fits. Drop oldest briefs first, then
    # degrade oldest full entries. Never touch selected[0]: newest stays full.
    while blocks_length(fulls, briefs) > RECENT_SESSIONS_BLOCK_MAX_CHARS:
        if briefs:
            briefs = briefs[:-1]
            continue
        if len(fulls) > 1:
            degraded = fulls[-1]
            fulls = fulls[:-1]
            briefs = [degraded, *briefs]
            continue
        # Last resort: truncate the newest full within the remaining block cap.
        break

    out: list[dict[str, Any]] = []
    for entry in fulls:
        content = render_full_entry(entry)
        if len(out) == 0 and len(content) > RECENT_SESSIONS_BLOCK_MAX_CHARS:
            content = truncate_text(content, RECENT_SESSIONS_BLOCK_MAX_CHARS - len(f"## {entry.label}\n"), "session memory")
        out.append({"label": entry.label, "content": content, "path": entry.path, "kind": entry.kind})
    if briefs:
        out.append(
            {
                "label": "earlier this week",
                "content": render_brief_lines(briefs),
                "path": briefs[0].path,
                "kind": "briefs",
            }
        )
    return out
