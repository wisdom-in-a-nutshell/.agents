#!/usr/bin/env python3
"""Query the local health sink with an agent-friendly CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import sys
import time
import uuid
from typing import Any

SCHEMA_VERSION = "1.0"

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_DEPENDENCY = 4
EXIT_TIMEOUT = 5


@dataclass
class HealthQueryError(Exception):
    code: str
    message: str
    hint: str
    exit_code: int = EXIT_GENERIC
    retryable: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "hint": self.hint,
        }


class HealthArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise HealthQueryError(
            code="E_INVALID_USAGE",
            message=message,
            hint="Run --help to see the supported commands and flags.",
            exit_code=EXIT_USAGE,
        )


def _discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


REPO_ROOT = _discover_repo_root(Path.cwd())
HEALTH_ROOT = REPO_ROOT / "reference" / "health"
METRICS_ROOT = HEALTH_ROOT / "metrics"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _today_local() -> date:
    return datetime.now().date()


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _round_or_none(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def _km_from_meters(value_m: float | None) -> float | None:
    return None if value_m is None else round(value_m / 1000.0, 3)


def _seconds_between(start: str, end: str) -> int:
    return max(0, int((_parse_iso_datetime(end) - _parse_iso_datetime(start)).total_seconds()))


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HealthQueryError(
            code="E_DATASET_MISSING",
            message=f"Missing health dataset file: {path}",
            hint="Run the sync script first or verify that the health sink exists.",
            exit_code=EXIT_DEPENDENCY,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HealthQueryError(
            code="E_INVALID_JSON",
            message=f"Could not parse health dataset file: {path}",
            hint="Inspect the file and rerun sync if it looks corrupted.",
            exit_code=EXIT_DEPENDENCY,
        ) from exc
    if not isinstance(payload, dict):
        raise HealthQueryError(
            code="E_INVALID_PAYLOAD",
            message=f"Unexpected non-object payload in {path}",
            hint="Inspect the local sink and rerun sync if needed.",
            exit_code=EXIT_DEPENDENCY,
        )
    return payload


def _dataset_dir(*parts: str) -> Path:
    root = METRICS_ROOT.joinpath(*parts)
    if not root.exists():
        raise HealthQueryError(
            code="E_DATASET_MISSING",
            message=f"Missing health dataset directory: {root}",
            hint="Run the sync script first or verify that the health sink exists.",
            exit_code=EXIT_DEPENDENCY,
        )
    return root


def _latest_payload(*parts: str) -> dict[str, Any]:
    return _load_json(_dataset_dir(*parts) / "latest.json")


def _dated_payloads(*parts: str) -> list[dict[str, Any]]:
    by_date_root = _dataset_dir(*parts) / "by-date"
    if not by_date_root.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for path in sorted(by_date_root.rglob("*.json")):
        payload = _load_json(path)
        if isinstance(payload.get("date"), str):
            payloads.append(payload)
    return payloads


def _window_dates(days: int, end_date: date | None) -> tuple[date, date]:
    if days <= 0:
        raise HealthQueryError(
            code="E_INVALID_DAYS",
            message="--days must be a positive integer.",
            hint="Pass a value like --days 7.",
            exit_code=EXIT_USAGE,
        )
    final = end_date or _today_local()
    start = final - timedelta(days=days - 1)
    return start, final


def _filter_payloads_by_window(payloads: list[dict[str, Any]], *, start_date: date, end_date: date) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for payload in payloads:
        try:
            payload_date = _parse_iso_date(payload["date"])
        except Exception:
            continue
        if start_date <= payload_date <= end_date:
            filtered.append(payload)
    return filtered


def _weight_latest() -> dict[str, Any]:
    payload = _latest_payload("weight")
    records = payload.get("records") or []
    record = records[0] if records else None
    found = isinstance(record, dict)
    return {
        "health_root": str(HEALTH_ROOT),
        "source": payload.get("source"),
        "found": found,
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "record": record if found else None,
        "weight_kg": _round_or_none(record.get("weight_kg")) if found else None,
    }


def _weight_avg(*, days: int, end_date: date | None) -> dict[str, Any]:
    payloads = _dated_payloads("weight")
    start_date, final_date = _window_dates(days, end_date)
    window_payloads = _filter_payloads_by_window(payloads, start_date=start_date, end_date=final_date)

    points: list[dict[str, Any]] = []
    for payload in window_payloads:
        for record in payload.get("records") or []:
            if isinstance(record, dict) and isinstance(record.get("weight_kg"), (int, float)):
                points.append(
                    {
                        "date": payload["date"],
                        "captured_at": record.get("captured_at"),
                        "weight_kg": float(record["weight_kg"]),
                    }
                )

    weights = [point["weight_kg"] for point in points]
    found = bool(weights)
    avg_weight = sum(weights) / len(weights) if weights else None
    first_weight = weights[0] if weights else None
    latest_weight = weights[-1] if weights else None

    return {
        "health_root": str(HEALTH_ROOT),
        "found": found,
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": final_date.isoformat(),
            "days": days,
        },
        "coverage": {
            "dates_with_records": [payload["date"] for payload in window_payloads],
            "record_count": len(points),
        },
        "avg_weight_kg": _round_or_none(avg_weight),
        "min_weight_kg": _round_or_none(min(weights) if weights else None),
        "max_weight_kg": _round_or_none(max(weights) if weights else None),
        "first_weight_kg": _round_or_none(first_weight),
        "latest_weight_kg": _round_or_none(latest_weight),
        "delta_weight_kg": _round_or_none((latest_weight - first_weight) if found else None),
        "measurements": [
            {
                "date": point["date"],
                "captured_at": point["captured_at"],
                "weight_kg": _round_or_none(point["weight_kg"]),
            }
            for point in points
        ],
    }


def _summarize_sleep_record(record: dict[str, Any]) -> dict[str, Any]:
    start = record.get("sleep_start")
    end = record.get("sleep_end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise HealthQueryError(
            code="E_INVALID_SLEEP_RECORD",
            message="Sleep record is missing sleep_start or sleep_end.",
            hint="Inspect the local sleep dataset for schema changes.",
            exit_code=EXIT_DEPENDENCY,
        )

    stage_totals: dict[str, int] = {}
    awake_interruptions = 0
    for stage in record.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        stage_start = stage.get("start_at")
        stage_end = stage.get("end_at")
        state_label = stage.get("state_label") or "unknown"
        if not isinstance(stage_start, str) or not isinstance(stage_end, str):
            continue
        duration_s = _seconds_between(stage_start, stage_end)
        stage_totals[state_label] = stage_totals.get(state_label, 0) + duration_s
        if state_label == "awake":
            awake_interruptions += 1

    duration_in_bed_s = _seconds_between(start, end)
    asleep_duration_s = sum(duration for label, duration in stage_totals.items() if label != "awake")

    return {
        "date": record.get("date"),
        "sleep_start": start,
        "sleep_end": end,
        "duration_in_bed_s": duration_in_bed_s,
        "duration_in_bed_human": _format_duration(duration_in_bed_s),
        "asleep_duration_s": asleep_duration_s,
        "asleep_duration_human": _format_duration(asleep_duration_s),
        "awake_duration_s": stage_totals.get("awake", 0),
        "awake_duration_human": _format_duration(stage_totals.get("awake", 0)),
        "awake_interruptions": awake_interruptions,
        "stage_totals_s": stage_totals,
        "stage_totals_human": {label: _format_duration(duration) for label, duration in stage_totals.items()},
        "source_model": record.get("source_model"),
        "source_model_id": record.get("source_model_id"),
    }


def _sleep_latest() -> dict[str, Any]:
    payload = _latest_payload("sleep", "stages")
    records = payload.get("records") or []
    record = records[0] if records else None
    found = isinstance(record, dict)
    return {
        "health_root": str(HEALTH_ROOT),
        "source": payload.get("source"),
        "found": found,
        "date": payload.get("date"),
        "generated_at": payload.get("generated_at"),
        "session": _summarize_sleep_record(record) if found else None,
    }


def _sleep_range(*, days: int, end_date: date | None) -> dict[str, Any]:
    payloads = _dated_payloads("sleep", "stages")
    start_date, final_date = _window_dates(days, end_date)
    window_payloads = _filter_payloads_by_window(payloads, start_date=start_date, end_date=final_date)

    sessions: list[dict[str, Any]] = []
    for payload in window_payloads:
        for record in payload.get("records") or []:
            if isinstance(record, dict):
                sessions.append(_summarize_sleep_record(record))

    found = bool(sessions)
    in_bed_values = [session["duration_in_bed_s"] for session in sessions]
    asleep_values = [session["asleep_duration_s"] for session in sessions]
    awake_interruptions = [session["awake_interruptions"] for session in sessions]

    stage_totals: dict[str, int] = {}
    for session in sessions:
        for label, duration in session["stage_totals_s"].items():
            stage_totals[label] = stage_totals.get(label, 0) + duration

    return {
        "health_root": str(HEALTH_ROOT),
        "found": found,
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": final_date.isoformat(),
            "days": days,
        },
        "coverage": {
            "dates_with_records": [payload["date"] for payload in window_payloads],
            "session_count": len(sessions),
        },
        "avg_duration_in_bed_s": int(sum(in_bed_values) / len(in_bed_values)) if in_bed_values else None,
        "avg_asleep_duration_s": int(sum(asleep_values) / len(asleep_values)) if asleep_values else None,
        "avg_awake_interruptions": _round_or_none(sum(awake_interruptions) / len(awake_interruptions), 2) if awake_interruptions else None,
        "total_stage_time_s": stage_totals,
        "total_stage_time_human": {label: _format_duration(duration) for label, duration in stage_totals.items()},
        "sessions": sessions,
    }


def _activity_record_summary(record: dict[str, Any]) -> dict[str, Any]:
    distance_m = float(record["distance_m"]) if isinstance(record.get("distance_m"), (int, float)) else None
    return {
        "date": record.get("date"),
        "steps": record.get("steps"),
        "distance_m": _round_or_none(distance_m),
        "distance_km": _km_from_meters(distance_m),
        "active_calories_kcal": _round_or_none(float(record["active_calories_kcal"])) if isinstance(record.get("active_calories_kcal"), (int, float)) else None,
        "total_calories_kcal": _round_or_none(float(record["total_calories_kcal"])) if isinstance(record.get("total_calories_kcal"), (int, float)) else None,
        "active_duration_s": record.get("active_duration_s"),
        "active_duration_human": _format_duration(record.get("active_duration_s")) if isinstance(record.get("active_duration_s"), int) else None,
        "intense_duration_s": record.get("intense_duration_s"),
        "moderate_duration_s": record.get("moderate_duration_s"),
        "soft_duration_s": record.get("soft_duration_s"),
        "timezone": record.get("timezone"),
    }


def _activity_date(*, query_date: date) -> dict[str, Any]:
    path = _dataset_dir("activity", "daily") / "by-date" / query_date.isoformat()[:4] / f"{query_date.isoformat()}.json"
    if not path.exists():
        return {
            "health_root": str(HEALTH_ROOT),
            "found": False,
            "query_date": query_date.isoformat(),
            "record": None,
        }
    payload = _load_json(path)
    records = payload.get("records") or []
    record = records[0] if records else None
    return {
        "health_root": str(HEALTH_ROOT),
        "source": payload.get("source"),
        "found": isinstance(record, dict),
        "query_date": query_date.isoformat(),
        "generated_at": payload.get("generated_at"),
        "record": _activity_record_summary(record) if isinstance(record, dict) else None,
    }


def _workout_summary(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
    distance_m = float(metrics["distance"]) if isinstance(metrics.get("distance"), (int, float)) else None
    return {
        "date": record.get("date"),
        "workout_id": record.get("workout_id"),
        "category": record.get("category"),
        "start_at": record.get("start_at"),
        "end_at": record.get("end_at"),
        "duration_s": _seconds_between(record["start_at"], record["end_at"]) if isinstance(record.get("start_at"), str) and isinstance(record.get("end_at"), str) else None,
        "distance_m": _round_or_none(distance_m),
        "distance_km": _km_from_meters(distance_m),
        "steps": metrics.get("steps"),
        "calories": _round_or_none(float(metrics["calories"])) if isinstance(metrics.get("calories"), (int, float)) else None,
        "intensity": metrics.get("intensity"),
        "timezone": record.get("timezone"),
    }


def _activity_workouts(*, days: int, end_date: date | None) -> dict[str, Any]:
    payloads = _dated_payloads("activity", "workouts")
    start_date, final_date = _window_dates(days, end_date)
    window_payloads = _filter_payloads_by_window(payloads, start_date=start_date, end_date=final_date)
    workouts: list[dict[str, Any]] = []
    for payload in window_payloads:
        for record in payload.get("records") or []:
            if isinstance(record, dict):
                workouts.append(_workout_summary(record))

    return {
        "health_root": str(HEALTH_ROOT),
        "found": bool(workouts),
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": final_date.isoformat(),
            "days": days,
        },
        "coverage": {
            "dates_with_records": [payload["date"] for payload in window_payloads],
            "workout_count": len(workouts),
        },
        "total_distance_m": _round_or_none(sum(workout["distance_m"] or 0.0 for workout in workouts)),
        "total_distance_km": _km_from_meters(sum(workout["distance_m"] or 0.0 for workout in workouts)),
        "total_steps": sum(int(workout["steps"] or 0) for workout in workouts),
        "total_calories": _round_or_none(sum(workout["calories"] or 0.0 for workout in workouts)),
        "workouts": workouts,
    }


def _summary_recent(*, days: int, end_date: date | None) -> dict[str, Any]:
    weight = _weight_avg(days=days, end_date=end_date)
    sleep = _sleep_range(days=days, end_date=end_date)
    workouts = _activity_workouts(days=days, end_date=end_date)

    start_date, final_date = _window_dates(days, end_date)
    daily_payloads = _filter_payloads_by_window(_dated_payloads("activity", "daily"), start_date=start_date, end_date=final_date)
    daily_records = []
    for payload in daily_payloads:
        for record in payload.get("records") or []:
            if isinstance(record, dict):
                daily_records.append(_activity_record_summary(record))

    avg_steps = None
    if daily_records:
        step_values = [int(record["steps"]) for record in daily_records if isinstance(record.get("steps"), int)]
        if step_values:
            avg_steps = round(sum(step_values) / len(step_values))

    highlights: list[str] = []
    if weight.get("found"):
        latest = weight.get("latest_weight_kg")
        avg = weight.get("avg_weight_kg")
        delta = weight.get("delta_weight_kg")
        highlights.append(f"Weight {latest} kg latest; {days}-day average {avg} kg; delta {delta} kg.")
    else:
        highlights.append(f"No weight measurements found in the last {days} days.")

    if sleep.get("found"):
        avg_asleep = sleep.get("avg_asleep_duration_s")
        coverage = sleep["coverage"]["session_count"]
        highlights.append(
            f"Sleep recorded on {coverage} night(s); average asleep duration {_format_duration(avg_asleep)}."
        )
    else:
        highlights.append(f"No sleep sessions found in the last {days} days.")

    if daily_records:
        highlights.append(
            f"Activity recorded on {len(daily_records)} day(s); average steps {avg_steps}."
        )
    else:
        highlights.append(f"No daily activity records found in the last {days} days.")

    if workouts.get("found"):
        highlights.append(
            f"{workouts['coverage']['workout_count']} workout(s) in the last {days} days totaling {workouts['total_distance_km']} km."
        )
    else:
        highlights.append(f"No workouts found in the last {days} days.")

    return {
        "health_root": str(HEALTH_ROOT),
        "window": {
            "start_date": start_date.isoformat(),
            "end_date": final_date.isoformat(),
            "days": days,
        },
        "weight": {
            "found": weight.get("found"),
            "avg_weight_kg": weight.get("avg_weight_kg"),
            "latest_weight_kg": weight.get("latest_weight_kg"),
            "delta_weight_kg": weight.get("delta_weight_kg"),
            "record_count": weight["coverage"]["record_count"],
        },
        "sleep": {
            "found": sleep.get("found"),
            "session_count": sleep["coverage"]["session_count"],
            "avg_asleep_duration_s": sleep.get("avg_asleep_duration_s"),
            "avg_duration_in_bed_s": sleep.get("avg_duration_in_bed_s"),
        },
        "activity": {
            "daily_record_count": len(daily_records),
            "avg_steps": avg_steps,
            "workout_count": workouts["coverage"]["workout_count"],
        },
        "highlights": highlights,
        "summary_text": " ".join(highlights),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = HealthArgumentParser(
        description="Query the local health sink with a stable agent-first CLI.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    mode.add_argument("--human", action="store_true", help="Emit concise human-readable output.")
    mode.add_argument("--plain", action="store_true", help="Emit stable key=value output.")
    parser.add_argument("--no-input", action="store_true", help="Confirm non-interactive execution.")

    subparsers = parser.add_subparsers(dest="domain", required=True)

    weight = subparsers.add_parser("weight", help="Query weight measurements.")
    weight_sub = weight.add_subparsers(dest="action", required=True)
    weight_sub.add_parser("latest", help="Return the latest weight measurement.")
    weight_avg = weight_sub.add_parser("avg", help="Return average weight over a date window.")
    weight_avg.add_argument("--days", type=int, required=True)
    weight_avg.add_argument("--end-date", type=date.fromisoformat)

    sleep = subparsers.add_parser("sleep", help="Query sleep sessions.")
    sleep_sub = sleep.add_subparsers(dest="action", required=True)
    sleep_sub.add_parser("latest", help="Return the latest sleep session summary.")
    sleep_range = sleep_sub.add_parser("range", help="Return sleep summaries over a date window.")
    sleep_range.add_argument("--days", type=int, required=True)
    sleep_range.add_argument("--end-date", type=date.fromisoformat)

    activity = subparsers.add_parser("activity", help="Query daily activity and workouts.")
    activity_sub = activity.add_subparsers(dest="action", required=True)
    activity_today = activity_sub.add_parser("today", help="Return today's daily activity record.")
    activity_today.add_argument("--date", type=date.fromisoformat, help="Override the query date.")
    activity_date = activity_sub.add_parser("date", help="Return the activity record for a specific date.")
    activity_date.add_argument("--date", type=date.fromisoformat, required=True)
    activity_workouts = activity_sub.add_parser("workouts", help="Return workouts over a date window.")
    activity_workouts.add_argument("--days", type=int, required=True)
    activity_workouts.add_argument("--end-date", type=date.fromisoformat)

    summary = subparsers.add_parser("summary", help="Return a lightweight recent-status summary.")
    summary_sub = summary.add_subparsers(dest="action", required=True)
    summary_recent = summary_sub.add_parser("recent", help="Summarize recent weight, sleep, and activity.")
    summary_recent.add_argument("--days", type=int, required=True)
    summary_recent.add_argument("--end-date", type=date.fromisoformat)

    return parser


def _resolve_mode(args: argparse.Namespace) -> str:
    if args.json:
        return "json"
    if args.human:
        return "human"
    if args.plain:
        return "plain"
    return "human" if sys.stdout.isatty() else "json"


def _normalize_global_flags(argv: list[str]) -> list[str]:
    movable = {"--json", "--human", "--plain", "--no-input"}
    front: list[str] = []
    rest: list[str] = []
    for token in argv:
        if token in movable:
            front.append(token)
        else:
            rest.append(token)
    return front + rest


def _resolve_mode_from_argv(argv: list[str]) -> str:
    if "--json" in argv:
        return "json"
    if "--human" in argv:
        return "human"
    if "--plain" in argv:
        return "plain"
    return "human" if sys.stdout.isatty() else "json"


def _run_query(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.domain == "weight" and args.action == "latest":
        return "weight latest", _weight_latest()
    if args.domain == "weight" and args.action == "avg":
        return "weight avg", _weight_avg(days=args.days, end_date=args.end_date)
    if args.domain == "sleep" and args.action == "latest":
        return "sleep latest", _sleep_latest()
    if args.domain == "sleep" and args.action == "range":
        return "sleep range", _sleep_range(days=args.days, end_date=args.end_date)
    if args.domain == "activity" and args.action == "today":
        return "activity today", _activity_date(query_date=args.date or _today_local())
    if args.domain == "activity" and args.action == "date":
        return "activity date", _activity_date(query_date=args.date)
    if args.domain == "activity" and args.action == "workouts":
        return "activity workouts", _activity_workouts(days=args.days, end_date=args.end_date)
    if args.domain == "summary" and args.action == "recent":
        return "summary recent", _summary_recent(days=args.days, end_date=args.end_date)

    raise HealthQueryError(
        code="E_INVALID_COMMAND",
        message="Unsupported command.",
        hint="Run --help to see the supported commands.",
        exit_code=EXIT_USAGE,
    )


def _render_human(command: str, data: dict[str, Any]) -> str:
    if command == "weight latest":
        if not data["found"]:
            return "No weight measurement found."
        return f"Latest weight: {data['weight_kg']} kg on {data['date']}."

    if command == "weight avg":
        if not data["found"]:
            return f"No weight measurements found between {data['window']['start_date']} and {data['window']['end_date']}."
        return (
            f"Weight over {data['window']['days']} days ending {data['window']['end_date']}: "
            f"avg {data['avg_weight_kg']} kg, latest {data['latest_weight_kg']} kg, "
            f"range {data['min_weight_kg']}–{data['max_weight_kg']} kg, "
            f"delta {data['delta_weight_kg']} kg."
        )

    if command == "sleep latest":
        if not data["found"]:
            return "No sleep session found."
        session = data["session"]
        return (
            f"Latest sleep ({session['date']}): "
            f"{session['asleep_duration_human']} asleep, "
            f"{session['duration_in_bed_human']} in bed, "
            f"{session['awake_interruptions']} awake interruption(s)."
        )

    if command == "sleep range":
        if not data["found"]:
            return f"No sleep sessions found between {data['window']['start_date']} and {data['window']['end_date']}."
        return (
            f"Sleep over {data['window']['days']} days ending {data['window']['end_date']}: "
            f"{data['coverage']['session_count']} session(s), "
            f"avg asleep {_format_duration(data['avg_asleep_duration_s'])}, "
            f"avg in bed {_format_duration(data['avg_duration_in_bed_s'])}, "
            f"avg awake interruptions {data['avg_awake_interruptions']}."
        )

    if command in {"activity today", "activity date"}:
        if not data["found"]:
            return f"No daily activity record found for {data['query_date']}."
        record = data["record"]
        return (
            f"Activity for {data['query_date']}: "
            f"{record['steps']} steps, "
            f"{record['distance_km']} km, "
            f"{record['active_duration_human']} active."
        )

    if command == "activity workouts":
        if not data["found"]:
            return f"No workouts found between {data['window']['start_date']} and {data['window']['end_date']}."
        return (
            f"Workouts over {data['window']['days']} days ending {data['window']['end_date']}: "
            f"{data['coverage']['workout_count']} workout(s), "
            f"{data['total_distance_km']} km total distance, "
            f"{data['total_steps']} total steps."
        )

    if command == "summary recent":
        return data["summary_text"]

    return json.dumps(data, sort_keys=True)


def _flatten_plain(prefix: str, value: Any) -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else key
            lines.extend(_flatten_plain(child_prefix, value[key]))
        return lines
    if isinstance(value, list):
        lines.append(f"{prefix}={json.dumps(value, sort_keys=True)}")
        return lines
    lines.append(f"{prefix}={value}")
    return lines


def _emit_success(*, mode: str, command: str, data: dict[str, Any], started_at: float, request_id: str) -> None:
    meta = {
        "request_id": request_id,
        "duration_ms": int((time.time() - started_at) * 1000),
        "timestamp_utc": _iso(_now_utc()),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "ok",
        "data": data,
        "error": None,
        "meta": meta,
    }

    if mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if mode == "plain":
        for line in _flatten_plain("", payload):
            print(line)
        return
    print(_render_human(command, data))


def _emit_error(*, mode: str, command: str | None, error: HealthQueryError, started_at: float, request_id: str) -> None:
    meta = {
        "request_id": request_id,
        "duration_ms": int((time.time() - started_at) * 1000),
        "timestamp_utc": _iso(_now_utc()),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "error",
        "data": None,
        "error": error.to_payload(),
        "meta": meta,
    }

    if mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif mode == "plain":
        for line in _flatten_plain("", payload):
            print(line)
    else:
        print(f"Error: {error.message}", file=sys.stderr)
        print(f"Hint: {error.hint}", file=sys.stderr)


def main() -> None:
    started_at = time.time()
    request_id = uuid.uuid4().hex
    parser = _build_parser()
    normalized_argv = _normalize_global_flags(sys.argv[1:])
    mode = _resolve_mode_from_argv(normalized_argv)
    args: argparse.Namespace | None = None

    try:
        args = parser.parse_args(normalized_argv)
        mode = _resolve_mode(args)
        command, data = _run_query(args)
        _emit_success(mode=mode, command=command, data=data, started_at=started_at, request_id=request_id)
        raise SystemExit(EXIT_OK)
    except HealthQueryError as error:
        command = None
        if args and getattr(args, "domain", None) and getattr(args, "action", None):
            command = f"{args.domain} {args.action}"
        _emit_error(mode=mode, command=command, error=error, started_at=started_at, request_id=request_id)
        raise SystemExit(error.exit_code)


if __name__ == "__main__":
    main()
