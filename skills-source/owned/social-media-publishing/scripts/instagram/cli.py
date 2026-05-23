#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_ENV_PATH = Path.home() / ".secrets/instagram/env"
DEFAULT_GRAPH_VERSION = "v23.0"
PROGRESS_CHOICES = ("auto", "off", "plain")
SUPPORTED_LIVE_ROUTES = ("dry-run",)


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
    env_path: Path
    access_token_present: bool
    ig_user_id_present: bool
    graph_version: str


@dataclass
class Runtime:
    request_id: str
    started_at: float


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

    def get(name: str, default: str = "") -> str:
        return os.environ.get(name) or env_values.get(name) or default

    return Config(
        env_path=env_path,
        access_token_present=bool(get("INSTAGRAM_ACCESS_TOKEN") or get("META_ACCESS_TOKEN")),
        ig_user_id_present=bool(get("INSTAGRAM_IG_USER_ID") or get("IG_USER_ID")),
        graph_version=get("META_GRAPH_VERSION", DEFAULT_GRAPH_VERSION),
    )


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_envelope(
    *,
    command: str,
    status: str,
    data: dict[str, Any] | None,
    error: dict[str, Any] | None,
    runtime: Runtime,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data or {},
        "error": error,
        "meta": {
            "request_id": runtime.request_id,
            "duration_ms": int((time.monotonic() - runtime.started_at) * 1000),
            "timestamp_utc": utc_now_iso(),
        },
    }


def emit(payload: dict[str, Any], args: argparse.Namespace) -> None:
    if getattr(args, "plain", False):
        if payload["status"] == "ok":
            result = (payload.get("data") or {}).get("result") or {}
            state = result.get("state") or "ok"
            print(state)
        else:
            error = payload.get("error") or {}
            print(f"error: {error.get('code')}: {error.get('message')}")
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def read_text_file(path_value: str, *, label: str) -> str:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise CliError(
            f"{label} file does not exist: {path}",
            code="E_FILE_NOT_FOUND",
            exit_code=2,
            hint=f"Check --{label.lower().replace(' ', '-')} and try again.",
            details={"path": str(path)},
        )
    return path.read_text(encoding="utf-8")


def resolve_caption(args: argparse.Namespace) -> str:
    if getattr(args, "text", None) and getattr(args, "text_file", None):
        raise CliError(
            "Use only one of --text or --text-file.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Pass inline text or a file path, not both.",
        )
    if getattr(args, "text_file", None):
        return read_text_file(args.text_file, label="text")
    return getattr(args, "text", "") or ""


def require_public_url(value: str | None, *, label: str) -> str:
    if not value:
        raise CliError(
            f"Missing required {label} URL.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint=f"Pass --{label}-url with a publicly reachable HTTPS URL.",
        )
    if not value.startswith("https://"):
        raise CliError(
            f"Instagram publishing requires a public HTTPS {label} URL.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Upload/stage the media to a public HTTPS URL first, or use --dry-run while preparing the asset.",
            details={"value_prefix": value[:24]},
        )
    return value


def command_status(args: argparse.Namespace, config: Config, runtime: Runtime) -> tuple[dict[str, Any], int]:
    missing = []
    if not config.access_token_present:
        missing.append("INSTAGRAM_ACCESS_TOKEN or META_ACCESS_TOKEN")
    if not config.ig_user_id_present:
        missing.append("INSTAGRAM_IG_USER_ID or IG_USER_ID")
    data = {
        "env_file": str(config.env_path),
        "configured": not missing,
        "missing": missing,
        "graph_version": config.graph_version,
        "capabilities": {
            "dry_run": ["post-image", "post-video", "post-carousel"],
            "live_publish": [],
        },
        "provider_requirements": [
            "Instagram Business or Creator account",
            "Meta developer app",
            "Instagram publishing permissions such as instagram_business_basic and instagram_business_content_publish",
            "Long-lived access token stored outside repo",
            "Instagram user id for the professional account",
            "Public HTTPS media URLs for provider-side fetch",
        ],
        "next_action": None if not missing else "Create ~/.secrets/instagram/env with account ids/tokens after Meta app setup.",
    }
    return build_envelope(command="instagram status", status="ok", data=data, error=None, runtime=runtime), 0


def build_post_payload(args: argparse.Namespace, *, kind: str) -> dict[str, Any]:
    caption = resolve_caption(args)
    payload: dict[str, Any] = {
        "kind": kind,
        "caption": caption,
        "caption_length": len(caption),
    }
    if kind == "image":
        payload["image_url"] = require_public_url(args.image_url, label="image")
        payload["provider_media_type"] = "IMAGE"
    elif kind == "video":
        payload["video_url"] = require_public_url(args.video_url, label="video")
        payload["provider_media_type"] = "REELS" if args.reel else "VIDEO"
        payload["share_to_feed"] = bool(args.share_to_feed)
        payload["cover_url"] = args.cover_url
    elif kind == "carousel":
        urls = args.media_url or []
        if len(urls) < 2:
            raise CliError(
                "Instagram carousel needs at least two --media-url values.",
                code="E_INVALID_ARGUMENTS",
                exit_code=2,
                hint="Pass --media-url multiple times with public HTTPS image/video URLs.",
            )
        payload["media_urls"] = [require_public_url(url, label="media") for url in urls]
        payload["provider_media_type"] = "CAROUSEL"
    return payload


def command_dry_run_post(args: argparse.Namespace, config: Config, runtime: Runtime, *, kind: str, command: str) -> tuple[dict[str, Any], int]:
    provider_payload = build_post_payload(args, kind=kind)
    data = {
        "requested_route": "dry-run" if args.dry_run else "direct-api",
        "selected_route": "dry-run",
        "routes": [
            {
                "route": "dry-run",
                "available": True,
                "decision": "selected",
                "reason_code": "DRY_RUN_ONLY_INITIAL_INTEGRATION",
            },
            {
                "route": "direct-api",
                "available": False,
                "decision": "blocked",
                "reason_code": "LIVE_PUBLISH_NOT_ENABLED_YET",
            },
        ],
        "provider_payload": provider_payload,
        "result": {"state": "validated"},
        "next_action": "Wire Meta OAuth/token storage and provider media container publish flow before live Instagram posting.",
    }
    if not args.dry_run:
        raise CliError(
            "Instagram live publishing is not enabled in this first integration pass.",
            code="E_NOT_IMPLEMENTED",
            exit_code=1,
            hint="Re-run with --dry-run, then add Meta app credentials and implement the direct publish route.",
            details={"command": command, "configured": config.access_token_present and config.ig_user_id_present},
        )
    return build_envelope(command=command, status="ok", data=data, error=None, runtime=runtime), 0


def add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to Instagram CLI env/config file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output. This is the default.")
    parser.add_argument("--plain", action="store_true", help="Emit stable plain text for quick inspection.")
    parser.add_argument("--no-input", action="store_true", help="Disable interactive behavior. Commands are currently non-interactive.")
    parser.add_argument("--progress", choices=PROGRESS_CHOICES, default="auto", help="Progress mode; progress goes to stderr only.")


def add_text_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--text", help="Inline caption text.")
    parser.add_argument("--text-file", help="UTF-8 caption text file.")
    parser.add_argument("--dry-run", action="store_true", help="Validate request without posting.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Instagram publishing helper for social-media-publishing.")
    add_global_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Inspect Instagram integration config and capabilities.")

    post_image = subparsers.add_parser("post-image", help="Validate/publish an Instagram image post from a public URL.")
    add_text_args(post_image)
    post_image.add_argument("--image-url", help="Public HTTPS image URL.")

    post_video = subparsers.add_parser("post-video", help="Validate/publish an Instagram video/Reel from a public URL.")
    add_text_args(post_video)
    post_video.add_argument("--video-url", help="Public HTTPS video URL.")
    post_video.add_argument("--cover-url", help="Optional public HTTPS cover image URL.")
    post_video.add_argument("--reel", action="store_true", help="Treat the video as an Instagram Reel.")
    post_video.add_argument("--share-to-feed", action="store_true", help="Request Reels share-to-feed when supported.")

    post_carousel = subparsers.add_parser("post-carousel", help="Validate/publish an Instagram carousel from public URLs.")
    add_text_args(post_carousel)
    post_carousel.add_argument("--media-url", action="append", help="Public HTTPS media URL; pass multiple times.")

    return parser


def run(argv: list[str] | None = None) -> int:
    runtime = Runtime(request_id=f"ig_{uuid.uuid4().hex[:12]}", started_at=time.monotonic())
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)
    command = f"instagram {args.command}"
    try:
        if args.command == "status":
            payload, exit_code = command_status(args, config, runtime)
        elif args.command == "post-image":
            payload, exit_code = command_dry_run_post(args, config, runtime, kind="image", command=command)
        elif args.command == "post-video":
            payload, exit_code = command_dry_run_post(args, config, runtime, kind="video", command=command)
        elif args.command == "post-carousel":
            payload, exit_code = command_dry_run_post(args, config, runtime, kind="carousel", command=command)
        else:  # pragma: no cover
            raise CliError(f"Unknown command: {args.command}", code="E_USAGE", exit_code=2)
    except CliError as exc:
        payload = build_envelope(
            command=command,
            status="error",
            data={},
            error={"code": exc.code, "message": str(exc), "retryable": exc.retryable, "hint": exc.hint, "details": exc.details},
            runtime=runtime,
        )
        emit(payload, args)
        return exc.exit_code
    except KeyboardInterrupt:
        payload = build_envelope(
            command=command,
            status="error",
            data={},
            error={"code": "E_INTERRUPTED", "message": "Interrupted by user.", "retryable": True, "hint": "Re-run when ready.", "details": None},
            runtime=runtime,
        )
        emit(payload, args)
        return 5
    emit(payload, args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
