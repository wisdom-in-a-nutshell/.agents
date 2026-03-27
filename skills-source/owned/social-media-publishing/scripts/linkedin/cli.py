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
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

DEFAULT_ENV_PATH = Path.home() / ".secrets/linkedin/env"
DEFAULT_TOKENS_PATH = Path.home() / ".secrets/linkedin/posting.tokens.json"
LEGACY_TOKENS_PATH = Path.home() / ".secrets/linkedin/personal-posting.tokens.json"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
INITIALIZE_IMAGE_UPLOAD_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
DEFAULT_SCOPE = "openid profile w_member_social"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_LINKEDIN_VERSION = "202603"


class CliError(RuntimeError):
    pass


@dataclass
class Config:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str
    linkedin_version: str
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
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


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
            f"Missing LINKEDIN_CLIENT_ID. Add it to {Path(args.env_file).expanduser()} or the environment."
        )
    if not client_secret:
        raise CliError(
            f"Missing LINKEDIN_CLIENT_SECRET. Add it to {Path(args.env_file).expanduser()} or the environment."
        )

    return Config(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        linkedin_version=linkedin_version,
        env_path=Path(args.env_file).expanduser(),
        tokens_path=resolve_tokens_path(Path(args.tokens_file).expanduser()),
    )


def resolve_tokens_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_TOKENS_PATH and LEGACY_TOKENS_PATH.exists():
        return LEGACY_TOKENS_PATH
    return path


def http_request(method: str, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url=url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CliError(f"HTTP {exc.code} for {url}\n{body}") from exc


def load_tokens(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CliError(f"Token file not found: {path}. Run authorize first.")
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
    )
    return json.loads(response_body.decode("utf-8"))


def refresh_access_token(config: Config, tokens: dict[str, Any]) -> dict[str, Any]:
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise CliError("Access token expired and no refresh token is available. Run authorize again.")
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
    )
    refreshed = json.loads(response_body.decode("utf-8"))
    merged = dict(tokens)
    merged.update(refreshed)
    merged["authorized_at"] = time.time()
    merged["access_token_expires_at"] = time.time() + float(refreshed.get("expires_in", 0))
    if "refresh_token_expires_in" in refreshed:
        merged["refresh_token_expires_at"] = time.time() + float(refreshed["refresh_token_expires_in"])
    return merged


def get_userinfo(access_token: str) -> dict[str, Any]:
    _, _, response_body = http_request(
        "GET",
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return json.loads(response_body.decode("utf-8"))


def ensure_access_token(config: Config, tokens: dict[str, Any]) -> dict[str, Any]:
    if token_still_valid(tokens):
        return tokens
    refreshed = refresh_access_token(config, tokens)
    save_tokens(config.tokens_path, refreshed)
    return refreshed


def build_author_urn(tokens: dict[str, Any]) -> str:
    member_sub = tokens.get("member_sub")
    if not member_sub:
        raise CliError("Missing member_sub in token file. Run authorize again.")
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


def post_ugc(access_token: str, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
    return http_request(
        "POST",
        UGC_POSTS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        data=json.dumps(payload).encode("utf-8"),
    )


def linkedin_rest_headers(access_token: str, *, version: str, content_type: str = "application/json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Linkedin-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": content_type,
    }


def post_rest_json(access_token: str, url: str, payload: dict[str, Any], *, version: str) -> tuple[int, dict[str, str], bytes]:
    return http_request(
        "POST",
        url,
        headers=linkedin_rest_headers(access_token, version=version),
        data=json.dumps(payload).encode("utf-8"),
    )


def initialize_image_upload(access_token: str, *, owner: str, version: str) -> tuple[str, str]:
    payload = {"initializeUploadRequest": {"owner": owner}}
    _, _, body = post_rest_json(access_token, INITIALIZE_IMAGE_UPLOAD_URL, payload, version=version)
    response = json.loads(body.decode("utf-8"))
    value = response.get("value") or {}
    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn:
        raise CliError(f"LinkedIn image initializeUpload response was missing uploadUrl/image.\n{json.dumps(response, indent=2, sort_keys=True)}")
    return str(upload_url), str(image_urn)


def upload_image_binary(access_token: str, *, upload_url: str, image_path: Path) -> None:
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
            with urllib.request.urlopen(request):
                return
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = CliError(f"HTTP {exc.code} uploading {image_path.name} with {method}\n{body}")
        except urllib.error.URLError as exc:
            last_error = CliError(f"Upload failed for {image_path.name} with {method}: {exc}")
    assert last_error is not None
    raise last_error


def build_rest_distribution_payload() -> dict[str, Any]:
    return {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": [],
    }


def build_rest_article_post_payload(
    *,
    author: str,
    text: str,
    visibility: str,
    url: str,
    title: str | None,
    description: str | None,
) -> dict[str, Any]:
    article: dict[str, Any] = {"source": url}
    if title:
        article["title"] = title
    if description:
        article["description"] = description
    return {
        "author": author,
        "commentary": text,
        "visibility": visibility,
        "distribution": build_rest_distribution_payload(),
        "content": {"article": article},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def build_image_post_payload(
    *,
    author: str,
    text: str,
    visibility: str,
    image_entries: list[dict[str, str]],
) -> dict[str, Any]:
    content_key = "multiImage" if len(image_entries) > 1 else "media"
    content_value: dict[str, Any]
    if len(image_entries) > 1:
        content_value = {
            "images": image_entries,
        }
    else:
        image = image_entries[0]
        content_value = {
            "id": image["id"],
        }
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
        raise CliError(f"Image file(s) not found:\n- " + "\n- ".join(missing))
    if len(paths) > 20:
        raise CliError("LinkedIn supports at most 20 images in one post.")
    return paths


def build_image_entries(image_paths: list[Path], alt_texts: list[str], image_urns: list[str]) -> list[dict[str, str]]:
    if len(alt_texts) not in {0, len(image_paths)}:
        raise CliError("Provide either no --alt-text values or one --alt-text per --image in the same order.")
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
        raise CliError("Local authorize flow expects an http:// redirect URI for the loopback server.")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise CliError("Local authorize flow expects localhost or 127.0.0.1 as the redirect host.")
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
                raise CliError(f"LinkedIn returned OAuth error: {error}")
            if state != expected_state:
                raise CliError("OAuth state mismatch. Aborting.")
            if not code:
                raise CliError("No authorization code was returned.")
            return code
    raise CliError("Timed out waiting for the LinkedIn OAuth callback.")


def command_authorize(args: argparse.Namespace) -> int:
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
    print("Open this URL in your browser and complete the LinkedIn consent flow:\n")
    print(url)
    print()
    if not args.no_browser:
        webbrowser.open(url)
    code = wait_for_callback(config.redirect_uri, state, args.timeout)
    token_payload = exchange_code(config, code)
    token_payload["authorized_at"] = time.time()
    token_payload["access_token_expires_at"] = time.time() + float(token_payload.get("expires_in", 0))
    if "refresh_token_expires_in" in token_payload:
        token_payload["refresh_token_expires_at"] = time.time() + float(token_payload["refresh_token_expires_in"])
    userinfo = get_userinfo(token_payload["access_token"])
    token_payload["member_sub"] = userinfo.get("sub")
    token_payload["author_urn"] = f"urn:li:person:{userinfo.get('sub')}" if userinfo.get("sub") else None
    token_payload["member_profile"] = userinfo
    save_tokens(config.tokens_path, token_payload)
    print(f"Saved LinkedIn tokens to {config.tokens_path}")
    if userinfo.get("name"):
        print(f"Authorized as: {userinfo['name']}")
    if token_payload.get("author_urn"):
        print(f"Author URN: {token_payload['author_urn']}")
    return 0


def load_post_text(args: argparse.Namespace) -> str:
    if args.text and args.text_file:
        raise CliError("Use either --text or --text-file, not both.")
    if args.text:
        return args.text.strip()
    if args.text_file:
        return Path(args.text_file).expanduser().read_text().strip()
    stdin_text = sys.stdin.read().strip()
    if stdin_text:
        return stdin_text
    raise CliError("Provide post text via --text, --text-file, or stdin.")


def command_whoami(args: argparse.Namespace) -> int:
    config = build_config(args)
    tokens = ensure_access_token(config, load_tokens(config.tokens_path))
    userinfo = get_userinfo(tokens["access_token"])
    print(json.dumps(userinfo, indent=2, sort_keys=True))
    return 0


def command_post(args: argparse.Namespace) -> int:
    config = build_config(args)
    tokens = ensure_access_token(config, load_tokens(config.tokens_path))
    if not tokens.get("member_sub"):
        userinfo = get_userinfo(tokens["access_token"])
        tokens["member_sub"] = userinfo.get("sub")
        tokens["author_urn"] = f"urn:li:person:{userinfo.get('sub')}" if userinfo.get("sub") else None
        tokens["member_profile"] = userinfo
        save_tokens(config.tokens_path, tokens)
    payload = make_post_payload(
        author=build_author_urn(tokens),
        text=load_post_text(args),
        visibility=args.visibility,
        url=args.url,
        title=args.title,
        description=args.description,
    )
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    status, headers, body = post_ugc(tokens["access_token"], payload)
    print(f"LinkedIn response status: {status}")
    restli_id = headers.get("X-RestLi-Id") or headers.get("x-restli-id")
    if restli_id:
        print(f"X-RestLi-Id: {restli_id}")
    if body:
        print(body.decode("utf-8", errors="replace"))
    return 0


def command_post_images(args: argparse.Namespace) -> int:
    config = build_config(args)
    tokens = ensure_access_token(config, load_tokens(config.tokens_path))
    if not tokens.get("member_sub"):
        userinfo = get_userinfo(tokens["access_token"])
        tokens["member_sub"] = userinfo.get("sub")
        tokens["author_urn"] = f"urn:li:person:{userinfo.get('sub')}" if userinfo.get("sub") else None
        tokens["member_profile"] = userinfo
        save_tokens(config.tokens_path, tokens)

    text = load_post_text(args)
    image_paths = load_image_paths(args.image)
    if len(image_paths) < 2:
        raise CliError("Use at least two --image values for a LinkedIn multi-image post.")

    if args.dry_run:
        dry_run_payload = {
            "author": build_author_urn(tokens),
            "commentary": text,
            "visibility": args.visibility,
            "distribution": build_rest_distribution_payload(),
            "content": {
                "multiImage": {
                    "images": [
                        {
                            "localPath": str(path),
                            **({"altText": args.alt_text[index].strip()} if index < len(args.alt_text) and args.alt_text[index].strip() else {}),
                        }
                        for index, path in enumerate(image_paths)
                    ]
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        print(json.dumps(dry_run_payload, indent=2, sort_keys=True))
        return 0

    image_urns: list[str] = []
    author_urn = build_author_urn(tokens)
    for image_path in image_paths:
        upload_url, image_urn = initialize_image_upload(
            tokens["access_token"],
            owner=author_urn,
            version=config.linkedin_version,
        )
        upload_image_binary(tokens["access_token"], upload_url=upload_url, image_path=image_path)
        image_urns.append(image_urn)
        if args.upload_settle_seconds > 0:
            time.sleep(args.upload_settle_seconds)

    payload = build_image_post_payload(
        author=author_urn,
        text=text,
        visibility=args.visibility,
        image_entries=build_image_entries(image_paths, args.alt_text, image_urns),
    )
    status, headers, body = post_rest_json(
        tokens["access_token"],
        REST_POSTS_URL,
        payload,
        version=config.linkedin_version,
    )
    print(f"LinkedIn response status: {status}")
    restli_id = headers.get("X-RestLi-Id") or headers.get("x-restli-id")
    if restli_id:
        print(f"X-RestLi-Id: {restli_id}")
    if body:
        print(body.decode("utf-8", errors="replace"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local LinkedIn posting helper.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local LinkedIn app credentials env file.")
    parser.add_argument("--tokens-file", default=str(DEFAULT_TOKENS_PATH), help="Path to machine-local LinkedIn token JSON file.")
    parser.add_argument("--linkedin-version", default=DEFAULT_LINKEDIN_VERSION, help="LinkedIn REST API version for /rest endpoints, formatted as YYYYMM.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize = subparsers.add_parser("authorize", help="Run the local OAuth authorize flow and save tokens.")
    authorize.add_argument("--timeout", type=int, default=180, help="Seconds to wait for the OAuth callback.")
    authorize.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser.")
    authorize.set_defaults(func=command_authorize)

    whoami = subparsers.add_parser("whoami", help="Show the LinkedIn profile tied to the current token.")
    whoami.set_defaults(func=command_whoami)

    post = subparsers.add_parser("post", help="Publish a text or article/link share to LinkedIn.")
    post.add_argument("--text", help="Inline post text.")
    post.add_argument("--text-file", help="Path to a file containing post text.")
    post.add_argument("--url", help="Optional URL to attach as an article share.")
    post.add_argument("--title", help="Optional article title when --url is used.")
    post.add_argument("--description", help="Optional article description when --url is used.")
    post.add_argument("--visibility", choices=["PUBLIC", "CONNECTIONS"], default="PUBLIC")
    post.add_argument("--dry-run", action="store_true", help="Print the request payload without publishing.")
    post.set_defaults(func=command_post)

    post_images = subparsers.add_parser("post-images", help="Publish a LinkedIn multi-image post with commentary text.")
    post_images.add_argument("--text", help="Inline post text.")
    post_images.add_argument("--text-file", help="Path to a file containing post text.")
    post_images.add_argument("--image", action="append", required=True, help="Image file path. Pass once per image in order.")
    post_images.add_argument("--alt-text", action="append", default=[], help="Optional alt text. Pass once per image in the same order.")
    post_images.add_argument("--visibility", choices=["PUBLIC", "CONNECTIONS"], default="PUBLIC")
    post_images.add_argument("--upload-settle-seconds", type=float, default=0.75, help="Small pause after each upload before creating the post.")
    post_images.add_argument("--dry-run", action="store_true", help="Print the planned payload without uploading or publishing.")
    post_images.set_defaults(func=command_post_images)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
