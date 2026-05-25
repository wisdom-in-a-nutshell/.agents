#!/usr/bin/env python3
"""Cloud-first transcription client for the local-transcription skill."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

DEFAULT_API_BASE_URL = (
    "https://aipodcasting-hzbxdueeg4eeatgh.eastus-01.azurewebsites.net"
)
DEFAULT_UPLOAD_MEDIA_BIN = Path.home() / "GitHub/scripts/bin/upload-media"
SCHEMA_VERSION = "1.0"
COMMAND_NAME = "local-transcription"
TERMINAL_JOB_STATUSES = {"completed", "failed", "canceled"}


class CliError(Exception):
    """Structured command failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        exit_code: int,
        retryable: bool,
        hint: str,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable
        self.hint = hint
        self.detail = detail


class CliArgumentParser(argparse.ArgumentParser):
    """Argument parser that returns JSON-shaped usage errors."""

    def error(self, message: str) -> None:
        raise CliError(
            code="E_USAGE",
            message=message,
            exit_code=2,
            retryable=False,
            hint="Run local-transcription --help for supported commands and flags.",
        )


class LocalTranscriptionApiClient:
    """Thin HTTP client for WIN transcription artifact jobs."""

    def __init__(
        self,
        *,
        api_base_url: str,
        request_timeout_seconds: float,
        poll_interval_seconds: float,
        poll_timeout_seconds: float,
        session: requests.Session | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.session = session or requests.Session()

    def submit_transcription(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a cached artifact transcription job."""

        return self._request_json(
            "POST",
            "/media/transcribe/artifacts",
            json_body=payload,
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch a job document."""

        return self._request_json("GET", f"/jobs/{job_id}")

    def wait_for_job(
        self,
        job_id: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Poll a job until it reaches a terminal state."""

        deadline = time.monotonic() + self.poll_timeout_seconds
        started_at = time.monotonic()
        last_status: str | None = None
        last_emit_at = 0.0
        heartbeat_seconds = max(60.0, self.poll_interval_seconds)

        while True:
            now = time.monotonic()
            job = self.get_job(job_id)
            status = str(job.get("status", "")).strip().lower()
            elapsed_seconds = now - started_at
            should_emit = status != last_status or now - last_emit_at >= heartbeat_seconds
            if progress_callback is not None and should_emit:
                progress_callback(
                    {
                        "event": "wait" if status != last_status else "heartbeat",
                        "job_id": job_id,
                        "status": status or "unknown",
                        "elapsed_seconds": elapsed_seconds,
                        "updated_at": job.get("updated_at"),
                    }
                )
                last_emit_at = now
            last_status = status

            if status in TERMINAL_JOB_STATUSES:
                if status == "completed":
                    return job
                error_payload = job.get("error") or {}
                raise CliError(
                    code="E_JOB_FAILED",
                    message=str(
                        error_payload.get("message") or f"Job {job_id} {status}."
                    ),
                    exit_code=1,
                    retryable=bool(job.get("should_retry")),
                    hint="Inspect the job payload or retry when the backend condition is resolved.",
                    detail=job,
                )

            if time.monotonic() >= deadline:
                raise CliError(
                    code="E_TIMEOUT",
                    message=f"Timed out while waiting for job {job_id}.",
                    exit_code=5,
                    retryable=True,
                    hint="Increase --poll-timeout-seconds or rerun with --no-wait.",
                    detail={"job_id": job_id},
                )

            time.sleep(self.poll_interval_seconds)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base_url}{path}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_body,
                timeout=self.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise CliError(
                code="E_TIMEOUT",
                message=f"Timed out while calling {url}.",
                exit_code=5,
                retryable=True,
                hint="Retry the command or increase --request-timeout-seconds.",
            ) from exc
        except requests.RequestException as exc:
            raise CliError(
                code="E_NETWORK",
                message=f"Failed to reach {url}.",
                exit_code=4,
                retryable=True,
                hint="Check network connectivity and API base URL configuration.",
            ) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if response.status_code >= 400:
            raise CliError(
                code=_http_error_code(response.status_code),
                message=_http_error_message(response, payload),
                exit_code=_http_exit_code(response.status_code),
                retryable=response.status_code >= 500,
                hint=_http_error_hint(response.status_code),
                detail=payload,
            )

        if not isinstance(payload, dict):
            raise CliError(
                code="E_API",
                message=f"Expected JSON object response from {url}.",
                exit_code=4,
                retryable=False,
                hint="Check whether the API endpoint returned a valid JSON payload.",
            )
        return payload


def build_parser() -> CliArgumentParser:
    """Build the CLI parser."""

    parser = CliArgumentParser(
        prog=COMMAND_NAME,
        description=(
            "Transcribe a local file or URL through the WIN cloud transcription job path. "
            "JSON is the default output contract."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _add_common_args(parser)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    _build_transcribe_parser(subparsers)
    _build_status_parser(subparsers)
    _build_doctor_parser(subparsers)
    return parser


def _build_transcribe_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "transcribe",
        help="Submit a cached transcription artifact job and return transcript text.",
    )
    _add_common_args(parser)
    _add_api_args(parser)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Local audio or media file to upload first.")
    group.add_argument("--url", help="Remote audio or media URL.")
    parser.add_argument(
        "--provider",
        default="local_transcription",
        help="WIN transcription provider. Default: local_transcription.",
    )
    parser.add_argument(
        "--diarize",
        dest="diarize",
        action="store_true",
        default=True,
        help="Enable diarized ElevenLabs Scribe path. Default.",
    )
    parser.add_argument(
        "--no-diarize",
        dest="diarize",
        action="store_false",
        help="Disable diarization for this request.",
    )
    parser.add_argument(
        "--channel-name",
        default="MISC",
        help="WIN channel name used when ingesting a URL. Default: MISC.",
    )
    parser.add_argument(
        "--use-cache",
        dest="use_cache",
        action="store_true",
        default=True,
        help="Use cached ingest/transcription data when available. Default.",
    )
    parser.add_argument(
        "--no-use-cache",
        dest="use_cache",
        action="store_false",
        help="Bypass cached ingest/transcription data.",
    )
    parser.add_argument(
        "--upload-media-bin",
        default=str(DEFAULT_UPLOAD_MEDIA_BIN),
        help="Path to shared upload-media helper for local files.",
    )
    parser.add_argument(
        "--upload-destination-prefix",
        default="local-transcription",
        help="Object destination prefix under the cache storage prefix.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit the job and return immediately without polling.",
    )


def _build_status_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser("status", help="Inspect a WIN transcription job.")
    _add_common_args(parser)
    _add_api_args(parser)
    parser.add_argument("--job-id", required=True, help="WIN job id to inspect.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until the job reaches a terminal state.",
    )


def _build_doctor_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser("doctor", help="Inspect local client readiness.")
    _add_common_args(parser)
    parser.add_argument(
        "--upload-media-bin",
        default=str(DEFAULT_UPLOAD_MEDIA_BIN),
        help="Path to shared upload-media helper.",
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        dest="output_mode",
        action="store_const",
        const="json",
        help="Emit machine-readable JSON output. Default.",
    )
    output_group.add_argument(
        "--plain",
        dest="output_mode",
        action="store_const",
        const="plain",
        help="Emit transcript text only for successful transcribe waits.",
    )
    parser.set_defaults(output_mode="json")
    parser.add_argument("-o", "--output", help="Write the JSON envelope to a file.")
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Disable prompts. This client is non-interactive regardless.",
    )


def _add_api_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("LOCAL_TRANSCRIPTION_WIN_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="WIN API base URL. This is not a secret.",
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
        default=7200.0,
        help="Maximum time to wait for a transcription job.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=10.0,
        help="Polling interval while waiting for a job.",
    )
    parser.add_argument(
        "--progress",
        default="auto",
        choices=["auto", "off", "plain", "jsonl"],
        help="Progress mode. Progress is emitted to stderr only.",
    )


def run(argv: list[str]) -> tuple[int, str]:
    """Run the CLI and return exit code plus stdout text."""

    started_at = time.monotonic()
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    request_id = uuid.uuid4().hex
    args: argparse.Namespace | None = None
    try:
        args = build_parser().parse_args(argv)
        data = _execute(args)
        envelope = _build_envelope(
            command=_command_label(args),
            status="ok",
            data=data,
            error=None,
            request_id=request_id,
            started_at=started_at,
            timestamp_utc=timestamp_utc,
        )
        _write_output_file(envelope, args)
        return 0, _format_output(args.output_mode, envelope)
    except CliError as exc:
        envelope = _build_envelope(
            command=f"{COMMAND_NAME} {_safe_subcommand(argv)}",
            status="error",
            data=_error_data(exc),
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
        if args is not None:
            _write_output_file(envelope, args)
        return exc.exit_code, _format_output(_safe_output_mode(argv), envelope)
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
        return 5, _format_output(_safe_output_mode(argv), envelope)


def main(argv: list[str] | None = None) -> int:
    """Entrypoint."""

    exit_code, output = run(argv or sys.argv[1:])
    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return exit_code


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.subcommand == "doctor":
        return _doctor(args)

    api_client = _build_api_client(args)
    if args.subcommand == "status":
        job = (
            api_client.wait_for_job(
                args.job_id,
                progress_callback=_progress_callback(args),
            )
            if args.wait
            else api_client.get_job(args.job_id)
        )
        return _data_from_job(
            job=job,
            input_meta=None,
            endpoint=None,
            cached=None,
        )

    if args.subcommand == "transcribe":
        payload, input_meta = _build_transcribe_payload(args)
        endpoint = "/media/transcribe/artifacts"
        _emit_progress(
            args,
            {
                "event": "submitting",
                "endpoint": endpoint,
                "wait": not args.no_wait,
            },
        )
        submission = api_client.submit_transcription(payload)
        job_id = str(submission["job_id"])
        _emit_progress(
            args,
            {
                "event": "submitted",
                "endpoint": endpoint,
                "job_id": job_id,
                "cached": bool(submission.get("cached", False)),
            },
        )
        if args.no_wait:
            return {
                "transcript": None,
                "artifacts": None,
                "source_id": None,
                "provider": args.provider,
                "job": {
                    "job_id": job_id,
                    "cached": bool(submission.get("cached", False)),
                    "status": "submitted",
                    "endpoint": endpoint,
                },
                "input": input_meta,
                "result": None,
            }

        job = api_client.wait_for_job(
            job_id,
            progress_callback=_progress_callback(args),
        )
        return _data_from_job(
            job=job,
            input_meta=input_meta,
            endpoint=endpoint,
            cached=bool(submission.get("cached", False)),
        )

    raise CliError(
        code="E_USAGE",
        message=f"Unsupported command: {args.subcommand}",
        exit_code=2,
        retryable=False,
        hint="Choose one of: transcribe, status, doctor.",
    )


def _build_transcribe_payload(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.url:
        input_payload = {"media_url": args.url}
        input_meta = {
            "media_url": args.url,
            "used_upload": False,
        }
    elif args.file:
        upload = upload_local_file(
            args.file,
            upload_media_bin=args.upload_media_bin,
            destination_prefix=args.upload_destination_prefix,
        )
        input_payload = {"media_url": upload["url"]}
        input_meta = {
            "file_path": upload["file_path"],
            "uploaded_url": upload["url"],
            "storage_prefix": upload["storage_prefix"],
            "destination_path": upload["destination_path"],
            "content_sha256": upload.get("content_sha256"),
            "cached": upload["cached"],
            "used_upload": True,
        }
    else:
        raise CliError(
            code="E_VALIDATION",
            message="One of --file or --url is required.",
            exit_code=2,
            retryable=False,
            hint="Pass exactly one input locator.",
        )

    payload = {
        **input_payload,
        "provider": args.provider,
        "diarize": bool(args.diarize),
        "channel_name": args.channel_name,
        "use_cache": bool(args.use_cache),
    }
    return payload, input_meta


def upload_local_file(
    file_path: str,
    *,
    upload_media_bin: str,
    destination_prefix: str,
) -> dict[str, Any]:
    """Upload a local file to R2 cache through the shared upload-media helper."""

    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise CliError(
            code="E_VALIDATION",
            message=f"Local file not found: {path}",
            exit_code=2,
            retryable=False,
            hint="Pass an existing local file path with --file.",
        )

    upload_bin = Path(upload_media_bin).expanduser().resolve()
    if not upload_bin.exists() or not os.access(upload_bin, os.X_OK):
        raise CliError(
            code="E_DEPENDENCY_MISSING",
            message=f"upload-media helper is not executable: {upload_bin}",
            exit_code=4,
            retryable=False,
            hint="Install or fix ~/GitHub/scripts/bin/upload-media.",
        )

    command = [
        str(upload_bin),
        "--json",
        "--no-input",
        "--file",
        str(path),
        "--storage-prefix",
        "cache",
        "--destination-prefix",
        destination_prefix,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CliError(
            code="E_DEPENDENCY_MISSING",
            message="Failed to execute upload-media.",
            exit_code=4,
            retryable=False,
            hint="Check that the upload-media helper is executable.",
        ) from exc

    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CliError(
            code="E_UPLOAD_FAILED",
            message="upload-media did not return valid JSON.",
            exit_code=4,
            retryable=False,
            hint="Inspect upload-media stdout and stderr.",
            detail={"stdout": completed.stdout, "stderr": completed.stderr},
        ) from exc

    if completed.returncode != 0:
        error = envelope.get("error") if isinstance(envelope, dict) else None
        raise CliError(
            code=str((error or {}).get("code") or "E_UPLOAD_FAILED"),
            message=str((error or {}).get("message") or "upload-media failed."),
            exit_code=completed.returncode or 4,
            retryable=bool((error or {}).get("retryable", True)),
            hint=str(
                (error or {}).get("hint")
                or completed.stderr.strip()
                or "Inspect upload-media output and retry."
            ),
            detail=envelope,
        )

    upload = (
        ((envelope.get("data") or {}).get("upload"))
        if isinstance(envelope, dict)
        else None
    )
    if not isinstance(upload, dict) or not upload.get("url"):
        raise CliError(
            code="E_UPLOAD_FAILED",
            message="upload-media returned an invalid upload payload.",
            exit_code=4,
            retryable=False,
            hint="Inspect upload-media JSON output for missing data.upload.url.",
            detail=envelope,
        )
    return {
        "file_path": str(upload.get("file_path", path)),
        "file_name": str(upload.get("file_name", path.name)),
        "storage_prefix": str(upload.get("storage_prefix", "cache")),
        "destination_path": str(upload.get("destination_path", "")),
        "content_sha256": str(upload.get("content_sha256", "")),
        "cached": bool(upload.get("cached", False)),
        "url": str(upload["url"]),
    }


def _data_from_job(
    *,
    job: dict[str, Any],
    input_meta: dict[str, Any] | None,
    endpoint: str | None,
    cached: bool | None,
) -> dict[str, Any]:
    result = job.get("result")
    if not isinstance(result, dict):
        result = None

    return {
        "transcript": (result or {}).get("text"),
        "artifacts": (
            {
                "transcript_url": result.get("transcript_url"),
                "words_url": result.get("words_url"),
                "sentences_url": result.get("sentences_url"),
            }
            if result
            else None
        ),
        "source_id": (result or {}).get("source_id"),
        "provider": (result or {}).get("provider"),
        "job": {
            "job_id": job.get("job_id"),
            "cached": bool(cached if cached is not None else job.get("cached", False)),
            "status": job.get("status"),
            "endpoint": endpoint or job.get("endpoint"),
        },
        "input": input_meta,
        "result": result,
    }


def _doctor(args: argparse.Namespace) -> dict[str, Any]:
    upload_bin = Path(args.upload_media_bin).expanduser().resolve()
    upload_media_ready = upload_bin.exists() and os.access(upload_bin, os.X_OK)
    return {
        "ready": {
            "client": True,
            "upload_media": upload_media_ready,
        },
        "upload_media": {
            "path": str(upload_bin),
            "exists": upload_bin.exists(),
            "executable": os.access(upload_bin, os.X_OK),
        },
        "default_api_base_url": DEFAULT_API_BASE_URL,
        "default_provider": "local_transcription",
        "default_diarize": True,
        "artifact_storage_prefix": "cache",
    }


def _build_api_client(args: argparse.Namespace) -> LocalTranscriptionApiClient:
    return LocalTranscriptionApiClient(
        api_base_url=args.api_base_url,
        request_timeout_seconds=args.request_timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        poll_timeout_seconds=args.poll_timeout_seconds,
    )


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


def _format_output(output_mode: str, envelope: dict[str, Any]) -> str:
    if output_mode == "plain":
        return _format_plain(envelope)
    return json.dumps(envelope, indent=2, sort_keys=True) + "\n"


def _format_plain(envelope: dict[str, Any]) -> str:
    if envelope.get("status") == "ok":
        data = envelope.get("data") or {}
        transcript = data.get("transcript")
        if transcript:
            return str(transcript).rstrip() + "\n"
        job = data.get("job") or {}
        if job:
            return f"job_id={job.get('job_id')}\nstatus={job.get('status')}\n"
        ready = data.get("ready")
        if ready:
            return "\n".join(f"{key}={value}" for key, value in ready.items()) + "\n"
    error = envelope.get("error") or {}
    return (
        f"status={envelope.get('status')}\n"
        f"error_code={error.get('code')}\n"
        f"message={error.get('message')}\n"
    )


def _write_output_file(envelope: dict[str, Any], args: argparse.Namespace) -> None:
    if not getattr(args, "output", None):
        return
    output_path = Path(args.output).expanduser().resolve()
    envelope["meta"]["output_path"] = str(output_path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise CliError(
            code="E_OUTPUT_WRITE",
            message=f"Failed to write output file: {output_path}",
            exit_code=1,
            retryable=False,
            hint="Check the output path and parent directory permissions.",
        ) from exc


def _progress_callback(
    args: argparse.Namespace,
) -> Callable[[dict[str, Any]], None] | None:
    if getattr(args, "progress", "auto") == "off":
        return None

    def _callback(event: dict[str, Any]) -> None:
        _emit_progress(args, event)

    return _callback


def _emit_progress(args: argparse.Namespace, event: dict[str, Any]) -> None:
    progress_mode = getattr(args, "progress", "auto")
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
    parts = ["progress"]
    for key in (
        "event",
        "job_id",
        "endpoint",
        "status",
        "elapsed_seconds",
        "cached",
        "wait",
    ):
        value = event.get(key)
        if value is None:
            continue
        if key == "elapsed_seconds":
            value = round(float(value), 1)
        parts.append(f"{key}={value}")
    sys.stderr.write(" ".join(parts) + "\n")
    sys.stderr.flush()


def _http_error_code(status_code: int) -> str:
    if status_code in {400, 422}:
        return "E_VALIDATION"
    if status_code in {401, 403}:
        return "E_AUTH"
    return "E_API"


def _http_exit_code(status_code: int) -> int:
    if status_code in {400, 422}:
        return 2
    if status_code in {401, 403}:
        return 3
    return 4


def _http_error_hint(status_code: int) -> str:
    if status_code in {400, 422}:
        return "Fix the request payload and rerun the command."
    if status_code in {401, 403}:
        return "Check API authentication or access configuration."
    return "Inspect the server response and retry if the failure is transient."


def _http_error_message(response: requests.Response, payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("detail") or payload.get("error") or response.text)
    return response.text or f"API request failed with HTTP {response.status_code}."


def _command_label(args: argparse.Namespace) -> str:
    return f"{COMMAND_NAME} {args.subcommand}"


def _safe_output_mode(argv: list[str]) -> str:
    return "plain" if "--plain" in argv else "json"


def _safe_subcommand(argv: list[str]) -> str:
    for item in argv:
        if item in {"transcribe", "status", "doctor"}:
            return item
    return "unknown"


def _error_data(exc: CliError) -> dict[str, Any] | None:
    if isinstance(exc.detail, dict):
        data = exc.detail.get("data")
        if isinstance(data, dict):
            return data
    return None


if __name__ == "__main__":
    raise SystemExit(main())
