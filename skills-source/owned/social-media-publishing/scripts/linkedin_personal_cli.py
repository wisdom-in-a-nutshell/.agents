#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
DEFAULT_TOKENS_PATH = Path.home() / ".secrets/linkedin/personal-posting.tokens.json"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
DEFAULT_SCOPE = "openid profile w_member_social"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"


class CliError(RuntimeError):
    pass


@dataclass
class Config:
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str
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
        env_path=Path(args.env_file).expanduser(),
        tokens_path=Path(args.tokens_file).expanduser(),
    )


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local LinkedIn personal posting helper.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local LinkedIn app credentials env file.")
    parser.add_argument("--tokens-file", default=str(DEFAULT_TOKENS_PATH), help="Path to machine-local LinkedIn token JSON file.")
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
