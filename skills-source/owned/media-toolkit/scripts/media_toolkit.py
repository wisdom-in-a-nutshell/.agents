#!/usr/bin/env python3
"""
Machine-primary media toolkit for WIN media endpoints.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from media_toolkit_lib.errors import CliArgumentParser, CliError, ParserExit
from media_toolkit_lib.io import (
    upload_local_file,
    write_json_file,
)

DEFAULT_API_BASE_URL = (
    "https://aipodcasting-hzbxdueeg4eeatgh.eastus-01.azurewebsites.net"
)
SCHEMA_VERSION = "1.0"
COMMAND_NAME = "media-toolkit"
LOGGER = logging.getLogger("media_toolkit")


def build_parser() -> CliArgumentParser:
    """Build the CLI parser."""

    parser = CliArgumentParser(
        prog=COMMAND_NAME,
        description=(
            "Run WIN media tools from a local file or URL. "
            "Use this for upload, transcription, transform, matting, and job inspection. "
            "Results are returned as JSON by default."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit upload --file $HOME/media/video.mp4 --output /tmp/upload.json\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3 --output /tmp/transcribe.json\n"
            "  media-toolkit transform --url https://example.com/video.mp4 "
            "--scale-width 1280 --scale-height 720 --output /tmp/transform.json\n"
            "  media-toolkit matte --file $HOME/media/video.mp4 --output /tmp/matte.json\n"
            "  media-toolkit status --job-id VIDEO_TRANSFORM_123 --wait"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    _build_upload_parser(subparsers)
    _build_transcribe_parser(subparsers)
    _build_transform_parser(subparsers)
    _build_matte_parser(subparsers)
    _build_status_parser(subparsers)
    return parser


def _build_upload_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "upload",
        help="Upload a local media file through the shared local uploader and return the uploaded URL.",
        description=(
            "Upload a local media file through the shared local uploader and return "
            "the upload metadata as a JSON envelope."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit upload --file $HOME/media/video.mp4\n"
            "  media-toolkit upload --file $HOME/media/audio.mp3 --output /tmp/upload.json\n"
            "  media-toolkit upload --file $HOME/media/video.mp4 --storage-prefix share"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    parser.add_argument(
        "--file",
        required=True,
        help="Local media file to upload.",
    )
    parser.add_argument(
        "--storage-prefix",
        default="share",
        help="Top-level storage prefix for the uploaded object.",
    )
    parser.add_argument(
        "--destination-prefix",
        default="agent-media-toolkit",
        help="Object path prefix under the storage prefix.",
    )


def _build_transcribe_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "transcribe",
        help="Submit a transcription job and return the completed transcript by default.",
        description=(
            "Submit a transcription job from a local file or URL. "
            "The command waits by default and returns the final JSON result envelope. "
            "Use --output to write that JSON envelope to disk."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3\n"
            "  media-toolkit transcribe --url https://example.com/audio.mp3 --output /tmp/transcribe.json\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3 --no-wait"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    _add_api_runtime_arguments(parser)
    _add_input_arguments(parser)
    _add_submission_arguments(parser)
    parser.add_argument(
        "--provider",
        default="auto",
        help="Transcription provider override.",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Enable speaker diarization.",
    )


def _build_transform_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "transform",
        help="Submit a transform job and return the completed transform result by default.",
        description=(
            "Submit a transform job from a local file or URL. "
            "The command waits by default and returns the final JSON result envelope. "
            "Use --output to write that JSON envelope to disk."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit transform --file $HOME/media/video.mp4 --scale-width 1280 --scale-height 720\n"
            "  media-toolkit transform --url https://example.com/video.mp4 --trim-start-seconds 5 --trim-end-seconds 30 --output /tmp/transform.json\n"
            "  media-toolkit transform --file $HOME/media/video.mp4 --no-wait"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    _add_api_runtime_arguments(parser)
    _add_input_arguments(parser)
    _add_submission_arguments(parser)
    parser.add_argument("--trim-start-seconds", type=float)
    parser.add_argument("--trim-end-seconds", type=float)
    parser.add_argument("--scale-width", type=int)
    parser.add_argument("--scale-height", type=int)
    parser.add_argument("--crop-width", type=int)
    parser.add_argument("--crop-height", type=int)
    parser.add_argument("--crop-x", type=int)
    parser.add_argument("--crop-y", type=int)
    parser.add_argument(
        "--trim-profile",
        default="standardized",
        choices=["standardized", "preserve_fps", "fast_copy", "fast_seek"],
        help="Trim behavior profile.",
    )
    parser.add_argument(
        "--storage-prefix",
        default="cache",
        help="Storage prefix for transform artifacts.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Maximum transform retry attempts.",
    )


def _build_matte_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "matte",
        help="Submit a foreground matting job and return the completed manifest by default.",
        description=(
            "Submit a foreground matting job from a local file or URL. "
            "The command waits by default and returns the final JSON result envelope. "
            "Use --output to write that JSON envelope or matte manifest to disk."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit matte --file $HOME/media/video.mp4\n"
            "  media-toolkit matte --url https://example.com/video.mp4 --output /tmp/matte.json\n"
            "  media-toolkit matte --file $HOME/media/video.mp4 --no-wait"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    _add_api_runtime_arguments(parser)
    _add_input_arguments(parser)
    _add_submission_arguments(parser)
    parser.add_argument(
        "--prompt",
        default="person",
        help="Matting prompt used for first-frame mask generation.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional duration cap for the matting run.",
    )
    parser.add_argument(
        "--storage-prefix",
        default="cache",
        help="Storage prefix for matting artifacts.",
    )


def _build_status_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "status",
        help="Inspect an existing media job.",
        description=(
            "Inspect an existing job by job_id. "
            "Use --wait to poll until the job reaches a terminal state. "
            "Use --output to write the fetched JSON envelope to disk."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit status --job-id VIDEO_TRANSFORM_123\n"
            "  media-toolkit status --job-id VIDEO_TRANSFORM_123 --wait --output /tmp/status.json"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    _add_api_runtime_arguments(parser)
    parser.add_argument(
        "--job-id",
        required=True,
        help="WIN job identifier to inspect.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until the job reaches a terminal state.",
    )


def _add_common_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        dest="output_mode",
        action="store_const",
        const="json",
        help="Emit machine-readable JSON output (default).",
    )
    output_group.add_argument(
        "--plain",
        dest="output_mode",
        action="store_const",
        const="plain",
        help="Emit concise plain-text output for inspection.",
    )
    parser.set_defaults(output_mode="json")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional file path for the final JSON result envelope.",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Disable prompts. This client is non-interactive regardless.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Emit debug diagnostics to stderr.",
    )


def _add_api_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("WIN_MEDIA_API_BASE_URL")
        or os.getenv("WIN_API_BASE_URL")
        or DEFAULT_API_BASE_URL,
        help="Base URL for the WIN API.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=60.0,
        help="Per-request HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--poll-timeout-seconds",
        type=float,
        default=3600.0,
        help="Maximum time to wait for a job before failing.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=5.0,
        help="Polling interval while waiting for a job.",
    )


def _add_submission_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--channel-name",
        default="MISC",
        help="Channel name used when ingesting a URL.",
    )
    parser.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        default=True,
        help="Use cached ingest or processing data when available.",
    )
    parser.add_argument(
        "--no-use-cache",
        dest="use_cache",
        action="store_false",
        help="Bypass cached ingest or processing data.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit the job and return immediately without polling.",
    )


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file",
        help="Local media file to upload before job submission.",
    )
    group.add_argument(
        "--url",
        help="Remote media URL to ingest before job submission.",
    )


def run(argv: list[str]) -> tuple[int, str]:
    """Run the client and return exit code plus output text."""

    parser = build_parser()
    started_at = time.monotonic()
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    request_id = uuid.uuid4().hex

    try:
        args = parser.parse_args(argv)
        _configure_logging(debug=args.debug)
        api_client = None
        if args.subcommand != "upload":
            from media_toolkit_lib.api import MediaToolkitApiClient

            api_client = MediaToolkitApiClient(
                api_base_url=args.api_base_url,
                request_timeout_seconds=args.request_timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
                poll_timeout_seconds=args.poll_timeout_seconds,
            )
        data = _execute_command(api_client, args)
        envelope = _build_envelope(
            command=f"{COMMAND_NAME} {args.subcommand}",
            status="ok",
            data=data,
            error=None,
            request_id=request_id,
            started_at=started_at,
            timestamp_utc=timestamp_utc,
        )
        _write_side_effect_outputs(envelope, args)
        output = _format_output(args.output_mode, envelope)
        return 0, output
    except ParserExit as exc:
        return exc.exit_code, exc.output
    except CliError as exc:
        envelope = _build_envelope(
            command=f"{COMMAND_NAME} {_safe_subcommand(argv)}",
            status="error",
            data=None,
            error={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "hint": exc.hint,
                "detail": exc.detail,
            },
            request_id=request_id,
            started_at=started_at,
            timestamp_utc=timestamp_utc,
        )
        output = _format_output(_safe_output_mode(argv), envelope)
        return exc.exit_code, output
    except KeyboardInterrupt:
        envelope = _build_envelope(
            command=f"{COMMAND_NAME} {_safe_subcommand(argv)}",
            status="error",
            data=None,
            error={
                "code": "E_TIMEOUT",
                "message": "Command interrupted.",
                "retryable": True,
                "hint": "Retry the command when ready.",
                "detail": None,
            },
            request_id=request_id,
            started_at=started_at,
            timestamp_utc=timestamp_utc,
        )
        output = _format_output(_safe_output_mode(argv), envelope)
        return 5, output


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint."""

    exit_code, output = run(argv or sys.argv[1:])
    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return exit_code


def _execute_command(
    api_client: MediaToolkitApiClient | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.subcommand == "upload":
        upload = upload_local_file(
            args.file,
            storage_prefix=args.storage_prefix,
            destination_prefix=args.destination_prefix,
        )
        return {
            "upload": upload,
            "input": {
                "file_path": upload["file_path"],
                "used_upload": True,
            },
            "result": None,
        }

    if api_client is None:
        raise CliError(
            code="E_API",
            message=f"API client missing for subcommand: {args.subcommand}",
            exit_code=1,
            retryable=False,
            hint="Retry the command or inspect the toolkit configuration.",
        )

    if args.subcommand == "status":
        job_doc = (
            api_client.wait_for_job(args.job_id)
            if args.wait
            else api_client.get_job(args.job_id)
        )
        return {
            "job": job_doc,
            "input": None,
            "result": job_doc.get("result"),
        }

    endpoint, payload, input_meta = _build_command_payload(args)
    submission = api_client.submit_job(endpoint, payload)

    result_payload: dict[str, Any] | None = None
    final_job_status = "submitted"
    if not args.no_wait:
        job_doc = api_client.wait_for_job(submission["job_id"])
        final_job_status = str(job_doc.get("status", "completed"))
        result_payload = job_doc.get("result")

    return {
        "job": {
            "job_id": submission["job_id"],
            "cached": bool(submission.get("cached", False)),
            "status": final_job_status,
            "endpoint": endpoint,
        },
        "input": input_meta,
        "result": result_payload,
    }


def _build_command_payload(
    args: argparse.Namespace,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    input_payload, input_meta = _resolve_input_payload(args)
    payload: dict[str, Any] = {
        **input_payload,
        "channel_name": args.channel_name,
        "use_cache": args.use_cache,
    }

    if args.subcommand == "transcribe":
        payload.update(
            {
                "provider": args.provider,
                "diarize": bool(args.diarize),
            }
        )
        return "/media/transcribe", payload, input_meta

    if args.subcommand == "transform":
        payload.update(
            {
                "trim_start_seconds": args.trim_start_seconds,
                "trim_end_seconds": args.trim_end_seconds,
                "scale_width": args.scale_width,
                "scale_height": args.scale_height,
                "crop_width": args.crop_width,
                "crop_height": args.crop_height,
                "crop_x": args.crop_x,
                "crop_y": args.crop_y,
                "trim_profile": args.trim_profile,
                "storage_prefix": args.storage_prefix,
                "max_retries": args.max_retries,
            }
        )
        return "/media/transform", _drop_none_values(payload), input_meta

    if args.subcommand == "matte":
        payload.update(
            {
                "prompt": args.prompt,
                "max_seconds": args.max_seconds,
                "storage_prefix": args.storage_prefix,
            }
        )
        return "/media/matte", _drop_none_values(payload), input_meta

    raise CliError(
        code="E_VALIDATION",
        message=f"Unsupported subcommand: {args.subcommand}",
        exit_code=2,
        retryable=False,
        hint="Choose one of: transcribe, transform, matte, status.",
    )


def _resolve_input_payload(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.url:
        return {"media_url": args.url}, {"media_url": args.url, "used_upload": False}

    if args.file:
        upload = upload_local_file(args.file)
        return (
            {"media_url": upload["url"]},
            {
                "file_path": upload["file_path"],
                "uploaded_url": upload["url"],
                "storage_prefix": upload["storage_prefix"],
                "destination_path": upload["destination_path"],
                "content_sha256": upload.get("content_sha256"),
                "cached": bool(upload.get("cached", False)),
                "used_upload": True,
            },
        )

    raise CliError(
        code="E_VALIDATION",
        message="One of --file or --url is required.",
        exit_code=2,
        retryable=False,
        hint="Pass exactly one input locator flag for the selected subcommand.",
    )


def _write_side_effect_outputs(
    envelope: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    if getattr(args, "output", None):
        output_path = str(Path(args.output).expanduser().resolve())
        envelope["meta"]["output_path"] = output_path
        write_json_file(args.output, envelope)


def _build_envelope(
    *,
    command: str,
    status: str,
    data: dict[str, Any] | None,
    error: dict[str, Any] | None,
    request_id: str,
    started_at: float,
    timestamp_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "data": data,
        "error": error,
        "meta": {
            "request_id": request_id,
            "duration_ms": int((time.monotonic() - started_at) * 1000),
            "timestamp_utc": timestamp_utc,
        },
    }


def _format_output(output_mode: str, payload: dict[str, Any]) -> str:
    if output_mode == "plain":
        return _format_plain(payload)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _format_plain(payload: dict[str, Any]) -> str:
    lines = [
        f"status={payload['status']}",
        f"command={payload['command']}",
    ]
    data = payload.get("data") or {}
    job = data.get("job") or {}
    if job:
        lines.append(f"job_id={job.get('job_id')}")
        lines.append(f"job_status={job.get('status')}")
    meta = payload.get("meta") or {}
    if meta.get("output_path"):
        lines.append(f"output_path={meta['output_path']}")
    error = payload.get("error")
    if error:
        lines.append(f"error_code={error.get('code')}")
        lines.append(f"message={error.get('message')}")
    return "\n".join(lines) + "\n"


def _safe_output_mode(argv: list[str]) -> str:
    return "plain" if "--plain" in argv else "json"


def _safe_subcommand(argv: list[str]) -> str:
    for item in argv:
        if item in {"transcribe", "transform", "matte", "status"}:
            return item
    return "unknown"


def _drop_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _configure_logging(*, debug: bool) -> None:
    if not debug:
        return
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    LOGGER.debug("Debug logging enabled.")


if __name__ == "__main__":
    raise SystemExit(main())
