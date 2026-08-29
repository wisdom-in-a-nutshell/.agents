#!/usr/bin/env python3
"""Upload local files through the scoped WIN client API and return cache URLs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

FIXED_API_BASE_URL = "https://api.aipodcast.ing"
UPLOAD_API_PATH = "/client/v1/uploads"
FIXED_SHOW = "TCR"
UPLOAD_PURPOSES = (
  "episode_main",
  "episode_asset",
  "episode_intro",
  "episode_outro",
  "thumbnail",
)
DEFAULT_UPLOAD_PURPOSE = "episode_asset"
DEFAULT_API_KEY_FILE = Path.home() / ".secrets/aipodcasting/env"
CLIENT_USER_AGENT = "ai-podcasting-agent/2.0"
SCHEMA_VERSION = "2.0"


class UploadHelperError(Exception):
  def __init__(
    self,
    code: str,
    message: str,
    retryable: bool,
    hint: str,
    exit_code: int,
  ) -> None:
    super().__init__(message)
    self.code = code
    self.message = message
    self.retryable = retryable
    self.hint = hint
    self.exit_code = exit_code


def now_utc_iso() -> str:
  return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_envelope(
  *,
  status: str,
  data: Any,
  error: dict[str, Any] | None,
  request_id: str,
  duration_ms: int,
) -> dict[str, Any]:
  return {
    "schema_version": SCHEMA_VERSION,
    "command": "upload-file",
    "status": status,
    "data": data,
    "error": error,
    "meta": {
      "request_id": request_id,
      "duration_ms": duration_ms,
      "timestamp_utc": now_utc_iso(),
    },
  }


def build_url(base_url: str, path: str) -> str:
  return f"{base_url.rstrip('/')}{path}"


def _strip_shell_quotes(value: str) -> str:
  stripped = value.strip()
  if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
    return stripped[1:-1]
  return stripped


def _read_secret_file(path: Path, names: tuple[str, ...]) -> str:
  try:
    content = path.read_text(encoding="utf-8")
  except FileNotFoundError:
    return ""
  except OSError:
    return ""

  for raw_line in content.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
      continue
    if line.startswith("export "):
      line = line[len("export ") :].strip()
    name, separator, value = line.partition("=")
    if separator == "=" and name.strip() in names:
      return _strip_shell_quotes(value)

  return content.strip()


def get_client_api_key() -> str:
  api_key_file = Path(
    os.getenv("AIPODCASTING_CLIENT_API_KEY_FILE", str(DEFAULT_API_KEY_FILE))
  ).expanduser()
  try:
    if api_key_file.stat().st_mode & 0o077:
      raise UploadHelperError(
        code="E_AUTH",
        message="AI Podcasting client credential file permissions are too broad.",
        retryable=False,
        hint=f"Run chmod 600 {api_key_file}, then run doctor.",
        exit_code=3,
      )
  except FileNotFoundError:
    pass
  except OSError:
    pass
  file_key = _read_secret_file(
    api_key_file,
    ("AIPODCASTING_CLIENT_API_KEY",),
  )
  if file_key:
    return file_key

  raise UploadHelperError(
    code="E_AUTH",
    message="AI Podcasting client credential file is missing or incomplete.",
    retryable=False,
    hint=(
      f"Create {api_key_file} with AIPODCASTING_CLIENT_API_KEY=<key> and mode 600, "
      "then run doctor."
    ),
    exit_code=3,
  )


def build_client_auth_headers() -> dict[str, str]:
  api_key = get_client_api_key()
  return {"Authorization": f"Bearer {api_key}"}


def parse_response_body(raw_bytes: bytes) -> Any:
  text = raw_bytes.decode("utf-8", errors="replace")
  if not text.strip():
    return {}

  try:
    return json.loads(text)
  except json.JSONDecodeError:
    return {"raw": text}


def request_json(
  method: str,
  url: str,
  timeout_seconds: float,
  payload: dict[str, Any] | None = None,
) -> Any:
  headers = {
    "Accept": "application/json",
    "User-Agent": CLIENT_USER_AGENT,
  }
  headers.update(build_client_auth_headers())
  body: bytes | None = None

  if payload is not None:
    body = json.dumps(payload).encode("utf-8")
    headers["Content-Type"] = "application/json"

  request = urlrequest.Request(url=url, data=body, headers=headers, method=method)

  try:
    with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
      return parse_response_body(response.read())
  except urlerror.HTTPError as exc:
    body = parse_response_body(exc.read())
    message = ""
    if isinstance(body, dict):
      detail = body.get("detail")
      if isinstance(detail, dict):
        message = str(detail.get("message") or "").strip()
      elif isinstance(detail, str):
        message = detail.strip()
      if not message:
        message = str(body.get("error") or body.get("message") or "").strip()
    raise UploadHelperError(
      code="E_HTTP",
      message=message or f"Request failed with HTTP {exc.code}",
      retryable=exc.code >= 500,
      hint="Verify the upload API is deployed and try again.",
      exit_code=4 if exc.code >= 500 else 2,
    ) from exc
  except TimeoutError as exc:
    raise UploadHelperError(
      code="E_TIMEOUT",
      message="Request timed out.",
      retryable=True,
      hint="Retry with a larger timeout.",
      exit_code=5,
    ) from exc
  except urlerror.URLError as exc:
    if isinstance(exc.reason, socket.timeout):
      raise UploadHelperError(
        code="E_TIMEOUT",
        message="Request timed out.",
        retryable=True,
        hint="Retry with a larger timeout.",
        exit_code=5,
      ) from exc

    raise UploadHelperError(
      code="E_NETWORK",
      message=f"Network error: {exc.reason}",
      retryable=True,
      hint=f"Check connectivity and confirm {FIXED_API_BASE_URL} is reachable.",
      exit_code=4,
    ) from exc


def is_public_http_url(value: str) -> bool:
  try:
    parsed = urlparse.urlparse(value.strip())
  except Exception:
    return False
  return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def looks_like_local_path(value: str) -> bool:
  stripped = value.strip()
  return (
    stripped.startswith("/")
    or stripped.startswith("./")
    or stripped.startswith("../")
    or stripped.startswith("~/")
  )


def resolve_local_path(path_value: str) -> Path:
  return Path(path_value.strip()).expanduser().resolve()


def validate_upload_source_list(field_name: str, links: list[str]) -> None:
  for link in links:
    if looks_like_local_path(link):
      local_path = resolve_local_path(link)
      if not local_path.exists() or not local_path.is_file():
        raise UploadHelperError(
          code="E_VALIDATION",
          message=f"{field_name} local file was not found: {local_path}",
          retryable=False,
          hint="Pass an existing local file path or a public HTTPS link.",
          exit_code=2,
        )
      continue

    if not is_public_http_url(link):
      raise UploadHelperError(
        code="E_VALIDATION",
        message=f"{field_name} must contain valid public HTTP/HTTPS URLs or local file paths.",
        retryable=False,
        hint="Provide a reachable public HTTPS link or an existing local file path.",
        exit_code=2,
      )


def guess_content_type(local_path: Path) -> str:
  guessed_type, _ = mimetypes.guess_type(local_path.name)
  return guessed_type or "application/octet-stream"


def request_upload_target(
  local_path: Path,
  timeout_seconds: float,
  purpose: str = DEFAULT_UPLOAD_PURPOSE,
) -> tuple[str, str, str, str]:
  content_type = guess_content_type(local_path)
  body = request_json(
    "POST",
    build_url(FIXED_API_BASE_URL, UPLOAD_API_PATH),
    timeout_seconds,
    {
      "show": FIXED_SHOW,
      "purpose": purpose,
      "filename": local_path.name,
      "content_type": content_type,
    },
  )

  presigned_url = ""
  file_url = ""
  object_key = ""
  if isinstance(body, dict):
    presigned_url = str(body.get("upload_url") or "").strip()
    file_url = str(body.get("public_url") or "").strip()
    object_key = str(body.get("object_key") or "").strip()

  if not presigned_url or not file_url or not object_key:
    raise UploadHelperError(
      code="E_BAD_RESPONSE",
      message="Upload API returned an unexpected response shape.",
      retryable=False,
      hint="Run doctor and verify /client/v1/uploads is deployed and healthy.",
      exit_code=1,
    )

  return presigned_url, file_url, content_type, object_key


def upload_file_bytes(
  presigned_url: str,
  local_path: Path,
  content_type: str,
  timeout_seconds: float,
) -> None:
  try:
    with open(local_path, "rb") as handle:
      body = handle.read()
  except OSError as exc:
    raise UploadHelperError(
      code="E_VALIDATION",
      message=f"Unable to read local file: {local_path}",
      retryable=False,
      hint="Check file permissions and try again.",
      exit_code=2,
    ) from exc

  request = urlrequest.Request(
    url=presigned_url,
    data=body,
    headers={"Content-Type": content_type},
    method="PUT",
  )

  try:
    with urlrequest.urlopen(request, timeout=timeout_seconds):
      return
  except urlerror.HTTPError as exc:
    raise UploadHelperError(
      code="E_UPSTREAM",
      message=f"Upload failed with HTTP {exc.code}.",
      retryable=True,
      hint="Retry the upload. If it keeps failing, confirm storage credentials are valid.",
      exit_code=4,
    ) from exc
  except TimeoutError as exc:
    raise UploadHelperError(
      code="E_TIMEOUT",
      message="Upload timed out.",
      retryable=True,
      hint="Retry with a larger timeout.",
      exit_code=5,
    ) from exc
  except urlerror.URLError as exc:
    raise UploadHelperError(
      code="E_NETWORK",
      message=f"Upload network error: {exc.reason}",
      retryable=True,
      hint="Check connectivity and retry.",
      exit_code=4,
    ) from exc


def resolve_upload_source_url(
  link: str,
  field_name: str,
  timeout_seconds: float,
  dry_run: bool,
  purpose: str = DEFAULT_UPLOAD_PURPOSE,
) -> tuple[str, dict[str, Any] | None]:
  stripped = link.strip()
  if not stripped:
    return "", None

  if is_public_http_url(stripped):
    return stripped, None

  if not looks_like_local_path(stripped):
    raise UploadHelperError(
      code="E_VALIDATION",
      message=f"{field_name} must be a public HTTP/HTTPS URL or local file path.",
      retryable=False,
      hint="Provide a reachable public HTTPS link or an existing local file path.",
      exit_code=2,
    )

  local_path = resolve_local_path(stripped)
  if not local_path.exists() or not local_path.is_file():
    raise UploadHelperError(
      code="E_VALIDATION",
      message=f"{field_name} local file was not found: {local_path}",
      retryable=False,
      hint="Pass an existing local file path.",
      exit_code=2,
    )

  presigned_url, file_url, content_type, object_key = request_upload_target(
    local_path,
    timeout_seconds,
    purpose,
  )
  upload_record = {
    "field": field_name,
    "source_path": str(local_path),
    "file_url": file_url,
    "content_type": content_type,
    "purpose": purpose,
    "lifecycle": "cache",
    "object_key": object_key,
    "uploaded": not dry_run,
  }

  if not dry_run:
    upload_file_bytes(presigned_url, local_path, content_type, timeout_seconds)

  return file_url, upload_record


def main() -> int:
  parser = argparse.ArgumentParser(
    prog="aip_local_upload_helper",
    description="Upload a local file through the scoped AI Podcasting client API.",
  )
  parser.add_argument("path", help="Local file path to upload.")
  parser.add_argument(
    "--purpose",
    choices=UPLOAD_PURPOSES,
    default=DEFAULT_UPLOAD_PURPOSE,
    help="Owning upload intent (default: episode_asset).",
  )
  parser.add_argument("--timeout-seconds", type=float, default=30.0, help="HTTP timeout.")
  parser.add_argument("--dry-run", action="store_true", help="Reserve a public URL but do not upload bytes.")
  output_group = parser.add_mutually_exclusive_group()
  output_group.add_argument(
    "--json",
    action="store_true",
    help="Emit the default machine-readable JSON output.",
  )
  output_group.add_argument(
    "--plain",
    action="store_true",
    help="Emit only the resulting public URL.",
  )
  parser.add_argument(
    "--request-id",
    default="",
    help="Optional correlation id. Auto-generated when omitted.",
  )
  parser.add_argument(
    "--no-input",
    action="store_true",
    help="Run non-interactively (accepted for agent compatibility).",
  )
  args = parser.parse_args()
  request_id = args.request_id or str(uuid.uuid4())
  start = time.perf_counter()

  try:
    file_url, upload_record = resolve_upload_source_url(
      args.path,
      "path",
      args.timeout_seconds,
      args.dry_run,
      purpose=args.purpose,
    )
    if args.plain:
      print(file_url)
    else:
      print(
        json.dumps(
          make_envelope(
            status="ok",
            data={"file_url": file_url, "upload": upload_record},
            error=None,
            request_id=request_id,
            duration_ms=int((time.perf_counter() - start) * 1000),
          )
        )
      )
    return 0
  except UploadHelperError as exc:
    error = {
      "code": exc.code,
      "message": exc.message,
      "retryable": exc.retryable,
      "hint": exc.hint,
    }
    if args.plain:
      print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
      if exc.hint:
        print(f"Hint: {exc.hint}", file=sys.stderr)
    else:
      print(
        json.dumps(
          make_envelope(
            status="error",
            data=None,
            error=error,
            request_id=request_id,
            duration_ms=int((time.perf_counter() - start) * 1000),
          )
        )
      )
    return exc.exit_code


if __name__ == "__main__":
  raise SystemExit(main())
