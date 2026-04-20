#!/usr/bin/env python3
"""Agent-first CLI for AI Podcasting episode operations."""

from __future__ import annotations

import argparse
import html
import json
import re
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
from aip_local_upload_helper import (
  UploadHelperError,
  resolve_upload_source_url,
  validate_upload_source_list,
)

SCHEMA_VERSION = "1.0"
FIXED_API_BASE_URL = "https://app.aipodcast.ing"
FIXED_SHOW = "TCR"
TEXT_PREVIEW_LIMIT = 280
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
PUBLICATION_STATE_VALUES = ("all", "published", "unpublished")
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
TCR_MAIN_MP3_MESSAGE = (
  "TCR submit-episode main file cannot be an MP3 link."
)
TCR_MAIN_MP3_HINT = (
  "Use the original recording/session/video source link for the main file, such as Riverside, "
  "YouTube, or a direct video file. MP3 links remain valid for intro/outro/supporting file fields "
  "when those fields expect audio."
)


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

  main_episode_file = payload.get("mainEpisodeFile")
  file_url = payload.get("fileUrl")
  files = payload.get("files")
  has_main_raw = (
    isinstance(files, dict)
    and isinstance(files.get("main"), dict)
    and isinstance(files["main"].get("raw"), str)
    and bool(files["main"]["raw"].strip())
  )
  has_main_episode_file = isinstance(main_episode_file, str) and bool(main_episode_file.strip())
  has_file_url = isinstance(file_url, str) and bool(file_url.strip())

  normalized_main_episode_file = str(main_episode_file).strip() if has_main_episode_file else ""
  normalized_file_url = str(file_url).strip() if has_file_url else ""
  normalized_main_raw = str(files["main"]["raw"]).strip() if has_main_raw else ""
  candidate_sources: list[tuple[str, str]] = []
  if has_main_episode_file:
    candidate_sources.append(("mainEpisodeFile", normalized_main_episode_file))
  if has_file_url:
    candidate_sources.append(("fileUrl", normalized_file_url))
  if has_main_raw:
    candidate_sources.append(("files.main.raw", normalized_main_raw))

  unique_source_values = {value for _, value in candidate_sources}
  if len(unique_source_values) > 1:
    conflicting_fields = ", ".join(field for field, _ in candidate_sources)
    raise ClientError(
      code="E_VALIDATION",
      message=f"submit-episode payload has conflicting main file values across {conflicting_fields}.",
      retryable=False,
      hint="Provide one main episode file, or keep all aliases identical.",
      exit_code=2,
    )

  if not candidate_sources:
    raise ClientError(
      code="E_VALIDATION",
      message="submit-episode payload requires a main episode file.",
      retryable=False,
      hint="Use references/submit-episode.example.json as baseline.",
      exit_code=2,
    )

  main_source_value = candidate_sources[0][1]
  validate_upload_source_list("submit-episode main file", [main_source_value])
  if looks_like_mp3_source(main_source_value):
    raise ClientError(
      code="E_VALIDATION",
      message=TCR_MAIN_MP3_MESSAGE,
      retryable=False,
      hint=TCR_MAIN_MP3_HINT,
      exit_code=2,
    )


def looks_like_mp3_source(value: str) -> bool:
  """Return whether a public URL or local path appears to point at an MP3 file."""
  candidate = value.strip()
  if not candidate:
    return False
  parsed = urlparse.urlparse(candidate)
  path = parsed.path if parsed.scheme else candidate
  path = path.split("?", 1)[0].split("#", 1)[0]
  return urlparse.unquote(path).lower().endswith(".mp3")


def validate_intro_copy_payload(payload: dict[str, Any]) -> None:
  if not payload:
    raise ClientError(
      code="E_VALIDATION",
      message="update-intro-copy payload must not be empty.",
      retryable=False,
      hint="Provide at least one intro field to update.",
      exit_code=2,
    )

  recording_link = payload.get("recordingLink", payload.get("introFile"))
  if isinstance(recording_link, str) and recording_link.strip():
    validate_upload_source_list("recordingLink", [recording_link.strip()])

  title = payload.get("title")
  if "title" in payload and (not isinstance(title, str) or not title.strip()):
    raise ClientError(
      code="E_VALIDATION",
      message="title must be a non-empty string when provided.",
      retryable=False,
      hint="Omit title if you are not updating it.",
      exit_code=2,
    )

  thumbnail_text = payload.get("thumbnailText")
  if "thumbnailText" in payload and (
    not isinstance(thumbnail_text, str) or not thumbnail_text.strip()
  ):
    raise ClientError(
      code="E_VALIDATION",
      message="thumbnailText must be a non-empty string when provided.",
      retryable=False,
      hint="Omit thumbnailText if you are not updating it.",
      exit_code=2,
    )

  transcript = payload.get("transcript", payload.get("introTranscript"))
  if (
    "transcript" in payload or "introTranscript" in payload
  ) and (not isinstance(transcript, str) or not transcript.strip()):
    raise ClientError(
      code="E_VALIDATION",
      message="transcript must be a non-empty string when provided.",
      retryable=False,
      hint="Omit transcript if you are not updating it.",
      exit_code=2,
    )

  instructions_to_editor = payload.get("instructionsToEditor", payload.get("editorInstructions"))
  if (
    "instructionsToEditor" in payload or "editorInstructions" in payload
  ) and (not isinstance(instructions_to_editor, str) or not instructions_to_editor.strip()):
    raise ClientError(
      code="E_VALIDATION",
      message="instructionsToEditor must be a non-empty string when provided.",
      retryable=False,
      hint="Omit instructionsToEditor if you are not updating it.",
      exit_code=2,
    )

  video_thumbnail_links = normalize_video_thumbnail_links(payload)
  if video_thumbnail_links:
    validate_upload_source_list("videoThumbnails", video_thumbnail_links)

  audio_thumbnail_link = payload.get("audioThumbnailLink")
  if isinstance(audio_thumbnail_link, str) and audio_thumbnail_link.strip():
    validate_upload_source_list("audioThumbnailLink", [audio_thumbnail_link.strip()])

  outro_music_link = payload.get("outroMusicLink")
  if isinstance(outro_music_link, str) and outro_music_link.strip():
    validate_upload_source_list("outroMusicLink", [outro_music_link.strip()])


def normalize_submit_payload(
  payload: dict[str, Any],
  timeout_seconds: float,
  dry_run: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
  normalized = json.loads(json.dumps(payload))
  upload_records: list[dict[str, Any]] = []
  main_file_value = ""
  main_file_field = ""

  files = normalized.get("files")
  if (
    isinstance(files, dict)
    and isinstance(files.get("main"), dict)
    and isinstance(files["main"].get("raw"), str)
    and files["main"]["raw"].strip()
  ):
    main_file_value = files["main"]["raw"].strip()
    main_file_field = "files.main.raw"
  elif (
    isinstance(normalized.get("mainEpisodeFile"), str)
    and normalized["mainEpisodeFile"].strip()
  ):
    main_file_value = normalized["mainEpisodeFile"].strip()
    main_file_field = "mainEpisodeFile"
  elif isinstance(normalized.get("fileUrl"), str) and normalized["fileUrl"].strip():
    main_file_value = normalized["fileUrl"].strip()
    main_file_field = "fileUrl"

  if main_file_value:
    resolved_main_file, upload_record = resolve_upload_source_url(
      main_file_value,
      main_file_field,
      timeout_seconds,
      dry_run,
    )
    files = normalized.setdefault("files", {})
    if isinstance(files, dict):
      main = files.setdefault("main", {})
      if isinstance(main, dict):
        main["raw"] = resolved_main_file
    if upload_record:
      upload_records.append(upload_record)

  normalized.pop("fileUrl", None)
  normalized.pop("mainEpisodeFile", None)

  asset_urls = normalized.get("assetUrls")
  if isinstance(asset_urls, list):
    resolved_asset_urls: list[str] = []
    for index, asset_url in enumerate(asset_urls):
      if not isinstance(asset_url, str) or not asset_url.strip():
        continue
      resolved_url, upload_record = resolve_upload_source_url(
        asset_url,
        f"assetUrls[{index}]",
        timeout_seconds,
        dry_run,
      )
      resolved_asset_urls.append(resolved_url)
      if upload_record:
        upload_records.append(upload_record)
    normalized["assetUrls"] = resolved_asset_urls

  return normalized, upload_records


def normalize_intro_copy_payload(
  payload: dict[str, Any],
  timeout_seconds: float,
  dry_run: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
  normalized: dict[str, Any] = {}
  upload_records: list[dict[str, Any]] = []
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

  if isinstance(normalized.get("introFile"), str) and normalized["introFile"].strip():
    resolved_url, upload_record = resolve_upload_source_url(
      normalized["introFile"],
      "introFile",
      timeout_seconds,
      dry_run,
    )
    normalized["introFile"] = resolved_url
    if upload_record:
      upload_records.append(upload_record)

  deliverables = normalized.get("deliverables")
  if isinstance(deliverables, dict):
    thumbnails = deliverables.get("thumbnails")
    if isinstance(thumbnails, dict):
      video = thumbnails.get("video")
      if isinstance(video, dict):
        current_url = video.get("url")
        if isinstance(current_url, str) and current_url.strip():
          resolved_url, upload_record = resolve_upload_source_url(
            current_url,
            "deliverables.thumbnails.video.url",
            timeout_seconds,
            dry_run,
          )
          video["url"] = resolved_url
          if upload_record:
            upload_records.append(upload_record)

        variants = video.get("variants")
        if isinstance(variants, list):
          resolved_variants: list[dict[str, Any]] = []
          for index, variant in enumerate(variants):
            if not isinstance(variant, dict):
              continue
            variant_copy = dict(variant)
            variant_url = variant_copy.get("url")
            if not isinstance(variant_url, str) or not variant_url.strip():
              continue
            resolved_url, upload_record = resolve_upload_source_url(
              variant_url,
              f"deliverables.thumbnails.video.variants[{index}].url",
              timeout_seconds,
              dry_run,
            )
            variant_copy["url"] = resolved_url
            resolved_variants.append(variant_copy)
            if upload_record:
              upload_records.append(upload_record)
          video["variants"] = resolved_variants

        ensure_video_thumbnail_payload(video)

      audio = thumbnails.get("audio")
      if isinstance(audio, dict):
        audio_url = audio.get("url")
        if isinstance(audio_url, str) and audio_url.strip():
          resolved_url, upload_record = resolve_upload_source_url(
            audio_url,
            "deliverables.thumbnails.audio.url",
            timeout_seconds,
            dry_run,
          )
          audio["url"] = resolved_url
          if upload_record:
            upload_records.append(upload_record)

  files = normalized.get("files")
  if isinstance(files, dict):
    episode_outro = files.get("episode_outro")
    if isinstance(episode_outro, dict):
      edited_url = episode_outro.get("edited")
      if isinstance(edited_url, str) and edited_url.strip():
        resolved_url, upload_record = resolve_upload_source_url(
          edited_url,
          "files.episode_outro.edited",
          timeout_seconds,
          dry_run,
        )
        episode_outro["edited"] = resolved_url
        if upload_record:
          upload_records.append(upload_record)

  return normalized, upload_records


def normalize_optional_string(value: Any) -> str | None:
  if not isinstance(value, str):
    return None

  candidate = value.strip()
  return candidate or None


def first_non_empty_string(*values: Any) -> str | None:
  for value in values:
    candidate = normalize_optional_string(value)
    if candidate is not None:
      return candidate

  return None


def normalize_string_list(value: Any) -> list[str]:
  if not isinstance(value, list):
    return []

  normalized: list[str] = []
  for item in value:
    candidate = normalize_optional_string(item)
    if candidate is not None:
      normalized.append(candidate)

  return normalized


def compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
  compacted: dict[str, Any] = {}
  for key, item in value.items():
    if item is None:
      continue

    if isinstance(item, str) and not item:
      continue

    if isinstance(item, list) and not item:
      continue

    if isinstance(item, dict):
      nested = compact_mapping(item)
      if not nested:
        continue
      compacted[key] = nested
      continue

    compacted[key] = item

  return compacted


def normalize_text_for_preview(value: Any) -> str:
  candidate = normalize_optional_string(value)
  if candidate is None:
    return ""

  normalized = html.unescape(candidate).replace("\xa0", " ")
  without_tags = HTML_TAG_RE.sub(" ", normalized)
  return WHITESPACE_RE.sub(" ", without_tags).strip()


def build_text_preview(value: Any, limit: int = TEXT_PREVIEW_LIMIT) -> dict[str, Any]:
  normalized = normalize_text_for_preview(value)
  if not normalized:
    return {"preview": None, "length": 0}

  if len(normalized) <= limit:
    return {"preview": normalized, "length": len(normalized)}

  preview_length = max(0, limit - 3)
  preview = normalized[:preview_length].rstrip()
  return {"preview": f"{preview}...", "length": len(normalized)}


def normalize_guests(value: Any) -> list[dict[str, Any]]:
  if not isinstance(value, list):
    return []

  guests: list[dict[str, Any]] = []
  for item in value:
    if not isinstance(item, dict):
      continue

    name = normalize_optional_string(item.get("name"))
    if name is None:
      continue

    guests.append(
      compact_mapping(
        {
          "name": name,
          "email": normalize_optional_string(item.get("email")),
          "title": normalize_optional_string(item.get("title")),
          "company": normalize_optional_string(item.get("company")),
        }
      )
    )

  return guests


def normalize_file_urls(value: Any) -> dict[str, Any] | None:
  if not isinstance(value, dict):
    return None

  normalized = compact_mapping(
    {
      "raw": normalize_optional_string(value.get("raw")),
      "edited": normalize_optional_string(value.get("edited")),
      "descript": normalize_optional_string(value.get("descript")),
    }
  )
  return normalized or None


def normalize_episode_files(value: Any) -> dict[str, Any]:
  files = value if isinstance(value, dict) else {}
  return compact_mapping(
    {
      "main": normalize_file_urls(files.get("main")),
      "intro": normalize_file_urls(files.get("intro")),
      "teaser": normalize_file_urls(files.get("teaser")),
      "special_sponsor": normalize_file_urls(files.get("special_sponsor")),
      "episode_outro": normalize_file_urls(files.get("episode_outro")),
    }
  )


def normalize_platforms(value: Any) -> list[dict[str, Any]]:
  if not isinstance(value, list):
    return []

  platforms: list[dict[str, Any]] = []
  for item in value:
    if not isinstance(item, dict):
      continue

    name = normalize_optional_string(item.get("name"))
    if name is None:
      continue

    platforms.append(
      compact_mapping(
        {
          "name": name,
          "url": normalize_optional_string(item.get("url")),
          "status": normalize_optional_string(item.get("status")),
          "publishedAt": normalize_optional_string(item.get("publishedAt")),
        }
      )
    )

  return platforms


def normalize_deliverable_asset(value: Any) -> dict[str, Any] | None:
  if not isinstance(value, dict):
    return None

  normalized = compact_mapping(
    {
      "url": normalize_optional_string(value.get("url")),
      "source_id": normalize_optional_string(value.get("source_id")),
      "created_at": normalize_optional_string(value.get("created_at")),
    }
  )
  return normalized or None


def normalize_deliverable_variants(value: Any) -> list[dict[str, Any]]:
  if not isinstance(value, list):
    return []

  variants: list[dict[str, Any]] = []
  for item in value:
    if not isinstance(item, dict):
      continue

    url = normalize_optional_string(item.get("url"))
    if url is None:
      continue

    variants.append(
      compact_mapping(
        {
          "url": url,
          "design_source_url": normalize_optional_string(item.get("design_source_url")),
          "source": normalize_optional_string(item.get("source")),
          "title_text": normalize_optional_string(item.get("title_text")),
          "template": normalize_optional_string(item.get("template")),
          "created_at": normalize_optional_string(item.get("created_at")),
        }
      )
    )

  return variants


def normalize_artwork(value: Any, deliverables_value: Any) -> dict[str, Any]:
  artwork = value if isinstance(value, dict) else {}
  deliverables = deliverables_value if isinstance(deliverables_value, dict) else {}
  thumbnails = deliverables.get("thumbnails")
  thumbnails_dict = thumbnails if isinstance(thumbnails, dict) else {}
  video = thumbnails_dict.get("video")
  video_dict = video if isinstance(video, dict) else {}
  audio = thumbnails_dict.get("audio")
  audio_dict = audio if isinstance(audio, dict) else {}

  return compact_mapping(
    {
      "videoThumbnailUrl": first_non_empty_string(
        artwork.get("videoThumbnailUrl"),
        video_dict.get("url"),
      ),
      "videoThumbnailDesignSourceUrl": first_non_empty_string(
        artwork.get("videoThumbnailDesignSourceUrl"),
        video_dict.get("design_source_url"),
      ),
      "audioThumbnailUrl": first_non_empty_string(
        artwork.get("audioThumbnailUrl"),
        audio_dict.get("url"),
      ),
      "videoThumbnailVariants": normalize_deliverable_variants(video_dict.get("variants")),
    }
  )


def normalize_deliverables(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    return {}

  media = value.get("media")
  media_dict = media if isinstance(media, dict) else {}
  media_video = media_dict.get("video")
  media_video_dict = media_video if isinstance(media_video, dict) else {}
  media_audio = media_dict.get("audio")
  media_audio_dict = media_audio if isinstance(media_audio, dict) else {}

  text = value.get("text")
  text_dict = text if isinstance(text, dict) else {}
  transcript = text_dict.get("transcript")
  transcript_dict = transcript if isinstance(transcript, dict) else {}
  chapters = text_dict.get("chapters")
  chapters_dict = chapters if isinstance(chapters, dict) else {}
  references = text_dict.get("references")
  references_dict = references if isinstance(references, dict) else {}
  show_notes = text_dict.get("show_notes")
  show_notes_dict = show_notes if isinstance(show_notes, dict) else {}

  links = value.get("links")
  links_dict = links if isinstance(links, dict) else {}
  social = value.get("social")
  social_dict = social if isinstance(social, dict) else {}

  return compact_mapping(
    {
      "video": compact_mapping(
        {
          "main": normalize_deliverable_asset(media_video_dict.get("main")),
          "main_4k": normalize_deliverable_asset(media_video_dict.get("main_4k")),
          "main_1080p": normalize_deliverable_asset(media_video_dict.get("main_1080p")),
          "trailer": normalize_deliverable_asset(media_video_dict.get("trailer")),
        }
      ),
      "audio": compact_mapping(
        {
          "main": normalize_deliverable_asset(media_audio_dict.get("main")),
          "enhanced": normalize_deliverable_asset(media_audio_dict.get("enhanced")),
        }
      ),
      "text": compact_mapping(
        {
          "transcriptHtml": normalize_deliverable_asset(transcript_dict.get("html")),
          "transcriptTxt": normalize_deliverable_asset(transcript_dict.get("txt")),
          "transcriptVtt": normalize_deliverable_asset(transcript_dict.get("vtt")),
          "transcriptSrt": normalize_deliverable_asset(transcript_dict.get("srt")),
          "chaptersTxt": normalize_deliverable_asset(chapters_dict.get("txt")),
          "chaptersJson": normalize_deliverable_asset(chapters_dict.get("json")),
          "referencesTxt": normalize_deliverable_asset(references_dict.get("txt")),
          "referencesJson": normalize_deliverable_asset(references_dict.get("json")),
          "showNotesTxt": normalize_deliverable_asset(show_notes_dict.get("txt")),
          "showNotesHtml": normalize_deliverable_asset(show_notes_dict.get("html")),
        }
      ),
      "links": compact_mapping(
        {
          "newsletter": normalize_optional_string(links_dict.get("newsletter")),
          "review": normalize_optional_string(links_dict.get("review")),
        }
      ),
      "social": compact_mapping(
        {
          "clip_ids": normalize_string_list(social_dict.get("clip_ids")),
          "clip_urls": normalize_string_list(social_dict.get("clip_urls")),
        }
      ),
    }
  )


def normalize_processed_assets(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    return {}

  episode = value.get("episode")
  episode_dict = episode if isinstance(episode, dict) else {}

  return compact_mapping(
    {
      "clips": normalize_string_list(value.get("clips")),
      "reviewUrl": normalize_optional_string(episode_dict.get("review")),
      "transcriptHtmlUrl": normalize_optional_string(value.get("transcript_html_url")),
      "newsletterUrl": normalize_optional_string(value.get("newsletter_url")),
      "packagedVideoUrl": normalize_optional_string(value.get("packaged_video_url")),
      "packagedVideo4kUrl": normalize_optional_string(value.get("packaged_video_4k_url")),
      "packagedAudioUrl": normalize_optional_string(value.get("packaged_audio_url")),
      "packagedTrailerUrl": normalize_optional_string(value.get("packaged_trailer_url")),
      "transcriptTextUrl": normalize_optional_string(value.get("transcript_text_url")),
      "chapterTextUrl": normalize_optional_string(value.get("chapter_text_url")),
      "referencesTextUrl": normalize_optional_string(value.get("references_text_url")),
      "showNotesTextUrl": normalize_optional_string(value.get("show_notes_text_url")),
    }
  )


def normalize_ads(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    return {}

  return compact_mapping({"midRollTimes": normalize_string_list(value.get("midRollTimes"))})


def normalize_shownotes(value: Any) -> dict[str, Any]:
  if not isinstance(value, dict):
    return {}

  main_description = build_text_preview(value.get("mainDescriptionHtml"))
  extracted_links = build_text_preview(value.get("extractedLinksHtml"))
  display_main_description = build_text_preview(value.get("displayMainDescriptionHtml"))
  display_extracted_links = build_text_preview(value.get("displayExtractedLinksHtml"))

  return compact_mapping(
    {
      "mainDescriptionPreview": main_description["preview"],
      "mainDescriptionLength": (
        main_description["length"] if main_description["length"] > 0 else None
      ),
      "extractedLinksPreview": extracted_links["preview"],
      "extractedLinksLength": (
        extracted_links["length"] if extracted_links["length"] > 0 else None
      ),
      "displayMainDescriptionPreview": display_main_description["preview"],
      "displayMainDescriptionLength": (
        display_main_description["length"] if display_main_description["length"] > 0 else None
      ),
      "displayExtractedLinksPreview": display_extracted_links["preview"],
      "displayExtractedLinksLength": (
        display_extracted_links["length"] if display_extracted_links["length"] > 0 else None
      ),
    }
  )


def sanitize_raw_episode(item: dict[str, Any]) -> dict[str, Any]:
  sanitized = json.loads(json.dumps(item))
  if isinstance(sanitized, dict):
    sanitized.pop("billing", None)
  return sanitized


def normalize_episode_item(item: dict[str, Any], include_raw: bool = False) -> dict[str, Any]:
  submission = item.get("submission") if isinstance(item.get("submission"), dict) else {}
  production = item.get("production") if isinstance(item.get("production"), dict) else {}
  publishing = item.get("publishing") if isinstance(item.get("publishing"), dict) else {}
  deliverables = item.get("deliverables")
  processed_assets = item.get("processed_assets")

  title = ""
  if isinstance(item.get("title"), str):
    title = item["title"].strip()
  elif isinstance(submission.get("title"), str):
    title = submission["title"].strip()

  status = ""
  if isinstance(publishing.get("status"), str):
    status = publishing["status"].strip()

  show_notes_preview = build_text_preview(submission.get("showNotes"))
  intro_transcript_preview = build_text_preview(submission.get("introTranscript"))
  editor_instructions_preview = build_text_preview(submission.get("editorInstructions"))
  title_inspiration_preview = build_text_preview(submission.get("titleInspiration"))
  editor_notes_preview = build_text_preview(production.get("editorNotes"))
  current_job = publishing.get("currentJob") if isinstance(publishing.get("currentJob"), dict) else {}
  duration = production.get("duration")

  normalized = compact_mapping(
    {
      "source_id": str(item.get("source_id") or "").strip(),
      "title": title,
      "show": str(item.get("show") or "").strip(),
      "status": status,
      "thumbnailText": first_non_empty_string(
        item.get("thumbnailText"),
        submission.get("thumbnailText"),
      ),
      "submissionTitle": normalize_optional_string(submission.get("title")),
      "submissionThumbnailText": normalize_optional_string(submission.get("thumbnailText")),
      "created_at": normalize_optional_string(item.get("created_at")),
      "updated_at": normalize_optional_string(item.get("updated_at")),
      "needsGuestReview": (
        item.get("needsGuestReview")
        if isinstance(item.get("needsGuestReview"), bool)
        else None
      ),
      "guests": normalize_guests(submission.get("guests")),
      "assetUrls": normalize_string_list(submission.get("assetUrls")),
      "publishing": compact_mapping(
        {
          "status": status,
          "scheduledDate": normalize_optional_string(publishing.get("scheduledDate")),
          "publishedDate": normalize_optional_string(publishing.get("publishedDate")),
          "platforms": normalize_platforms(publishing.get("platforms")),
          "currentJob": compact_mapping(
            {
              "jobId": normalize_optional_string(current_job.get("jobId")),
              "startedAt": normalize_optional_string(current_job.get("startedAt")),
            }
          ),
        }
      ),
      "production": compact_mapping(
        {
          "priority": normalize_optional_string(production.get("priority")),
          "editorName": normalize_optional_string(production.get("editorName")),
          "duration": (
            duration
            if isinstance(duration, (int, float)) and not isinstance(duration, bool)
            else None
          ),
          "tags": normalize_string_list(production.get("tags")),
        }
      ),
      "copy": compact_mapping(
        {
          "showNotesPreview": show_notes_preview["preview"],
          "showNotesLength": (
            show_notes_preview["length"] if show_notes_preview["length"] > 0 else None
          ),
          "introTranscriptPreview": intro_transcript_preview["preview"],
          "introTranscriptLength": (
            intro_transcript_preview["length"]
            if intro_transcript_preview["length"] > 0
            else None
          ),
          "editorInstructionsPreview": editor_instructions_preview["preview"],
          "editorInstructionsLength": (
            editor_instructions_preview["length"]
            if editor_instructions_preview["length"] > 0
            else None
          ),
          "titleInspirationPreview": title_inspiration_preview["preview"],
          "titleInspirationLength": (
            title_inspiration_preview["length"]
            if title_inspiration_preview["length"] > 0
            else None
          ),
          "editorNotesPreview": editor_notes_preview["preview"],
          "editorNotesLength": (
            editor_notes_preview["length"] if editor_notes_preview["length"] > 0 else None
          ),
        }
      ),
      "files": normalize_episode_files(item.get("files")),
      "artwork": normalize_artwork(item.get("artwork"), deliverables),
      "deliverables": normalize_deliverables(deliverables),
      "processedAssets": normalize_processed_assets(processed_assets),
      "ads": normalize_ads(item.get("ads")),
      "shownotes": normalize_shownotes(item.get("shownotes")),
    }
  )

  if include_raw:
    normalized["raw_episode"] = sanitize_raw_episode(item)

  return normalized


def is_published_episode(item: dict[str, Any]) -> bool:
  publishing = item.get("publishing")
  if not isinstance(publishing, dict):
    return False

  status = normalize_optional_string(publishing.get("status"))
  return (status or "").lower() == "published"


def parse_optional_iso_datetime(value: Any) -> datetime | None:
  candidate = normalize_optional_string(value)
  if candidate is None:
    return None

  normalized = f"{candidate[:-1]}+00:00" if candidate.endswith("Z") else candidate

  try:
    parsed = datetime.fromisoformat(normalized)
  except ValueError:
    return None

  if parsed.tzinfo is None:
    return parsed.replace(tzinfo=timezone.utc)

  return parsed.astimezone(timezone.utc)


def get_episode_sort_datetime(item: dict[str, Any], publication_state: str) -> datetime:
  publishing = item.get("publishing") if isinstance(item.get("publishing"), dict) else {}

  if publication_state == "unpublished":
    candidate_values = [
      publishing.get("scheduledDate"),
      item.get("updated_at"),
      item.get("created_at"),
      publishing.get("publishedDate"),
    ]
  else:
    candidate_values = [
      publishing.get("publishedDate"),
      publishing.get("scheduledDate"),
      item.get("updated_at"),
      item.get("created_at"),
    ]

  for value in candidate_values:
    parsed = parse_optional_iso_datetime(value)
    if parsed is not None:
      return parsed

  return datetime.min.replace(tzinfo=timezone.utc)


def sort_episode_items(
  items: list[dict[str, Any]],
  publication_state: str,
) -> list[dict[str, Any]]:
  return sorted(
    items,
    key=lambda item: (
      get_episode_sort_datetime(item, publication_state),
      normalize_optional_string(item.get("source_id")) or "",
    ),
    reverse=True,
  )


def filter_episode_items(
  items: list[dict[str, Any]],
  publication_state: str,
) -> list[dict[str, Any]]:
  if publication_state == "all":
    return items

  filtered: list[dict[str, Any]] = []
  for item in items:
    published = is_published_episode(item)
    if publication_state == "published" and published:
      filtered.append(item)
    elif publication_state == "unpublished" and not published:
      filtered.append(item)

  return filtered


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


def build_list_filters(args: argparse.Namespace) -> dict[str, Any]:
  return {
    "show": FIXED_SHOW,
    "publication_state": args.publication_state,
    "start_date": args.start_date or None,
    "end_date": args.end_date or None,
    "limit": args.limit,
    "include_raw": bool(args.include_raw),
  }


def run_list_episodes(args: argparse.Namespace) -> dict[str, Any]:
  include_published = args.publication_state in ("all", "published")
  params = {
    "includePublished": "true" if include_published else "false",
    "show": FIXED_SHOW,
    "startDate": args.start_date or "",
    "endDate": args.end_date or "",
  }
  url = build_url(FIXED_API_BASE_URL, "/api/episodes", params)
  filters = build_list_filters(args)

  if args.dry_run:
    return {
      "dry_run": True,
      "filters": filters,
      "request": {"method": "GET", "url": url},
    }

  body = request_json("GET", url, args.timeout_seconds)
  matched_items = filter_episode_items(extract_episode_items(body), args.publication_state)
  matched_items = sort_episode_items(matched_items, args.publication_state)
  matched_count = len(matched_items)
  items = [normalize_episode_item(item, include_raw=args.include_raw) for item in matched_items]

  if args.limit is not None and args.limit >= 0:
    items = items[: args.limit]

  return {
    "count": len(items),
    "matched_count": matched_count,
    "detail_level": "summary+raw" if args.include_raw else "summary",
    "filters": filters,
    "items": items,
  }


def run_submit_episode(args: argparse.Namespace) -> dict[str, Any]:
  payload = ensure_mapping(load_json_file(args.payload_file), "submit-episode")
  validate_submit_payload(payload)
  payload, upload_records = normalize_submit_payload(payload, args.timeout_seconds, args.dry_run)
  payload["show"] = FIXED_SHOW

  url = build_url(FIXED_API_BASE_URL, "/api/episodes/submit")

  if args.dry_run:
    return {
      "dry_run": True,
      "planned_uploads": upload_records,
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
      hint="Use list-episodes first, then pass its source_id.",
      exit_code=2,
    )

  payload = ensure_mapping(load_json_file(args.payload_file), "update-intro-copy")
  validate_intro_copy_payload(payload)
  payload, upload_records = normalize_intro_copy_payload(
    payload,
    args.timeout_seconds,
    args.dry_run,
  )
  encoded_source_id = urlparse.quote(source_id, safe="")
  url = build_url(FIXED_API_BASE_URL, f"/api/episodes/{encoded_source_id}/intro")

  if args.dry_run:
    return {
      "dry_run": True,
      "planned_uploads": upload_records,
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
  return "json"


def print_human_success(command: str, data: dict[str, Any]) -> None:
  if command == "list-episodes":
    items = data.get("items", [])
    matched_count = data.get("matched_count", len(items))
    filters = data.get("filters", {})
    publication_state = filters.get("publication_state", "all")
    print(f"Found {data.get('count', len(items))} of {matched_count} {publication_state} episode(s).")
    for item in items:
      print(
        f"- {item.get('source_id', '')} | {item.get('show', '')} | {item.get('status', '')} | {item.get('title', '')}"
      )
      thumbnail_text = item.get("thumbnailText")
      if thumbnail_text:
        print(f"  thumbnailText: {thumbnail_text}")
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
  if command == "list-episodes":
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
    "list-episodes",
    help=f"List {FIXED_SHOW} episodes with rich summaries and publication-state filters.",
  )
  list_parser.add_argument(
    "--publication-state",
    choices=PUBLICATION_STATE_VALUES,
    default="all",
    help="Which episode set to return: all, published, or unpublished (default: all).",
  )
  list_parser.add_argument("--start-date", default="", help="Optional start date YYYY-MM-DD.")
  list_parser.add_argument("--end-date", default="", help="Optional end date YYYY-MM-DD.")
  list_parser.add_argument(
    "--limit",
    type=int,
    default=200,
    help="Max episodes to return after newest-first sorting.",
  )
  list_parser.add_argument(
    "--include-raw",
    action="store_true",
    help="Include a sanitized upstream episode payload under each item as raw_episode.",
  )
  list_parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show outbound request shape without calling the API.",
  )

  submit_parser = subparsers.add_parser(
    "submit-episode",
    help="Submit a new episode payload to /api/episodes/submit.",
  )
  submit_parser.add_argument(
    "--payload-file",
    required=True,
    help=(
      "Path to JSON payload file. Provide the main episode file as mainEpisodeFile for plain-English "
      "input, or as files.main.raw if you already have the backend payload shape. A top-level fileUrl "
      "is also accepted as a compatibility alias. Main-file fields may be public URLs or local file "
      "paths. Local file paths are uploaded first and replaced with public URLs."
    ),
  )
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
      "File-like fields may be public URLs or local file paths. "
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
    if args.command == "list-episodes":
      data = run_list_episodes(args)
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
  except (ClientError, UploadHelperError) as exc:
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
