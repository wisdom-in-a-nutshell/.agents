#!/usr/bin/env python3
"""Agent-first CLI for AI Podcasting episode operations."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

SCHEMA_VERSION = "1.0"
FIXED_API_BASE_URL = "https://app.aipodcast.ing"
FIXED_SHOW = "TCR"
INTRO_COPY_FIELDS = {
  "recordingLink",
  "transcript",
  "instructionsToEditor",
  "title",
  "thumbnailText",
  "videoThumbnails",
  "videoThumbnailLink",
  "videoThumbnailLinks",
  "audioThumbnailLink",
  "outroMusicLink",
}

INTRO_COPY_FIELD_MAP = {
  "recordingLink": "introFile",
  "transcript": "introTranscript",
  "instructionsToEditor": "editorInstructions",
  "title": "title",
  "thumbnailText": "thumbnailText",
  "videoThumbnails": "videoThumbnails",
  "videoThumbnailLink": "videoThumbnailLink",
  "videoThumbnailLinks": "videoThumbnailLinks",
  "audioThumbnailLink": "audioThumbnailLink",
  "outroMusicLink": "outroMusicLink",
  # Backward-compatible aliases
  "introFile": "introFile",
  "introTranscript": "introTranscript",
  "editorInstructions": "editorInstructions",
}


class ClientError(Exception):
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


def build_url(base_url: str, path: str, params: dict[str, str] | None = None) -> str:
  base = base_url.rstrip("/")
  url = f"{base}{path}"
  if not params:
    return url

  normalized = {k: v for k, v in params.items() if v is not None and v != ""}
  if not normalized:
    return url

  return f"{url}?{urlparse.urlencode(normalized)}"


def load_json_file(path: str) -> Any:
  try:
    with open(path, "r", encoding="utf-8") as handle:
      return json.load(handle)
  except FileNotFoundError as exc:
    raise ClientError(
      code="E_VALIDATION",
      message=f"Payload file not found: {path}",
      retryable=False,
      hint="Pass an existing JSON payload file path.",
      exit_code=2,
    ) from exc
  except json.JSONDecodeError as exc:
    raise ClientError(
      code="E_VALIDATION",
      message=f"Payload file is not valid JSON: {path}",
      retryable=False,
      hint=f"Fix JSON syntax near line {exc.lineno}, column {exc.colno}.",
      exit_code=2,
    ) from exc


def to_error_message(body: Any, fallback: str) -> str:
  if isinstance(body, dict):
    value = body.get("error") or body.get("message") or body.get("details")
    if isinstance(value, str) and value.strip():
      return value.strip()
  return fallback


def classify_http_error(status_code: int, body: Any) -> ClientError:
  message = to_error_message(body, f"Request failed with HTTP {status_code}")

  if status_code in (400, 404, 422):
    return ClientError(
      code="E_VALIDATION",
      message=message,
      retryable=False,
      hint="Check command arguments and payload shape, then retry.",
      exit_code=2,
    )

  if status_code in (401, 403):
    return ClientError(
      code="E_AUTH",
      message=message,
      retryable=False,
      hint="Verify credentials/session for the target environment.",
      exit_code=3,
    )

  if status_code in (408, 504):
    return ClientError(
      code="E_TIMEOUT",
      message=message,
      retryable=True,
      hint="Retry with a larger --timeout-seconds value.",
      exit_code=5,
    )

  if status_code >= 500:
    return ClientError(
      code="E_UPSTREAM",
      message=message,
      retryable=True,
      hint="Backend is unavailable or failed. Retry shortly.",
      exit_code=4,
    )

  return ClientError(
    code="E_HTTP",
    message=message,
    retryable=False,
    hint="Inspect API response details and retry.",
    exit_code=1,
  )


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
    raise classify_http_error(exc.code, parse_response_body(exc.read())) from exc
  except TimeoutError as exc:
    raise ClientError(
      code="E_TIMEOUT",
      message="Request timed out.",
      retryable=True,
      hint="Retry with a larger --timeout-seconds value.",
      exit_code=5,
    ) from exc
  except urlerror.URLError as exc:
    if isinstance(exc.reason, socket.timeout):
      raise ClientError(
        code="E_TIMEOUT",
        message="Request timed out.",
        retryable=True,
        hint="Retry with a larger --timeout-seconds value.",
        exit_code=5,
      ) from exc

    raise ClientError(
      code="E_NETWORK",
      message=f"Network error: {exc.reason}",
      retryable=True,
      hint=f"Check connectivity and confirm {FIXED_API_BASE_URL} is reachable.",
      exit_code=4,
    ) from exc


def ensure_mapping(payload: Any, context: str) -> dict[str, Any]:
  if isinstance(payload, dict):
    return payload

  raise ClientError(
    code="E_VALIDATION",
    message=f"{context} payload must be a JSON object.",
    retryable=False,
    hint="Wrap payload fields in a JSON object with key/value pairs.",
    exit_code=2,
  )


def is_public_http_url(value: str) -> bool:
  try:
    parsed = urlparse.urlparse(value.strip())
  except Exception:
    return False
  return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def looks_like_local_path(value: str) -> bool:
  stripped = value.strip()
  return stripped.startswith("/") or stripped.startswith("./") or stripped.startswith("../")


def normalize_public_url_list(value: Any) -> list[str]:
  if isinstance(value, str):
    candidate = value.strip()
    return [candidate] if candidate else []

  if not isinstance(value, list):
    return []

  normalized: list[str] = []
  for item in value:
    if isinstance(item, str):
      candidate = item.strip()
      if candidate:
        normalized.append(candidate)

  return normalized


def validate_public_url_list(field_name: str, links: list[str]) -> None:
  for link in links:
    if looks_like_local_path(link):
      raise ClientError(
        code="E_VALIDATION",
        message=f"{field_name} must use public HTTP/HTTPS URLs, not local file paths.",
        retryable=False,
        hint="Upload the file to cloud storage first and provide a public HTTPS link.",
        exit_code=2,
      )

    if not is_public_http_url(link):
      raise ClientError(
        code="E_VALIDATION",
        message=f"{field_name} must contain valid public HTTP/HTTPS URLs.",
        retryable=False,
        hint="Provide a reachable public HTTPS link.",
        exit_code=2,
      )


def normalize_video_thumbnail_links(payload: dict[str, Any]) -> list[str]:
  links = normalize_public_url_list(payload.get("videoThumbnails"))
  links.extend(normalize_public_url_list(payload.get("videoThumbnailLinks")))
  links.extend(normalize_public_url_list(payload.get("videoThumbnailLink")))

  deduped: list[str] = []
  seen: set[str] = set()
  for link in links:
    if link not in seen:
      deduped.append(link)
      seen.add(link)

  return deduped


def ensure_video_thumbnail_payload(video: dict[str, Any]) -> None:
  raw_variants = video.get("variants")
  variants = (
    [item for item in raw_variants if isinstance(item, dict)]
    if isinstance(raw_variants, list)
    else []
  )
  valid_variants = [
    variant
    for variant in variants
    if isinstance(variant.get("url"), str) and variant["url"].strip()
  ]

  if valid_variants:
    video["variants"] = valid_variants
  elif "variants" in video:
    video.pop("variants", None)

  current_url = video.get("url")
  normalized_url = current_url.strip() if isinstance(current_url, str) else ""

  if normalized_url and not valid_variants:
    variant: dict[str, Any] = {"url": normalized_url}
    design_source_url = video.get("design_source_url")
    if isinstance(design_source_url, str) and design_source_url.strip():
      variant["design_source_url"] = design_source_url.strip()
    video["variants"] = [variant]
    return

  if not normalized_url and valid_variants:
    video["url"] = str(valid_variants[0]["url"]).strip()


def validate_submit_payload(payload: dict[str, Any]) -> None:
  show = payload.get("show")
  if show is not None and str(show).strip().upper() not in ("", FIXED_SHOW):
    raise ClientError(
      code="E_VALIDATION",
      message=f"submit-episode is locked to show '{FIXED_SHOW}'.",
      retryable=False,
      hint=f"Set 'show' to '{FIXED_SHOW}' or remove it from payload.",
      exit_code=2,
    )

  file_url = payload.get("fileUrl")
  files = payload.get("files")
  has_file_url = isinstance(file_url, str) and bool(file_url.strip())
  has_main_raw = (
    isinstance(files, dict)
    and isinstance(files.get("main"), dict)
    and isinstance(files["main"].get("raw"), str)
    and bool(files["main"]["raw"].strip())
  )

  if not has_file_url and not has_main_raw:
    raise ClientError(
      code="E_VALIDATION",
      message="submit-episode payload requires either files.main.raw or fileUrl.",
      retryable=False,
      hint="Use references/submit-episode.example.json as baseline.",
      exit_code=2,
    )

  candidate_links: list[str] = []
  if has_file_url:
    candidate_links.append(str(file_url).strip())
  if has_main_raw:
    candidate_links.append(str(files["main"]["raw"]).strip())

  for link in candidate_links:
    if looks_like_local_path(link):
      raise ClientError(
        code="E_VALIDATION",
        message="submit-episode main file must be a public URL, not a local file path.",
        retryable=False,
        hint="Upload the file to cloud storage first and provide a public HTTPS link.",
        exit_code=2,
      )

  if not any(is_public_http_url(link) for link in candidate_links):
    raise ClientError(
      code="E_VALIDATION",
      message="submit-episode main file link must be a valid public HTTP/HTTPS URL.",
      retryable=False,
      hint="Set files.main.raw or fileUrl to a reachable public HTTPS link.",
      exit_code=2,
    )


def validate_intro_copy_payload(payload: dict[str, Any]) -> None:
  if not payload:
    raise ClientError(
      code="E_VALIDATION",
      message="update-intro-copy payload must not be empty.",
      retryable=False,
      hint="Provide the current intro payload or the user-facing intro fields for recording, title, and thumbnails.",
      exit_code=2,
    )

  missing_required: list[str] = []

  recording_link = payload.get("recordingLink", payload.get("introFile"))
  if not isinstance(recording_link, str) or not recording_link.strip():
    missing_required.append("recordingLink")
  else:
    validate_public_url_list("recordingLink", [recording_link.strip()])

  title = payload.get("title")
  if not isinstance(title, str) or not title.strip():
    missing_required.append("title")

  video_thumbnail_links = normalize_video_thumbnail_links(payload)
  if video_thumbnail_links:
    validate_public_url_list("videoThumbnails", video_thumbnail_links)

  audio_thumbnail_link = payload.get("audioThumbnailLink")
  if isinstance(audio_thumbnail_link, str) and audio_thumbnail_link.strip():
    validate_public_url_list("audioThumbnailLink", [audio_thumbnail_link.strip()])

  outro_music_link = payload.get("outroMusicLink")
  if isinstance(outro_music_link, str) and outro_music_link.strip():
    validate_public_url_list("outroMusicLink", [outro_music_link.strip()])

  if not missing_required:
    return

  optional_fields = ", ".join(
    [
      "videoThumbnails",
      "thumbnailText",
      "transcript",
      "instructionsToEditor",
      "audioThumbnailLink",
      "outroMusicLink",
    ]
  )
  missing = ", ".join(missing_required)
  raise ClientError(
    code="E_VALIDATION",
    message=f"update-intro-copy is missing required fields: {missing}.",
    retryable=False,
    hint=(
      "Required: recordingLink, title. "
      f"Optional: {optional_fields}."
    ),
    exit_code=2,
  )


def normalize_intro_copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
  normalized: dict[str, Any] = {}
  for key, value in payload.items():
    mapped_key = INTRO_COPY_FIELD_MAP.get(key, key)
    normalized[mapped_key] = value

  video_thumbnail_links = normalize_public_url_list(normalized.pop("videoThumbnails", None))
  video_thumbnail_links.extend(normalize_public_url_list(normalized.pop("videoThumbnailLinks", None)))
  video_thumbnail_links.extend(normalize_public_url_list(normalized.pop("videoThumbnailLink", None)))
  audio_thumbnail_link = normalized.pop("audioThumbnailLink", None)
  outro_music_link = normalized.pop("outroMusicLink", None)

  deduped_video_thumbnail_links: list[str] = []
  seen_video_links: set[str] = set()
  for link in video_thumbnail_links:
    if link not in seen_video_links:
      deduped_video_thumbnail_links.append(link)
      seen_video_links.add(link)

  if deduped_video_thumbnail_links:
    deliverables = normalized.setdefault("deliverables", {})
    if isinstance(deliverables, dict):
      thumbnails = deliverables.setdefault("thumbnails", {})
      if isinstance(thumbnails, dict):
        video = thumbnails.setdefault("video", {})
        if isinstance(video, dict):
          video["url"] = deduped_video_thumbnail_links[0]
          video["variants"] = [{"url": link} for link in deduped_video_thumbnail_links]

  if isinstance(audio_thumbnail_link, str) and audio_thumbnail_link.strip():
    deliverables = normalized.setdefault("deliverables", {})
    if isinstance(deliverables, dict):
      thumbnails = deliverables.setdefault("thumbnails", {})
      if isinstance(thumbnails, dict):
        audio = thumbnails.setdefault("audio", {})
        if isinstance(audio, dict):
          audio["url"] = audio_thumbnail_link.strip()

  if isinstance(outro_music_link, str) and outro_music_link.strip():
    files = normalized.setdefault("files", {})
    if isinstance(files, dict):
      episode_outro = files.setdefault("episode_outro", {})
      if isinstance(episode_outro, dict):
        episode_outro["edited"] = outro_music_link.strip()

  deliverables = normalized.get("deliverables")
  if isinstance(deliverables, dict):
    thumbnails = deliverables.get("thumbnails")
    if isinstance(thumbnails, dict):
      video = thumbnails.get("video")
      if isinstance(video, dict):
        ensure_video_thumbnail_payload(video)

  return normalized


def normalize_episode_item(item: dict[str, Any]) -> dict[str, str]:
  submission = item.get("submission")
  publishing = item.get("publishing")

  title = ""
  if isinstance(item.get("title"), str):
    title = item["title"].strip()
  elif isinstance(submission, dict) and isinstance(submission.get("title"), str):
    title = submission["title"].strip()

  status = ""
  if isinstance(publishing, dict) and isinstance(publishing.get("status"), str):
    status = publishing["status"].strip()

  return {
    "source_id": str(item.get("source_id") or "").strip(),
    "title": title,
    "show": str(item.get("show") or "").strip(),
    "status": status,
  }


def extract_episode_items(body: Any) -> list[dict[str, Any]]:
  if isinstance(body, list):
    return [item for item in body if isinstance(item, dict)]

  if isinstance(body, dict):
    items = body.get("items")
    if isinstance(items, list):
      return [item for item in items if isinstance(item, dict)]

    episodes = body.get("episodes")
    if isinstance(episodes, list):
      return [item for item in episodes if isinstance(item, dict)]

  raise ClientError(
    code="E_BAD_RESPONSE",
    message="Unexpected response shape from /api/episodes.",
    retryable=False,
    hint="Run with --json to inspect output and align parsing rules.",
    exit_code=1,
  )


def run_list_backlog_episodes(args: argparse.Namespace) -> dict[str, Any]:
  params = {
    "includePublished": "false",
    "show": FIXED_SHOW,
    "startDate": args.start_date or "",
    "endDate": args.end_date or "",
  }
  url = build_url(FIXED_API_BASE_URL, "/api/episodes", params)

  if args.dry_run:
    return {
      "dry_run": True,
      "request": {"method": "GET", "url": url},
    }

  body = request_json("GET", url, args.timeout_seconds)
  items = [normalize_episode_item(item) for item in extract_episode_items(body)]

  if args.limit is not None and args.limit >= 0:
    items = items[: args.limit]

  return {
    "count": len(items),
    "items": items,
  }


def run_submit_episode(args: argparse.Namespace) -> dict[str, Any]:
  payload = ensure_mapping(load_json_file(args.payload_file), "submit-episode")
  validate_submit_payload(payload)
  payload["show"] = FIXED_SHOW

  url = build_url(FIXED_API_BASE_URL, "/api/episodes/submit")

  if args.dry_run:
    return {
      "dry_run": True,
      "request": {"method": "POST", "url": url, "payload": payload},
    }

  body = request_json("POST", url, args.timeout_seconds, payload)

  source_id = ""
  if isinstance(body, dict) and isinstance(body.get("episode"), dict):
    source_id = str(body["episode"].get("source_id") or "")

  return {
    "source_id": source_id,
    "response": body,
  }


def run_update_intro_copy(args: argparse.Namespace) -> dict[str, Any]:
  source_id = args.source_id.strip()
  if not source_id:
    raise ClientError(
      code="E_VALIDATION",
      message="--source-id is required.",
      retryable=False,
      hint="Use list-backlog-episodes first, then pass its source_id.",
      exit_code=2,
    )

  payload = ensure_mapping(load_json_file(args.payload_file), "update-intro-copy")
  validate_intro_copy_payload(payload)
  payload = normalize_intro_copy_payload(payload)
  encoded_source_id = urlparse.quote(source_id, safe="")
  url = build_url(FIXED_API_BASE_URL, f"/api/episodes/{encoded_source_id}/intro")

  if args.dry_run:
    return {
      "dry_run": True,
      "request": {"method": "PATCH", "url": url, "payload": payload},
    }

  body = request_json("PATCH", url, args.timeout_seconds, payload)

  response_source_id = source_id
  if isinstance(body, dict) and isinstance(body.get("episode"), dict):
    response_source_id = str(body["episode"].get("source_id") or source_id)

  return {
    "source_id": response_source_id,
    "response": body,
  }


def make_envelope(
  command: str,
  status: str,
  data: Any,
  error: dict[str, Any] | None,
  request_id: str,
  duration_ms: int,
) -> dict[str, Any]:
  return {
    "schema_version": SCHEMA_VERSION,
    "command": command,
    "status": status,
    "data": data,
    "error": error,
    "meta": {
      "request_id": request_id,
      "duration_ms": duration_ms,
      "timestamp_utc": now_utc_iso(),
    },
  }


def resolve_output_mode(args: argparse.Namespace) -> str:
  if args.json:
    return "json"
  if args.human:
    return "human"
  if args.plain:
    return "plain"
  return "human" if sys.stdout.isatty() else "json"


def print_human_success(command: str, data: dict[str, Any]) -> None:
  if command == "list-backlog-episodes":
    items = data.get("items", [])
    print(f"Found {data.get('count', len(items))} backlog episode(s).")
    for item in items:
      print(f"- {item.get('source_id', '')} | {item.get('show', '')} | {item.get('title', '')}")
    return

  if command in ("submit-episode", "update-intro-copy"):
    source_id = data.get("source_id")
    if source_id:
      print(f"Completed {command}. source_id={source_id}")
    else:
      print(f"Completed {command}.")
    return

  print(json.dumps(data, ensure_ascii=True))


def print_plain_success(command: str, data: dict[str, Any]) -> None:
  if command == "list-backlog-episodes":
    print("source_id\tshow\tstatus\ttitle")
    for item in data.get("items", []):
      print(
        f"{item.get('source_id', '')}\t{item.get('show', '')}\t{item.get('status', '')}\t{item.get('title', '')}"
      )
    return

  if command in ("submit-episode", "update-intro-copy"):
    print(str(data.get("source_id") or ""))
    return

  print(json.dumps(data, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    prog="ai_podcasting_client",
    description="Agent-first client for AI Podcasting episode operations.",
  )

  output_group = parser.add_mutually_exclusive_group()
  output_group.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
  output_group.add_argument("--human", action="store_true", help="Emit concise human-readable output.")
  output_group.add_argument("--plain", action="store_true", help="Emit stable plain-text output.")

  parser.add_argument(
    "--timeout-seconds",
    type=float,
    default=30.0,
    help="HTTP timeout in seconds (default: 30).",
  )
  parser.add_argument(
    "--request-id",
    default="",
    help="Optional request id for correlation. Auto-generated when omitted.",
  )
  parser.add_argument(
    "--no-input",
    action="store_true",
    help="Run non-interactively (accepted for agent compatibility).",
  )
  subparsers = parser.add_subparsers(dest="command", required=True)

  list_parser = subparsers.add_parser(
    "list-backlog-episodes",
    help=f"List non-published {FIXED_SHOW} episodes and return source_id values.",
  )
  list_parser.add_argument("--start-date", default="", help="Optional start date YYYY-MM-DD.")
  list_parser.add_argument("--end-date", default="", help="Optional end date YYYY-MM-DD.")
  list_parser.add_argument("--limit", type=int, default=200, help="Max episodes to return.")
  list_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show outbound request shape without calling the API.",
  )

  submit_parser = subparsers.add_parser(
    "submit-episode",
    help="Submit a new episode payload to /api/episodes/submit.",
  )
  submit_parser.add_argument("--payload-file", required=True, help="Path to JSON payload file.")
  submit_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show outbound request shape without calling the API.",
  )

  intro_parser = subparsers.add_parser(
    "update-intro-copy",
    help="Patch intro/title/thumbnail/editor copy for an episode.",
  )
  intro_parser.add_argument("--source-id", required=True, help="Episode source_id.")
  intro_parser.add_argument(
    "--payload-file",
    required=True,
    help=(
      "Path to JSON payload file. Supports the current app intro payload directly, "
      "or the user-facing convenience fields "
      "(recordingLink/title/thumbnailText/videoThumbnails/audioThumbnailLink/outroMusicLink). "
      "Provide one or multiple video thumbnail URLs and the client will normalize them "
      "into the app's thumbnail shape."
    ),
  )
  intro_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show outbound request shape without calling the API.",
  )

  return parser


def main() -> int:
  parser = build_parser()
  args = parser.parse_args()

  request_id = args.request_id or str(uuid.uuid4())
  mode = resolve_output_mode(args)
  start = time.perf_counter()

  try:
    if args.command == "list-backlog-episodes":
      data = run_list_backlog_episodes(args)
    elif args.command == "submit-episode":
      data = run_submit_episode(args)
    elif args.command == "update-intro-copy":
      data = run_update_intro_copy(args)
    else:
      raise ClientError(
        code="E_VALIDATION",
        message=f"Unsupported command: {args.command}",
        retryable=False,
        hint="Run with --help for supported commands.",
        exit_code=2,
      )

    duration_ms = int((time.perf_counter() - start) * 1000)

    if mode == "json":
      print(
        json.dumps(
          make_envelope(
            command=args.command,
            status="ok",
            data=data,
            error=None,
            request_id=request_id,
            duration_ms=duration_ms,
          ),
          ensure_ascii=True,
        )
      )
    elif mode == "plain":
      print_plain_success(args.command, data)
    else:
      print_human_success(args.command, data)

    return 0
  except ClientError as exc:
    duration_ms = int((time.perf_counter() - start) * 1000)
    error_payload = {
      "code": exc.code,
      "message": exc.message,
      "retryable": exc.retryable,
      "hint": exc.hint,
    }

    if mode == "json":
      print(
        json.dumps(
          make_envelope(
            command=args.command,
            status="error",
            data=None,
            error=error_payload,
            request_id=request_id,
            duration_ms=duration_ms,
          ),
          ensure_ascii=True,
        )
      )
    else:
      print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)
      if exc.hint:
        print(f"Hint: {exc.hint}", file=sys.stderr)

    return exc.exit_code
  except Exception as exc:  # pragma: no cover
    duration_ms = int((time.perf_counter() - start) * 1000)
    error_payload = {
      "code": "E_INTERNAL",
      "message": str(exc),
      "retryable": False,
      "hint": "Inspect traceback and retry.",
    }

    if mode == "json":
      print(
        json.dumps(
          make_envelope(
            command=args.command,
            status="error",
            data=None,
            error=error_payload,
            request_id=request_id,
            duration_ms=duration_ms,
          ),
          ensure_ascii=True,
        )
      )
    else:
      print(f"Error [E_INTERNAL]: {exc}", file=sys.stderr)

    return 1


if __name__ == "__main__":
  raise SystemExit(main())
