#!/usr/bin/env python3
"""Fetch a normalized personal health snapshot and write the local health sink."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_HEALTH_SNAPSHOT_API_URL = (
    "https://aipodcasting-hzbxdueeg4eeatgh.eastus-01.azurewebsites.net"
    "/personal/health/withings-snapshot"
)


class HealthSyncError(Exception):
    """Raised when the snapshot fetch or local write fails."""


def _discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


REPO_ROOT = _discover_repo_root(Path.cwd())


def _default_output_root() -> Path:
    return (REPO_ROOT / "reference" / "health").resolve()


def _default_person() -> str:
    return REPO_ROOT.name.strip().lower()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the normalized health snapshot and refresh the local sink.",
    )
    parser.add_argument("--output-root", type=Path, default=_default_output_root())
    parser.add_argument("--person", default=_default_person())
    parser.add_argument("--days-back", type=int, default=None)
    parser.add_argument("--measurement-days-back", type=int, default=None)
    parser.add_argument("--activity-days-back", type=int, default=None)
    parser.add_argument("--workout-days-back", type=int, default=None)
    parser.add_argument("--sleep-days-back", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _fetch_snapshot(*, api_url: str, params: dict[str, Any]) -> dict[str, Any]:
    query_params = {key: value for key, value in params.items() if value is not None}
    url = api_url
    if query_params:
        url = f"{api_url}?{urlencode(query_params)}"

    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=60.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HealthSyncError(f"Failed to fetch health snapshot from {url}: {exc}") from exc

    if not isinstance(payload, dict):
        raise HealthSyncError("Health snapshot endpoint returned a non-object payload.")
    return payload


def _infer_source(snapshot: dict[str, Any]) -> str:
    for key in ("source", "provider", "upstream_source"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    devices_latest = (
        snapshot.get("metrics", {})
        .get("devices", {})
        .get("latest", {})
    )
    if isinstance(devices_latest, dict):
        value = devices_latest.get("source")
        if isinstance(value, str) and value.strip():
            return value.strip()

    return "api"


def _write_health_snapshot(*, output_root: Path, snapshot: dict[str, Any]) -> list[Path]:
    metrics_root = output_root / "metrics"
    generated_at = datetime.fromisoformat(snapshot["generated_at"])
    metrics = snapshot["metrics"]
    source = _infer_source(snapshot)
    written_paths: list[Path] = []

    devices = metrics["devices"]
    written_paths.extend(
        _write_latest_and_snapshot(
            root=metrics_root / "devices",
            latest_payload=devices["latest"],
            snapshot_payload=devices["snapshot"],
            snapshot_date=devices["snapshot_date"],
            source=source,
        )
    )

    dataset_roots = {
        "weight": metrics_root / "weight",
        "body_composition": metrics_root / "body-composition",
        "activity_daily": metrics_root / "activity" / "daily",
        "activity_workouts": metrics_root / "activity" / "workouts",
        "sleep_summary": metrics_root / "sleep" / "summary",
        "sleep_stages": metrics_root / "sleep" / "stages",
    }

    for dataset_name, root in dataset_roots.items():
        written_paths.extend(
            _write_dated_record_map(
                root=root,
                dated_records=metrics[dataset_name]["by_date"],
                generated_at=generated_at,
                source=source,
            )
        )

    return written_paths


def _write_dated_record_map(
    *,
    root: Path,
    dated_records: dict[str, list[dict[str, Any]]],
    generated_at: datetime,
    source: str,
) -> list[Path]:
    written_paths: list[Path] = []
    for record_date in sorted(dated_records):
        payload = {
            "date": record_date,
            "source": source,
            "generated_at": generated_at.isoformat(),
            "records": dated_records[record_date],
        }
        dated_path = root / "by-date" / record_date[:4] / f"{record_date}.json"
        _write_json(dated_path, payload)
        written_paths.append(dated_path)

    latest_path = root / "latest.json"
    _write_json(
        latest_path,
        _load_latest_payload_from_history(root=root, generated_at=generated_at, source=source),
    )
    written_paths.append(latest_path)
    return written_paths


def _write_latest_and_snapshot(
    *,
    root: Path,
    latest_payload: dict[str, Any],
    snapshot_payload: dict[str, Any],
    snapshot_date: str,
    source: str,
) -> list[Path]:
    latest_path = root / "latest.json"
    snapshot_path = root / "snapshots" / snapshot_date[:4] / f"{snapshot_date}.json"
    _write_json(latest_path, {**latest_payload, "source": latest_payload.get("source", source)})
    _write_json(snapshot_path, {**snapshot_payload, "source": snapshot_payload.get("source", source)})
    return [latest_path, snapshot_path]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_latest_payload_from_history(*, root: Path, generated_at: datetime, source: str) -> dict[str, Any]:
    by_date_root = root / "by-date"
    if not by_date_root.exists():
        return {"date": None, "generated_at": generated_at.isoformat(), "records": [], "source": source}

    latest_payload: dict[str, Any] | None = None
    latest_date: str | None = None
    for dated_path in sorted(by_date_root.rglob("*.json")):
        payload = json.loads(dated_path.read_text(encoding="utf-8"))
        payload_date = payload.get("date")
        if not isinstance(payload_date, str):
            continue
        if latest_date is None or payload_date > latest_date:
            latest_date = payload_date
            latest_payload = payload
    if latest_payload is None:
        return {"date": None, "generated_at": generated_at.isoformat(), "records": [], "source": source}
    return {**latest_payload, "generated_at": generated_at.isoformat(), "source": latest_payload.get("source", source)}


def main() -> None:
    args = _parse_args()
    params = {
        "person": args.person,
        "days_back": args.days_back,
        "measurement_days_back": args.measurement_days_back,
        "activity_days_back": args.activity_days_back,
        "workout_days_back": args.workout_days_back,
        "sleep_days_back": args.sleep_days_back,
    }
    snapshot = _fetch_snapshot(api_url=DEFAULT_HEALTH_SNAPSHOT_API_URL, params=params)
    written_paths = _write_health_snapshot(output_root=args.output_root, snapshot=snapshot)

    if args.json:
        print(
            json.dumps(
                {
                    "api_url": DEFAULT_HEALTH_SNAPSHOT_API_URL,
                    "output_root": str(args.output_root),
                    "person": args.person,
                    "windows": snapshot.get("windows", {}),
                    "written_paths": [str(path) for path in written_paths],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    for path in written_paths:
        print(path)


if __name__ == "__main__":
    try:
        main()
    except HealthSyncError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
