"""PRAW-based Reddit client for reliable gallery and image posting."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from .models import (
    FlairTemplate,
    GalleryImage,
    PrawSubmitResponse,
    RedditAuthSettings,
)


class PrawClient:
    """PRAW-based Reddit client with reliable media upload support."""

    def __init__(
        self,
        *,
        auth_settings: Optional[RedditAuthSettings] = None,
    ) -> None:
        self._auth_settings = auth_settings or RedditAuthSettings.from_env()
        self._praw = _load_praw_module()
        self._reddit: Optional[Any] = None

    def _get_reddit(self) -> Any:
        """Get or create the cached PRAW Reddit instance."""
        reddit_factory = self._praw.Reddit
        if self._auth_settings.totp_secret:
            return reddit_factory(
                client_id=self._auth_settings.client_id,
                client_secret=self._auth_settings.client_secret,
                username=self._auth_settings.username,
                password=self._auth_settings.build_login_password(),
                user_agent=self._auth_settings.user_agent,
            )

        if self._reddit is None:
            self._reddit = reddit_factory(
                client_id=self._auth_settings.client_id,
                client_secret=self._auth_settings.client_secret,
                username=self._auth_settings.username,
                password=self._auth_settings.build_login_password(),
                user_agent=self._auth_settings.user_agent,
            )
        return self._reddit

    def submit_image(
        self,
        *,
        subreddit: str,
        title: str,
        image_path: str | Path,
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
    ) -> PrawSubmitResponse:
        """Submit an image post to a subreddit."""
        reddit = self._get_reddit()
        sub = reddit.subreddit(subreddit)
        submission = sub.submit_image(
            title=title,
            image_path=str(image_path),
            flair_id=flair_id,
            flair_text=flair_text,
            nsfw=nsfw,
            spoiler=spoiler,
            send_replies=send_replies,
        )
        return _submit_response(submission)

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
    ) -> PrawSubmitResponse:
        """Submit a link post to a subreddit."""
        reddit = self._get_reddit()
        sub = reddit.subreddit(subreddit)
        submission = sub.submit(
            title=title,
            url=url,
            flair_id=flair_id,
            flair_text=flair_text,
            nsfw=nsfw,
            spoiler=spoiler,
            send_replies=send_replies,
            resubmit=resubmit,
        )
        return _submit_response(submission)

    def submit_self(
        self,
        *,
        subreddit: str,
        title: str,
        selftext: str = "",
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
    ) -> PrawSubmitResponse:
        """Submit a self post to a subreddit."""
        reddit = self._get_reddit()
        sub = reddit.subreddit(subreddit)
        submission = sub.submit(
            title=title,
            selftext=selftext,
            flair_id=flair_id,
            flair_text=flair_text,
            nsfw=nsfw,
            spoiler=spoiler,
            send_replies=send_replies,
        )
        return _submit_response(submission)

    def submit_gallery(
        self,
        *,
        subreddit: str,
        title: str,
        images: list[GalleryImage] | list[dict],
        flair_id: Optional[str] = None,
        flair_text: Optional[str] = None,
        nsfw: bool = False,
        spoiler: bool = False,
        send_replies: bool = True,
    ) -> PrawSubmitResponse:
        """Submit a gallery post with multiple images."""
        reddit = self._get_reddit()
        sub = reddit.subreddit(subreddit)
        praw_images: list[dict] = []
        for image in images:
            if isinstance(image, GalleryImage):
                praw_images.append(image.to_praw_dict())
            else:
                praw_images.append(image)

        submission = sub.submit_gallery(
            title=title,
            images=praw_images,
            flair_id=flair_id,
            flair_text=flair_text,
            nsfw=nsfw,
            spoiler=spoiler,
            send_replies=send_replies,
        )
        return _submit_response(submission)

    def get_subreddit_flairs(self, subreddit: str) -> list[FlairTemplate]:
        """Get available post flairs for a subreddit."""
        reddit = self._get_reddit()
        sub = reddit.subreddit(subreddit)
        return [FlairTemplate.from_praw_template(item) for item in sub.flair.link_templates]

    def add_comment(
        self,
        *,
        text: str,
        post_url: Optional[str] = None,
        post_id: Optional[str] = None,
    ) -> str:
        """Reply to an existing submission and return the comment permalink."""
        if not post_url and not post_id:
            raise ValueError("post_url or post_id is required.")

        reddit = self._get_reddit()
        if post_id:
            submission = reddit.submission(id=post_id)
        else:
            submission = reddit.submission(url=post_url)

        comment = submission.reply(text)
        return f"https://reddit.com{comment.permalink}"


def _submit_response(submission: Any) -> PrawSubmitResponse:
    return PrawSubmitResponse(
        id=submission.id,
        url=f"https://reddit.com{submission.permalink}",
        title=submission.title,
        permalink=submission.permalink,
    )


def _load_praw_module() -> ModuleType:
    """Import the optional `praw` dependency with a clear install hint."""
    try:
        return importlib.import_module("praw")
    except ImportError as exc:
        raise RuntimeError(
            "praw is required for Reddit media posting. Install it in the active environment."
        ) from exc
