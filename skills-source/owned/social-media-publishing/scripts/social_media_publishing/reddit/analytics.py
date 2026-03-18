"""Lightweight Reddit submission analytics helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from social_media_publishing.reddit.client import RedditClient, RedditClientError
from social_media_publishing.reddit.models import RedditPost


class RedditProfileWorkflowConfig(BaseModel):
    """Configuration options for fetching Reddit submissions."""

    username: Optional[str] = Field(
        default=None,
        description="Optional override for the Reddit username to query.",
    )
    max_items: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Soft cap on the number of submissions to fetch.",
    )
    include_hidden: bool = Field(
        default=False,
        description="Whether to include hidden or removed posts when supported.",
    )

    model_config = ConfigDict(extra="forbid")


class RedditProfilePostsResult(BaseModel):
    """Fetched Reddit submissions and query metadata."""

    posts: list[RedditPost] = Field(default_factory=list)
    fetched_at: datetime = Field(..., description="UTC timestamp when fetch completed.")
    cutoff_timestamp: Optional[datetime] = Field(
        None,
        description="UTC cutoff used to filter posts, if any.",
    )

    model_config = ConfigDict(extra="ignore")


class RedditClientProtocol(Protocol):
    """Structural contract for Reddit analytics clients."""

    def iter_user_submissions(
        self,
        *,
        username: Optional[str] = None,
        max_items: Optional[int] = None,
        include_hidden: bool = False,
    ) -> Iterable[RedditPost]: ...

    def close(self) -> None: ...


class RedditProfileWorkflowError(Exception):
    """Raised when the Reddit analytics workflow encounters an unrecoverable error."""


class RedditProfileWorkflow:
    """Fetch and filter recent Reddit submissions for lightweight analytics."""

    def __init__(
        self,
        config: Optional[RedditProfileWorkflowConfig] = None,
        *,
        client: Optional[RedditClientProtocol] = None,
        now_factory: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._config = config or RedditProfileWorkflowConfig()
        self._client: RedditClientProtocol = client or RedditClient()
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def fetch_recent_posts(
        self,
        *,
        days: int,
        max_items: Optional[int] = None,
        include_hidden: Optional[bool] = None,
    ) -> RedditProfilePostsResult:
        """Fetch submissions created within the last `days` days."""
        if days <= 0:
            raise ValueError("days must be a positive integer.")

        cutoff = self._now_factory() - timedelta(days=days)
        return self._fetch_posts_since(
            cutoff=cutoff,
            max_items=max_items,
            include_hidden=include_hidden,
        )

    def _fetch_posts_since(
        self,
        *,
        cutoff: datetime,
        max_items: Optional[int],
        include_hidden: Optional[bool],
    ) -> RedditProfilePostsResult:
        username = self._config.username
        include_hidden = (
            include_hidden
            if include_hidden is not None
            else self._config.include_hidden
        )
        effective_max_items = _coalesce_limit(max_items, self._config.max_items)
        fetched_at = self._now_factory()

        try:
            iterator = self._client.iter_user_submissions(
                username=username,
                max_items=effective_max_items,
                include_hidden=include_hidden,
            )
            posts = _collect_until_cutoff(
                iterator=iterator,
                cutoff=cutoff,
                limit=effective_max_items,
            )
        except RedditClientError as exc:
            raise RedditProfileWorkflowError(str(exc)) from exc

        return RedditProfilePostsResult(
            posts=posts,
            fetched_at=fetched_at,
            cutoff_timestamp=cutoff,
        )

    def close(self) -> None:
        """Close the underlying client."""
        self._client.close()

    def __enter__(self) -> "RedditProfileWorkflow":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()


def _collect_until_cutoff(
    *,
    iterator: Iterable[RedditPost],
    cutoff: datetime,
    limit: Optional[int],
) -> list[RedditPost]:
    posts: list[RedditPost] = []
    for post in iterator:
        if post.created_utc < cutoff:
            continue
        posts.append(post)
        if limit is not None and len(posts) >= limit:
            break
    return posts


def _coalesce_limit(
    explicit_limit: Optional[int],
    configured_limit: Optional[int],
) -> Optional[int]:
    if explicit_limit is None:
        return configured_limit
    if configured_limit is None:
        return explicit_limit
    return min(explicit_limit, configured_limit)
