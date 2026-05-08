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
DEFAULT_ENV_PATH = Path.home() / ".secrets/youtube/env"
DEFAULT_MODAL_PYTHON = Path("/Users/dobby/GitHub/modal_functions/venv/bin/python")
DEFAULT_MODAL_APP = "aip-processor"
DEFAULT_MODAL_FUNCTION = "upload_youtube_video"
DEFAULT_MODAL_VOLUME = "cache"
DEFAULT_STAGING_PREFIX = "youtube-staging"
DEFAULT_PRIVACY = "private"
PRIVACY_CHOICES = ("private", "unlisted", "public")
ROUTE_CHOICES = ("auto", "modal", "dry-run")
PROGRESS_CHOICES = ("auto", "off", "plain")
REEXEC_ENV = "SOCIAL_YOUTUBE_REEXECED"


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
    modal_python: Path
    modal_app: str
    modal_function: str
    modal_volume: str
    default_credentials_id: str | None


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

    def get_value(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name) or env_values.get(name) or default

    return Config(
        env_path=env_path,
        modal_python=Path(
            get_value("SOCIAL_YOUTUBE_MODAL_PYTHON", str(DEFAULT_MODAL_PYTHON))
            or str(DEFAULT_MODAL_PYTHON)
        ).expanduser(),
        modal_app=get_value("SOCIAL_YOUTUBE_MODAL_APP", DEFAULT_MODAL_APP)
        or DEFAULT_MODAL_APP,
        modal_function=get_value(
            "SOCIAL_YOUTUBE_MODAL_FUNCTION", DEFAULT_MODAL_FUNCTION
        )
        or DEFAULT_MODAL_FUNCTION,
        modal_volume=get_value("SOCIAL_YOUTUBE_MODAL_VOLUME", DEFAULT_MODAL_VOLUME)
        or DEFAULT_MODAL_VOLUME,
        default_credentials_id=get_value("YOUTUBE_DEFAULT_CREDENTIALS_ID"),
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
        "data": data if data is not None else {},
        "error": error,
        "meta": {
            "request_id": runtime.request_id,
            "duration_ms": int((time.monotonic() - runtime.started_at) * 1000),
            "timestamp_utc": utc_now_iso(),
        },
    }


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_plain(payload: dict[str, Any]) -> None:
    if payload["status"] == "ok":
        data = payload.get("data") or {}
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict) and result.get("video_url"):
            print(result["video_url"])
        else:
            print(payload["status"])
        return
    err = payload.get("error") or {}
    print(f"error: {err.get('code', 'E_GENERIC')}: {err.get('message', '')}")


def emit_result(payload: dict[str, Any], args: argparse.Namespace) -> None:
    if getattr(args, "plain", False):
        emit_plain(payload)
    else:
        emit_json(payload)


def progress(args: argparse.Namespace, message: str) -> None:
    mode = getattr(args, "progress", "auto")
    if mode == "off":
        return
    print(f"[youtube] {message}", file=sys.stderr, flush=True)


def require_file(path_value: str, *, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise CliError(
            f"{label} file does not exist: {path}",
            code="E_FILE_NOT_FOUND",
            exit_code=2,
            retryable=False,
            hint=f"Check the --{label.lower()} path and try again.",
            details={"path": str(path)},
        )
    return path.resolve()


def read_text_file(path_value: str, *, label: str) -> str:
    path = require_file(path_value, label=label)
    return path.read_text(encoding="utf-8")


def resolve_description(args: argparse.Namespace) -> str:
    if args.description and args.description_file:
        raise CliError(
            "Use only one of --description or --description-file.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Pass inline text with --description or a file with --description-file, not both.",
        )
    if args.description_file:
        return read_text_file(args.description_file, label="description")
    return args.description or ""


def resolve_credentials_id(args: argparse.Namespace, config: Config) -> str:
    credentials_id = args.credentials_id or config.default_credentials_id
    if not credentials_id:
        raise CliError(
            "Missing YouTube credentials id.",
            code="E_MISSING_CREDENTIALS_ID",
            exit_code=2,
            retryable=False,
            hint="Pass --credentials-id ADITHYAN or set YOUTUBE_DEFAULT_CREDENTIALS_ID in ~/.secrets/youtube/env.",
        )
    return credentials_id


def import_modal_module():
    try:
        import modal  # type: ignore
    except (
        Exception
    ) as exc:  # pragma: no cover - exercised through status/reexec behavior
        raise CliError(
            "Python runtime cannot import the Modal SDK.",
            code="E_MODAL_SDK_MISSING",
            exit_code=4,
            retryable=False,
            hint="Run with the modal_functions venv Python or set SOCIAL_YOUTUBE_MODAL_PYTHON.",
            details={"exception_type": type(exc).__name__, "message": str(exc)},
        ) from exc
    return modal


def can_import_modal_here() -> tuple[bool, str | None]:
    try:
        import modal  # noqa: F401  # type: ignore

        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def maybe_reexec_with_modal_python(args: argparse.Namespace, config: Config) -> None:
    available, _ = can_import_modal_here()
    if available:
        return
    if os.environ.get(REEXEC_ENV) == "1":
        return
    if not config.modal_python.is_file():
        return

    env = os.environ.copy()
    env[REEXEC_ENV] = "1"
    progress(args, f"re-running with Modal Python: {config.modal_python}")
    os.execve(
        str(config.modal_python),
        [str(config.modal_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        env,
    )


def modal_response_to_result(raw_response: Any) -> dict[str, Any]:
    if not isinstance(raw_response, dict):
        raise CliError(
            "Modal YouTube uploader returned a non-object response.",
            code="E_MODAL_BAD_RESPONSE",
            exit_code=1,
            retryable=False,
            details={"response_type": type(raw_response).__name__},
        )

    if raw_response.get("status") == "ok":
        data = raw_response.get("data")
        if isinstance(data, dict):
            return data
        raise CliError(
            "Modal YouTube uploader returned an invalid success payload.",
            code="E_MODAL_BAD_RESPONSE",
            exit_code=1,
            retryable=False,
            details={"response": raw_response},
        )

    if raw_response.get("status") == "error":
        err = (
            raw_response.get("data")
            if isinstance(raw_response.get("data"), dict)
            else {}
        )
        code = str(err.get("code") or "E_MODAL_UPLOAD_FAILED")
        message = str(err.get("message") or "Modal YouTube upload failed")
        raise CliError(
            message,
            code=code,
            exit_code=3 if code == "auth" else 5 if code == "timeout" else 1,
            retryable=code in {"timeout", "upload_retry_exhausted"},
            hint="Check YouTube Studio for a possible partial upload before retrying."
            if code in {"timeout", "upload_retry_exhausted"}
            else None,
            details=err.get("details"),
        )

    # Older generated clients may unwrap the Modal envelope and return data directly.
    if raw_response.get("video_id") or raw_response.get("video_url"):
        return raw_response

    raise CliError(
        "Modal YouTube uploader returned an unknown response shape.",
        code="E_MODAL_BAD_RESPONSE",
        exit_code=1,
        retryable=False,
        details={"response": raw_response},
    )


def build_routes(
    *, selected_route: str, using_local_file: bool
) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    modal_reason = (
        "SELECTED_FOR_LOCAL_FILE_STAGING"
        if using_local_file
        else "SELECTED_FOR_PUBLIC_URL"
    )
    routes.append(
        {
            "route": "modal",
            "status": "available",
            "decision": "selected" if selected_route == "modal" else "not_selected",
            "reason_code": modal_reason
            if selected_route == "modal"
            else "LOWER_PRIORITY",
        }
    )
    routes.append(
        {
            "route": "local",
            "status": "unsupported",
            "decision": "not_selected",
            "reason_code": "LOCAL_YOUTUBE_UPLOADER_NOT_IMPLEMENTED",
        }
    )
    return routes


def make_staged_remote_path(
    *, request_id: str, source_path: Path, prefix: str, role: str
) -> str:
    suffix = source_path.suffix or (".jpg" if role == "thumbnail" else ".mp4")
    safe_role = "thumbnail" if role == "thumbnail" else "video"
    return f"/{prefix.strip('/')}/{request_id}/{safe_role}{suffix.lower()}"


def stage_file_to_modal_volume(
    *,
    modal: Any,
    volume_name: str,
    local_path: Path,
    remote_path: str,
    force: bool,
    args: argparse.Namespace,
) -> None:
    progress(
        args, f"staging {local_path.name} to Modal volume {volume_name}:{remote_path}"
    )
    volume = modal.Volume.from_name(volume_name, create_if_missing=False)
    with volume.batch_upload(force=force) as batch:
        batch.put_file(str(local_path), remote_path)


def cleanup_staged_paths(
    *, modal: Any, volume_name: str, paths: list[str], args: argparse.Namespace
) -> None:
    if not paths:
        return
    volume = modal.Volume.from_name(volume_name, create_if_missing=False)
    for path in paths:
        try:
            progress(args, f"removing staged Modal volume file: {path}")
            volume.remove_file(path)
        except Exception as exc:
            progress(args, f"warning: failed to remove staged file {path}: {exc}")


def call_modal_upload(
    *,
    modal: Any,
    config: Config,
    payload: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    progress(args, f"calling Modal function {config.modal_app}.{config.modal_function}")
    function = modal.Function.from_name(config.modal_app, config.modal_function)
    raw_response = function.remote(**payload)
    return modal_response_to_result(raw_response)


def command_status(
    args: argparse.Namespace, config: Config, runtime: Runtime
) -> tuple[dict[str, Any], int]:
    modal_available, modal_error = can_import_modal_here()
    data = {
        "env_path": str(config.env_path),
        "env_file_exists": config.env_path.exists(),
        "modal_python": str(config.modal_python),
        "modal_python_exists": config.modal_python.exists(),
        "modal_sdk_importable": modal_available,
        "modal_sdk_error": modal_error,
        "modal_app": config.modal_app,
        "modal_function": config.modal_function,
        "modal_volume": config.modal_volume,
        "default_credentials_id_configured": bool(config.default_credentials_id),
        "remote_check": "skipped",
    }
    return build_envelope(
        command="youtube status", status="ok", data=data, error=None, runtime=runtime
    ), 0


def command_upload_video(
    args: argparse.Namespace, config: Config, runtime: Runtime
) -> tuple[dict[str, Any], int]:
    if bool(args.video) == bool(args.video_url):
        raise CliError(
            "Provide exactly one of --video or --video-url.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Use --video for a local file or --video-url for a public direct video URL.",
        )
    if args.thumbnail and args.thumbnail_url:
        raise CliError(
            "Provide at most one of --thumbnail or --thumbnail-url.",
            code="E_INVALID_ARGUMENTS",
            exit_code=2,
            hint="Use --thumbnail for a local file or --thumbnail-url for a public direct image URL.",
        )

    credentials_id = resolve_credentials_id(args, config)
    description = resolve_description(args)
    using_local_file = bool(args.video)
    requested_route = "dry_run" if args.route == "dry-run" else args.route
    dry_run = bool(args.dry_run or args.route == "dry-run")
    selected_route = "modal"

    video_path = require_file(args.video, label="video") if args.video else None
    thumbnail_path = (
        require_file(args.thumbnail, label="thumbnail") if args.thumbnail else None
    )

    base_payload: dict[str, Any] = {
        "title": args.title,
        "description": description,
        "video_url": args.video_url,
        "privacy_status": args.privacy,
        "credentials_id": credentials_id,
        "publish_at": args.publish_at,
        "playlist_id": args.playlist_id,
        "thumbnail_url": args.thumbnail_url,
        "made_for_kids": args.made_for_kids,
        "embeddable": not args.no_embeddable,
        "notify_subscribers": not args.no_notify_subscribers,
    }

    staged_paths: list[str] = []
    if video_path:
        base_payload["video_volume_path"] = make_staged_remote_path(
            request_id=runtime.request_id,
            source_path=video_path,
            prefix=args.staging_prefix,
            role="video",
        )
        base_payload["video_url"] = None
        staged_paths.append(base_payload["video_volume_path"])
    if thumbnail_path:
        base_payload["thumbnail_volume_path"] = make_staged_remote_path(
            request_id=runtime.request_id,
            source_path=thumbnail_path,
            prefix=args.staging_prefix,
            role="thumbnail",
        )
        base_payload["thumbnail_url"] = None
        staged_paths.append(base_payload["thumbnail_volume_path"])

    routes = build_routes(
        selected_route=selected_route,
        using_local_file=using_local_file,
    )

    if dry_run:
        data = {
            "requested_route": requested_route,
            "selected_route": selected_route,
            "routes": routes,
            "dry_run": True,
            "artifact": {
                "kind": "youtube_video",
                "source": "local_file" if using_local_file else "public_url",
                "video_path": str(video_path) if video_path else None,
                "video_url": args.video_url,
                "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
                "thumbnail_url": args.thumbnail_url,
            },
            "payload_preview": {
                k: v for k, v in base_payload.items() if k != "description"
            },
            "result": {"state": "validated", "video_url": None, "video_id": None},
            "next_action": "rerun without --dry-run to publish",
        }
        return build_envelope(
            command="youtube upload-video",
            status="ok",
            data=data,
            error=None,
            runtime=runtime,
        ), 0

    maybe_reexec_with_modal_python(args, config)
    modal = import_modal_module()

    if video_path:
        stage_file_to_modal_volume(
            modal=modal,
            volume_name=config.modal_volume,
            local_path=video_path,
            remote_path=base_payload["video_volume_path"],
            force=args.force_stage,
            args=args,
        )
    if thumbnail_path:
        stage_file_to_modal_volume(
            modal=modal,
            volume_name=config.modal_volume,
            local_path=thumbnail_path,
            remote_path=base_payload["thumbnail_volume_path"],
            force=args.force_stage,
            args=args,
        )

    try:
        upload_result = call_modal_upload(
            modal=modal, config=config, payload=base_payload, args=args
        )
    finally:
        if staged_paths and not args.keep_staged:
            cleanup_staged_paths(
                modal=modal,
                volume_name=config.modal_volume,
                paths=staged_paths,
                args=args,
            )

    data = {
        "requested_route": requested_route,
        "selected_route": selected_route,
        "routes": routes,
        "dry_run": False,
        "artifact": {
            "kind": "youtube_video",
            "source": "local_file" if using_local_file else "public_url",
            "video_path": str(video_path) if video_path else None,
            "video_url": args.video_url,
            "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
            "thumbnail_url": args.thumbnail_url,
        },
        "staging": {
            "modal_volume": config.modal_volume,
            "paths": staged_paths,
            "kept": bool(args.keep_staged),
        },
        "result": {
            "state": "uploaded",
            "video_id": upload_result.get("video_id"),
            "video_url": upload_result.get("video_url"),
            "privacy_status": args.privacy,
            "playlist_id": args.playlist_id,
            "attempts": upload_result.get("attempts"),
            "upload_retried": upload_result.get("upload_retried"),
        },
        "provider_response": upload_result.get("response"),
        "next_action": None,
    }
    return build_envelope(
        command="youtube upload-video",
        status="ok",
        data=data,
        error=None,
        runtime=runtime,
    ), 0


def add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Path to non-secret YouTube CLI config env file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output. This is the default.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Emit stable plain text for quick inspection.",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Disable interactive behavior. Currently all commands are non-interactive.",
    )
    parser.add_argument(
        "--progress",
        choices=PROGRESS_CHOICES,
        default="auto",
        help="Progress reporting mode. Progress is written to stderr only.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YouTube publishing helper for the social-media-publishing skill."
    )
    add_global_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "status", help="Inspect YouTube CLI and Modal runtime configuration."
    )

    upload = subparsers.add_parser(
        "upload-video", help="Upload a video to YouTube through Modal."
    )
    upload.add_argument(
        "--video", help="Local video file to stage into Modal volume before upload."
    )
    upload.add_argument(
        "--video-url", help="Public direct video URL for Modal to download and upload."
    )
    upload.add_argument("--title", required=True, help="YouTube video title.")
    upload.add_argument("--description", help="Inline YouTube description text.")
    upload.add_argument(
        "--description-file", help="Path to a UTF-8 text/Markdown description file."
    )
    upload.add_argument(
        "--privacy",
        choices=PRIVACY_CHOICES,
        default=DEFAULT_PRIVACY,
        help="YouTube privacy status. Defaults to private for safety.",
    )
    upload.add_argument(
        "--credentials-id",
        help="YouTube credential id configured in Modal youtube-oauth, e.g. ADITHYAN.",
    )
    upload.add_argument(
        "--publish-at", help="Optional ISO timestamp for scheduled publishing."
    )
    upload.add_argument("--playlist-id", help="Optional YouTube playlist id.")
    upload.add_argument(
        "--thumbnail", help="Local thumbnail image to stage into Modal volume."
    )
    upload.add_argument(
        "--thumbnail-url", help="Public direct thumbnail URL for Modal to download."
    )
    upload.add_argument(
        "--made-for-kids",
        action="store_true",
        help="Set YouTube selfDeclaredMadeForKids=true.",
    )
    upload.add_argument(
        "--no-embeddable", action="store_true", help="Disable embedding."
    )
    upload.add_argument(
        "--no-notify-subscribers",
        action="store_true",
        help="Do not notify subscribers.",
    )
    upload.add_argument(
        "--route",
        choices=ROUTE_CHOICES,
        default="auto",
        help="Delivery route. auto/modal both use Modal; dry-run validates only.",
    )
    upload.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show the selected route without uploading.",
    )
    upload.add_argument(
        "--staging-prefix",
        default=DEFAULT_STAGING_PREFIX,
        help="Modal volume prefix for staged local files.",
    )
    upload.add_argument(
        "--force-stage",
        action="store_true",
        help="Allow overwriting existing staged files if paths collide.",
    )
    upload.add_argument(
        "--keep-staged",
        action="store_true",
        help="Keep staged Modal volume files after successful upload.",
    )

    return parser


def run(argv: list[str] | None = None) -> int:
    runtime = Runtime(
        request_id=f"yt_{uuid.uuid4().hex[:12]}", started_at=time.monotonic()
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)

    try:
        if args.command == "status":
            payload, exit_code = command_status(args, config, runtime)
        elif args.command == "upload-video":
            payload, exit_code = command_upload_video(args, config, runtime)
        else:  # pragma: no cover
            raise CliError(
                f"Unknown command: {args.command}", code="E_USAGE", exit_code=2
            )
    except CliError as exc:
        payload = build_envelope(
            command=f"youtube {getattr(args, 'command', 'unknown')}",
            status="error",
            data={},
            error={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "hint": exc.hint,
                "details": exc.details,
            },
            runtime=runtime,
        )
        emit_result(payload, args)
        return exc.exit_code
    except KeyboardInterrupt:
        payload = build_envelope(
            command=f"youtube {getattr(args, 'command', 'unknown')}",
            status="error",
            data={},
            error={
                "code": "E_INTERRUPTED",
                "message": "Interrupted by user.",
                "retryable": True,
                "hint": "Re-run the command when ready. Check YouTube Studio for partial uploads if interruption happened during provider upload.",
                "details": None,
            },
            runtime=runtime,
        )
        emit_result(payload, args)
        return 5
    except Exception as exc:
        payload = build_envelope(
            command=f"youtube {getattr(args, 'command', 'unknown')}",
            status="error",
            data={},
            error={
                "code": "E_UNEXPECTED",
                "message": str(exc),
                "retryable": False,
                "hint": "Run status, then retry with --progress plain if you need operator logs.",
                "details": {"exception_type": type(exc).__name__},
            },
            runtime=runtime,
        )
        emit_result(payload, args)
        return 1

    emit_result(payload, args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
