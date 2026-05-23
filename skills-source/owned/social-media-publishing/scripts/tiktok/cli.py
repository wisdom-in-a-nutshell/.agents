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
DEFAULT_ENV_PATH = Path.home() / ".secrets/tiktok/env"
PROGRESS_CHOICES = ("auto", "off", "plain")
PRIVACY_CHOICES = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
SOURCE_CHOICES = ("PULL_FROM_URL", "FILE_UPLOAD")
PHOTO_POST_MODE_CHOICES = ("DIRECT_POST", "MEDIA_UPLOAD")


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
    client_key_present: bool
    client_secret_present: bool
    access_token_present: bool
    posting_audit_passed: bool


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
        client_key_present=bool(get("TIKTOK_CLIENT_KEY")),
        client_secret_present=bool(get("TIKTOK_CLIENT_SECRET")),
        access_token_present=bool(get("TIKTOK_ACCESS_TOKEN")),
        posting_audit_passed=(get("TIKTOK_CONTENT_POSTING_AUDIT_PASSED", "").lower() in {"1", "true", "yes"}),
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
            print(result.get("state") or "ok")
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


def resolve_title(args: argparse.Namespace) -> str:
    if getattr(args, "text", None) and getattr(args, "text_file", None):
        raise CliError("Use only one of --text or --text-file.", code="E_INVALID_ARGUMENTS", exit_code=2, hint="Pass inline text or a file path, not both.")
    if getattr(args, "text_file", None):
        return read_text_file(args.text_file, label="text")
    return getattr(args, "text", "") or ""


def require_public_url(value: str | None) -> str:
    if not value:
        raise CliError("Missing --video-url for PULL_FROM_URL posting.", code="E_INVALID_ARGUMENTS", exit_code=2, hint="Pass --video-url with a publicly reachable HTTPS MP4 URL, or use --source FILE_UPLOAD once upload support is implemented.")
    if not value.startswith("https://"):
        raise CliError("TikTok PULL_FROM_URL requires a public HTTPS video URL.", code="E_INVALID_ARGUMENTS", exit_code=2, hint="Stage the video at a public HTTPS URL first.", details={"value_prefix": value[:24]})
    return value


def command_status(args: argparse.Namespace, config: Config, runtime: Runtime) -> tuple[dict[str, Any], int]:
    missing = []
    if not config.client_key_present:
        missing.append("TIKTOK_CLIENT_KEY")
    if not config.client_secret_present:
        missing.append("TIKTOK_CLIENT_SECRET")
    if not config.access_token_present:
        missing.append("TIKTOK_ACCESS_TOKEN")
    data = {
        "env_file": str(config.env_path),
        "configured": not missing,
        "missing": missing,
        "posting_audit_passed": config.posting_audit_passed,
        "capabilities": {
            "dry_run": ["post-video", "post-photos"],
            "live_publish": [],
        },
        "provider_requirements": [
            "TikTok developer app",
            "Login Kit/OAuth user token with Content Posting scopes",
            "Content Posting API access",
            "video.publish for Direct Post or video.upload for Upload/inbox flow",
            "TikTok app audit before public direct posts; unaudited direct posts are private-only",
            "Explicit creator consent/metadata per TikTok UX requirements",
        ],
        "next_action": None if not missing else "Create ~/.secrets/tiktok/env after TikTok developer app/OAuth setup.",
    }
    return build_envelope(command="tiktok status", status="ok", data=data, error=None, runtime=runtime), 0


def command_post_video(args: argparse.Namespace, config: Config, runtime: Runtime) -> tuple[dict[str, Any], int]:
    title = resolve_title(args)
    if len(title) > 2200:
        raise CliError("TikTok caption exceeds 2200 characters.", code="E_INVALID_ARGUMENTS", exit_code=2, hint="Shorten the caption/title.", details={"title_length": len(title)})
    if args.source == "FILE_UPLOAD" and not args.video:
        raise CliError("FILE_UPLOAD needs --video.", code="E_INVALID_ARGUMENTS", exit_code=2, hint="Pass a local --video path or use --source PULL_FROM_URL with --video-url.")
    if args.source == "FILE_UPLOAD" and args.video and not Path(args.video).expanduser().is_file():
        raise CliError("Video file does not exist.", code="E_FILE_NOT_FOUND", exit_code=2, hint="Check --video and try again.", details={"path": args.video})
    source_info: dict[str, Any] = {"source": args.source}
    if args.source == "PULL_FROM_URL":
        source_info["video_url"] = require_public_url(args.video_url)
    else:
        video_path = Path(args.video).expanduser().resolve()
        source_info["video_path"] = str(video_path)
        source_info["video_size"] = video_path.stat().st_size
    provider_payload = {
        "post_info": {
            "title": title,
            "title_length": len(title),
            "privacy_level": args.privacy,
            "disable_duet": args.disable_duet,
            "disable_comment": args.disable_comment,
            "disable_stitch": args.disable_stitch,
            "brand_content_toggle": args.brand_content,
            "brand_organic_toggle": args.brand_organic,
            "is_aigc": args.ai_generated,
        },
        "source_info": source_info,
    }
    data = {
        "requested_route": "dry-run" if args.dry_run else "direct-api",
        "selected_route": "dry-run",
        "routes": [
            {"route": "dry-run", "available": True, "decision": "selected", "reason_code": "DRY_RUN_ONLY_INITIAL_INTEGRATION"},
            {"route": "direct-api", "available": False, "decision": "blocked", "reason_code": "LIVE_PUBLISH_NOT_ENABLED_YET"},
        ],
        "provider_payload": provider_payload,
        "result": {"state": "validated"},
        "next_action": "Wire OAuth/token storage, creator_info/query, publish init, upload/status polling, and audit-aware privacy gating before live TikTok posting.",
    }
    if not args.dry_run:
        raise CliError("TikTok live publishing is not enabled in this first integration pass.", code="E_NOT_IMPLEMENTED", exit_code=1, hint="Re-run with --dry-run. For live posting, complete TikTok developer app/OAuth/audit setup first.", details={"configured": config.access_token_present, "posting_audit_passed": config.posting_audit_passed})
    return build_envelope(command="tiktok post-video", status="ok", data=data, error=None, runtime=runtime), 0


def resolve_description(args: argparse.Namespace) -> str:
    if getattr(args, "description", None) and getattr(args, "description_file", None):
        raise CliError(
            "Use only one of --description or --description-file.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Pass inline description or a file path, not both.",
        )
    if getattr(args, "description_file", None):
        return read_text_file(args.description_file, label="description")
    return getattr(args, "description", "") or ""


def require_public_photo_urls(urls: list[str] | None) -> list[str]:
    if not urls:
        raise CliError(
            "TikTok photo posts need at least one --photo-url.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Pass --photo-url one or more times with publicly reachable HTTPS image URLs.",
        )
    if len(urls) > 35:
        raise CliError(
            "TikTok photo posts support at most 35 photos.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Reduce the number of --photo-url values to 35 or fewer.",
            details={"photo_count": len(urls)},
        )
    return [_require_https_url(url, label="photo") for url in urls]


def _require_https_url(value: str | None, *, label: str) -> str:
    if not value:
        raise CliError(
            f"Missing --{label}-url.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint=f"Pass --{label}-url with a publicly reachable HTTPS URL.",
        )
    if not value.startswith("https://"):
        raise CliError(
            f"TikTok PULL_FROM_URL requires a public HTTPS {label} URL.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Stage the media at a public HTTPS URL first.",
            details={"value_prefix": value[:24]},
        )
    return value


def command_post_photos(args: argparse.Namespace, config: Config, runtime: Runtime) -> tuple[dict[str, Any], int]:
    title = getattr(args, "title", "") or ""
    description = resolve_description(args)
    if len(title) > 90:
        raise CliError(
            "TikTok photo title exceeds 90 characters.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Shorten --title.",
            details={"title_length": len(title)},
        )
    if len(description) > 4000:
        raise CliError(
            "TikTok photo description exceeds 4000 characters.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Shorten the description.",
            details={"description_length": len(description)},
        )
    photo_urls = require_public_photo_urls(args.photo_url)
    if args.cover_index < 0 or args.cover_index >= len(photo_urls):
        raise CliError(
            "--cover-index is outside the photo list.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Use a zero-based cover index within the number of --photo-url values.",
            details={"cover_index": args.cover_index, "photo_count": len(photo_urls)},
        )

    post_info: dict[str, Any] = {
        "title": title,
        "title_length": len(title),
        "description": description,
        "description_length": len(description),
    }
    if args.post_mode == "DIRECT_POST":
        post_info.update(
            {
                "privacy_level": args.privacy,
                "disable_comment": args.disable_comment,
                "auto_add_music": args.auto_add_music,
                "brand_content_toggle": args.brand_content,
                "brand_organic_toggle": args.brand_organic,
            }
        )

    provider_payload = {
        "media_type": "PHOTO",
        "post_mode": args.post_mode,
        "post_info": post_info,
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_images": photo_urls,
            "photo_cover_index": args.cover_index,
        },
    }
    data = {
        "requested_route": "dry-run" if args.dry_run else "direct-api",
        "selected_route": "dry-run",
        "routes": [
            {"route": "dry-run", "available": True, "decision": "selected", "reason_code": "DRY_RUN_ONLY_INITIAL_INTEGRATION"},
            {"route": "direct-api", "available": False, "decision": "blocked", "reason_code": "LIVE_PUBLISH_NOT_ENABLED_YET"},
        ],
        "provider_payload": provider_payload,
        "result": {"state": "validated"},
        "next_action": "Wire OAuth/token storage, creator_info/query, content init, status polling, and audit-aware privacy gating before live TikTok photo posting.",
    }
    if not args.dry_run:
        raise CliError(
            "TikTok live photo publishing is not enabled in this first integration pass.",
            code="E_NOT_IMPLEMENTED",
            exit_code=1,
            hint="Re-run with --dry-run. For live posting, complete TikTok developer app/OAuth/audit setup first.",
            details={"configured": config.access_token_present, "posting_audit_passed": config.posting_audit_passed},
        )
    return build_envelope(command="tiktok post-photos", status="ok", data=data, error=None, runtime=runtime), 0


def add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to TikTok CLI env/config file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output. This is the default.")
    parser.add_argument("--plain", action="store_true", help="Emit stable plain text for quick inspection.")
    parser.add_argument("--no-input", action="store_true", help="Disable interactive behavior. Commands are currently non-interactive.")
    parser.add_argument("--progress", choices=PROGRESS_CHOICES, default="auto", help="Progress mode; progress goes to stderr only.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok publishing helper for social-media-publishing.")
    add_global_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Inspect TikTok integration config and capabilities.")

    post_video = subparsers.add_parser("post-video", help="Validate/publish a TikTok video post.")
    post_video.add_argument("--text", help="Inline caption/title text.")
    post_video.add_argument("--text-file", help="UTF-8 caption/title text file.")
    post_video.add_argument("--video", help="Local video file for FILE_UPLOAD route.")
    post_video.add_argument("--video-url", help="Public HTTPS video URL for PULL_FROM_URL route.")
    post_video.add_argument("--source", choices=SOURCE_CHOICES, default="PULL_FROM_URL", help="TikTok media transfer route.")
    post_video.add_argument("--privacy", choices=PRIVACY_CHOICES, default="SELF_ONLY", help="TikTok privacy level; SELF_ONLY is safest for first tests.")
    post_video.add_argument("--disable-duet", action="store_true")
    post_video.add_argument("--disable-comment", action="store_true")
    post_video.add_argument("--disable-stitch", action="store_true")
    post_video.add_argument("--brand-content", action="store_true", help="Paid partnership/branded content disclosure.")
    post_video.add_argument("--brand-organic", action="store_true", help="Promoting own brand/business disclosure.")
    post_video.add_argument("--ai-generated", action="store_true", help="Mark as AI-generated content when applicable.")
    post_video.add_argument("--dry-run", action="store_true", help="Validate request without posting.")

    post_photos = subparsers.add_parser("post-photos", help="Validate/publish a TikTok photo-mode post from public URLs.")
    post_photos.add_argument("--title", default="", help="Photo post title, max 90 characters.")
    post_photos.add_argument("--description", help="Inline photo post description, max 4000 characters.")
    post_photos.add_argument("--description-file", help="UTF-8 photo post description file.")
    post_photos.add_argument("--photo-url", action="append", help="Public HTTPS photo URL; pass one or more times, max 35.")
    post_photos.add_argument("--cover-index", type=int, default=0, help="Zero-based index of the cover photo.")
    post_photos.add_argument("--post-mode", choices=PHOTO_POST_MODE_CHOICES, default="DIRECT_POST", help="DIRECT_POST or MEDIA_UPLOAD.")
    post_photos.add_argument("--privacy", choices=PRIVACY_CHOICES, default="SELF_ONLY", help="Privacy level for DIRECT_POST.")
    post_photos.add_argument("--disable-comment", action="store_true")
    post_photos.add_argument("--auto-add-music", action="store_true")
    post_photos.add_argument("--brand-content", action="store_true", help="Paid partnership/branded content disclosure.")
    post_photos.add_argument("--brand-organic", action="store_true", help="Promoting own brand/business disclosure.")
    post_photos.add_argument("--dry-run", action="store_true", help="Validate request without posting.")
    return parser


def run(argv: list[str] | None = None) -> int:
    runtime = Runtime(request_id=f"tt_{uuid.uuid4().hex[:12]}", started_at=time.monotonic())
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)
    command = f"tiktok {args.command}"
    try:
        if args.command == "status":
            payload, exit_code = command_status(args, config, runtime)
        elif args.command == "post-video":
            payload, exit_code = command_post_video(args, config, runtime)
        elif args.command == "post-photos":
            payload, exit_code = command_post_photos(args, config, runtime)
        else:  # pragma: no cover
            raise CliError(f"Unknown command: {args.command}", code="E_USAGE", exit_code=2)
    except CliError as exc:
        payload = build_envelope(command=command, status="error", data={}, error={"code": exc.code, "message": str(exc), "retryable": exc.retryable, "hint": exc.hint, "details": exc.details}, runtime=runtime)
        emit(payload, args)
        return exc.exit_code
    except KeyboardInterrupt:
        payload = build_envelope(command=command, status="error", data={}, error={"code": "E_INTERRUPTED", "message": "Interrupted by user.", "retryable": True, "hint": "Re-run when ready.", "details": None}, runtime=runtime)
        emit(payload, args)
        return 5
    emit(payload, args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
