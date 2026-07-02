#!/usr/bin/env python3
"""Report Codex reset credit expirations without exposing auth secrets."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ENDPOINT = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check available Codex reset credits and expiration times."
    )
    parser.add_argument(
        "--auth-path",
        default="~/.codex/auth.json",
        help="Path to Codex auth JSON. Defaults to ~/.codex/auth.json.",
    )
    parser.add_argument(
        "--timezone",
        help="IANA timezone for local display, for example America/Los_Angeles.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit redacted JSON with parsed expiration fields.",
    )
    return parser.parse_args()


def load_auth(auth_path: Path) -> tuple[str, str]:
    if not auth_path.exists():
        raise RuntimeError(f"missing auth file: {auth_path}")

    try:
        auth = json.loads(auth_path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"auth file is not valid JSON: {auth_path}") from exc

    tokens = auth.get("tokens") or {}
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not access_token or not account_id:
        raise RuntimeError("auth file is missing tokens.access_token or tokens.account_id")

    return access_token, account_id


def fetch_credits(access_token: str, account_id: str) -> dict:
    request = urllib.request.Request(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {access_token}",
            "ChatGPT-Account-ID": account_id,
            "originator": "Codex Desktop",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body[:200] if body else exc.reason
        raise RuntimeError(f"endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach endpoint: {exc.reason}") from exc


def display_timezone(name: str | None) -> dt.tzinfo:
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(f"unknown timezone: {name}") from exc
    return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def redact_and_enrich(data: dict, timezone: dt.tzinfo) -> dict:
    enriched_credits = []
    for credit in data.get("credits") or []:
        expires_at = credit.get("expires_at")
        granted_at = credit.get("granted_at")
        item = {
            "title": credit.get("title"),
            "status": credit.get("status"),
            "reset_type": credit.get("reset_type"),
            "expires_at_utc": expires_at,
            "expires_at_local": None,
            "granted_at_utc": granted_at,
        }
        if expires_at:
            item["expires_at_local"] = parse_timestamp(expires_at).astimezone(timezone).isoformat()
        enriched_credits.append(item)

    return {
        "available_count": data.get("available_count"),
        "total_earned_count": data.get("total_earned_count"),
        "timezone": str(timezone),
        "credits": enriched_credits,
    }


def format_dt(value: str, timezone: dt.tzinfo) -> tuple[str, str]:
    timestamp = parse_timestamp(value)
    return (
        timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
        timestamp.astimezone(timezone).strftime("%Y-%m-%d %H:%M:%S %Z"),
    )


def print_human(data: dict, timezone: dt.tzinfo) -> None:
    credits = data.get("credits") or []
    available = data.get("available_count", len(credits))
    print(f"Available Codex reset credits: {available}")
    print(f"Display timezone: {timezone}")

    if not credits:
        print("No reset credits were returned.")
        return

    for index, credit in enumerate(credits, start=1):
        expires_at = credit.get("expires_at")
        if not expires_at:
            local = utc = "unknown"
        else:
            utc, local = format_dt(expires_at, timezone)
        status = credit.get("status", "unknown")
        title = credit.get("title", "Codex reset credit")
        print(f"{index}. {title} | {status} | expires {local} ({utc})")


def main() -> int:
    args = parse_args()
    try:
        access_token, account_id = load_auth(Path(args.auth_path).expanduser())
        timezone = display_timezone(args.timezone)
        data = fetch_credits(access_token, account_id)
        if args.json:
            print(json.dumps(redact_and_enrich(data, timezone), indent=2, sort_keys=True))
        else:
            print_human(data, timezone)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
