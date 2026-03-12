#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


VALID_KINDS = {"morning", "night", "general"}
REQUIRED_FIELDS = {
    "morning": ["sleep", "energy_10", "mood_10", "grateful", "one_thing_that_matters"],
    "night": [
        "mood_10",
        "energy_10",
        "went_well",
        "could_have_been_improved",
        "actions_to_improve_tomorrow",
    ],
    "general": ["summary"],
}
SCORE_FIELDS = {"energy_10", "mood_10"}


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


def detect_workspace_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in [cwd, *cwd.parents]:
        if (path / "AGENTS.md").is_file():
            return path
    return cwd


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text())
    if args.payload_json:
        return json.loads(args.payload_json)
    raise SystemExit("Provide --payload-file or --payload-json.")


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def build_output_path(workspace_root: Path, kind: str, date: str, timestamp: datetime, entry_id: str | None) -> Path:
    day_dir = workspace_root / "journal" / "entries" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    if kind == "general":
        suffix = entry_id or timestamp.strftime("%H%M%S")
        return day_dir / f"general-{suffix}.json"
    return day_dir / f"{kind}.json"


def validate_score(name: str, value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return f"{name} must be numeric"
    if not 0 <= value <= 10:
        return f"{name} must be between 0 and 10"
    return None


def normalize_sleep(entry: dict[str, Any]) -> None:
    sleep = entry.get("sleep")
    legacy_score = entry.pop("sleep_10", None)
    legacy_notes = entry.pop("sleep_notes", None)

    if sleep is None:
        if legacy_score is not None or legacy_notes is not None:
            sleep = {}
        else:
            return

    if not isinstance(sleep, dict):
        return

    if "score_10" not in sleep and legacy_score is not None:
        sleep["score_10"] = legacy_score
    if "notes" not in sleep and isinstance(legacy_notes, str) and legacy_notes.strip():
        sleep["notes"] = legacy_notes.strip()

    entry["sleep"] = sleep


def missing_fields(kind: str, entry: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS[kind]:
        value = entry.get(field)
        if field == "sleep":
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
    for field in SCORE_FIELDS:
        if field in entry:
            error = validate_score(field, entry[field])
            if error:
                errors.append(error)
    if kind == "morning" and "sleep" in entry:
        sleep = entry["sleep"]
        if not isinstance(sleep, dict):
            errors.append("sleep must be an object")
        else:
            error = validate_score("sleep.score_10", sleep.get("score_10"))
            if error:
                errors.append(error)
            notes = sleep.get("notes")
            if notes is not None and (not isinstance(notes, str) or not notes.strip()):
                errors.append("sleep.notes must be a non-empty string when provided")
    return errors


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
    existing = load_existing(output_path)

    entry: dict[str, Any] = {
        **existing,
        **payload,
        "agent": args.agent or workspace_root.name,
        "date": args.date,
        "kind": args.kind,
        "tz": args.tz,
        "updated_at": timestamp.isoformat(),
        "source": args.source,
    }

    if args.kind == "morning":
        normalize_sleep(entry)

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
