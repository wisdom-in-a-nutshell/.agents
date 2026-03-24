#!/usr/bin/env python3
"""Upload local files to the AIP frontend storage API and return public URLs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

FIXED_API_BASE_URL = "https://app.aipodcast.ing"
UPLOAD_API_PATH = "/api/core/upload/generate-presigned-url"
DEFAULT_UPLOAD_FOLDER = "permanent"


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


def build_url(base_url: str, path: str) -> str:
  return f"{base_url.rstrip('/')}{path}"


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
  headers = {"Accept": "application/json"}
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
  folder: str = DEFAULT_UPLOAD_FOLDER,
) -> tuple[str, str, str]:
  content_type = guess_content_type(local_path)
  body = request_json(
    "POST",
    build_url(FIXED_API_BASE_URL, UPLOAD_API_PATH),
    timeout_seconds,
    {
      "filename": f"{folder}/{local_path.name}",
      "contentType": content_type,
    },
  )

  presigned_url = ""
  file_url = ""
  if isinstance(body, dict):
    presigned_url = str(body.get("presignedUrl") or "").strip()
    file_url = str(body.get("fileUrl") or "").strip()

  if not presigned_url or not file_url:
    raise UploadHelperError(
      code="E_BAD_RESPONSE",
      message="Upload API returned an unexpected response shape.",
      retryable=False,
      hint="Verify /api/core/upload/generate-presigned-url is deployed and healthy.",
      exit_code=1,
    )

  return presigned_url, file_url, content_type


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
  folder: str = DEFAULT_UPLOAD_FOLDER,
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

  presigned_url, file_url, content_type = request_upload_target(local_path, timeout_seconds, folder)
  upload_record = {
    "field": field_name,
    "source_path": str(local_path),
    "file_url": file_url,
    "content_type": content_type,
    "folder": folder,
    "uploaded": not dry_run,
  }

  if not dry_run:
    upload_file_bytes(presigned_url, local_path, content_type, timeout_seconds)

  return file_url, upload_record


def main() -> int:
  parser = argparse.ArgumentParser(
    prog="aip_local_upload_helper",
    description="Upload a local file to the AI Podcasting storage API and print its public URL.",
  )
  parser.add_argument("path", help="Local file path to upload.")
  parser.add_argument("--folder", default=DEFAULT_UPLOAD_FOLDER, help="Upload folder prefix.")
  parser.add_argument("--timeout-seconds", type=float, default=30.0, help="HTTP timeout.")
  parser.add_argument("--dry-run", action="store_true", help="Reserve a public URL but do not upload bytes.")
  parser.add_argument("--json", action="store_true", help="Emit JSON output.")
  args = parser.parse_args()

  try:
    file_url, upload_record = resolve_upload_source_url(
      args.path,
      "path",
      args.timeout_seconds,
      args.dry_run,
      folder=args.folder,
    )
    if args.json:
      print(json.dumps({"status": "ok", "fileUrl": file_url, "upload": upload_record}))
    else:
      print(file_url)
    return 0
  except UploadHelperError as exc:
    if args.json:
      print(
        json.dumps(
          {
            "status": "error",
            "error": {
              "code": exc.code,
              "message": exc.message,
              "retryable": exc.retryable,
              "hint": exc.hint,
            },
          }
        )
      )
    else:
      print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
      if exc.hint:
        print(f"Hint: {exc.hint}", file=sys.stderr)
    return exc.exit_code


if __name__ == "__main__":
  raise SystemExit(main())
