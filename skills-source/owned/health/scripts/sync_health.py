#!/usr/bin/env python3
"""Sync health data into the canonical local sink."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import time as monotonic_time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_API_BASE_URL = "https://wbsapi.withings.net"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_KEY_VAULT_NAME = "kv-shared-repos"
DEFAULT_REFRESH_TOKEN_SECRET_NAME = "withings--refresh-token-adi"
DEFAULT_TOKEN_STORE_MODE = "key_vault"

DEFAULT_MEASUREMENT_DAYS_BACK = 2
DEFAULT_ACTIVITY_DAYS_BACK = 2
DEFAULT_WORKOUT_DAYS_BACK = 2
DEFAULT_SLEEP_DAYS_BACK = 2

BACKFILL_MEASUREMENT_DAYS_BACK = 3650
BACKFILL_ACTIVITY_DAYS_BACK = 90
BACKFILL_WORKOUT_DAYS_BACK = 180
BACKFILL_SLEEP_DAYS_BACK = 30

WITHINGS_SLEEP_MAX_WINDOW_DAYS = 7
WITHINGS_SLEEP_STAGE_DATA_FIELDS = ",".join(
    [
        "hr",
        "rr",
        "snoring",
        "sdnn_1",
        "rmssd",
        "hrv_quality",
        "mvt_score",
        "chest_movement_rate",
        "withings_index",
        "breathing_sounds",
    ]
)
WITHINGS_SLEEP_SUMMARY_DATA_FIELDS = ",".join(
    [
        "nb_rem_episodes",
        "sleep_efficiency",
        "sleep_latency",
        "total_sleep_time",
        "total_timeinbed",
        "wakeup_latency",
        "waso",
        "apnea_hypopnea_index",
        "breathing_disturbances_intensity",
        "asleepduration",
        "deepsleepduration",
        "durationtosleep",
        "durationtowakeup",
        "hr_average",
        "hr_max",
        "hr_min",
        "lightsleepduration",
        "night_events",
        "out_of_bed_count",
        "remsleepduration",
        "rr_average",
        "rr_max",
        "rr_min",
        "sleep_score",
        "snoring",
        "snoringepisodecount",
        "wakeupcount",
        "wakeupduration",
        "mvt_score_avg",
        "mvt_active_duration",
        "rmssd_start_avg",
        "rmssd_end_avg",
        "chest_movement_rate_wellness_average",
        "chest_movement_rate_wellness_min",
        "chest_movement_rate_wellness_max",
        "breathing_sounds",
        "breathing_sounds_episode_count",
        "chest_movement_rate_average",
        "chest_movement_rate_min",
        "chest_movement_rate_max",
        "core_body_temperature_min",
        "core_body_temperature_max",
        "core_body_temperature_avg",
        "core_body_temperature_status",
    ]
)

MEASUREMENT_FIELD_MAP: dict[int, str] = {
    1: "weight_kg",
    5: "fat_free_mass_kg",
    6: "fat_ratio_pct",
    8: "fat_mass_kg",
    76: "muscle_mass_kg",
    77: "hydration_kg",
    88: "bone_mass_kg",
    91: "pulse_wave_velocity_mps",
}

BODY_COMPOSITION_FIELDS = {
    "fat_free_mass_kg",
    "fat_ratio_pct",
    "fat_mass_kg",
    "muscle_mass_kg",
    "hydration_kg",
    "bone_mass_kg",
    "pulse_wave_velocity_mps",
}


class HealthSyncError(Exception):
    """Raised when the health sync workflow cannot proceed."""


@dataclass(slots=True)
class SyncConfig:
    output_root: Path
    measurement_days_back: int = DEFAULT_MEASUREMENT_DAYS_BACK
    activity_days_back: int = DEFAULT_ACTIVITY_DAYS_BACK
    workout_days_back: int = DEFAULT_WORKOUT_DAYS_BACK
    sleep_days_back: int = DEFAULT_SLEEP_DAYS_BACK


def _discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


REPO_ROOT = _discover_repo_root(Path.cwd())


def _read_env_file_values() -> dict[str, str]:
    env_path = os.environ.get("HEALTH_ENV_FILE")
    path = Path(env_path) if env_path else REPO_ROOT / ".env"
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[key] = value
    return parsed


ENV_FILE_VALUES = _read_env_file_values()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        value = ENV_FILE_VALUES.get(name, default)
    return value


def _default_output_root() -> Path:
    env_root = _env("HEALTH_REFERENCE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return (REPO_ROOT / "reference" / "health").resolve()


class WithingsTokenStore:
    """Resolve and persist the Withings refresh token."""

    def __init__(self) -> None:
        self.mode = (_env("WITHINGS_TOKEN_STORE", DEFAULT_TOKEN_STORE_MODE) or DEFAULT_TOKEN_STORE_MODE).strip().lower()
        self.key_vault_name = (_env("WITHINGS_KEY_VAULT_NAME", DEFAULT_KEY_VAULT_NAME) or DEFAULT_KEY_VAULT_NAME).strip()
        self.refresh_token_secret_name = (
            _env("WITHINGS_REFRESH_TOKEN_SECRET_NAME", DEFAULT_REFRESH_TOKEN_SECRET_NAME)
            or DEFAULT_REFRESH_TOKEN_SECRET_NAME
        ).strip()

    def get_refresh_token(self) -> str:
        if self.mode in {"env", "env_file"}:
            refresh_token = (_env("WITHINGS_REFRESH_TOKEN") or "").strip()
            if not refresh_token:
                raise HealthSyncError("Missing WITHINGS_REFRESH_TOKEN for env token-store mode.")
            return refresh_token

        if self.mode not in {"key_vault", "keyvault", ""}:
            raise HealthSyncError(f"Unsupported WITHINGS_TOKEN_STORE mode: {self.mode}")

        return self._read_key_vault_secret(self.refresh_token_secret_name)

    def save_refresh_token(self, refresh_token: str) -> None:
        refresh_token_value = refresh_token.strip()
        if not refresh_token_value:
            return

        if self.mode in {"env", "env_file"}:
            self._save_refresh_token_to_env_file(refresh_token_value)
            os.environ["WITHINGS_REFRESH_TOKEN"] = refresh_token_value
            return

        self._write_key_vault_secret(self.refresh_token_secret_name, refresh_token_value)

    def _read_key_vault_secret(self, secret_name: str) -> str:
        result = subprocess.run(
            [
                "/opt/homebrew/bin/az" if Path("/opt/homebrew/bin/az").exists() else "az",
                "keyvault",
                "secret",
                "show",
                "--vault-name",
                self.key_vault_name,
                "--name",
                secret_name,
                "--query",
                "value",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise HealthSyncError(
                f"Failed to read Key Vault secret {secret_name}: {result.stderr.strip()}"
            )
        value = result.stdout.strip()
        if not value:
            raise HealthSyncError(f"Key Vault secret {secret_name} is empty.")
        return value

    def _write_key_vault_secret(self, secret_name: str, value: str) -> None:
        result = subprocess.run(
            [
                "/opt/homebrew/bin/az" if Path("/opt/homebrew/bin/az").exists() else "az",
                "keyvault",
                "secret",
                "set",
                "--vault-name",
                self.key_vault_name,
                "--name",
                secret_name,
                "--value",
                value,
                "--output",
                "none",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise HealthSyncError(
                f"Failed to write Key Vault secret {secret_name}: {result.stderr.strip()}"
            )

    def _save_refresh_token_to_env_file(self, refresh_token: str) -> None:
        path = Path(_env("HEALTH_ENV_FILE") or REPO_ROOT / ".env")
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        key = "WITHINGS_REFRESH_TOKEN"
        replaced = False
        for index, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[index] = f"{key}={refresh_token}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={refresh_token}")
        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


class WithingsApiClient:
    """Self-contained Withings client for health sync use."""

    def __init__(self, *, timeout: float = DEFAULT_HTTP_TIMEOUT) -> None:
        self.timeout = timeout
        self.base_url = (_env("WITHINGS_API_BASE_URL", DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip("/")
        self.client_id = (_env("WITHINGS_CLIENT_ID") or "").strip()
        self.client_secret = (_env("WITHINGS_CLIENT_SECRET") or "").strip()
        if not self.client_id or not self.client_secret:
            raise HealthSyncError(
                "Missing Withings sync credentials. Set WITHINGS_CLIENT_ID and WITHINGS_CLIENT_SECRET."
            )
        self.token_store = WithingsTokenStore()
        self.access_token: str | None = None
        self.access_token_expires_at = 0.0

    def get_devices(self) -> dict[str, Any]:
        return self._post_form("/v2/user", {"action": "getdevice"})

    def get_measurements(self, *, startdate: int, enddate: int) -> dict[str, Any]:
        return self._post_form(
            "/measure",
            {
                "action": "getmeas",
                "startdate": startdate,
                "enddate": enddate,
            },
        )

    def get_activity(self, *, startdateymd: str, enddateymd: str) -> dict[str, Any]:
        return self._post_form(
            "/v2/measure",
            {
                "action": "getactivity",
                "startdateymd": startdateymd,
                "enddateymd": enddateymd,
            },
        )

    def get_workouts(self, *, startdateymd: str, enddateymd: str) -> dict[str, Any]:
        return self._post_form(
            "/v2/measure",
            {
                "action": "getworkouts",
                "startdateymd": startdateymd,
                "enddateymd": enddateymd,
            },
        )

    def get_sleep(self, *, startdate: int, enddate: int, data_fields: str) -> dict[str, Any]:
        return self._post_form(
            "/v2/sleep",
            {
                "action": "get",
                "startdate": startdate,
                "enddate": enddate,
                "data_fields": data_fields,
            },
        )

    def get_sleep_summary(self, *, startdateymd: str, enddateymd: str, data_fields: str) -> dict[str, Any]:
        return self._post_form(
            "/v2/sleep",
            {
                "action": "getsummary",
                "startdateymd": startdateymd,
                "enddateymd": enddateymd,
                "data_fields": data_fields,
            },
        )

    def _post_form(self, service_path: str, data: dict[str, Any], *, use_bearer: bool = True) -> dict[str, Any]:
        url = f"{self.base_url}/{service_path.lstrip('/')}"
        body = urlencode({key: value for key, value in data.items() if value is not None}).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if use_bearer:
            headers["Authorization"] = f"Bearer {self.get_access_token()}"

        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise HealthSyncError(f"Withings request failed for {service_path}: {exc}") from exc

        if not isinstance(payload, dict) or payload.get("status") not in {None, 0, "0"}:
            raise HealthSyncError(f"Withings returned an error for {service_path}: {payload}")

        body_payload = payload.get("body")
        if body_payload is None:
            return {}
        if not isinstance(body_payload, dict):
            raise HealthSyncError(f"Withings returned an unexpected body for {service_path}: {payload}")
        return body_payload

    def get_access_token(self) -> str:
        if self.access_token and self.access_token_expires_at > monotonic_time.monotonic() + 60:
            return self.access_token

        refresh_token = self.token_store.get_refresh_token()
        nonce = self._get_nonce()
        token_response = self._post_form(
            "/v2/oauth2",
            {
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "nonce": nonce,
                "signature": _build_withings_signature(
                    client_secret=self.client_secret,
                    action="requesttoken",
                    client_id=self.client_id,
                    nonce=nonce,
                ),
            },
            use_bearer=False,
        )
        access_token = (token_response.get("access_token") or "").strip()
        if not access_token:
            raise HealthSyncError(f"Withings token refresh did not return an access token: {token_response}")

        rotated_refresh_token = (token_response.get("refresh_token") or "").strip()
        if rotated_refresh_token and rotated_refresh_token != refresh_token:
            self.token_store.save_refresh_token(rotated_refresh_token)

        expires_in = token_response.get("expires_in")
        try:
            expires_in_value = int(expires_in) if expires_in is not None else 10800
        except (TypeError, ValueError):
            expires_in_value = 10800

        self.access_token = access_token
        self.access_token_expires_at = monotonic_time.monotonic() + expires_in_value
        return access_token

    def _get_nonce(self) -> str:
        timestamp = str(int(monotonic_time.time()))
        body = self._post_form(
            "/v2/signature",
            {
                "action": "getnonce",
                "client_id": self.client_id,
                "timestamp": timestamp,
                "signature": _build_withings_signature(
                    client_secret=self.client_secret,
                    action="getnonce",
                    client_id=self.client_id,
                    timestamp=timestamp,
                ),
            },
            use_bearer=False,
        )
        nonce = (body.get("nonce") or "").strip()
        if not nonce:
            raise HealthSyncError("Withings nonce response was missing nonce.")
        return nonce


def _build_withings_signature(*, client_secret: str, **params: str) -> str:
    ordered_values = ",".join(value for _, value in sorted(params.items()))
    return hmac.new(
        client_secret.encode("utf-8"),
        ordered_values.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def export_health(config: SyncConfig) -> list[Path]:
    client = WithingsApiClient()
    now = datetime.now(tz=UTC)
    end_date = now.date()
    measurements_start = end_date - timedelta(days=config.measurement_days_back)
    activity_start = end_date - timedelta(days=config.activity_days_back)
    workouts_start = end_date - timedelta(days=config.workout_days_back)
    sleep_start = end_date - timedelta(days=config.sleep_days_back)

    metrics_root = config.output_root / "metrics"
    written_paths: list[Path] = []

    devices = client.get_devices()
    written_paths.extend(
        _write_latest_and_snapshot(
            root=metrics_root / "devices",
            latest_payload={
                "source": "withings",
                "generated_at": now.isoformat(),
                "records": devices.get("devices", []),
            },
            snapshot_payload=devices,
            snapshot_date=end_date.isoformat(),
        )
    )

    measurements = client.get_measurements(
        startdate=_start_of_day_timestamp(measurements_start),
        enddate=_end_of_day_timestamp(end_date),
    )
    weight_records, body_composition_records = _normalize_measurements(measurements)
    written_paths.extend(
        _write_dated_record_map(root=metrics_root / "weight", dated_records=weight_records, generated_at=now)
    )
    written_paths.extend(
        _write_dated_record_map(
            root=metrics_root / "body-composition",
            dated_records=body_composition_records,
            generated_at=now,
        )
    )

    activity = client.get_activity(startdateymd=activity_start.isoformat(), enddateymd=end_date.isoformat())
    written_paths.extend(
        _write_dated_record_map(
            root=metrics_root / "activity" / "daily",
            dated_records=_normalize_activity(activity),
            generated_at=now,
        )
    )

    workouts = client.get_workouts(startdateymd=workouts_start.isoformat(), enddateymd=end_date.isoformat())
    written_paths.extend(
        _write_dated_record_map(
            root=metrics_root / "activity" / "workouts",
            dated_records=_normalize_workouts(workouts),
            generated_at=now,
        )
    )

    sleep_summary = client.get_sleep_summary(
        startdateymd=sleep_start.isoformat(),
        enddateymd=end_date.isoformat(),
        data_fields=WITHINGS_SLEEP_SUMMARY_DATA_FIELDS,
    )
    written_paths.extend(
        _write_dated_record_map(
            root=metrics_root / "sleep" / "summary",
            dated_records=_normalize_sleep_summaries(sleep_summary),
            generated_at=now,
        )
    )

    sleep_stages = _fetch_sleep_stages(client=client, start_date=sleep_start, end_date=end_date)
    written_paths.extend(
        _write_dated_record_map(
            root=metrics_root / "sleep" / "stages",
            dated_records=_normalize_sleep_stages(sleep_stages),
            generated_at=now,
        )
    )

    return written_paths


def _normalize_measurements(payload: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    measuregrps = payload.get("measuregrps", [])
    weight_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    body_composition_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in measuregrps:
        timestamp = group.get("date")
        if not isinstance(timestamp, int):
            continue
        zone = _resolve_zone(group.get("timezone"))
        captured_at = datetime.fromtimestamp(timestamp, tz=zone)
        record_date = captured_at.date().isoformat()
        base_record = {
            "captured_at": captured_at.isoformat(),
            "measure_group_id": group.get("grpid"),
            "device_id": group.get("hash_deviceid") or group.get("deviceid"),
        }
        weight_value: float | None = None
        body_record: dict[str, Any] = dict(base_record)

        for measure in group.get("measures", []):
            field_name = MEASUREMENT_FIELD_MAP.get(measure.get("type"))
            if field_name is None:
                continue
            scaled_value = _scale_withings_measure(measure)
            if scaled_value is None:
                continue
            if field_name == "weight_kg":
                weight_value = scaled_value
            elif field_name in BODY_COMPOSITION_FIELDS:
                body_record[field_name] = scaled_value

        if weight_value is not None:
            weight_records[record_date].append({**base_record, "weight_kg": weight_value})
        if any(field in body_record for field in BODY_COMPOSITION_FIELDS):
            body_composition_records[record_date].append(body_record)
    return dict(weight_records), dict(body_composition_records)


def _normalize_activity(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("activities", []):
        raw = dict(record)
        known_keys = {
            "date",
            "steps",
            "distance",
            "calories",
            "totalcalories",
            "soft",
            "moderate",
            "intense",
            "active",
            "hash_deviceid",
            "deviceid",
            "timezone",
        }
        normalized = {
            "date": raw.get("date"),
            "steps": raw.get("steps"),
            "distance_m": raw.get("distance"),
            "active_calories_kcal": raw.get("calories"),
            "total_calories_kcal": raw.get("totalcalories"),
            "soft_duration_s": raw.get("soft"),
            "moderate_duration_s": raw.get("moderate"),
            "intense_duration_s": raw.get("intense"),
            "active_duration_s": raw.get("active"),
            "device_id": raw.get("hash_deviceid") or raw.get("deviceid"),
            "timezone": raw.get("timezone"),
            "extra": {key: value for key, value in raw.items() if key not in known_keys},
        }
        compacted = _compact_structure(normalized)
        records_by_date[compacted["date"]].append(compacted)
    return dict(records_by_date)


def _normalize_workouts(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for workout in payload.get("series", []):
        raw = dict(workout)
        timezone_name = raw.get("timezone")
        zone = _resolve_zone(timezone_name)
        start_timestamp = raw.get("startdate")
        end_timestamp = raw.get("enddate")
        known_keys = {"id", "category", "date", "startdate", "enddate", "deviceid", "timezone", "data"}
        normalized = {
            "date": raw.get("date"),
            "workout_id": raw.get("id"),
            "category": raw.get("category"),
            "start_at": datetime.fromtimestamp(start_timestamp, tz=zone).isoformat() if isinstance(start_timestamp, int) else None,
            "end_at": datetime.fromtimestamp(end_timestamp, tz=zone).isoformat() if isinstance(end_timestamp, int) else None,
            "device_id": raw.get("deviceid"),
            "timezone": timezone_name,
            "metrics": raw.get("data", {}),
            "extra": {key: value for key, value in raw.items() if key not in known_keys},
        }
        compacted = _compact_structure(normalized)
        if isinstance(compacted.get("date"), str):
            records_by_date[compacted["date"]].append(compacted)
    return dict(records_by_date)


def _normalize_sleep_summaries(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in payload.get("series", []):
        raw = dict(record)
        timezone_name = raw.get("timezone") or "UTC"
        zone = _resolve_zone(timezone_name)
        start_timestamp = raw.get("startdate")
        end_timestamp = raw.get("enddate")
        known_keys = {"startdate", "enddate", "date", "data", "timezone"}
        normalized = _compact_structure(
            {
                "date": raw.get("date"),
                "sleep_start": datetime.fromtimestamp(start_timestamp, tz=zone).isoformat() if isinstance(start_timestamp, int) else None,
                "sleep_end": datetime.fromtimestamp(end_timestamp, tz=zone).isoformat() if isinstance(end_timestamp, int) else None,
                "metrics": raw.get("data", {}),
                "extra": {key: value for key, value in raw.items() if key not in known_keys},
            }
        )
        record_date = normalized.get("date")
        if isinstance(record_date, str):
            records_by_date[record_date].append(normalized)
    return dict(records_by_date)


def _normalize_sleep_stages(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped_stages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in _group_sleep_sessions(payload.get("series", [])):
        grouped_stages[session["date"]].append(session)
    return dict(grouped_stages)


def _group_sleep_sessions(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not stages:
        return []

    sorted_stages = sorted((_compact_structure(dict(stage)) for stage in stages), key=lambda stage: stage["startdate"])
    sessions: list[list[dict[str, Any]]] = []
    current_session: list[dict[str, Any]] = []
    previous_end: int | None = None
    session_gap_seconds = 7200

    for stage in sorted_stages:
        start_timestamp = stage["startdate"]
        if previous_end is not None and start_timestamp - previous_end > session_gap_seconds and current_session:
            sessions.append(current_session)
            current_session = []
        current_session.append(stage)
        previous_end = stage["enddate"]

    if current_session:
        sessions.append(current_session)

    normalized_sessions: list[dict[str, Any]] = []
    for session in sessions:
        end_zone = _resolve_zone("Europe/Berlin")
        session_end = datetime.fromtimestamp(session[-1]["enddate"], tz=end_zone)
        source_model = next((stage.get("model") for stage in session if stage.get("model")), None)
        source_model_id = next((stage.get("model_id") for stage in session if stage.get("model_id") is not None), None)
        top_level_extra = next(
            (
                {
                    key: value
                    for key, value in stage.items()
                    if key not in {"startdate", "enddate", "state", "model", "model_id", "hr", "rr", "snoring", "sdnn_1", "rmssd"}
                }
                for stage in session
                if any(
                    key not in {"startdate", "enddate", "state", "model", "model_id", "hr", "rr", "snoring", "sdnn_1", "rmssd"}
                    for key in stage
                )
            ),
            {},
        )
        normalized_stages = []
        for stage in session:
            normalized_stages.append(
                _compact_structure(
                    {
                        "start_at": datetime.fromtimestamp(stage["startdate"], tz=end_zone).isoformat(),
                        "end_at": datetime.fromtimestamp(stage["enddate"], tz=end_zone).isoformat(),
                        "state_code": stage["state"],
                        "state_label": _sleep_state_label(stage["state"]),
                        "metrics": {
                            "hr": stage.get("hr"),
                            "rr": stage.get("rr"),
                            "snoring": stage.get("snoring"),
                            "sdnn_1": stage.get("sdnn_1"),
                            "rmssd": stage.get("rmssd"),
                        },
                    }
                )
            )
        normalized_sessions.append(
            _compact_structure(
                {
                    "date": session_end.date().isoformat(),
                    "sleep_start": datetime.fromtimestamp(session[0]["startdate"], tz=end_zone).isoformat(),
                    "sleep_end": session_end.isoformat(),
                    "source_model": source_model,
                    "source_model_id": source_model_id,
                    "extra": top_level_extra,
                    "stages": normalized_stages,
                }
            )
        )
    return normalized_sessions


def _fetch_sleep_stages(*, client: WithingsApiClient, start_date: date, end_date: date) -> dict[str, Any]:
    merged_series: list[dict[str, Any]] = []
    seen_stage_keys: set[tuple[int, int, int]] = set()
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=WITHINGS_SLEEP_MAX_WINDOW_DAYS - 1), end_date)
        chunk = client.get_sleep(
            startdate=_start_of_day_timestamp(current_start),
            enddate=_end_of_day_timestamp(current_end),
            data_fields=WITHINGS_SLEEP_STAGE_DATA_FIELDS,
        )
        for stage in chunk.get("series", []):
            start_timestamp = stage.get("startdate")
            end_timestamp = stage.get("enddate")
            state = stage.get("state")
            if not isinstance(start_timestamp, int) or not isinstance(end_timestamp, int) or not isinstance(state, int):
                continue
            key = (start_timestamp, end_timestamp, state)
            if key in seen_stage_keys:
                continue
            seen_stage_keys.add(key)
            merged_series.append(stage)
        current_start = current_end + timedelta(days=1)
    return {"series": merged_series}


def _write_dated_record_map(*, root: Path, dated_records: dict[str, list[dict[str, Any]]], generated_at: datetime) -> list[Path]:
    written_paths: list[Path] = []
    for record_date in sorted(dated_records):
        payload = {
            "date": record_date,
            "source": "withings",
            "generated_at": generated_at.isoformat(),
            "records": dated_records[record_date],
        }
        dated_path = root / "by-date" / record_date[:4] / f"{record_date}.json"
        _write_json(dated_path, payload)
        written_paths.append(dated_path)
    latest_path = root / "latest.json"
    _write_json(latest_path, _load_latest_payload_from_history(root=root, generated_at=generated_at))
    written_paths.append(latest_path)
    return written_paths


def _write_latest_and_snapshot(*, root: Path, latest_payload: dict[str, Any], snapshot_payload: dict[str, Any], snapshot_date: str) -> list[Path]:
    latest_path = root / "latest.json"
    snapshot_path = root / "snapshots" / snapshot_date[:4] / f"{snapshot_date}.json"
    _write_json(latest_path, latest_payload)
    _write_json(snapshot_path, snapshot_payload)
    return [latest_path, snapshot_path]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_latest_payload_from_history(*, root: Path, generated_at: datetime) -> dict[str, Any]:
    by_date_root = root / "by-date"
    if not by_date_root.exists():
        return {"date": None, "generated_at": generated_at.isoformat(), "records": [], "source": "withings"}

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
        return {"date": None, "generated_at": generated_at.isoformat(), "records": [], "source": "withings"}
    return {**latest_payload, "generated_at": generated_at.isoformat()}


def _sleep_state_label(state_code: int) -> str | None:
    return {
        0: "awake",
        1: "light",
        2: "deep",
        3: "rem",
        4: "manual",
        5: "unspecified",
        15: "out_of_bed",
    }.get(state_code)


def _compact_structure(value: Any) -> Any:
    if isinstance(value, dict):
        compacted = {key: _compact_structure(item) for key, item in value.items()}
        return {key: item for key, item in compacted.items() if item is not None and item != {} and item != []}
    if isinstance(value, list):
        compacted_items = [_compact_structure(item) for item in value]
        return [item for item in compacted_items if item is not None and item != {} and item != []]
    return value


def _scale_withings_measure(measure: dict[str, Any]) -> float | None:
    value = measure.get("value")
    unit = measure.get("unit")
    if not isinstance(value, (int, float)) or not isinstance(unit, int):
        return None
    return round(float(value) * (10**unit), 6)


def _start_of_day_timestamp(value: date) -> int:
    return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp())


def _end_of_day_timestamp(value: date) -> int:
    return int(datetime.combine(value, time.max, tzinfo=UTC).timestamp())


def _resolve_zone(timezone_name: str | None) -> ZoneInfo:
    if not timezone_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _resolve_window(*, explicit_value: int | None, default_value: int, backfill_value: int, use_backfill: bool) -> int:
    if explicit_value is not None:
        return explicit_value
    if use_backfill:
        return backfill_value
    return default_value


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync personal health data into the local health sink.")
    parser.add_argument("--provider", choices=("withings",), default="withings")
    parser.add_argument("--output-root", type=Path, default=_default_output_root())
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--measurement-days-back", type=int, default=None)
    parser.add_argument("--activity-days-back", type=int, default=None)
    parser.add_argument("--workout-days-back", type=int, default=None)
    parser.add_argument("--sleep-days-back", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.provider != "withings":
        raise SystemExit(f"Unsupported provider: {args.provider}")

    config = SyncConfig(
        output_root=args.output_root,
        measurement_days_back=_resolve_window(
            explicit_value=args.measurement_days_back,
            default_value=DEFAULT_MEASUREMENT_DAYS_BACK,
            backfill_value=BACKFILL_MEASUREMENT_DAYS_BACK,
            use_backfill=args.backfill,
        ),
        activity_days_back=_resolve_window(
            explicit_value=args.activity_days_back,
            default_value=DEFAULT_ACTIVITY_DAYS_BACK,
            backfill_value=BACKFILL_ACTIVITY_DAYS_BACK,
            use_backfill=args.backfill,
        ),
        workout_days_back=_resolve_window(
            explicit_value=args.workout_days_back,
            default_value=DEFAULT_WORKOUT_DAYS_BACK,
            backfill_value=BACKFILL_WORKOUT_DAYS_BACK,
            use_backfill=args.backfill,
        ),
        sleep_days_back=_resolve_window(
            explicit_value=args.sleep_days_back,
            default_value=DEFAULT_SLEEP_DAYS_BACK,
            backfill_value=BACKFILL_SLEEP_DAYS_BACK,
            use_backfill=args.backfill,
        ),
    )
    written_paths = export_health(config)

    if args.json:
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "output_root": str(config.output_root),
                    "backfill": args.backfill,
                    "windows": {
                        "measurement_days_back": config.measurement_days_back,
                        "activity_days_back": config.activity_days_back,
                        "workout_days_back": config.workout_days_back,
                        "sleep_days_back": config.sleep_days_back,
                    },
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
