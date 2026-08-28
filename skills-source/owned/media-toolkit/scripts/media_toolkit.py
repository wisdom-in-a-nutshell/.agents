#!/usr/bin/env python3
"""
Machine-primary media toolkit for media processing endpoints.
"""

from __future__ import annotations

import argparse
import json
import logging
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
    DEFAULT_INPUT_UPLOAD_PREFIX,
    upload_local_file,
    write_json_file,
)

DEFAULT_API_BASE_URL = (
    "https://api.aipodcast.ing"
)
TRANSCRIPTION_PROVIDER = "local_transcription"
TRANSCRIPTION_UPLOAD_STORAGE_PREFIX = "cache"
TRANSCRIPTION_UPLOAD_DESTINATION_PREFIX = "local-transcription"
SCHEMA_VERSION = "1.0"
COMMAND_NAME = "media-toolkit"
LOGGER = logging.getLogger("media_toolkit")
DEFAULT_PROGRESS_MODE = "auto"


def build_parser() -> CliArgumentParser:
    """Build the CLI parser."""

    parser = CliArgumentParser(
        prog=COMMAND_NAME,
        description=(
            "Run media operations from a local file or URL. "
            "Use this for upload, transcription, segmentation, transform, matting, and job inspection. "
            "Results are returned as JSON by default."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit upload --file $HOME/media/video.mp4 --output /tmp/upload.json\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3 --output /tmp/transcribe.json\n"
            "  media-toolkit segment image --file $HOME/media/image.png --prompt \"black ball\" --output /tmp/segment-image.json\n"
            "  media-toolkit segment video --url https://example.com/video.mp4 --prompt \"black ball\" --anchor-seconds 14 --window-start-seconds 12 --window-end-seconds 64 --output /tmp/segment-video.json\n"
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
    _build_segment_parser(subparsers)
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
        default=DEFAULT_INPUT_UPLOAD_PREFIX,
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
        help="Transcribe local or remote media and return transcript text plus artifacts.",
        description=(
            "Transcribe a local file or URL through the WIN artifact-backed transcription path. "
            "The command waits by default and returns transcript text plus cached artifact URLs. "
            "Use --output to write that JSON envelope to disk."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3\n"
            "  media-toolkit transcribe --url https://example.com/audio.mp3 --output /tmp/transcribe.json\n"
            "  media-toolkit transcribe --url https://www.youtube.com/watch?v=VIDEO_ID --identify-speakers\n"
            "  media-toolkit transcribe --file $HOME/media/audio.mp3 --no-wait"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_runtime_arguments(parser)
    _add_api_runtime_arguments(parser)
    _add_input_arguments(parser)
    parser.add_argument(
        "--channel-name",
        default="MISC",
        help="Channel name used when ingesting a URL.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit the job and return immediately without polling.",
    )
    parser.add_argument(
        "--identify-speakers",
        action="store_true",
        help="Identify diarized speakers as real names before returning transcript artifacts.",
    )
    parser.add_argument(
        "--speaker-identification-context",
        default=None,
        help="Optional extra context for speaker identification.",
    )
    parser.add_argument(
        "--force-speaker-identification",
        action="store_true",
        help="Rerun speaker identification even if mapped speakers already exist.",
    )


def _build_segment_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "segment",
        help="Segment image or video media and return SAM 3.1 mask/alpha artifacts.",
        description=(
            "Run direct SAM 3.1 segmentation on image or video media. "
            "Choose the media kind first, then pass either --file or --url."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit segment image --file $HOME/media/image.png --prompt \"black ball\"\n"
            "  media-toolkit segment video --file $HOME/media/video.mp4 --prompt \"black ball\" --anchor-seconds 14 --window-start-seconds 12 --window-end-seconds 64\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    nested = parser.add_subparsers(dest="segment_kind", required=True)
    _build_segment_image_parser(nested)
    _build_segment_video_parser(nested)


def _build_segment_image_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "image",
        help="Submit an image segmentation job and return the completed segmentation result by default.",
        description=(
            "Submit a SAM 3.1 image segmentation job from a local file or URL. "
            "The command waits by default and returns the final JSON result envelope."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit segment image --file $HOME/media/image.png --prompt \"black ball\"\n"
            "  media-toolkit segment image --url https://example.com/image.png --with-alpha --output /tmp/segment-image.json\n"
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
        help="Segmentation prompt used to identify the target object or region.",
    )
    parser.add_argument(
        "--storage-prefix",
        default="cache",
        help="Storage prefix for segmentation artifacts.",
    )
    parser.add_argument(
        "--with-alpha",
        action="store_true",
        help="Also generate an alpha-matted output artifact. Mask output is always generated.",
    )


def _build_segment_video_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "video",
        help="Submit a video segmentation job and return the completed segmentation result by default.",
        description=(
            "Submit a SAM 3.1 video segmentation job from a local file or URL. "
            "The command waits by default and returns the final JSON result envelope."
        ),
        epilog=(
            "Examples:\n"
            "  media-toolkit segment video --file $HOME/media/video.mp4 --prompt \"black ball\" --anchor-seconds 14 --window-start-seconds 12 --window-end-seconds 64\n"
            "  media-toolkit segment video --url https://example.com/video.mp4 --anchor-frame-index 240 --propagation-direction both --with-alpha --output /tmp/segment-video.json\n"
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
        help="Segmentation prompt used to identify the target object or region.",
    )
    parser.add_argument(
        "--anchor-seconds",
        type=float,
        default=None,
        help="Approximate timestamp where tracking should initialize.",
    )
    parser.add_argument(
        "--anchor-frame-index",
        type=int,
        default=None,
        help="Explicit frame index where tracking should initialize.",
    )
    parser.add_argument(
        "--window-start-seconds",
        type=float,
        default=None,
        help="Optional lower tracking bound in seconds on the original timeline.",
    )
    parser.add_argument(
        "--window-start-frame-index",
        type=int,
        default=None,
        help="Optional lower tracking bound as an explicit frame index.",
    )
    parser.add_argument(
        "--window-end-seconds",
        type=float,
        default=None,
        help="Optional upper tracking bound in seconds on the original timeline.",
    )
    parser.add_argument(
        "--window-end-frame-index",
        type=int,
        default=None,
        help="Optional upper tracking bound as an explicit frame index.",
    )
    parser.add_argument(
        "--propagation-direction",
        default="forward",
        choices=["forward", "backward", "both"],
        help='Propagation direction for the SAM 3.1 video predictor.',
    )
    parser.add_argument(
        "--max-frame-num-to-track",
        type=int,
        default=None,
        help="Optional bound on how many frames to track.",
    )
    parser.add_argument(
        "--storage-prefix",
        default="cache",
        help="Storage prefix for segmentation artifacts.",
    )
    parser.add_argument(
        "--with-alpha",
        action="store_true",
        help="Also generate an alpha-matted output artifact. Mask output is always generated.",
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
        help="Backend job identifier to inspect.",
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
        "--progress",
        default=DEFAULT_PROGRESS_MODE,
        choices=["auto", "off", "plain", "jsonl"],
        help=(
            "Progress mode for long waits. Progress is emitted to stderr only and "
            "never changes the final stdout result."
        ),
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
        _validate_args(args)
        _configure_logging(debug=args.debug)
        api_client = _build_api_client(args)
        data = _execute_command(api_client, args)
        envelope = _build_envelope(
            command=_command_label(args),
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
            data=_cli_error_data(exc),
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
        _write_side_effect_outputs(envelope, args)
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
        _write_side_effect_outputs(envelope, args)
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
    api_client: Any | None,
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
            api_client.wait_for_job(
                args.job_id,
                progress_callback=_build_progress_callback(args),
            )
            if args.wait
            else api_client.get_job(args.job_id)
        )
        return {
            "job": job_doc,
            "input": None,
            "result": job_doc.get("result"),
        }

    endpoint, payload, input_meta = _build_command_payload(args)
    progress_callback = _build_progress_callback(args)
    emit_submit_progress = (not args.no_wait) or (
        getattr(args, "progress", DEFAULT_PROGRESS_MODE) != DEFAULT_PROGRESS_MODE
    )
    if emit_submit_progress:
        _emit_progress(
            args,
            {
                "event": "submitting",
                "endpoint": endpoint,
                "wait": not args.no_wait,
            },
        )
    submission = api_client.submit_job(endpoint, payload)
    if emit_submit_progress:
        _emit_progress(
            args,
            {
                "event": "submitted",
                "endpoint": endpoint,
                "job_id": submission["job_id"],
                "cached": bool(submission.get("cached", False)),
            },
        )

    result_payload: dict[str, Any] | None = None
    final_job_status = "submitted"
    if not args.no_wait:
        try:
            job_doc = api_client.wait_for_job(
                submission["job_id"],
                progress_callback=progress_callback,
            )
        except CliError as exc:
            recovered_job = _recover_after_wait_failure(
                api_client=api_client,
                submission=submission,
                endpoint=endpoint,
                input_meta=input_meta,
                progress_callback=progress_callback,
                exc=exc,
            )
            if recovered_job is None:
                raise
            job_doc = recovered_job
        final_job_status = str(job_doc.get("status", "completed"))
        result_payload = job_doc.get("result")

    job_summary = {
        "job_id": submission["job_id"],
        "cached": bool(submission.get("cached", False)),
        "status": final_job_status,
        "endpoint": endpoint,
    }
    if args.subcommand == "transcribe":
        return _build_transcription_output(
            api_client=api_client,
            job_summary=job_summary,
            input_meta=input_meta,
            result_payload=result_payload,
        )

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
    if args.subcommand == "transcribe":
        input_payload, input_meta = _resolve_input_payload(
            args,
            storage_prefix=TRANSCRIPTION_UPLOAD_STORAGE_PREFIX,
            destination_prefix=TRANSCRIPTION_UPLOAD_DESTINATION_PREFIX,
        )
        return (
            "/media/transcribe/artifacts",
            {
                **input_payload,
                "channel_name": args.channel_name,
                "use_cache": True,
                "provider": TRANSCRIPTION_PROVIDER,
                "diarize": True,
                "identify_speakers": bool(args.identify_speakers),
                "speaker_identification_context": args.speaker_identification_context,
                "force_speaker_identification": bool(args.force_speaker_identification),
            },
            input_meta,
        )

    input_payload, input_meta = _resolve_input_payload(args)
    payload: dict[str, Any] = {
        **input_payload,
        "channel_name": args.channel_name,
        "use_cache": args.use_cache,
    }

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

    if args.subcommand == "segment":
        payload.update(
            {
                "prompt": args.prompt,
                "storage_prefix": args.storage_prefix,
                "generate_alpha": bool(getattr(args, "with_alpha", False)),
            }
        )
        if args.segment_kind == "image":
            return "/media/segment/image", _drop_none_values(payload), input_meta

        if args.segment_kind == "video":
            anchor = _build_frame_reference(
                seconds=args.anchor_seconds,
                frame_index=args.anchor_frame_index,
            )
            window_start = _build_frame_reference(
                seconds=args.window_start_seconds,
                frame_index=args.window_start_frame_index,
            )
            window_end = _build_frame_reference(
                seconds=args.window_end_seconds,
                frame_index=args.window_end_frame_index,
            )
            window = _build_tracking_window(start=window_start, end=window_end)
            payload.update(
                {
                    "anchor": anchor,
                    "window": window,
                    "propagation_direction": args.propagation_direction,
                    "max_frame_num_to_track": args.max_frame_num_to_track,
                }
            )
            return "/media/segment/video", _drop_none_values(payload), input_meta

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
        hint="Choose one of: upload, transcribe, segment, transform, matte, status.",
    )


def _resolve_input_payload(
    args: argparse.Namespace,
    *,
    storage_prefix: str = DEFAULT_INPUT_UPLOAD_PREFIX,
    destination_prefix: str = "agent-media-toolkit",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.url:
        return {"media_url": args.url}, {"media_url": args.url, "used_upload": False}

    if args.file:
        upload = upload_local_file(
            args.file,
            storage_prefix=storage_prefix,
            destination_prefix=destination_prefix,
        )
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


def _build_transcription_output(
    *,
    api_client: Any,
    job_summary: dict[str, Any],
    input_meta: dict[str, Any],
    result_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    artifacts = _artifacts_from_transcription_result(result_payload)
    transcript = result_payload.get("text") if isinstance(result_payload, dict) else None
    if not transcript and artifacts and artifacts.get("transcript_url"):
        transcript = api_client.fetch_text(str(artifacts["transcript_url"]))

    return {
        "transcript": transcript,
        "artifacts": artifacts,
        "source_id": result_payload.get("source_id") if isinstance(result_payload, dict) else None,
        "provider": result_payload.get("provider") if isinstance(result_payload, dict) else None,
        "speaker_identification": (
            result_payload.get("speaker_identification")
            if isinstance(result_payload, dict)
            else None
        ),
        "job": job_summary,
        "input": input_meta,
    }


def _artifacts_from_transcription_result(
    result_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(result_payload, dict):
        return None
    return {
        "transcript_url": result_payload.get("transcript_url"),
        "words_url": result_payload.get("words_url"),
        "sentences_url": result_payload.get("sentences_url"),
    }


def _write_side_effect_outputs(
    envelope: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    if getattr(args, "output", None):
        output_path = str(Path(args.output).expanduser().resolve())
        envelope["meta"]["output_path"] = output_path
        write_json_file(args.output, envelope)


def _cli_error_data(exc: CliError) -> dict[str, Any] | None:
    if isinstance(exc.detail, dict):
        data = exc.detail.get("data")
        if isinstance(data, dict):
            return data
    return None


def _recover_after_wait_failure(
    *,
    api_client: Any,
    submission: dict[str, Any],
    endpoint: str,
    input_meta: dict[str, Any],
    progress_callback: Any,
    exc: CliError,
) -> dict[str, Any] | None:
    partial_data = {
        "job": {
            "job_id": submission["job_id"],
            "cached": bool(submission.get("cached", False)),
            "status": "submitted",
            "endpoint": endpoint,
        },
        "input": input_meta,
        "result": None,
    }

    try:
        job_doc = api_client.get_job(submission["job_id"])
    except CliError:
        exc.detail = {
            "job_id": submission["job_id"],
            "endpoint": endpoint,
            "data": partial_data,
            "last_error": exc.detail,
        }
        return None

    job_status = str(job_doc.get("status", "")).strip().lower()
    if job_status == "completed":
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "completed",
                    "job_id": submission["job_id"],
                    "status": job_status,
                    "updated_at": job_doc.get("updated_at"),
                    "queue_dequeue_count": job_doc.get("queue_dequeue_count"),
                    "recovered": True,
                }
            )
        return job_doc

    partial_data["job"]["status"] = job_doc.get("status", "submitted")
    partial_data["result"] = job_doc.get("result")
    exc.detail = {
        "job_id": submission["job_id"],
        "endpoint": endpoint,
        "job": job_doc,
        "data": partial_data,
        "last_error": exc.detail,
    }
    return None


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
    data = payload.get("data") or {}
    transcript = data.get("transcript")
    if payload.get("status") == "ok" and transcript:
        return str(transcript).rstrip() + "\n"

    lines = [
        f"status={payload['status']}",
        f"command={payload['command']}",
    ]
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
    found_top_level = None
    for item in argv:
        if item in {"upload", "transcribe", "segment", "transform", "matte", "status"}:
            found_top_level = item
            break
    if found_top_level != "segment":
        return found_top_level or "unknown"
    for item in argv:
        if item in {"image", "video"}:
            return f"segment {item}"
    return "unknown"


def _command_label(args: argparse.Namespace) -> str:
    if args.subcommand == "segment":
        return f"{COMMAND_NAME} segment {args.segment_kind}"
    return f"{COMMAND_NAME} {args.subcommand}"


def _build_api_client(args: argparse.Namespace) -> Any | None:
    if args.subcommand == "upload":
        return None

    from media_toolkit_lib.api import MediaToolkitApiClient

    return MediaToolkitApiClient(
        api_base_url=DEFAULT_API_BASE_URL,
        request_timeout_seconds=args.request_timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        poll_timeout_seconds=args.poll_timeout_seconds,
    )


def _build_progress_callback(args: argparse.Namespace):
    if getattr(args, "progress", DEFAULT_PROGRESS_MODE) == "off":
        return None

    def _callback(event: dict[str, Any]) -> None:
        _emit_progress(args, event)

    return _callback


def _emit_progress(args: argparse.Namespace, event: dict[str, Any]) -> None:
    progress_mode = getattr(args, "progress", DEFAULT_PROGRESS_MODE)
    if progress_mode == "off":
        return

    if progress_mode == "jsonl":
        payload = {
            "type": "progress",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")
        sys.stderr.flush()
        return

    line = _format_progress_plain(event)
    if not line:
        return
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def _format_progress_plain(event: dict[str, Any]) -> str:
    ordered_keys = [
        "event",
        "job_id",
        "endpoint",
        "status",
        "elapsed_seconds",
        "updated_at",
        "queue_dequeue_count",
        "cached",
        "wait",
    ]
    parts = ["progress"]
    for key in ordered_keys:
        value = event.get(key)
        if value is None:
            continue
        if key == "elapsed_seconds":
            value = round(float(value), 1)
        parts.append(f"{key}={value}")
    return " ".join(parts)


def _validate_args(args: argparse.Namespace) -> None:
    if args.subcommand != "segment" or args.segment_kind != "video":
        return
    _validate_frame_reference_args(
        seconds=args.anchor_seconds,
        frame_index=args.anchor_frame_index,
        seconds_flag="--anchor-seconds",
        frame_flag="--anchor-frame-index",
        label="anchor",
    )
    _validate_frame_reference_args(
        seconds=args.window_start_seconds,
        frame_index=args.window_start_frame_index,
        seconds_flag="--window-start-seconds",
        frame_flag="--window-start-frame-index",
        label="window.start",
    )
    _validate_frame_reference_args(
        seconds=args.window_end_seconds,
        frame_index=args.window_end_frame_index,
        seconds_flag="--window-end-seconds",
        frame_flag="--window-end-frame-index",
        label="window.end",
    )
    _validate_window_order(args)
    if (
        args.max_frame_num_to_track is not None
        and args.max_frame_num_to_track < 1
    ):
        raise CliError(
            code="E_VALIDATION",
            message="--max-frame-num-to-track must be >= 1.",
            exit_code=2,
            retryable=False,
            hint="Provide a positive frame count or omit the flag.",
        )


def _drop_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _build_frame_reference(
    *,
    seconds: float | None,
    frame_index: int | None,
) -> dict[str, Any] | None:
    if seconds is None and frame_index is None:
        return None
    reference: dict[str, Any] = {}
    if seconds is not None:
        reference["seconds"] = seconds
    if frame_index is not None:
        reference["frame_index"] = frame_index
    return reference


def _build_tracking_window(
    *,
    start: dict[str, Any] | None,
    end: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if start is None and end is None:
        return None
    window: dict[str, Any] = {}
    if start is not None:
        window["start"] = start
    if end is not None:
        window["end"] = end
    return window


def _validate_frame_reference_args(
    *,
    seconds: float | None,
    frame_index: int | None,
    seconds_flag: str,
    frame_flag: str,
    label: str,
) -> None:
    if seconds is not None and seconds < 0:
        raise CliError(
            code="E_VALIDATION",
            message=f"{seconds_flag} must be >= 0.",
            exit_code=2,
            retryable=False,
            hint=f"Provide a non-negative {label} timestamp or omit the flag.",
        )
    if frame_index is not None and frame_index < 0:
        raise CliError(
            code="E_VALIDATION",
            message=f"{frame_flag} must be >= 0.",
            exit_code=2,
            retryable=False,
            hint=f"Provide a non-negative {label} frame index or omit the flag.",
        )
    if seconds is not None and frame_index is not None:
        raise CliError(
            code="E_VALIDATION",
            message=f"Provide at most one of {seconds_flag} or {frame_flag}.",
            exit_code=2,
            retryable=False,
            hint=f"Choose either a seconds-based or frame-based reference for {label}.",
        )


def _validate_window_order(args: argparse.Namespace) -> None:
    if (
        args.window_start_seconds is not None
        and args.window_end_seconds is not None
        and args.window_start_seconds >= args.window_end_seconds
    ):
        raise CliError(
            code="E_VALIDATION",
            message="--window-start-seconds must be earlier than --window-end-seconds.",
            exit_code=2,
            retryable=False,
            hint="Provide a strictly increasing window in seconds or use frame indexes instead.",
        )
    if (
        args.window_start_frame_index is not None
        and args.window_end_frame_index is not None
        and args.window_start_frame_index >= args.window_end_frame_index
    ):
        raise CliError(
            code="E_VALIDATION",
            message="--window-start-frame-index must be earlier than --window-end-frame-index.",
            exit_code=2,
            retryable=False,
            hint="Provide a strictly increasing window in frame indexes or use seconds instead.",
        )


def _configure_logging(*, debug: bool) -> None:
    if not debug:
        return
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    LOGGER.debug("Debug logging enabled.")


if __name__ == "__main__":
    raise SystemExit(main())
