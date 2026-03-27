#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_ENV_PATH = Path.home() / ".secrets/x/env"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
API_BASE = "https://api.x.com"
DEFAULT_USER_FIELDS = "created_at,description,verified,public_metrics,profile_image_url"


class CliError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "E_GENERIC",
        exit_code: int = 1,
        retryable: bool = False,
        hint: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.retryable = retryable
        self.hint = hint
        self.details = details


@dataclass
class Config:
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    env_path: Path
    request_timeout_seconds: float


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_config(args: argparse.Namespace) -> Config:
    env_path = Path(args.env_file).expanduser()
    env_values = parse_env_file(env_path)

    def get_value(name: str) -> str:
        return os.environ.get(name) or env_values.get(name) or ""

    return Config(
        api_key=get_value("X_API_KEY"),
        api_secret=get_value("X_API_SECRET"),
        access_token=get_value("X_ACCESS_TOKEN"),
        access_token_secret=get_value("X_ACCESS_TOKEN_SECRET"),
        env_path=env_path,
        request_timeout_seconds=float(getattr(args, "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)),
    )


def require_config(config: Config) -> None:
    missing = []
    if not config.api_key:
        missing.append("X_API_KEY")
    if not config.api_secret:
        missing.append("X_API_SECRET")
    if not config.access_token:
        missing.append("X_ACCESS_TOKEN")
    if not config.access_token_secret:
        missing.append("X_ACCESS_TOKEN_SECRET")
    if missing:
        raise CliError(
            "X credentials are incomplete.",
            code="E_CONFIG",
            exit_code=2,
            hint="Populate ~/.secrets/x/env with the required OAuth 1.0a user-context credentials.",
            details={"missing": missing, "env_file": str(config.env_path)},
        )


def oauth_percent_encode(value: str) -> str:
    return urllib.parse.quote(str(value), safe="~-._")


def oauth_base_params(config: Config) -> dict[str, str]:
    return {
        "oauth_consumer_key": config.api_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": config.access_token,
        "oauth_version": "1.0",
    }


def normalize_params(params: dict[str, str]) -> str:
    items = sorted((oauth_percent_encode(k), oauth_percent_encode(v)) for k, v in params.items())
    return "&".join(f"{k}={v}" for k, v in items)


def build_oauth1_authorization_header(config: Config, method: str, url: str, *, query_params: dict[str, str] | None = None) -> str:
    oauth_params = oauth_base_params(config)
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    combined_params = dict(oauth_params)
    if parsed.query:
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            combined_params[key] = value
    if query_params:
        combined_params.update(query_params)
    normalized = normalize_params(combined_params)
    base_string = "&".join(
        [
            method.upper(),
            oauth_percent_encode(base_url),
            oauth_percent_encode(normalized),
        ]
    )
    signing_key = f"{oauth_percent_encode(config.api_secret)}&{oauth_percent_encode(config.access_token_secret)}"
    signature = base64.b64encode(hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()).decode()
    oauth_params["oauth_signature"] = signature
    header_items = ", ".join(
        f'{oauth_percent_encode(k)}="{oauth_percent_encode(v)}"' for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_items}"


def now_iso_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_http_error(url: str, status: int, body_text: str) -> CliError:
    retryable = status in {429} or status >= 500
    if status in {401, 403}:
        return CliError(
            f"X rejected the request with HTTP {status}.",
            code="E_AUTH",
            exit_code=3,
            retryable=False,
            hint="Verify the OAuth 1.0a user-context credentials and that the app has write access for the endpoint you are calling.",
            details={"url": url, "status": status, "body": body_text},
        )
    if status == 429:
        return CliError(
            "X rate-limited the request.",
            code="E_RATE_LIMIT",
            exit_code=4,
            retryable=True,
            hint="Wait and retry. Reduce bursty posting if this keeps happening.",
            details={"url": url, "status": status, "body": body_text},
        )
    if status >= 500:
        return CliError(
            f"X server error (HTTP {status}).",
            code="E_NETWORK",
            exit_code=4,
            retryable=True,
            hint="Retry the command later.",
            details={"url": url, "status": status, "body": body_text},
        )
    return CliError(
        f"X returned HTTP {status}.",
        code="E_INVALID_INPUT" if status in {400, 404, 409, 422} else "E_GENERIC",
        exit_code=2 if status in {400, 404, 409, 422} else 1,
        retryable=retryable,
        hint="Check the request shape and the app permissions for this endpoint.",
        details={"url": url, "status": status, "body": body_text},
    )


def http_request(method: str, url: str, *, headers: dict[str, str], data: bytes | None, timeout_seconds: float) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise classify_http_error(url, exc.code, body) from exc
    except TimeoutError as exc:
        raise CliError(
            f"Timed out calling {url}.",
            code="E_TIMEOUT",
            exit_code=5,
            retryable=True,
            hint="Retry with a larger --request-timeout-seconds if needed.",
        ) from exc
    except urllib.error.URLError as exc:
        raise CliError(
            f"Network error calling {url}: {exc.reason}",
            code="E_NETWORK",
            exit_code=4,
            retryable=True,
            hint="Check network connectivity and retry.",
        ) from exc


def x_json_request(config: Config, method: str, path: str, *, query_params: dict[str, str] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    require_config(config)
    url = f"{API_BASE}{path}"
    if query_params:
        url = f"{url}?{urllib.parse.urlencode(query_params)}"
    auth_header = build_oauth1_authorization_header(config, method, url)
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    _, _, body = http_request(method, url, headers=headers, data=data, timeout_seconds=config.request_timeout_seconds)
    return json.loads(body.decode("utf-8"))


def flatten_plain(prefix: str, value: Any) -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for key in sorted(value.keys()):
            child_prefix = f"{prefix}.{key}" if prefix else key
            lines.extend(flatten_plain(child_prefix, value[key]))
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}=[]"]
        lines: list[str] = []
        for index, item in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            lines.extend(flatten_plain(child_prefix, item))
        return lines
    rendered = "" if value is None else str(value)
    return [f"{prefix}={rendered}"]


def determine_output_mode(args: argparse.Namespace) -> str:
    if getattr(args, "plain", False):
        return "plain"
    return "json"


def emit_success(args: argparse.Namespace, command: str, data: dict[str, Any], *, start_time: float, request_id: str) -> int:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "ok",
        "data": data,
        "error": None,
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.time() - start_time) * 1000),
            "timestamp_utc": now_iso_utc(),
        },
    }
    if determine_output_mode(args) == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True))
    else:
        print("\n".join(flatten_plain("data", data)))
    return 0


def emit_error(args: argparse.Namespace, command: str, error: CliError, *, start_time: float, request_id: str) -> int:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": "error",
        "data": {},
        "error": {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
            "hint": error.hint,
            "details": error.details,
        },
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.time() - start_time) * 1000),
            "timestamp_utc": now_iso_utc(),
        },
    }
    if determine_output_mode(args) == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True), file=sys.stderr)
    else:
        print(f"error.code={error.code}\nerror.message={str(error)}", file=sys.stderr)
        if error.hint:
            print(f"error.hint={error.hint}", file=sys.stderr)
    return error.exit_code


def load_post_text(args: argparse.Namespace) -> str:
    if args.text and args.text_file:
        raise CliError("Use either --text or --text-file, not both.", code="E_INVALID_INPUT", exit_code=2)
    if args.text:
        return args.text.strip()
    if args.text_file:
        return Path(args.text_file).expanduser().read_text().strip()
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            return stdin_text
    raise CliError(
        "Provide post text via --text, --text-file, or stdin.",
        code="E_INVALID_INPUT",
        exit_code=2,
        hint="Pass --text-file /abs/path/body.txt for repeatable posting.",
    )


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    data: dict[str, Any] = {
        "files": {
            "env_file": str(config.env_path),
            "env_file_exists": config.env_path.exists(),
        },
        "auth": {
            "has_api_key": bool(config.api_key),
            "has_api_secret": bool(config.api_secret),
            "has_access_token": bool(config.access_token),
            "has_access_token_secret": bool(config.access_token_secret),
        },
        "identity": None,
        "capabilities": {
            "supported_commands": ["status", "post"],
            "json_default": True,
            "plain_available": True,
            "can_post": False,
            "can_probe_identity": False,
        },
        "notes": [],
    }
    if not config.env_path.exists():
        data["notes"].append("X env file is missing. Add OAuth 1.0a user-context credentials first.")
        return data
    try:
        require_config(config)
    except CliError as exc:
        data["notes"].append(f"Credential check failed: {exc.code} {exc}")
        if exc.hint:
            data["notes"].append(exc.hint)
        return data
    data["capabilities"]["can_post"] = True
    data["capabilities"]["can_probe_identity"] = True
    if args.no_probe_identity:
        data["notes"].append("Identity probe skipped.")
        return data
    try:
        user = x_json_request(
            config,
            "GET",
            "/2/users/me",
            query_params={"user.fields": DEFAULT_USER_FIELDS},
        )
        user_data = user.get("data") or {}
        data["identity"] = {
            "id": user_data.get("id"),
            "name": user_data.get("name"),
            "username": user_data.get("username"),
            "verified": user_data.get("verified"),
        }
    except CliError as exc:
        data["notes"].append(f"Identity probe failed: {exc.code} {exc}")
        if exc.hint:
            data["notes"].append(exc.hint)
    return data


def command_post(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    require_config(config)
    payload = {"text": load_post_text(args)}
    if args.dry_run:
        return {"dry_run": True, "payload": payload}
    response = x_json_request(config, "POST", "/2/tweets", json_body=payload)
    return {
        "dry_run": False,
        "tweet": response.get("data") or {},
        "raw": response,
    }


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local X app credentials env file.")
    common.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS, help="HTTP request timeout in seconds.")
    mode = common.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON output. This is also the default.")
    mode.add_argument("--plain", action="store_true", help="Emit stable plain text for shell pipelines or quick operator inspection.")
    common.add_argument("--no-input", action="store_true", help="Disable any future interactive behavior.")

    parser = argparse.ArgumentParser(description="X/Twitter posting helper.", parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Inspect X auth/runtime state for this machine and app.", parents=[common])
    status.add_argument("--no-probe-identity", action="store_true", help="Skip the live /2/users/me identity probe.")
    status.set_defaults(func=command_status, command_path="x status")

    post = subparsers.add_parser("post", help="Publish a text post to X.", parents=[common])
    post.add_argument("--text", help="Inline post text.")
    post.add_argument("--text-file", help="Path to a file containing post text.")
    post.add_argument("--dry-run", action="store_true", help="Print the request payload without publishing.")
    post.set_defaults(func=command_post, command_path="x post")

    return parser


def main() -> int:
    start_time = time.time()
    request_id = secrets.token_hex(8)
    parser = build_parser()
    args = parser.parse_args()
    command = getattr(args, "command_path", f"x {args.command}")
    try:
        data = args.func(args)
        return emit_success(args, command, data, start_time=start_time, request_id=request_id)
    except CliError as exc:
        return emit_error(args, command, exc, start_time=start_time, request_id=request_id)


if __name__ == "__main__":
    raise SystemExit(main())
