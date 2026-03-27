"""Robust native Reddit video posting helpers."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .praw_client import PrawClient


class RedditVideoPostTarget(BaseModel):
    """Target subreddit and title settings for one native video post."""

    subreddit: str = Field(..., description="Subreddit name without r/ prefix.")
    title: str = Field(..., description="Post title.")
    flair_keywords: list[str] = Field(
        default_factory=list,
        description="Ordered flair text keywords used to auto-select a flair template.",
    )

    model_config = ConfigDict(extra="forbid")


class RedditVideoPostingConfig(BaseModel):
    """Runtime configuration for serial Reddit native video posting."""

    video_path: Path = Field(..., description="Local MP4 path used for native upload.")
    first_comment_text: str = Field(
        ...,
        description="Markdown comment posted after media is verified live.",
    )
    poll_timeout_seconds: int = Field(default=600, ge=30)
    poll_interval_seconds: int = Field(default=15, ge=5)
    sleep_between_posts_seconds: int = Field(default=30, ge=0)
    retry_attempts: int = Field(default=1, ge=1)
    delete_failed_posts: bool = Field(default=True)
    existing_post_lookback_minutes: int = Field(default=360, ge=5)
    existing_post_ready_check_seconds: int = Field(default=120, ge=10)

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


class RedditVideoPostResult(BaseModel):
    """Outcome of processing one subreddit target."""

    subreddit: str = Field(..., description="Subreddit name without r/ prefix.")
    title: str = Field(..., description="Post title.")
    status: str = Field(..., description="Result status.")
    post_id: Optional[str] = Field(None, description="Created or reused post id.")
    post_url: Optional[str] = Field(None, description="Created or reused post URL.")
    comment_url: Optional[str] = Field(None, description="First comment permalink.")
    error: Optional[str] = Field(None, description="Failure reason.")
    note: Optional[str] = Field(None, description="Non-fatal recovery note.")

    model_config = ConfigDict(extra="forbid")


def encode_video_for_reddit_native_upload(
    *, input_path: Path, output_path: Path
) -> Path:
    """Encode an MP4 to a safer Reddit-native upload profile."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        "fps=30,scale='if(gt(iw,1920),1920,iw)':'if(gt(ih,1080),1080,ih)':force_original_aspect_ratio=decrease",
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "22",
        "-maxrate",
        "6M",
        "-bufsize",
        "12M",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-ar",
        "48000",
        str(output_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg failed"
        raise RuntimeError(f"Failed to encode video for Reddit upload: {details}")
    return output_path


class NativeRedditVideoPostingWorkflow:
    """Serial native-video posting workflow with readiness verification."""

    def __init__(
        self,
        *,
        config: RedditVideoPostingConfig,
        client: Optional[PrawClient] = None,
    ) -> None:
        self._config = config
        self._client = client or PrawClient()
        self._reddit = self._client._get_reddit()
        self._http = httpx.Client(follow_redirects=True, timeout=15.0)
        self._username = str(self._reddit.user.me()).lower()

    def close(self) -> None:
        """Release network resources."""
        self._http.close()

    def run(self, targets: list[RedditVideoPostTarget]) -> list[RedditVideoPostResult]:
        """Post the configured video to subreddits serially with health checks."""
        results: list[RedditVideoPostResult] = []
        for index, target in enumerate(targets):
            results.append(self._run_target(target))
            if index < len(targets) - 1 and self._config.sleep_between_posts_seconds > 0:
                time.sleep(self._config.sleep_between_posts_seconds)
        return results

    def _run_target(self, target: RedditVideoPostTarget) -> RedditVideoPostResult:
        existing = self._find_recent_matching_submission(target=target)
        if existing is not None:
            if self._wait_for_video_ready(
                existing,
                timeout_seconds=self._config.existing_post_ready_check_seconds,
            ):
                comment_url = self._ensure_first_comment(existing)
                return RedditVideoPostResult(
                    subreddit=target.subreddit,
                    title=target.title,
                    status="existing_ready",
                    post_id=existing.id,
                    post_url=self._submission_url(existing),
                    comment_url=comment_url,
                    note="Reused existing ready post with matching title.",
                )
            if self._config.delete_failed_posts:
                self._delete_submission(existing)

        last_error: Optional[str] = None
        recovered_note: Optional[str] = None
        for attempt in range(1, self._config.retry_attempts + 1):
            submission, recovered_note, submit_error = self._submit_video_once(target=target)
            if submission is None:
                last_error = submit_error
                continue

            if self._wait_for_video_ready(submission):
                comment_url = self._ensure_first_comment(submission)
                return RedditVideoPostResult(
                    subreddit=target.subreddit,
                    title=target.title,
                    status="posted",
                    post_id=submission.id,
                    post_url=self._submission_url(submission),
                    comment_url=comment_url,
                    note=recovered_note,
                )

            last_error = (
                f"Media processing did not complete within "
                f"{self._config.poll_timeout_seconds}s"
            )
            if self._config.delete_failed_posts:
                self._delete_submission(submission)
            if attempt < self._config.retry_attempts:
                time.sleep(max(10, self._config.poll_interval_seconds))

        return RedditVideoPostResult(
            subreddit=target.subreddit,
            title=target.title,
            status="failed",
            error=last_error or "Unknown error",
        )

    def _submit_video_once(
        self, *, target: RedditVideoPostTarget
    ) -> tuple[Optional[Any], Optional[str], Optional[str]]:
        sub = self._reddit.subreddit(target.subreddit)
        flair_id = self._pick_flair_id(sub=sub, keywords=target.flair_keywords)
        try:
            submission = sub.submit_video(
                title=target.title,
                video_path=str(self._config.video_path),
                flair_id=flair_id,
                send_replies=True,
                resubmit=True,
            )
            return submission, None, None
        except Exception as exc:
            error_text = str(exc)
            recovered = self._find_recent_matching_submission(
                target=target,
                max_age_minutes=20,
            )
            if recovered is not None:
                return recovered, f"Recovered from submit exception: {error_text}", None
            return None, None, error_text

    def _pick_flair_id(self, *, sub: Any, keywords: list[str]) -> Optional[str]:
        if not keywords:
            return None
        try:
            templates = list(sub.flair.link_templates)
        except Exception:
            return None

        for keyword in keywords:
            needle = keyword.lower().strip()
            for template in templates:
                flair_text = str(template.get("text") or "")
                flair_id = template.get("id")
                if flair_id and needle in flair_text.lower():
                    return str(flair_id)
        return None

    def _find_recent_matching_submission(
        self,
        *,
        target: RedditVideoPostTarget,
        max_age_minutes: Optional[int] = None,
    ) -> Optional[Any]:
        lookback_minutes = (
            max_age_minutes
            if max_age_minutes is not None
            else self._config.existing_post_lookback_minutes
        )
        now_ts = datetime.now(timezone.utc).timestamp()
        for submission in self._reddit.user.me().submissions.new(limit=100):
            same_subreddit = (
                str(submission.subreddit.display_name).lower()
                == target.subreddit.lower().strip()
            )
            same_title = str(submission.title).strip() == target.title.strip()
            if not same_subreddit or not same_title:
                continue

            age_minutes = (now_ts - float(submission.created_utc)) / 60.0
            if age_minutes <= lookback_minutes:
                return submission
        return None

    def _wait_for_video_ready(
        self, submission: Any, timeout_seconds: Optional[int] = None
    ) -> bool:
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self._config.poll_timeout_seconds
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            refreshed = self._reddit.submission(id=submission.id)
            dash_url = self._get_dash_url(refreshed)
            if dash_url and self._is_playlist_live(dash_url):
                return True
            time.sleep(self._config.poll_interval_seconds)
        return False

    def _get_dash_url(self, submission: Any) -> Optional[str]:
        media = submission.media or submission.secure_media
        if not isinstance(media, dict):
            return None
        reddit_video = media.get("reddit_video")
        if not isinstance(reddit_video, dict):
            return None
        dash_url = reddit_video.get("dash_url")
        if isinstance(dash_url, str) and dash_url.strip():
            return dash_url
        return None

    def _is_playlist_live(self, dash_url: str) -> bool:
        try:
            response = self._http.get(dash_url)
            return response.status_code == 200
        except Exception:
            return False

    def _ensure_first_comment(self, submission: Any) -> Optional[str]:
        submission.comment_sort = "new"
        submission.comments.replace_more(limit=0)
        for comment in submission.comments:
            author = getattr(comment, "author", None)
            if author and str(author).lower() == self._username:
                return f"https://reddit.com{comment.permalink}"
        created = submission.reply(self._config.first_comment_text)
        return f"https://reddit.com{created.permalink}"

    def _delete_submission(self, submission: Any) -> None:
        try:
            submission.delete()
        except Exception:
            return

    @staticmethod
    def _submission_url(submission: Any) -> str:
        return f"https://reddit.com{submission.permalink}"
