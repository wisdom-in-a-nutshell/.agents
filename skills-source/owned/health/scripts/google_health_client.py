#!/usr/bin/env python3
"""Small Google Health API client for Fitbit/Pixel health-data probes.

This is intentionally a low-level probe client, not the canonical sync path.
The canonical Dobby read surface remains the repo-local health sink under
``memory/areas/health/``. Use this client to validate OAuth and inspect Google
Health API payloads before a normalized snapshot writer is added upstream.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE_URL = "https://health.googleapis.com"
DEFAULT_CREDENTIALS_FILE = Path.home() / ".secrets" / "google-health" / "env"
DEFAULT_TOKEN_FILE = Path.home() / ".secrets" / "google-health" / "token.json"
DEFAULT_REDIRECT_URI = "https://www.google.com"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.profile.readonly",
    "https://www.googleapis.com/auth/googlehealth.settings.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
]
SECRET_FIELDS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "GOOGLE_HEALTH_CLIENT_SECRET",
}

INTERVAL_DATA_TYPES = {
    "active-energy-burned",
    "active-minutes",
    "active-zone-minutes",
    "activity-level",
    "altitude",
    "calories-in-heart-rate-zone",
    "distance",
    "floors",
    "sedentary-period",
    "steps",
    "swim-lengths-data",
    "time-in-heart-rate-zone",
    "total-calories",
}
SAMPLE_DATA_TYPES = {
    "blood-glucose",
    "body-fat",
    "core-body-temperature",
    "heart-rate",
    "heart-rate-variability",
    "height",
    "oxygen-saturation",
    "respiratory-rate-sleep-summary",
    "run-vo2-max",
    "temperature",
    "vo2-max",
    "weight",
}
DAILY_DATA_TYPES = {
    "daily-heart-rate-variability",
    "daily-heart-rate-zones",
    "daily-oxygen-saturation",
    "daily-respiratory-rate",
    "daily-resting-heart-rate",
    "daily-sleep-temperature-derivations",
    "daily-vo2-max",
}
SESSION_DATA_TYPES = {"exercise"}


class GoogleHealthClientError(Exception):
    """Raised for OAuth, request, or CLI contract errors."""


@dataclass
class Credentials:
    client_id: str
    client_secret: str
    redirect_uri: str


def _strip_shell_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        name, separator, value = line.partition("=")
        if separator != "=":
            continue
        values[name.strip()] = _strip_shell_quotes(value)
    return values


def _resolve_credentials(args: argparse.Namespace) -> Credentials:
    file_values = _read_env_file(args.credentials_file.expanduser())
    client_id = (
        args.client_id
        or os.getenv("GOOGLE_HEALTH_CLIENT_ID")
        or file_values.get("GOOGLE_HEALTH_CLIENT_ID")
        or file_values.get("GOOGLE_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        args.client_secret
        or os.getenv("GOOGLE_HEALTH_CLIENT_SECRET")
        or file_values.get("GOOGLE_HEALTH_CLIENT_SECRET")
        or file_values.get("GOOGLE_CLIENT_SECRET")
        or ""
    ).strip()
    redirect_uri = (
        args.redirect_uri
        or os.getenv("GOOGLE_HEALTH_REDIRECT_URI")
        or file_values.get("GOOGLE_HEALTH_REDIRECT_URI")
        or DEFAULT_REDIRECT_URI
    ).strip()
    return Credentials(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)


def _require_client_id(credentials: Credentials) -> None:
    if not credentials.client_id:
        raise GoogleHealthClientError(
            "Missing GOOGLE_HEALTH_CLIENT_ID. Put it in ~/.secrets/google-health/env "
            "or pass --client-id."
        )


def _require_full_credentials(credentials: Credentials) -> None:
    _require_client_id(credentials)
    if not credentials.client_secret:
        raise GoogleHealthClientError(
            "Missing GOOGLE_HEALTH_CLIENT_SECRET. Put it in ~/.secrets/google-health/env "
            "or pass --client-secret."
        )


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _redact_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) <= 10:
        return "<redacted>"
    return f"{value[:6]}...{value[-4:]}"


def _redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            if key in SECRET_FIELDS or key.lower().endswith("token") or "secret" in key.lower():
                redacted[key] = _redact_value(value)
            else:
                redacted[key] = _redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload]
    return payload


def _emit(payload: Any, *, show_secrets: bool = False) -> None:
    if show_secrets:
        sys.stdout.write(_json_dumps(payload))
    else:
        sys.stdout.write(_json_dumps(_redact_payload(payload)))


def _load_token(path: Path) -> dict[str, Any]:
    expanded = path.expanduser()
    if not expanded.exists():
        return {}
    try:
        payload = json.loads(expanded.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GoogleHealthClientError(f"Invalid JSON token file: {expanded}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GoogleHealthClientError(f"Token file must contain a JSON object: {expanded}")
    return payload


def _save_token(path: Path, token: dict[str, Any]) -> None:
    expanded = path.expanduser()
    expanded.parent.mkdir(parents=True, exist_ok=True)
    expanded.write_text(_json_dumps(token), encoding="utf-8")
    try:
        os.chmod(expanded, 0o600)
    except OSError:
        pass


def _with_expiry(token: dict[str, Any]) -> dict[str, Any]:
    result = dict(token)
    expires_in = result.get("expires_in")
    if isinstance(expires_in, int):
        result["expires_at"] = (datetime.now(UTC) + timedelta(seconds=max(0, expires_in - 60))).isoformat()
    return result


def _token_expired(token: dict[str, Any]) -> bool:
    expires_at = token.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return datetime.now(UTC) >= expiry


def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    body = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _send_json_request(request)


def _send_json_request(request: Request, *, retry_once: bool = True) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=60.0) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code == 429 and retry_once:
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = min(30, max(1, int(retry_after or "1")))
            except ValueError:
                delay = 1
            time.sleep(delay)
            return _send_json_request(request, retry_once=False)
        details = ""
        try:
            details = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            details = str(exc)
        raise GoogleHealthClientError(f"HTTP {exc.code} from {request.full_url}: {details}") from exc
    except URLError as exc:
        raise GoogleHealthClientError(f"Request failed for {request.full_url}: {exc}") from exc

    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GoogleHealthClientError(f"Non-JSON response from {request.full_url}: {raw[:500]}") from exc
    if not isinstance(payload, dict):
        raise GoogleHealthClientError(f"Expected JSON object from {request.full_url}; got {type(payload).__name__}")
    return payload


def _exchange_code(credentials: Credentials, code: str) -> dict[str, Any]:
    _require_full_credentials(credentials)
    return _with_expiry(
        _post_form(
            TOKEN_URL,
            {
                "code": code,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "redirect_uri": credentials.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    )


def _refresh(credentials: Credentials, token: dict[str, Any]) -> dict[str, Any]:
    _require_full_credentials(credentials)
    refresh_token = str(token.get("refresh_token") or "").strip()
    if not refresh_token:
        raise GoogleHealthClientError("Token file has no refresh_token; run exchange-code again with offline access.")
    refreshed = _with_expiry(
        _post_form(
            TOKEN_URL,
            {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    )
    # Google often omits refresh_token on refresh; keep the old one unless it rotates.
    merged = {**token, **refreshed}
    if "refresh_token" not in refreshed:
        merged["refresh_token"] = refresh_token
    return merged


def _access_token(args: argparse.Namespace, credentials: Credentials) -> str:
    if args.access_token:
        return args.access_token.strip()
    token = _load_token(args.token_file)
    if not token:
        raise GoogleHealthClientError(
            f"No token file found at {args.token_file.expanduser()}. Run auth-url and exchange-code first, "
            "or pass --access-token for one-off probes."
        )
    if _token_expired(token):
        token = _refresh(credentials, token)
        _save_token(args.token_file, token)
    access_token = str(token.get("access_token") or "").strip()
    if not access_token:
        raise GoogleHealthClientError("Token file has no access_token.")
    return access_token


def _api_url(path: str, params: dict[str, Any] | None = None) -> str:
    normalized = path.strip()
    if normalized.startswith(API_BASE_URL):
        url = normalized
    else:
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        if not normalized.startswith("/v4/"):
            normalized = "/v4" + normalized
        url = API_BASE_URL + normalized
    clean_params = {key: value for key, value in (params or {}).items() if value not in (None, "")}
    if clean_params:
        url = f"{url}?{urlencode(clean_params)}"
    return url


def _api_request(
    *,
    args: argparse.Namespace,
    credentials: Credentials,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _access_token(args, credentials)
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(_api_url(path, params), data=data, headers=headers, method=method.upper())
    return _send_json_request(request)


def _paginate(
    *,
    args: argparse.Namespace,
    credentials: Credentials,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    collection_keys: tuple[str, ...],
) -> dict[str, Any]:
    accumulated: dict[str, list[Any]] = {key: [] for key in collection_keys}
    current_params = dict(params or {})
    current_body = dict(body or {}) if body is not None else None
    page_count = 0
    while True:
        payload = _api_request(
            args=args,
            credentials=credentials,
            method=method,
            path=path,
            params=current_params,
            body=current_body,
        )
        page_count += 1
        for key in collection_keys:
            value = payload.get(key)
            if isinstance(value, list):
                accumulated[key].extend(value)
        next_page_token = payload.get("nextPageToken") or payload.get("next_page_token") or ""
        if not next_page_token:
            break
        if method.upper() == "GET":
            current_params["pageToken"] = next_page_token
        else:
            assert current_body is not None
            current_body["pageToken"] = next_page_token
    return {**accumulated, "pageCount": page_count, "nextPageToken": ""}


def _snake_data_type(data_type: str) -> str:
    return data_type.replace("-", "_")


def _lower_camel_data_type(data_type: str) -> str:
    parts = _snake_data_type(data_type).split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _build_filter(data_type: str, start: str | None, end: str | None, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if not start and not end:
        return None

    field: str
    if data_type == "sleep":
        field = "sleep.interval.civil_end_time"
    elif data_type in SESSION_DATA_TYPES:
        field = f"{_snake_data_type(data_type)}.interval.civil_start_time"
    elif data_type in INTERVAL_DATA_TYPES:
        field = f"{_snake_data_type(data_type)}.interval.civil_start_time"
    elif data_type in SAMPLE_DATA_TYPES:
        field = f"{_snake_data_type(data_type)}.sample_time.civil_time"
    elif data_type in DAILY_DATA_TYPES:
        # The docs use lowerCamelCase daily summary filter fields.
        field = f"{_lower_camel_data_type(data_type)}.date"
    else:
        raise GoogleHealthClientError(
            f"Do not know the default time filter field for {data_type!r}. Pass --filter explicitly."
        )

    expressions = []
    if start:
        expressions.append(f'{field} >= "{start}"')
    if end:
        expressions.append(f'{field} < "{end}"')
    return " AND ".join(expressions)


def _civil_datetime(value: str) -> dict[str, Any]:
    date_part, separator, time_part = value.partition("T")
    try:
        parsed_date = date.fromisoformat(date_part)
    except ValueError as exc:
        raise GoogleHealthClientError(f"Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM[:SS], got {value!r}") from exc
    result: dict[str, Any] = {
        "date": {"year": parsed_date.year, "month": parsed_date.month, "day": parsed_date.day}
    }
    if separator:
        pieces = time_part.split(":")
        if len(pieces) not in {2, 3}:
            raise GoogleHealthClientError(f"Expected HH:MM or HH:MM:SS time in {value!r}")
        try:
            hours = int(pieces[0])
            minutes = int(pieces[1])
            seconds = int(pieces[2]) if len(pieces) == 3 else 0
        except ValueError as exc:
            raise GoogleHealthClientError(f"Invalid time in {value!r}") from exc
        result["time"] = {"hours": hours, "minutes": minutes, "seconds": seconds}
    return result


def _physical_interval(start: str, end: str) -> dict[str, str]:
    return {"startTime": start, "endTime": end}


def cmd_auth_url(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    _require_client_id(credentials)
    scopes = args.scope or DEFAULT_SCOPES
    params: dict[str, str] = {
        "client_id": credentials.client_id,
        "redirect_uri": credentials.redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "scope": " ".join(scopes),
    }
    if args.state:
        params["state"] = args.state
    if args.force_consent:
        params["prompt"] = "consent"
    payload = {"authorization_url": f"{AUTH_URL}?{urlencode(params)}", "scopes": scopes}
    _emit(payload, show_secrets=True)


def cmd_exchange_code(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    token = _exchange_code(credentials, args.code.strip())
    _save_token(args.token_file, token)
    _emit({"token_file": str(args.token_file.expanduser()), "token": token}, show_secrets=args.show_secrets)


def cmd_refresh_token(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    token = _load_token(args.token_file)
    if not token:
        raise GoogleHealthClientError(f"No token file found at {args.token_file.expanduser()}")
    refreshed = _refresh(credentials, token)
    _save_token(args.token_file, refreshed)
    _emit({"token_file": str(args.token_file.expanduser()), "token": refreshed}, show_secrets=args.show_secrets)


def cmd_profile(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    _emit(_api_request(args=args, credentials=credentials, method="GET", path="/users/me/profile"))


def cmd_settings(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    _emit(_api_request(args=args, credentials=credentials, method="GET", path="/users/me/settings"))


def cmd_identity(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    _emit(_api_request(args=args, credentials=credentials, method="GET", path="/users/me/identity"))


def cmd_devices(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    params = {"pageSize": args.page_size}
    if args.all_pages:
        payload = _paginate(
            args=args,
            credentials=credentials,
            method="GET",
            path="/users/me/pairedDevices",
            params=params,
            collection_keys=("pairedDevices",),
        )
    else:
        payload = _api_request(
            args=args,
            credentials=credentials,
            method="GET",
            path="/users/me/pairedDevices",
            params=params,
        )
    _emit(payload)


def cmd_list(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    data_type = args.data_type
    params = {
        "pageSize": args.page_size,
        "filter": _build_filter(data_type, args.start, args.end, args.filter),
    }
    path = f"/users/me/dataTypes/{data_type}/dataPoints"
    if args.all_pages:
        payload = _paginate(
            args=args,
            credentials=credentials,
            method="GET",
            path=path,
            params=params,
            collection_keys=("dataPoints",),
        )
    else:
        payload = _api_request(args=args, credentials=credentials, method="GET", path=path, params=params)
    _emit(payload)


def cmd_reconcile(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    data_type = args.data_type
    params = {
        "pageSize": args.page_size,
        "filter": _build_filter(data_type, args.start, args.end, args.filter),
        "dataSourceFamily": args.data_source_family,
    }
    path = f"/users/me/dataTypes/{data_type}/dataPoints:reconcile"
    if args.all_pages:
        payload = _paginate(
            args=args,
            credentials=credentials,
            method="GET",
            path=path,
            params=params,
            collection_keys=("dataPoints",),
        )
    else:
        payload = _api_request(args=args, credentials=credentials, method="GET", path=path, params=params)
    _emit(payload)


def cmd_daily_rollup(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    body: dict[str, Any] = {
        "range": {"start": _civil_datetime(args.start), "end": _civil_datetime(args.end)},
        "windowSizeDays": args.window_size_days,
    }
    if args.page_size:
        body["pageSize"] = args.page_size
    if args.data_source_family:
        body["dataSourceFamily"] = args.data_source_family
    path = f"/users/me/dataTypes/{args.data_type}/dataPoints:dailyRollUp"
    if args.all_pages:
        payload = _paginate(
            args=args,
            credentials=credentials,
            method="POST",
            path=path,
            body=body,
            collection_keys=("rollupDataPoints",),
        )
    else:
        payload = _api_request(args=args, credentials=credentials, method="POST", path=path, body=body)
    _emit(payload)


def cmd_rollup(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    body: dict[str, Any] = {
        "range": _physical_interval(args.start_time, args.end_time),
        "windowSize": args.window_size,
    }
    if args.page_size:
        body["pageSize"] = args.page_size
    if args.data_source_family:
        body["dataSourceFamily"] = args.data_source_family
    path = f"/users/me/dataTypes/{args.data_type}/dataPoints:rollUp"
    if args.all_pages:
        payload = _paginate(
            args=args,
            credentials=credentials,
            method="POST",
            path=path,
            body=body,
            collection_keys=("rollupDataPoints",),
        )
    else:
        payload = _api_request(args=args, credentials=credentials, method="POST", path=path, body=body)
    _emit(payload)


def cmd_request(args: argparse.Namespace) -> None:
    credentials = _resolve_credentials(args)
    body = None
    if args.body:
        body = json.loads(args.body)
    params = dict(item.split("=", 1) for item in args.param)
    payload = _api_request(
        args=args,
        credentials=credentials,
        method=args.method,
        path=args.path,
        params=params,
        body=body,
    )
    _emit(payload)


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS_FILE)
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--client-id", default="")
    parser.add_argument("--client-secret", default="")
    parser.add_argument("--redirect-uri", default="")
    parser.add_argument("--access-token", default="", help="Use a one-off bearer token instead of the token file.")
    parser.add_argument("--show-secrets", action="store_true", help="Do not redact token fields in command output.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Low-level Google Health API client for Fitbit/Pixel health-data probes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _add_global_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth = subparsers.add_parser("auth-url", help="Build a browser authorization URL.")
    auth.add_argument("--scope", action="append", help="OAuth scope; repeat to override the default read scopes.")
    auth.add_argument("--state", default="")
    auth.add_argument("--force-consent", action="store_true", help="Add prompt=consent to help obtain/rotate refresh_token.")
    auth.set_defaults(func=cmd_auth_url)

    exchange = subparsers.add_parser("exchange-code", help="Exchange an OAuth authorization code and save token JSON.")
    exchange.add_argument("--code", required=True)
    exchange.set_defaults(func=cmd_exchange_code)

    refresh = subparsers.add_parser("refresh-token", help="Refresh token JSON using the saved refresh_token.")
    refresh.set_defaults(func=cmd_refresh_token)

    profile = subparsers.add_parser("profile", help="GET users/me/profile.")
    profile.set_defaults(func=cmd_profile)

    settings = subparsers.add_parser("settings", help="GET users/me/settings.")
    settings.set_defaults(func=cmd_settings)

    identity = subparsers.add_parser("identity", help="GET users/me/identity.")
    identity.set_defaults(func=cmd_identity)

    devices = subparsers.add_parser("devices", help="GET users/me/pairedDevices.")
    devices.add_argument("--page-size", type=int, default=100)
    devices.add_argument("--all-pages", action="store_true")
    devices.set_defaults(func=cmd_devices)

    list_cmd = subparsers.add_parser("list", help="List raw data points for a data type.")
    list_cmd.add_argument("data_type", help="Kebab-case data type, e.g. steps, heart-rate, sleep, weight.")
    list_cmd.add_argument("--start", help="Civil lower bound, e.g. 2026-06-01 or 2026-06-01T00:00:00.")
    list_cmd.add_argument("--end", help="Civil upper bound, exclusive.")
    list_cmd.add_argument("--filter", help="Raw Google Health filter expression; overrides --start/--end.")
    list_cmd.add_argument("--page-size", type=int)
    list_cmd.add_argument("--all-pages", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    reconcile = subparsers.add_parser("reconcile", help="List reconciled data points for a data type.")
    reconcile.add_argument("data_type")
    reconcile.add_argument("--start")
    reconcile.add_argument("--end")
    reconcile.add_argument("--filter")
    reconcile.add_argument("--page-size", type=int)
    reconcile.add_argument("--all-pages", action="store_true")
    reconcile.add_argument("--data-source-family", default="users/me/dataSourceFamilies/all-sources")
    reconcile.set_defaults(func=cmd_reconcile)

    daily = subparsers.add_parser("daily-rollup", help="POST dataPoints:dailyRollUp for civil-date rollups.")
    daily.add_argument("data_type")
    daily.add_argument("--start", required=True, help="Civil start date/time, usually YYYY-MM-DD.")
    daily.add_argument("--end", required=True, help="Civil end date/time, exclusive, usually YYYY-MM-DD.")
    daily.add_argument("--window-size-days", type=int, default=1)
    daily.add_argument("--page-size", type=int)
    daily.add_argument("--all-pages", action="store_true")
    daily.add_argument("--data-source-family", default="users/me/dataSourceFamilies/all-sources")
    daily.set_defaults(func=cmd_daily_rollup)

    rollup = subparsers.add_parser("rollup", help="POST dataPoints:rollUp for physical-time rollups.")
    rollup.add_argument("data_type")
    rollup.add_argument("--start-time", required=True, help="RFC3339 start, e.g. 2026-06-01T00:00:00Z.")
    rollup.add_argument("--end-time", required=True, help="RFC3339 end, exclusive.")
    rollup.add_argument("--window-size", required=True, help="Google duration, e.g. 86400s.")
    rollup.add_argument("--page-size", type=int)
    rollup.add_argument("--all-pages", action="store_true")
    rollup.add_argument("--data-source-family", default="users/me/dataSourceFamilies/all-sources")
    rollup.set_defaults(func=cmd_rollup)

    request = subparsers.add_parser("request", help="Raw authenticated Google Health API request.")
    request.add_argument("method", choices=["GET", "POST", "PATCH", "DELETE"])
    request.add_argument("path", help="Path like /v4/users/me/profile or /users/me/profile.")
    request.add_argument("--param", action="append", default=[], help="Query parameter as key=value; repeatable.")
    request.add_argument("--body", help="JSON request body for POST/PATCH.")
    request.set_defaults(func=cmd_request)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except GoogleHealthClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON body: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
