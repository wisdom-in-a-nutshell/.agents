#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_ENV_PATH = Path.home() / ".secrets/linkedin/env"
DEFAULT_TOKENS_PATH = Path.home() / ".secrets/linkedin/posting.tokens.json"
LEGACY_TOKENS_PATH = Path.home() / ".secrets/linkedin/personal-posting.tokens.json"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
INITIALIZE_IMAGE_UPLOAD_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
SOCIAL_ACTIONS_URL = "https://api.linkedin.com/rest/socialActions"
DEFAULT_SCOPE = "openid profile w_member_social"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_LINKEDIN_VERSION = "202603"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0


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
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str
    linkedin_version: str
    request_timeout_seconds: float
    env_path: Path
    tokens_path: Path


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


def resolve_tokens_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_TOKENS_PATH and LEGACY_TOKENS_PATH.exists():
        return LEGACY_TOKENS_PATH
    return path


def build_config(args: argparse.Namespace) -> Config:
    env_values = parse_env_file(Path(args.env_file).expanduser())

    def get_value(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name) or env_values.get(name) or default

    client_id = get_value("LINKEDIN_CLIENT_ID")
    client_secret = get_value("LINKEDIN_CLIENT_SECRET")
    redirect_uri = get_value("LINKEDIN_REDIRECT_URI", DEFAULT_REDIRECT_URI)
    scope = get_value("LINKEDIN_SCOPE", DEFAULT_SCOPE)
    linkedin_version = getattr(args, "linkedin_version", None) or get_value("LINKEDIN_VERSION", DEFAULT_LINKEDIN_VERSION)

    if not client_id:
        raise CliError(
            f"Missing LINKEDIN_CLIENT_ID. Add it to {Path(args.env_file).expanduser()} or the environment.",
            code="E_CONFIG",
            exit_code=2,
            hint="Sync machine secrets or point --env-file at the generated LinkedIn env file.",
        )
    if not client_secret:
        raise CliError(
            f"Missing LINKEDIN_CLIENT_SECRET. Add it to {Path(args.env_file).expanduser()} or the environment.",
            code="E_CONFIG",
            exit_code=2,
            hint="Sync machine secrets or point --env-file at the generated LinkedIn env file.",
        )

    return Config(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        linkedin_version=linkedin_version,
        request_timeout_seconds=float(getattr(args, "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)),
        env_path=Path(args.env_file).expanduser(),
        tokens_path=resolve_tokens_path(Path(args.tokens_file).expanduser()),
    )


def now_iso_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_http_error(url: str, status: int, body_text: str) -> CliError:
    lowered = body_text.lower()
    if status in {401, 403}:
        return CliError(
            f"LinkedIn rejected the request with HTTP {status}.",
            code="E_AUTH",
            exit_code=3,
            retryable=False,
            hint="Re-run authorize if your token expired, or verify the LinkedIn app has the required product/scope.",
            details={"url": url, "status": status, "body": body_text},
        )
    if status == 429:
        return CliError(
            "LinkedIn rate-limited the request.",
            code="E_RATE_LIMIT",
            exit_code=4,
            retryable=True,
            hint="Wait and retry. For repeated throttling, reduce bursty posting/comment activity.",
            details={"url": url, "status": status, "body": body_text},
        )
    if status >= 500:
        return CliError(
            f"LinkedIn server error (HTTP {status}).",
            code="E_NETWORK",
            exit_code=4,
            retryable=True,
            hint="Retry the command. If it keeps failing, check LinkedIn API status or try again later.",
            details={"url": url, "status": status, "body": body_text},
        )
    code = "E_INVALID_INPUT" if status in {400, 404, 409, 422} else "E_GENERIC"
    hint = None
    if "syntax exception in path variables" in lowered:
        hint = "Check that the supplied post URN or comment URN is valid and URL-safe."
    elif "unpermitted fields" in lowered:
        hint = "Check the request shape against the current LinkedIn API docs for this endpoint."
    return CliError(
        f"LinkedIn returned HTTP {status}.",
        code=code,
        exit_code=2 if code == "E_INVALID_INPUT" else 1,
        retryable=False,
        hint=hint,
        details={"url": url, "status": status, "body": body_text},
    )


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url=url, method=method, headers=headers or {}, data=data)
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
            hint="Retry with a larger --request-timeout-seconds if LinkedIn is slow right now.",
        ) from exc
    except urllib.error.URLError as exc:
        raise CliError(
            f"Network error calling {url}: {exc.reason}",
            code="E_NETWORK",
            exit_code=4,
            retryable=True,
            hint="Check network connectivity and retry.",
        ) from exc


def load_tokens(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliError(
            f"Token file not found: {path}.",
            code="E_AUTH",
            exit_code=3,
            hint="Run authorize once, or point --tokens-file at an existing LinkedIn token file.",
        )
    return json.loads(path.read_text())


def save_tokens(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def token_still_valid(tokens: dict[str, Any]) -> bool:
    expires_at = tokens.get("access_token_expires_at")
    if not expires_at:
        return False
    return float(expires_at) > time.time() + 60


def exchange_code(config: Config, code: str) -> dict[str, Any]:
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
        }
    ).encode()
    _, _, response_body = http_request(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body,
        timeout_seconds=config.request_timeout_seconds,
    )
    return json.loads(response_body.decode("utf-8"))


def refresh_access_token(config: Config, tokens: dict[str, Any]) -> dict[str, Any]:
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise CliError(
            "Access token expired and no refresh token is available.",
            code="E_AUTH",
            exit_code=3,
            hint="Run authorize again.",
        )
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }
    ).encode()
    _, _, response_body = http_request(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body,
        timeout_seconds=config.request_timeout_seconds,
    )
    refreshed = json.loads(response_body.decode("utf-8"))
    merged = dict(tokens)
    merged.update(refreshed)
    merged["authorized_at"] = time.time()
    merged["access_token_expires_at"] = time.time() + float(refreshed.get("expires_in", 0))
    if "refresh_token_expires_in" in refreshed:
        merged["refresh_token_expires_at"] = time.time() + float(refreshed["refresh_token_expires_in"])
    return merged


def get_userinfo(config: Config, access_token: str) -> dict[str, Any]:
    _, _, response_body = http_request(
        "GET",
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout_seconds=config.request_timeout_seconds,
    )
    return json.loads(response_body.decode("utf-8"))


def ensure_access_token(config: Config, tokens: dict[str, Any]) -> dict[str, Any]:
    if token_still_valid(tokens):
        return tokens
    refreshed = refresh_access_token(config, tokens)
    save_tokens(config.tokens_path, refreshed)
    return refreshed


def ensure_member_context(config: Config, tokens: dict[str, Any]) -> dict[str, Any]:
    tokens = ensure_access_token(config, tokens)
    if tokens.get("member_sub"):
        return tokens
    userinfo = get_userinfo(config, tokens["access_token"])
    tokens["member_sub"] = userinfo.get("sub")
    tokens["author_urn"] = f"urn:li:person:{userinfo.get('sub')}" if userinfo.get("sub") else None
    tokens["member_profile"] = userinfo
    save_tokens(config.tokens_path, tokens)
    return tokens


def build_author_urn(tokens: dict[str, Any]) -> str:
    member_sub = tokens.get("member_sub")
    if not member_sub:
        raise CliError(
            "Missing member_sub in token file.",
            code="E_AUTH",
            exit_code=3,
            hint="Run authorize again to refresh the saved LinkedIn identity.",
        )
    return f"urn:li:person:{member_sub}"


def make_post_payload(*, author: str, text: str, visibility: str, url: str | None, title: str | None, description: str | None) -> dict[str, Any]:
    share_content: dict[str, Any] = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "NONE",
    }
    if url:
        media_item: dict[str, Any] = {
            "status": "READY",
            "originalUrl": url,
        }
        if title:
            media_item["title"] = {"text": title}
        if description:
            media_item["description"] = {"text": description}
        share_content["shareMediaCategory"] = "ARTICLE"
        share_content["media"] = [media_item]
    return {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }


def post_ugc(config: Config, access_token: str, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
    return http_request(
        "POST",
        UGC_POSTS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        data=json.dumps(payload).encode("utf-8"),
        timeout_seconds=config.request_timeout_seconds,
    )


def linkedin_rest_headers(access_token: str, *, version: str, content_type: str = "application/json", extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Linkedin-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": content_type,
    }
    if extra:
        headers.update(extra)
    return headers


def post_rest_json(config: Config, access_token: str, url: str, payload: dict[str, Any], *, version: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    return http_request(
        "POST",
        url,
        headers=linkedin_rest_headers(access_token, version=version, extra=extra_headers),
        data=json.dumps(payload).encode("utf-8"),
        timeout_seconds=config.request_timeout_seconds,
    )


def get_rest_json(config: Config, access_token: str, url: str, *, version: str, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    _, _, body = http_request(
        "GET",
        url,
        headers=linkedin_rest_headers(access_token, version=version, extra=extra_headers),
        timeout_seconds=config.request_timeout_seconds,
    )
    return json.loads(body.decode("utf-8"))


def initialize_image_upload(config: Config, access_token: str, *, owner: str, version: str) -> tuple[str, str]:
    payload = {"initializeUploadRequest": {"owner": owner}}
    _, _, body = post_rest_json(config, access_token, INITIALIZE_IMAGE_UPLOAD_URL, payload, version=version)
    response = json.loads(body.decode("utf-8"))
    value = response.get("value") or {}
    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn:
        raise CliError(
            "LinkedIn image initializeUpload response was missing uploadUrl or image.",
            code="E_API",
            exit_code=1,
            details=response,
        )
    return str(upload_url), str(image_urn)


def upload_image_binary(config: Config, access_token: str, *, upload_url: str, image_path: Path) -> None:
    content_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    data = image_path.read_bytes()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": content_type,
    }
    last_error: CliError | None = None
    for method in ("PUT", "POST"):
        request = urllib.request.Request(upload_url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(request, timeout=config.request_timeout_seconds):
                return
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = classify_http_error(upload_url, exc.code, body)
        except TimeoutError as exc:
            last_error = CliError(
                f"Timed out uploading {image_path.name}.",
                code="E_TIMEOUT",
                exit_code=5,
                retryable=True,
                hint="Retry with a larger --request-timeout-seconds if LinkedIn upload is slow.",
            )
        except urllib.error.URLError as exc:
            last_error = CliError(
                f"Upload failed for {image_path.name}: {exc.reason}",
                code="E_NETWORK",
                exit_code=4,
                retryable=True,
                hint="Check network connectivity and retry.",
            )
    assert last_error is not None
    raise last_error


def build_rest_distribution_payload() -> dict[str, Any]:
    return {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": [],
    }


def build_image_post_payload(*, author: str, text: str, visibility: str, image_entries: list[dict[str, str]]) -> dict[str, Any]:
    content_key = "multiImage" if len(image_entries) > 1 else "media"
    content_value: dict[str, Any]
    if len(image_entries) > 1:
        content_value = {"images": image_entries}
    else:
        image = image_entries[0]
        content_value = {"id": image["id"]}
        if image.get("altText"):
            content_value["altText"] = image["altText"]
        if image.get("title"):
            content_value["title"] = image["title"]
    return {
        "author": author,
        "commentary": text,
        "visibility": visibility,
        "distribution": build_rest_distribution_payload(),
        "content": {content_key: content_value},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def load_image_paths(raw_paths: list[str]) -> list[Path]:
    paths = [Path(raw).expanduser() for raw in raw_paths]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise CliError(
            "One or more image files were not found.",
            code="E_INVALID_INPUT",
            exit_code=2,
            hint="Check the --image paths and try again.",
            details={"missing": missing},
        )
    if len(paths) > 20:
        raise CliError(
            "LinkedIn supports at most 20 images in one post.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    return paths


def build_image_entries(image_paths: list[Path], alt_texts: list[str], image_urns: list[str]) -> list[dict[str, str]]:
    if len(alt_texts) not in {0, len(image_paths)}:
        raise CliError(
            "Provide either no --alt-text values or one --alt-text per --image in the same order.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    entries: list[dict[str, str]] = []
    for index, (path, image_urn) in enumerate(zip(image_paths, image_urns, strict=True)):
        entry: dict[str, str] = {"id": image_urn}
        if alt_texts:
            alt_text = alt_texts[index].strip()
            if alt_text:
                entry["altText"] = alt_text
        if len(image_paths) == 1:
            entry["title"] = path.stem.replace("-", " ").replace("_", " ")
        entries.append(entry)
    return entries


class CallbackHandler(BaseHTTPRequestHandler):
    server_version = "LinkedInLocalAuth/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.server.oauth_query = query  # type: ignore[attr-defined]
        body = "You can close this tab and return to Codex."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def wait_for_callback(redirect_uri: str, expected_state: str, timeout_seconds: int) -> str:
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != "http":
        raise CliError(
            "Local authorize flow expects an http:// redirect URI for the loopback server.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise CliError(
            "Local authorize flow expects localhost or 127.0.0.1 as the redirect host.",
            code="E_INVALID_INPUT",
            exit_code=2,
        )
    port = parsed.port or 80
    server = HTTPServer((parsed.hostname, port), CallbackHandler)
    server.timeout = timeout_seconds
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        server.handle_request()
        query = getattr(server, "oauth_query", None)
        if query:
            state = (query.get("state") or [""])[0]
            code = (query.get("code") or [""])[0]
            error = (query.get("error") or [""])[0]
            if error:
                raise CliError(
                    f"LinkedIn returned OAuth error: {error}",
                    code="E_AUTH",
                    exit_code=3,
                )
            if state != expected_state:
                raise CliError("OAuth state mismatch.", code="E_AUTH", exit_code=3)
            if not code:
                raise CliError("No authorization code was returned.", code="E_AUTH", exit_code=3)
            return code
    raise CliError(
        "Timed out waiting for the LinkedIn OAuth callback.",
        code="E_TIMEOUT",
        exit_code=5,
        retryable=True,
        hint="Retry authorize and complete the LinkedIn consent flow before the timeout expires.",
    )


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


def encode_urn(urn: str) -> str:
    return urllib.parse.quote(urn, safe="")


def to_iso_from_epoch_ms(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def to_iso_from_epoch_seconds(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(value), tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def summarize_post(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": post.get("id"),
        "author": post.get("author"),
        "visibility": post.get("visibility"),
        "published_at": to_iso_from_epoch_ms(post.get("publishedAt")) or post.get("publishedAt"),
        "last_modified_at": to_iso_from_epoch_ms(post.get("lastModifiedAt")) or post.get("lastModifiedAt"),
        "commentary": post.get("commentary") or "",
        "content_keys": sorted((post.get("content") or {}).keys()),
        "raw": post,
    }


def make_lenient_config(args: argparse.Namespace) -> Config:
    env_path = Path(args.env_file).expanduser()
    env_values = parse_env_file(env_path)
    return Config(
        client_id=os.environ.get("LINKEDIN_CLIENT_ID") or env_values.get("LINKEDIN_CLIENT_ID") or "",
        client_secret=os.environ.get("LINKEDIN_CLIENT_SECRET") or env_values.get("LINKEDIN_CLIENT_SECRET") or "",
        redirect_uri=os.environ.get("LINKEDIN_REDIRECT_URI") or env_values.get("LINKEDIN_REDIRECT_URI") or DEFAULT_REDIRECT_URI,
        scope=os.environ.get("LINKEDIN_SCOPE") or env_values.get("LINKEDIN_SCOPE") or DEFAULT_SCOPE,
        linkedin_version=getattr(args, "linkedin_version", None) or os.environ.get("LINKEDIN_VERSION") or env_values.get("LINKEDIN_VERSION") or DEFAULT_LINKEDIN_VERSION,
        request_timeout_seconds=float(getattr(args, "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)),
        env_path=env_path,
        tokens_path=resolve_tokens_path(Path(args.tokens_file).expanduser()),
    )


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


def emit_success(args: argparse.Namespace, command: str, data: dict[str, Any], *, start_time: float, request_id: str) -> int:
    mode = determine_output_mode(args)
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
    if mode == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True))
    else:
        print("\n".join(flatten_plain("data", data)))
    return 0


def emit_error(args: argparse.Namespace, command: str, error: CliError, *, start_time: float, request_id: str) -> int:
    mode = determine_output_mode(args)
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
    if mode == "json":
        print(json.dumps(envelope, indent=2, sort_keys=True), file=sys.stderr)
    else:
        print(f"error.code={error.code}\nerror.message={str(error)}", file=sys.stderr)
        if error.hint:
            print(f"error.hint={error.hint}", file=sys.stderr)
    return error.exit_code


def command_authorize(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    state = secrets.token_urlsafe(24)
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "state": state,
            "scope": config.scope,
        }
    )
    url = f"{AUTH_URL}?{params}"
    if not args.no_browser and not args.no_input:
        webbrowser.open(url)
    code = wait_for_callback(config.redirect_uri, state, args.timeout)
    token_payload = exchange_code(config, code)
    token_payload["authorized_at"] = time.time()
    token_payload["access_token_expires_at"] = time.time() + float(token_payload.get("expires_in", 0))
    if "refresh_token_expires_in" in token_payload:
        token_payload["refresh_token_expires_at"] = time.time() + float(token_payload["refresh_token_expires_in"])
    userinfo = get_userinfo(config, token_payload["access_token"])
    token_payload["member_sub"] = userinfo.get("sub")
    token_payload["author_urn"] = f"urn:li:person:{userinfo.get('sub')}" if userinfo.get("sub") else None
    token_payload["member_profile"] = userinfo
    save_tokens(config.tokens_path, token_payload)
    return {
        "authorize_url": url,
        "tokens_file": str(config.tokens_path),
        "name": userinfo.get("name"),
        "sub": userinfo.get("sub"),
        "author_urn": token_payload.get("author_urn"),
    }


def command_whoami(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    userinfo = get_userinfo(config, tokens["access_token"])
    return {
        "name": userinfo.get("name"),
        "sub": userinfo.get("sub"),
        "author_urn": build_author_urn(tokens),
        "profile": userinfo,
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    config = make_lenient_config(args)
    env_values = parse_env_file(config.env_path)
    data: dict[str, Any] = {
        "files": {
            "env_file": str(config.env_path),
            "env_file_exists": config.env_path.exists(),
            "tokens_file": str(config.tokens_path),
            "tokens_file_exists": config.tokens_path.exists(),
            "using_legacy_tokens_file": config.tokens_path == LEGACY_TOKENS_PATH,
        },
        "auth": {
            "has_client_id": bool(config.client_id),
            "has_client_secret": bool(config.client_secret),
            "redirect_uri": env_values.get("LINKEDIN_REDIRECT_URI") or DEFAULT_REDIRECT_URI,
            "scope": env_values.get("LINKEDIN_SCOPE") or DEFAULT_SCOPE,
            "linkedin_version": config.linkedin_version,
            "authorized": False,
        },
        "identity": None,
        "capabilities": {
            "supported_commands": [
                "authorize",
                "status",
                "whoami",
                "post",
                "post-image",
                "post-images",
                "comment",
                "get-post",
                "list-posts",
            ],
            "json_default": True,
            "plain_available": True,
            "can_authorize": bool(config.client_id and config.client_secret),
            "can_post": False,
            "read_back": {
                "probed": False,
                "allowed": None,
                "reason": "probe_not_run",
            },
        },
        "notes": [],
    }

    if not config.env_path.exists():
        data["notes"].append("LinkedIn env file is missing. Authorize will not work until machine secrets are synced.")
    if not config.tokens_path.exists():
        data["notes"].append("LinkedIn token file is missing. Run authorize once on this machine.")
        return data

    tokens = load_tokens(config.tokens_path)
    access_token_valid = token_still_valid(tokens)
    data["auth"].update(
        {
            "authorized": True,
            "access_token_valid_now": access_token_valid,
            "authorized_at": to_iso_from_epoch_seconds(tokens.get("authorized_at")),
            "access_token_expires_at": to_iso_from_epoch_seconds(tokens.get("access_token_expires_at")),
            "refresh_token_expires_at": to_iso_from_epoch_seconds(tokens.get("refresh_token_expires_at")),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "member_sub_cached": tokens.get("member_sub"),
        }
    )
    if access_token_valid and tokens.get("member_sub"):
        data["capabilities"]["can_post"] = True
        data["identity"] = {
            "name": (tokens.get("member_profile") or {}).get("name"),
            "sub": tokens.get("member_sub"),
            "author_urn": tokens.get("author_urn") or f"urn:li:person:{tokens.get('member_sub')}",
            "source": "cached_token",
        }

    if not access_token_valid and not (config.client_id and config.client_secret):
        data["notes"].append("Access token appears expired and client credentials are not available for refresh.")
        return data

    try:
        tokens = ensure_member_context(config, tokens)
        userinfo = get_userinfo(config, tokens["access_token"])
        data["identity"] = {
            "name": userinfo.get("name"),
            "sub": userinfo.get("sub"),
            "author_urn": build_author_urn(tokens),
            "source": "live_userinfo",
        }
        data["capabilities"]["can_post"] = True
    except CliError as exc:
        data["notes"].append(f"Identity check failed: {exc.code} {exc}")
        if exc.hint:
            data["notes"].append(exc.hint)
        if data["capabilities"]["can_post"]:
            data["notes"].append("Using cached member identity from the token file; posting may still work.")
            return data
        return data

    if args.no_probe_read:
        data["notes"].append("Read-back probe skipped.")
        return data

    data["capabilities"]["read_back"]["probed"] = True
    author_urn = build_author_urn(tokens)
    query = urllib.parse.urlencode(
        {
            "author": author_urn,
            "q": "author",
            "count": 1,
            "sortBy": "LAST_MODIFIED",
        }
    )
    try:
        get_rest_json(
            config,
            tokens["access_token"],
            f"{REST_POSTS_URL}?{query}",
            version=config.linkedin_version,
            extra_headers={"X-RestLi-Method": "FINDER"},
        )
        data["capabilities"]["read_back"].update({"allowed": True, "reason": "list_posts_ok"})
    except CliError as exc:
        data["capabilities"]["read_back"].update(
            {
                "allowed": False,
                "reason": exc.code,
                "message": str(exc),
                "hint": exc.hint,
            }
        )
        data["notes"].append("Posting is available, but LinkedIn read-back endpoints may still be permission-limited for this app.")

    return data


def command_post(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    payload = make_post_payload(
        author=build_author_urn(tokens),
        text=load_post_text(args),
        visibility=args.visibility,
        url=args.url,
        title=args.title,
        description=args.description,
    )
    if args.dry_run:
        return {"dry_run": True, "payload": payload}
    status, headers, body = post_ugc(config, tokens["access_token"], payload)
    restli_id = headers.get("X-RestLi-Id") or headers.get("x-restli-id")
    return {
        "dry_run": False,
        "http_status": status,
        "post_urn": restli_id,
        "response_body": body.decode("utf-8", errors="replace") if body else None,
    }


def publish_images(config: Config, tokens: dict[str, Any], *, text: str, visibility: str, image_paths: list[Path], alt_texts: list[str], settle_seconds: float, dry_run: bool) -> dict[str, Any]:
    author_urn = build_author_urn(tokens)
    if dry_run:
        payload = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": build_rest_distribution_payload(),
            "content": {
                "multiImage" if len(image_paths) > 1 else "media": {
                    "images": [
                        {
                            "localPath": str(path),
                            **({"altText": alt_texts[index].strip()} if index < len(alt_texts) and alt_texts[index].strip() else {}),
                        }
                        for index, path in enumerate(image_paths)
                    ]
                }
                if len(image_paths) > 1
                else {
                    "localPath": str(image_paths[0]),
                    **({"altText": alt_texts[0].strip()} if alt_texts and alt_texts[0].strip() else {}),
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        return {"dry_run": True, "payload": payload}

    image_urns: list[str] = []
    for image_path in image_paths:
        upload_url, image_urn = initialize_image_upload(config, tokens["access_token"], owner=author_urn, version=config.linkedin_version)
        upload_image_binary(config, tokens["access_token"], upload_url=upload_url, image_path=image_path)
        image_urns.append(image_urn)
        if settle_seconds > 0:
            time.sleep(settle_seconds)

    payload = build_image_post_payload(
        author=author_urn,
        text=text,
        visibility=visibility,
        image_entries=build_image_entries(image_paths, alt_texts, image_urns),
    )
    status, headers, body = post_rest_json(config, tokens["access_token"], REST_POSTS_URL, payload, version=config.linkedin_version)
    restli_id = headers.get("X-RestLi-Id") or headers.get("x-restli-id")
    return {
        "dry_run": False,
        "http_status": status,
        "post_urn": restli_id,
        "uploaded_images": image_urns,
        "response_body": body.decode("utf-8", errors="replace") if body else None,
    }


def command_post_image(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    image_paths = load_image_paths([args.image])
    alt_texts = [args.alt_text] if args.alt_text else []
    return publish_images(
        config,
        tokens,
        text=load_post_text(args),
        visibility=args.visibility,
        image_paths=image_paths,
        alt_texts=alt_texts,
        settle_seconds=args.upload_settle_seconds,
        dry_run=args.dry_run,
    )


def command_post_images(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    image_paths = load_image_paths(args.image)
    if len(image_paths) < 2:
        raise CliError(
            "Use at least two --image values for a LinkedIn multi-image post.",
            code="E_INVALID_INPUT",
            exit_code=2,
            hint="Use post-image for a single image, or pass two or more --image values here.",
        )
    return publish_images(
        config,
        tokens,
        text=load_post_text(args),
        visibility=args.visibility,
        image_paths=image_paths,
        alt_texts=args.alt_text,
        settle_seconds=args.upload_settle_seconds,
        dry_run=args.dry_run,
    )


def command_get_post(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    encoded = encode_urn(args.post_urn)
    data = get_rest_json(
        config,
        tokens["access_token"],
        f"{REST_POSTS_URL}/{encoded}?viewContext={args.view_context}",
        version=config.linkedin_version,
    )
    return {"post": summarize_post(data)}


def command_list_posts(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    author_urn = build_author_urn(tokens)
    query = urllib.parse.urlencode(
        {
            "author": author_urn,
            "q": "author",
            "count": args.count,
            "sortBy": args.sort_by,
        }
    )
    data = get_rest_json(
        config,
        tokens["access_token"],
        f"{REST_POSTS_URL}?{query}",
        version=config.linkedin_version,
        extra_headers={"X-RestLi-Method": "FINDER"},
    )
    elements = data.get("elements") or []
    return {
        "count": len(elements),
        "posts": [
            {key: value for key, value in summarize_post(post).items() if key != "raw"} for post in elements
        ],
        "paging": data.get("paging") or {},
    }


def command_comment(args: argparse.Namespace) -> dict[str, Any]:
    config = build_config(args)
    tokens = ensure_member_context(config, load_tokens(config.tokens_path))
    actor = build_author_urn(tokens)
    payload: dict[str, Any] = {
        "actor": actor,
        "object": args.post_urn,
        "message": {"text": load_post_text(args)},
    }
    if args.parent_comment:
        payload["parentComment"] = args.parent_comment
    if args.dry_run:
        return {"dry_run": True, "payload": payload}
    encoded_target = encode_urn(args.parent_comment if args.parent_comment else args.post_urn)
    status, headers, body = post_rest_json(
        config,
        tokens["access_token"],
        f"{SOCIAL_ACTIONS_URL}/{encoded_target}/comments",
        payload,
        version=config.linkedin_version,
    )
    body_json = json.loads(body.decode("utf-8")) if body else {}
    comment_id = headers.get("x-restli-id") or headers.get("X-RestLi-Id") or body_json.get("id")
    return {
        "dry_run": False,
        "http_status": status,
        "comment_id": comment_id,
        "comment_urn": body_json.get("commentUrn"),
        "post_urn": args.post_urn,
        "response": body_json,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LinkedIn posting helper.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local LinkedIn app credentials env file.")
    parser.add_argument("--tokens-file", default=str(DEFAULT_TOKENS_PATH), help="Path to machine-local LinkedIn token JSON file.")
    parser.add_argument("--linkedin-version", default=DEFAULT_LINKEDIN_VERSION, help="LinkedIn REST API version for /rest endpoints, formatted as YYYYMM.")
    parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS, help="HTTP request timeout in seconds.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON output. This is also the default.")
    mode.add_argument("--plain", action="store_true", help="Emit stable plain text for shell pipelines or quick operator inspection.")
    parser.add_argument("--no-input", action="store_true", help="Disable browser auto-open and any interactive input.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize = subparsers.add_parser("authorize", help="Run the local OAuth authorize flow and save tokens.")
    authorize.add_argument("--timeout", type=int, default=180, help="Seconds to wait for the OAuth callback.")
    authorize.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser.")
    authorize.set_defaults(func=command_authorize, command_path="linkedin authorize")

    status = subparsers.add_parser("status", help="Inspect LinkedIn auth/runtime state for this machine and app.")
    status.add_argument("--no-probe-read", action="store_true", help="Skip the non-mutating read-back permission probe.")
    status.set_defaults(func=command_status, command_path="linkedin status")

    whoami = subparsers.add_parser("whoami", help="Show the LinkedIn profile tied to the current token.")
    whoami.set_defaults(func=command_whoami, command_path="linkedin whoami")

    post = subparsers.add_parser("post", help="Publish a text or article/link share to LinkedIn.")
    post.add_argument("--text", help="Inline post text.")
    post.add_argument("--text-file", help="Path to a file containing post text.")
    post.add_argument("--url", help="Optional URL to attach as an article share.")
    post.add_argument("--title", help="Optional article title when --url is used.")
    post.add_argument("--description", help="Optional article description when --url is used.")
    post.add_argument("--visibility", choices=["PUBLIC", "CONNECTIONS"], default="PUBLIC")
    post.add_argument("--dry-run", action="store_true", help="Print the request payload without publishing.")
    post.set_defaults(func=command_post, command_path="linkedin post")

    post_image = subparsers.add_parser("post-image", help="Publish a LinkedIn single-image post with commentary text.")
    post_image.add_argument("--text", help="Inline post text.")
    post_image.add_argument("--text-file", help="Path to a file containing post text.")
    post_image.add_argument("--image", required=True, help="Single image file path.")
    post_image.add_argument("--alt-text", default="", help="Optional alt text for the image.")
    post_image.add_argument("--visibility", choices=["PUBLIC", "CONNECTIONS"], default="PUBLIC")
    post_image.add_argument("--upload-settle-seconds", type=float, default=0.75, help="Small pause after upload before creating the post.")
    post_image.add_argument("--dry-run", action="store_true", help="Print the planned payload without uploading or publishing.")
    post_image.set_defaults(func=command_post_image, command_path="linkedin post-image")

    post_images = subparsers.add_parser("post-images", help="Publish a LinkedIn multi-image post with commentary text.")
    post_images.add_argument("--text", help="Inline post text.")
    post_images.add_argument("--text-file", help="Path to a file containing post text.")
    post_images.add_argument("--image", action="append", required=True, help="Image file path. Pass once per image in order.")
    post_images.add_argument("--alt-text", action="append", default=[], help="Optional alt text. Pass once per image in the same order.")
    post_images.add_argument("--visibility", choices=["PUBLIC", "CONNECTIONS"], default="PUBLIC")
    post_images.add_argument("--upload-settle-seconds", type=float, default=0.75, help="Small pause after each upload before creating the post.")
    post_images.add_argument("--dry-run", action="store_true", help="Print the planned payload without uploading or publishing.")
    post_images.set_defaults(func=command_post_images, command_path="linkedin post-images")

    get_post = subparsers.add_parser("get-post", help="Fetch one post by LinkedIn post URN.")
    get_post.add_argument("--post-urn", required=True, help="LinkedIn post URN, for example urn:li:ugcPost:... or urn:li:share:...")
    get_post.add_argument("--view-context", choices=["AUTHOR", "READER"], default="AUTHOR")
    get_post.set_defaults(func=command_get_post, command_path="linkedin get-post")

    list_posts = subparsers.add_parser("list-posts", help="List recent posts for the authenticated member.")
    list_posts.add_argument("--count", type=int, default=10, help="Maximum number of posts to return.")
    list_posts.add_argument("--sort-by", choices=["LAST_MODIFIED", "PUBLISHED_AT", "CREATED_AT"], default="LAST_MODIFIED")
    list_posts.set_defaults(func=command_list_posts, command_path="linkedin list-posts")

    comment = subparsers.add_parser("comment", help="Create a comment on a LinkedIn post.")
    comment.add_argument("--post-urn", required=True, help="Target post URN to comment on.")
    comment.add_argument("--text", help="Inline comment text.")
    comment.add_argument("--text-file", help="Path to a file containing comment text.")
    comment.add_argument("--parent-comment", help="Optional parent comment URN for nested comments.")
    comment.add_argument("--dry-run", action="store_true", help="Print the request payload without publishing the comment.")
    comment.set_defaults(func=command_comment, command_path="linkedin comment")

    return parser


def main() -> int:
    start_time = time.time()
    request_id = secrets.token_hex(8)
    parser = build_parser()
    args = parser.parse_args()
    command = getattr(args, "command_path", f"linkedin {args.command}")
    try:
        data = args.func(args)
        return emit_success(args, command, data, start_time=start_time, request_id=request_id)
    except CliError as exc:
        return emit_error(args, command, exc, start_time=start_time, request_id=request_id)


if __name__ == "__main__":
    raise SystemExit(main())
