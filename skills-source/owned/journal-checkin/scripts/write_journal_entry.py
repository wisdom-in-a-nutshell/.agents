#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


VALID_KINDS = {"morning", "night", "general"}
GENERAL_TITLE_MAX_WORDS = 7
GENERAL_SUMMARY_MAX_SENTENCES = 3
GENERAL_SUMMARY_MAX_WORDS = 45
REQUIRED_FIELDS = {
    "morning": ["sleep", "energy", "mood", "grateful", "one_thing_that_matters"],
    "night": [
        "mood",
        "energy",
        "went_well",
        "could_have_been_improved",
        "actions_to_improve_tomorrow",
    ],
    "general": ["title", "summary", "body", "body_format"],
}
STATE_FIELDS = {"sleep", "energy", "mood"}
WORD_RE = re.compile(r"[\w’'/-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write journal entries in a normalized structure."
    )
    parser.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    parser.add_argument("--date", required=True, help="Entry date in YYYY-MM-DD format.")
    parser.add_argument("--source", required=True, help="Short source label, for example chat:text.")
    parser.add_argument("--payload-file", help="Path to a JSON payload file.")
    parser.add_argument("--payload-json", help="Inline JSON payload.")
    parser.add_argument("--workspace-root", help="Workspace root to write under.")
    parser.add_argument("--agent", help="Optional explicit value for the `agent` field.")
    parser.add_argument("--tz", default="Europe/Berlin")
    parser.add_argument("--entry-id", help="Optional stable id for general entries.")
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


WORKSPACE_MARKERS = ("soul.md", "memory", "journal")


def is_workspace(path: Path) -> bool:
    return all((path / marker).exists() for marker in WORKSPACE_MARKERS)


def detect_workspace_root() -> Path:
    env = os.environ.get("DOBBY_WORKSPACE", "").strip()
    if env:
        path = Path(env).expanduser().resolve()
        if is_workspace(path):
            return path
        raise SystemExit(
            f"DOBBY_WORKSPACE does not look like a Dobby workspace: {path}. "
            "Expected soul.md, memory/, and journal/."
        )

    cwd = Path.cwd().resolve()
    for path in [cwd, *cwd.parents]:
        if is_workspace(path):
            return path
    return cwd


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text())
    if args.payload_json:
        return json.loads(args.payload_json)
    raise SystemExit("Provide --payload-file or --payload-json.")


def load_existing_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def build_output_path(workspace_root: Path, kind: str, date: str, timestamp: datetime, entry_id: str | None) -> Path:
    day_dir = workspace_root / "journal" / "daily" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    if kind == "general":
        return day_dir / "general.json"
    return day_dir / f"{kind}.json"


def validate_score(name: str, value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return f"{name} must be numeric"
    if not 0 <= value <= 10:
        return f"{name} must be between 0 and 10"
    return None


def word_count(value: str) -> int:
    return len(WORD_RE.findall(value))


def sentence_count(value: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])\s+", value.strip()) if part.strip()]) or 1


def compact_words(value: str, limit: int) -> str:
    words = WORD_RE.findall(value)
    if len(words) <= limit:
        return value.strip()
    return " ".join(words[:limit]).rstrip(" ,;:") + "…"


def compact_summary(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if sentences:
        text = " ".join(sentences[:GENERAL_SUMMARY_MAX_SENTENCES])
    return compact_words(text, GENERAL_SUMMARY_MAX_WORDS)


def missing_fields(kind: str, entry: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS[kind]:
        value = entry.get(field)
        if field in STATE_FIELDS:
            if not isinstance(value, dict) or value.get("score_10") is None:
                missing.append(field)
            continue
        if field == "grateful":
            if not isinstance(value, list) or len([item for item in value if str(item).strip()]) < 3:
                missing.append(field)
            continue
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(field)
    return missing


def validate_entry(kind: str, entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if kind == "general":
        title = entry.get("title")
        if isinstance(title, str):
            title_words = word_count(title)
            if title_words < 1 or title_words > GENERAL_TITLE_MAX_WORDS:
                errors.append(f"title must be 1-{GENERAL_TITLE_MAX_WORDS} words")
        summary = entry.get("summary")
        if isinstance(summary, str):
            if word_count(summary) > GENERAL_SUMMARY_MAX_WORDS:
                errors.append(f"summary must be at most {GENERAL_SUMMARY_MAX_WORDS} words")
            if sentence_count(summary) > GENERAL_SUMMARY_MAX_SENTENCES:
                errors.append(f"summary must be at most {GENERAL_SUMMARY_MAX_SENTENCES} sentences")
        if entry.get("body_format") != "markdown":
            errors.append("body_format must be markdown")

    for field in STATE_FIELDS:
        if field not in entry:
            continue
        state = entry[field]
        if not isinstance(state, dict):
            errors.append(f"{field} must be an object")
            continue
        error = validate_score(f"{field}.score_10", state.get("score_10"))
        if error:
            errors.append(error)
        notes = state.get("notes")
        if notes is not None and (not isinstance(notes, str) or not notes.strip()):
            errors.append(f"{field}.notes must be a non-empty string when provided")
    return errors


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw = [str(part).strip() for part in value]
    else:
        raw = [str(value).strip()]
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not item or item in seen:
            continue
        seen.add(item)
        tags.append(item)
    return tags


def general_entry_id(entry: dict[str, Any], timestamp: datetime, explicit_id: str | None) -> str:
    if explicit_id:
        return explicit_id
    existing = entry.get("id")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    seed = json.dumps(entry, sort_keys=True, ensure_ascii=False) + timestamp.isoformat()
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{timestamp.strftime('%H%M%S')}-{digest}"


def build_general_entry(payload: dict[str, Any], args: argparse.Namespace, timestamp: datetime) -> dict[str, Any]:
    entry: dict[str, Any] = {
        **payload,
        "source": args.source,
        "captured_at": payload.get("captured_at") or timestamp.isoformat(),
    }
    entry["id"] = general_entry_id(entry, timestamp, args.entry_id)
    entry["title"] = compact_words(
        str(entry.get("title") or entry.get("summary") or "Journal capture").strip(),
        GENERAL_TITLE_MAX_WORDS,
    )
    entry["summary"] = compact_summary(str(entry.get("summary") or entry["title"]).strip())
    entry["body"] = str(
        entry.get("body")
        or entry.get("what_feels_present")
        or entry.get("what_matters_now")
        or entry.get("raw_input")
        or entry["summary"]
    ).strip()
    entry["body_format"] = "markdown"
    entry["tags"] = normalize_tags(entry.get("tags"))
    return entry


def load_general_container(path: Path, date: str, args: argparse.Namespace, timestamp: datetime, workspace_root: Path) -> dict[str, Any]:
    if path.exists():
        existing = json.loads(path.read_text())
        if not isinstance(existing, dict):
            raise SystemExit(f"Existing general journal is not an object: {path}")
        existing.setdefault("entries", [])
        return existing
    return {
        "agent": args.agent or workspace_root.name,
        "date": date,
        "kind": "general",
        "tz": args.tz,
        "captured_at": timestamp.isoformat(),
        "updated_at": timestamp.isoformat(),
        "source": "journal-checkin",
        "schema_version": 1,
        "entries": [],
    }


def append_general_json(path: Path, entry: dict[str, Any], args: argparse.Namespace, timestamp: datetime, workspace_root: Path) -> None:
    container = load_general_container(path, args.date, args, timestamp, workspace_root)
    if container.get("kind") != "general":
        raise SystemExit(f"Existing general journal has wrong kind: {path}")
    entries = container.get("entries")
    if not isinstance(entries, list):
        raise SystemExit(f"Existing general journal entries is not a list: {path}")

    entries.append(entry)
    entries.sort(key=lambda item: (str(item.get("captured_at", "")), str(item.get("id", ""))))
    container.update(
        {
            "agent": container.get("agent") or args.agent or workspace_root.name,
            "date": args.date,
            "kind": "general",
            "tz": container.get("tz") or args.tz,
            "updated_at": timestamp.isoformat(),
            "source": container.get("source") or "journal-checkin",
            "schema_version": container.get("schema_version") or 1,
            "entries": entries,
        }
    )
    container["captured_at"] = container.get("captured_at") or entry["captured_at"]
    path.write_text(json.dumps(container, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    payload = load_payload(args)

    zone = ZoneInfo(args.tz)
    timestamp = datetime.now(zone)
    workspace_root = (
        Path(args.workspace_root).resolve()
        if args.workspace_root
        else detect_workspace_root()
    )
    if not workspace_root.is_dir():
        raise SystemExit(f"Invalid workspace root: {workspace_root}")

    output_path = build_output_path(workspace_root, args.kind, args.date, timestamp, args.entry_id)

    if args.kind == "general":
        entry = build_general_entry(payload, args, timestamp)
        if not args.allow_partial:
            missing = missing_fields(args.kind, entry)
            if missing:
                print(json.dumps({"ok": False, "missing": missing}, indent=2))
                return 3
        validation_errors = validate_entry(args.kind, entry)
        if validation_errors:
            print(json.dumps({"ok": False, "errors": validation_errors}, indent=2))
            return 2
        append_general_json(output_path, entry, args, timestamp, workspace_root)
        print(json.dumps({"ok": True, "path": str(output_path)}, indent=2))
        return 0

    existing = load_existing_json(output_path)
    entry: dict[str, Any] = {
        **existing,
        **payload,
        "agent": args.agent or workspace_root.name,
        "date": args.date,
        "kind": args.kind,
        "tz": args.tz,
        "captured_at": existing.get("captured_at", timestamp.isoformat()),
        "source": args.source,
    }

    validation_errors = validate_entry(args.kind, entry)
    if validation_errors:
        print(json.dumps({"ok": False, "errors": validation_errors}, indent=2))
        return 2

    if not args.allow_partial:
        missing = missing_fields(args.kind, entry)
        if missing:
            print(json.dumps({"ok": False, "missing": missing}, indent=2))
            return 3

    output_path.write_text(json.dumps(entry, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"ok": True, "path": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
