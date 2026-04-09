#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "1.0"
DEFAULT_ENV_PATH = Path.home() / ".secrets/x/env"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
API_BASE = "https://api.x.com"
DEFAULT_USER_FIELDS = "created_at,description,verified,public_metrics,profile_image_url"
MEDIA_UPLOAD_PATH = "/2/media/upload"
MEDIA_UPLOAD_INITIALIZE_PATH = "/2/media/upload/initialize"
MEDIA_UPLOAD_APPEND_PATH_TEMPLATE = "/2/media/upload/{media_id}/append"
MEDIA_UPLOAD_FINALIZE_PATH_TEMPLATE = "/2/media/upload/{media_id}/finalize"
DEFAULT_VIDEO_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_VIDEO_PROCESSING_TIMEOUT_SECONDS = 900.0
MAX_VIDEO_PROCESSING_TIMEOUT_SECONDS = 2700.0
DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS = 4
MAX_VIDEO_TRANSFER_REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_MEDIA_CHUNK_SIZE_BYTES = 4 * 1024 * 1024
MAX_X_VIDEO_SIZE_BYTES = 512 * 1024 * 1024
DEFAULT_VIDEO_SOURCE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)
ALLOWED_X_VIDEO_MEDIA_TYPES = {
    "video/mp4",
    "video/webm",
    "video/mp2t",
    "video/quicktime",
}


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


def classify_source_download_http_error(url: str, status: int, body_text: str) -> CliError:
    lowered = body_text.lower()
    if status in {401, 403}:
        hint = "The source host denied automated access. Retry with a direct public URL, or download the file locally and use --video."
        if "error code: 1010" in lowered:
            hint = "The source host blocked this client signature (for example Cloudflare 1010). Retry with --video after downloading locally, or use a less restrictive public file URL."
        return CliError(
            f"Source host rejected the video download with HTTP {status}.",
            code="E_SOURCE_ACCESS",
            exit_code=4,
            retryable=False,
            hint=hint,
            details={"url": url, "status": status, "body": body_text},
        )
    if status == 429:
        return CliError(
            "Source host rate-limited the video download.",
            code="E_RATE_LIMIT",
            exit_code=4,
            retryable=True,
            hint="Wait and retry, or download the file locally and use --video.",
            details={"url": url, "status": status, "body": body_text},
        )
    if status >= 500:
        return CliError(
            f"Source host returned HTTP {status} while downloading the video.",
            code="E_NETWORK",
            exit_code=4,
            retryable=True,
            hint="Retry later, or download the file locally and use --video.",
            details={"url": url, "status": status, "body": body_text},
        )
    return CliError(
        f"Source host returned HTTP {status} while downloading the video.",
        code="E_INVALID_INPUT" if status in {400, 404, 409, 422} else "E_GENERIC",
        exit_code=2 if status in {400, 404, 409, 422} else 1,
        retryable=False,
        hint="Check that --video-url points directly to a downloadable video file, or use --video with a local file.",
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


def x_request(
    config: Config,
    method: str,
    path: str,
    *,
    query_params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout_seconds: float | None = None,
) -> tuple[int, dict[str, str], bytes]:
    require_config(config)
    url = f"{API_BASE}{path}"
    if query_params:
        url = f"{url}?{urllib.parse.urlencode(query_params)}"
    auth_header = build_oauth1_authorization_header(config, method, url)
    merged_headers = {"Authorization": auth_header}
    if headers:
        merged_headers.update(headers)
    return http_request(method, url, headers=merged_headers, data=data, timeout_seconds=timeout_seconds or config.request_timeout_seconds)


def x_json_request(config: Config, method: str, path: str, *, query_params: dict[str, str] | None = None, json_body: dict[str, Any] | None = None, timeout_seconds: float | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"} if json_body is not None else {}
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    _, _, body = x_request(config, method, path, query_params=query_params, headers=headers, data=data, timeout_seconds=timeout_seconds)
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


def should_emit_progress(args: argparse.Namespace) -> bool:
    progress = getattr(args, "progress", "auto")
    if progress == "off":
        return False
    if progress == "plain":
        return True
    return sys.stderr.isatty()


def emit_progress(args: argparse.Namespace, message: str) -> None:
    if should_emit_progress(args):
        print(message, file=sys.stderr, flush=True)


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


def load_optional_post_text(args: argparse.Namespace) -> str:
    if args.text and args.text_file:
        raise CliError("Use either --text or --text-file, not both.", code="E_INVALID_INPUT", exit_code=2)
    if args.text:
        return args.text.strip()
    if args.text_file:
        return Path(args.text_file).expanduser().read_text().strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def load_x_video_path(raw_path: str) -> tuple[Path, str]:
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise CliError(
            f"Video file not found: {path}",
            code="E_INVALID_INPUT",
            exit_code=2,
            hint="Check the --video path and try again.",
        )
    if not path.is_file():
        raise CliError(
            f"Video path is not a file: {path}",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise CliError(
            f"Video file is empty: {path}",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    if size_bytes > MAX_X_VIDEO_SIZE_BYTES:
        raise CliError(
            "X video uploads must not exceed 512 MB.",
            code="E_INVALID_INPUT",
            exit_code=2,
            details={"path": str(path), "file_size_bytes": size_bytes, "max_size_bytes": MAX_X_VIDEO_SIZE_BYTES},
        )
    media_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
    if media_type not in ALLOWED_X_VIDEO_MEDIA_TYPES:
        raise CliError(
            f"Unsupported X video media type: {media_type}",
            code="E_INVALID_INPUT",
            exit_code=2,
            hint="Use MP4/H.264 when in doubt.",
            details={"path": str(path), "media_type": media_type},
        )
    return path, media_type


def compute_adaptive_video_processing_timeout_seconds(file_size_bytes: int) -> float:
    size_mb = file_size_bytes / (1024 * 1024)
    extra_seconds = max(0.0, size_mb - 100.0) * 2.4
    return min(MAX_VIDEO_PROCESSING_TIMEOUT_SECONDS, max(DEFAULT_VIDEO_PROCESSING_TIMEOUT_SECONDS, round(DEFAULT_VIDEO_PROCESSING_TIMEOUT_SECONDS + extra_seconds)))


def resolve_video_processing_timeout_seconds(explicit_timeout_seconds: float | None, *, file_size_bytes: int) -> tuple[float, str]:
    if explicit_timeout_seconds is not None:
        return float(explicit_timeout_seconds), "explicit"
    return compute_adaptive_video_processing_timeout_seconds(file_size_bytes), "auto"


def compute_transfer_attempt_timeout_seconds(config: Config, attempt_index: int) -> float:
    return min(MAX_VIDEO_TRANSFER_REQUEST_TIMEOUT_SECONDS, config.request_timeout_seconds * (2**attempt_index))


def download_video_url_to_tempfile(config: Config, video_url: str, *, progress_callback: Callable[[str], None] | None = None) -> tuple[Path, dict[str, Any], str]:
    parsed = urllib.parse.urlparse(video_url)
    if parsed.scheme not in {"http", "https"}:
        raise CliError(
            "Video URL must start with http:// or https://.",
            code="E_INVALID_INPUT",
            exit_code=2,
            hint="Pass a direct public MP4 URL, or use --video for a local file.",
        )
    suffix = Path(parsed.path).suffix or ".mp4"
    temp_dir = Path(tempfile.mkdtemp(prefix="x-video-"))
    local_path = temp_dir / f"source{suffix}"
    content_type = ""
    content_length = None
    last_error: CliError | None = None
    for attempt_index in range(DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS):
        timeout_seconds = compute_transfer_attempt_timeout_seconds(config, attempt_index)
        try:
            request = urllib.request.Request(
                video_url,
                method="GET",
                headers={
                    "User-Agent": DEFAULT_VIDEO_SOURCE_USER_AGENT,
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                content_length = response.headers.get("Content-Length")
                with local_path.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = classify_source_download_http_error(video_url, exc.code, body)
        except TimeoutError:
            last_error = CliError(
                f"Timed out downloading {video_url}.",
                code="E_TIMEOUT",
                exit_code=5,
                retryable=True,
                hint="Retry with a larger --request-timeout-seconds if the source host is slow.",
            )
        except urllib.error.URLError as exc:
            last_error = CliError(
                f"Failed to download {video_url}: {exc.reason}",
                code="E_NETWORK",
                exit_code=4,
                retryable=True,
                hint="Check the URL and retry. The source must be publicly reachable from this machine.",
            )
        if local_path.exists():
            with contextlib.suppress(Exception):
                local_path.unlink()
        if last_error is None or (not last_error.retryable or attempt_index + 1 >= DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS):
            if last_error is not None:
                raise last_error
            break
        if progress_callback:
            next_timeout_seconds = compute_transfer_attempt_timeout_seconds(config, attempt_index + 1)
            progress_callback(
                f"[x] retrying source video download (attempt {attempt_index + 2}/{DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS}, timeout {int(next_timeout_seconds)}s)"
            )
        time.sleep(min(2**attempt_index, 8))
    downloaded_path, media_type = load_x_video_path(str(local_path))
    metadata = {
        "source_url": video_url,
        "downloaded_path": str(downloaded_path),
        "content_type": content_type,
        "content_length_header": content_length,
        "file_size_bytes": downloaded_path.stat().st_size,
    }
    return downloaded_path, metadata, media_type


def build_multipart_form_data(*, fields: dict[str, Any], files: list[tuple[str, str, bytes, str]] | None = None) -> tuple[str, bytes]:
    boundary = f"----dobby{secrets.token_hex(16)}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(str(value).encode())
        parts.append(b"\r\n")
    for name, filename, content, content_type in files or []:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(content)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(parts)


def x_multipart_request(config: Config, method: str, path: str, *, query_params: dict[str, str] | None = None, fields: dict[str, Any], files: list[tuple[str, str, bytes, str]] | None = None, timeout_seconds: float | None = None) -> dict[str, Any]:
    boundary, body = build_multipart_form_data(fields=fields, files=files)
    _, _, response_body = x_request(
        config,
        method,
        path,
        query_params=query_params,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        data=body,
        timeout_seconds=timeout_seconds,
    )
    return json.loads(response_body.decode("utf-8")) if response_body else {}


def initialize_x_video_upload(config: Config, *, media_type: str, total_bytes: int) -> dict[str, Any]:
    # v2 chunked upload: POST /2/media/upload/initialize with a JSON body.
    # Replaces the deprecated /2/media/upload?command=INIT form shape, which
    # the API now rejects because /2/media/upload only accepts image/subtitle
    # categories. See https://docs.x.com/x-api/media and xdevplatform/xdk-*.
    response = x_json_request(
        config,
        "POST",
        MEDIA_UPLOAD_INITIALIZE_PATH,
        json_body={
            "media_type": media_type,
            "media_category": "tweet_video",
            "total_bytes": total_bytes,
        },
    )
    data = response.get("data") or {}
    media_id = data.get("id")
    if not media_id:
        raise CliError(
            "X media initialize response was missing media id.",
            code="E_API",
            exit_code=1,
            details=response,
        )
    return data


def append_x_video_chunk(config: Config, *, media_id: str, segment_index: int, chunk: bytes, chunk_media_type: str, progress_callback: Callable[[str], None] | None = None) -> None:
    # v2 chunked upload: POST /2/media/upload/{media_id}/append with a
    # multipart/form-data body that has `segment_index` as a text form field
    # and `media` as a binary file part. The old /2/media/upload?command=APPEND
    # shape is no longer accepted.
    append_path = MEDIA_UPLOAD_APPEND_PATH_TEMPLATE.format(
        media_id=urllib.parse.quote(media_id, safe="")
    )
    last_error: CliError | None = None
    for attempt_index in range(DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS):
        timeout_seconds = compute_transfer_attempt_timeout_seconds(config, attempt_index)
        try:
            x_multipart_request(
                config,
                "POST",
                append_path,
                fields={"segment_index": segment_index},
                files=[("media", f"chunk-{segment_index}.bin", chunk, chunk_media_type)],
                timeout_seconds=timeout_seconds,
            )
            return
        except CliError as exc:
            last_error = exc
        if last_error is None or (not last_error.retryable or attempt_index + 1 >= DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS):
            if last_error is not None:
                raise last_error
            return
        if progress_callback:
            next_timeout_seconds = compute_transfer_attempt_timeout_seconds(config, attempt_index + 1)
            progress_callback(
                f"[x] retrying upload segment {segment_index} after {last_error.code} (attempt {attempt_index + 2}/{DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS}, timeout {int(next_timeout_seconds)}s)"
            )
        time.sleep(min(2**attempt_index, 8))


def finalize_x_video_upload(config: Config, *, media_id: str) -> dict[str, Any]:
    # v2 chunked upload: POST /2/media/upload/{media_id}/finalize with no body.
    # Replaces the deprecated /2/media/upload?command=FINALIZE form shape.
    finalize_path = MEDIA_UPLOAD_FINALIZE_PATH_TEMPLATE.format(
        media_id=urllib.parse.quote(media_id, safe="")
    )
    _, _, response_body = x_request(
        config,
        "POST",
        finalize_path,
    )
    if not response_body:
        return {}
    response = json.loads(response_body.decode("utf-8"))
    return response.get("data") or {}


def get_x_media_upload_status(config: Config, *, media_id: str) -> dict[str, Any]:
    response = x_json_request(
        config,
        "GET",
        MEDIA_UPLOAD_PATH,
        query_params={"command": "STATUS", "media_id": media_id},
    )
    return response.get("data") or {}


def build_x_post_payload(*, text: str, media_ids: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if text:
        payload["text"] = text
    if media_ids:
        payload["media"] = {"media_ids": media_ids}
    return payload

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
            "supported_commands": ["status", "post", "post-video"],
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


def publish_x_video(
    args: argparse.Namespace,
    config: Config,
    *,
    text: str,
    video_path: Path,
    media_type: str,
    dry_run: bool,
) -> dict[str, Any]:
    file_size_bytes = video_path.stat().st_size
    processing_timeout_seconds, processing_timeout_mode = resolve_video_processing_timeout_seconds(
        args.video_processing_timeout_seconds,
        file_size_bytes=file_size_bytes,
    )
    payload = build_x_post_payload(text=text, media_ids=["<pending-media-id>"])
    if dry_run:
        return {
            "dry_run": True,
            "upload_plan": {
                "local_path": str(video_path),
                "file_size_bytes": file_size_bytes,
                "media_type": media_type,
                "chunk_size_bytes": DEFAULT_MEDIA_CHUNK_SIZE_BYTES,
                "chunk_count": (file_size_bytes + DEFAULT_MEDIA_CHUNK_SIZE_BYTES - 1) // DEFAULT_MEDIA_CHUNK_SIZE_BYTES,
                "wait_for_processing": not args.no_wait_for_video,
                "poll_interval_seconds": args.video_poll_interval_seconds,
                "processing_timeout_seconds": processing_timeout_seconds,
                "processing_timeout_mode": processing_timeout_mode,
                "request_timeout_seconds": config.request_timeout_seconds,
                "transfer_max_attempts": DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS,
            },
            "payload": payload,
        }

    emit_progress(args, f"[x] initializing video upload for {video_path.name}")
    init_data = initialize_x_video_upload(config, media_type=media_type, total_bytes=file_size_bytes)
    media_id = str(init_data["id"])
    uploaded_segments = 0
    with video_path.open("rb") as handle:
        segment_index = 0
        while True:
            chunk = handle.read(DEFAULT_MEDIA_CHUNK_SIZE_BYTES)
            if not chunk:
                break
            emit_progress(args, f"[x] uploading segment {segment_index}")
            append_x_video_chunk(
                config,
                media_id=media_id,
                segment_index=segment_index,
                chunk=chunk,
                chunk_media_type=media_type,
                progress_callback=lambda message: emit_progress(args, message),
            )
            uploaded_segments += 1
            segment_index += 1

    emit_progress(args, f"[x] finalizing upload for {video_path.name}")
    finalize_data = finalize_x_video_upload(config, media_id=media_id)
    status_data = finalize_data
    processing_info = finalize_data.get("processing_info") or {}
    if args.no_wait_for_video:
        emit_progress(args, "[x] skipping video readiness wait because --no-wait-for-video was set")
    elif processing_info:
        deadline = time.time() + processing_timeout_seconds
        last_state = None
        last_progress = None
        while True:
            state = str(processing_info.get("state") or "")
            progress_percent = processing_info.get("progress_percent")
            if state == "succeeded":
                emit_progress(args, f"[x] video processing succeeded: media_id={media_id}")
                break
            if state == "failed":
                error = processing_info.get("error") or {}
                raise CliError(
                    "X video processing failed.",
                    code="E_API",
                    exit_code=1,
                    hint="Check the source file format and retry with a standard MP4/H.264 export.",
                    details={"media_id": media_id, "processing_info": processing_info, "error": error},
                )
            if time.time() >= deadline:
                raise CliError(
                    f"Timed out waiting for X to process the video (last state: {state or 'unknown'}).",
                    code="E_TIMEOUT",
                    exit_code=5,
                    retryable=True,
                    hint="Retry with a larger --video-processing-timeout-seconds if X is still processing the upload.",
                    details={"media_id": media_id, "processing_info": processing_info},
                )
            if state != last_state or progress_percent != last_progress:
                extra = f", progress={progress_percent}%" if progress_percent is not None else ""
                emit_progress(args, f"[x] waiting for video processing: state={state or 'unknown'}{extra}")
                last_state = state
                last_progress = progress_percent
            sleep_seconds = float(processing_info.get("check_after_secs") or args.video_poll_interval_seconds)
            time.sleep(max(args.video_poll_interval_seconds, min(sleep_seconds, 60.0)))
            status_data = get_x_media_upload_status(config, media_id=media_id)
            processing_info = status_data.get("processing_info") or {}

    emit_progress(args, "[x] creating post")
    response = x_json_request(config, "POST", "/2/tweets", json_body=build_x_post_payload(text=text, media_ids=[media_id]))
    return {
        "dry_run": False,
        "tweet": response.get("data") or {},
        "raw": response,
        "media_id": media_id,
        "media_key": init_data.get("media_key"),
        "uploaded_segments": uploaded_segments,
        "processing_timeout_seconds": processing_timeout_seconds,
        "processing_timeout_mode": processing_timeout_mode,
        "media_status": status_data,
    }


def command_post_video(args: argparse.Namespace) -> dict[str, Any]:
    if args.video_poll_interval_seconds <= 0:
        raise CliError(
            "--video-poll-interval-seconds must be greater than 0.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    if args.video_processing_timeout_seconds is not None and args.video_processing_timeout_seconds <= 0:
        raise CliError(
            "--video-processing-timeout-seconds must be greater than 0.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    config = build_config(args)
    require_config(config)
    text = load_optional_post_text(args)
    if args.video_url:
        if args.dry_run:
            return {
                "dry_run": True,
                "upload_plan": {
                    "source_type": "video_url",
                    "source_url": args.video_url,
                    "wait_for_processing": not args.no_wait_for_video,
                    "poll_interval_seconds": args.video_poll_interval_seconds,
                    "processing_timeout_seconds": args.video_processing_timeout_seconds,
                    "processing_timeout_mode": "explicit" if args.video_processing_timeout_seconds is not None else "auto_after_download",
                    "request_timeout_seconds": config.request_timeout_seconds,
                    "transfer_max_attempts": DEFAULT_VIDEO_TRANSFER_MAX_ATTEMPTS,
                },
                "payload": build_x_post_payload(text=text, media_ids=["<pending-media-id>"]),
            }
        emit_progress(args, f"[x] downloading video from {args.video_url}")
        video_path, download_meta, media_type = download_video_url_to_tempfile(
            config,
            args.video_url,
            progress_callback=lambda message: emit_progress(args, message),
        )
        try:
            result = publish_x_video(args, config, text=text, video_path=video_path, media_type=media_type, dry_run=False)
            result["video_source"] = {"type": "video_url", **download_meta}
            return result
        finally:
            with contextlib.suppress(Exception):
                shutil.rmtree(video_path.parent)
    video_path, media_type = load_x_video_path(args.video)
    result = publish_x_video(args, config, text=text, video_path=video_path, media_type=media_type, dry_run=args.dry_run)
    if not args.dry_run:
        result["video_source"] = {
            "type": "local_file",
            "local_path": str(video_path),
            "file_size_bytes": video_path.stat().st_size,
            "media_type": media_type,
        }
    return result


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local X app credentials env file.")
    common.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS, help="HTTP request timeout in seconds.")
    mode = common.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON output. This is also the default.")
    mode.add_argument("--plain", action="store_true", help="Emit stable plain text for shell pipelines or quick operator inspection.")
    common.add_argument("--no-input", action="store_true", help="Disable any future interactive behavior.")
    common.add_argument(
        "--progress",
        choices=["auto", "off", "plain"],
        default="auto",
        help="Progress reporting mode for long-running commands. Emits progress on stderr only.",
    )

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

    post_video = subparsers.add_parser("post-video", help="Publish a video post to X.", parents=[common])
    post_video.add_argument("--text", help="Inline post text.")
    post_video.add_argument("--text-file", help="Path to a file containing post text.")
    post_video_source = post_video.add_mutually_exclusive_group(required=True)
    post_video_source.add_argument("--video", help="Local video file path.")
    post_video_source.add_argument("--video-url", help="Direct public video URL. The client downloads it first, then uploads it to X.")
    post_video.add_argument(
        "--video-poll-interval-seconds",
        type=float,
        default=DEFAULT_VIDEO_POLL_INTERVAL_SECONDS,
        help="Minimum seconds between X video processing polls.",
    )
    post_video.add_argument(
        "--video-processing-timeout-seconds",
        type=float,
        default=None,
        help="Total time to wait for X to process the uploaded video before failing. Defaults to an adaptive value based on video size.",
    )
    post_video.add_argument(
        "--no-wait-for-video",
        action="store_true",
        help="Skip waiting for the uploaded video to finish processing before creating the post.",
    )
    post_video.add_argument("--dry-run", action="store_true", help="Print the request payload without uploading or publishing.")
    post_video.set_defaults(func=command_post_video, command_path="x post-video")

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
