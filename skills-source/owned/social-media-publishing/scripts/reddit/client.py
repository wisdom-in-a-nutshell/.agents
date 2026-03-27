"""HTTP client for interacting with Reddit's OAuth API."""

from __future__ import annotations

import time
from typing import Iterable, Optional

import httpx

from .models import (
    RedditAuthSettings,
    RedditListing,
    RedditMediaUploadLease,
    RedditPost,
    RedditSubmitResponse,
)

AUTH_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE_URL = "https://oauth.reddit.com"


class RedditClientError(Exception):
    """Raised when the Reddit client encounters an unrecoverable error."""


class RedditClient:
    """Thin wrapper over Reddit's OAuth-backed JSON API."""

    def __init__(
        self,
        *,
        auth_settings: Optional[RedditAuthSettings] = None,
        http_client: Optional[httpx.Client] = None,
        timeout: float = 30.0,
    ) -> None:
        self._auth_settings = auth_settings or RedditAuthSettings.from_env()
        self._timeout = timeout
        self._access_token: Optional[str] = None
        self._token_expiry_epoch: float = 0.0
        self._http = http_client or httpx.Client(
            base_url=API_BASE_URL,
            timeout=self._timeout,
            headers={"User-Agent": self._auth_settings.user_agent},
        )

    def fetch_user_submissions(
        self,
        *,
        username: Optional[str] = None,
        limit: int = 100,
        after: Optional[str] = None,
        include_hidden: bool = False,
    ) -> RedditListing:
        """Fetch one page of submissions for the authenticated user."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100 inclusive.")

        user = username or self._auth_settings.username
        params: dict[str, int | str] = {"limit": limit}
        if after:
            params["after"] = after
        if include_hidden:
            params["show"] = "all"

        response_json = self._request(
            "GET",
            f"/user/{user}/submitted",
            params=params,
        )
        data = response_json.get("data", {})
        posts = [RedditPost.from_api_payload(child) for child in data.get("children", [])]
        return RedditListing(posts=posts, after=data.get("after"))

    def iter_user_submissions(
        self,
        *,
        username: Optional[str] = None,
        max_items: Optional[int] = None,
        include_hidden: bool = False,
        page_size: int = 100,
    ) -> Iterable[RedditPost]:
        """Iterate user submissions while handling pagination."""
        fetched = 0
        after: Optional[str] = None

        while True:
            listing = self.fetch_user_submissions(
                username=username,
                limit=min(page_size, max_items - fetched) if max_items else page_size,
                after=after,
                include_hidden=include_hidden,
            )
            if not listing.posts:
                break

            for post in listing.posts:
                yield post
                fetched += 1
                if max_items and fetched >= max_items:
                    return

            if not listing.after:
                break
            after = listing.after

    def submit_link(
        self,
        *,
        subreddit: str,
        title: str,
        url: str,
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
        resubmit: bool = True,
    ) -> RedditSubmitResponse:
        """Submit a link post to a subreddit."""
        data: dict[str, str | bool] = {
            "sr": subreddit,
            "kind": "link",
            "title": title,
            "url": url,
            "nsfw": nsfw,
            "spoiler": spoiler,
            "sendreplies": send_replies,
            "resubmit": resubmit,
            "api_type": "json",
        }
        if flair_id:
            data["flair_id"] = flair_id
        if flair_text:
            data["flair_text"] = flair_text

        return RedditSubmitResponse.from_api_payload(self._submit(data))

    def submit_image(
        self,
        *,
        subreddit: str,
        title: str,
        image_path: str,
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
    ) -> RedditSubmitResponse:
        """Submit an image post via the JSON API."""
        import mimetypes
        from pathlib import Path

        path = Path(image_path)
        if not path.exists():
            raise RedditClientError(f"Image file not found: {image_path}")

        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        image_data = path.read_bytes()
        lease = self._get_media_upload_lease(path.name, mime_type)
        self._upload_media_to_s3(lease, image_data, mime_type)
        image_url = f"{lease.upload_url}/{lease.upload_fields.get('key', '')}"

        data: dict[str, str | bool] = {
            "sr": subreddit,
            "kind": "image",
            "title": title,
            "url": image_url,
            "nsfw": nsfw,
            "spoiler": spoiler,
            "sendreplies": send_replies,
            "api_type": "json",
        }
        if flair_id:
            data["flair_id"] = flair_id
        if flair_text:
            data["flair_text"] = flair_text

        return RedditSubmitResponse.from_api_payload(self._submit(data))

    def submit_self(
        self,
        *,
        subreddit: str,
        title: str,
        text: str = "",
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
    ) -> RedditSubmitResponse:
        """Submit a self post to a subreddit."""
        data: dict[str, str | bool] = {
            "sr": subreddit,
            "kind": "self",
            "title": title,
            "text": text,
            "nsfw": nsfw,
            "spoiler": spoiler,
            "sendreplies": send_replies,
            "api_type": "json",
        }
        if flair_id:
            data["flair_id"] = flair_id
        if flair_text:
            data["flair_text"] = flair_text

        return RedditSubmitResponse.from_api_payload(self._submit(data))

    def _submit(self, data: dict) -> dict:
        self._ensure_access_token()
        response = self._http.post(
            "/api/submit",
            data=data,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code >= 400:
            raise RedditClientError(
                f"Reddit submit error {response.status_code}: {response.text}"
            )

        payload = response.json()
        errors = payload.get("json", {}).get("errors", [])
        if errors:
            error_msgs = [f"{error[0]}: {error[1]}" for error in errors if isinstance(error, list)]
            raise RedditClientError(f"Reddit submit failed: {'; '.join(error_msgs)}")
        return payload

    def _get_media_upload_lease(
        self, filename: str, mime_type: str
    ) -> RedditMediaUploadLease:
        self._ensure_access_token()
        response = self._http.post(
            "/api/media/asset.json",
            data={"filepath": filename, "mimetype": mime_type},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code >= 400:
            raise RedditClientError(
                f"Failed to get media upload lease: {response.status_code}: {response.text}"
            )
        return RedditMediaUploadLease.from_api_payload(response.json())

    def _upload_media_to_s3(
        self,
        lease: RedditMediaUploadLease,
        image_data: bytes,
        mime_type: str,
    ) -> None:
        files = {
            "file": (lease.upload_fields.get("key", "image"), image_data, mime_type)
        }
        response = httpx.post(
            lease.upload_url,
            data=lease.upload_fields,
            files=files,
            timeout=60.0,
        )
        if response.status_code not in (200, 201, 204):
            raise RedditClientError(
                f"Failed to upload media to S3: {response.status_code}: {response.text}"
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        self._ensure_access_token()
        response = self._http.request(
            method,
            path,
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code >= 400:
            raise RedditClientError(
                f"Reddit API error {response.status_code}: {response.text}"
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise RedditClientError("Unexpected response payload from Reddit API.")
        return payload

    def _ensure_access_token(self) -> None:
        if self._access_token and time.time() < self._token_expiry_epoch:
            return

        auth = httpx.BasicAuth(
            self._auth_settings.client_id, self._auth_settings.client_secret
        )
        data = {
            "grant_type": "password",
            "username": self._auth_settings.username,
            "password": self._auth_settings.build_login_password(),
        }
        headers = {"User-Agent": self._auth_settings.user_agent}
        response = httpx.post(
            AUTH_URL,
            data=data,
            auth=auth,
            headers=headers,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise RedditClientError(
                "Failed to obtain Reddit access token: "
                f"{response.status_code} {response.text}"
            )

        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise RedditClientError("Reddit authentication response missing access_token.")

        expires_in = token_data.get("expires_in", 3600)
        self._access_token = access_token
        self._token_expiry_epoch = time.time() + max(int(expires_in) - 60, 0)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "RedditClient":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()
