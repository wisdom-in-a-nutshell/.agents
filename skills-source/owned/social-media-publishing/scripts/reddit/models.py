"""Typed data models for Reddit publishing helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RedditAuthSettings(BaseModel):
    """Authentication credentials required for Reddit script access."""

    client_id: str = Field(..., description="Reddit application client identifier.")
    client_secret: str = Field(..., description="Reddit application client secret.")
    username: str = Field(..., description="Reddit username for password grant auth.")
    password: str = Field(..., description="Reddit password for password grant auth.")
    user_agent: str = Field(
        ..., description="User-Agent string registered with the Reddit application."
    )
    totp_secret: Optional[str] = Field(
        None,
        description="Optional TOTP secret used to generate 2FA codes for automated logins.",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @classmethod
    def from_env(cls) -> "RedditAuthSettings":
        """Create settings from the standard Reddit environment variables."""
        from os import environ

        try:
            return cls(
                client_id=environ["REDDIT_CLIENT_ID"],
                client_secret=environ["REDDIT_CLIENT_SECRET"],
                username=environ["REDDIT_USERNAME"],
                password=environ["REDDIT_PASSWORD"],
                user_agent=environ["REDDIT_USER_AGENT"],
                totp_secret=environ.get("REDDIT_TOTP_SECRET"),
            )
        except KeyError as error:
            missing_key = error.args[0]
            raise ValueError(
                "Missing environment variable required for Reddit authentication: "
                f"{missing_key}"
            ) from error

    def build_login_password(self) -> str:
        """Return the Reddit password, appending a TOTP code when configured."""
        if not self.totp_secret:
            return self.password

        try:
            import time

            import pyotp
        except ImportError as exc:
            raise RuntimeError(
                "pyotp must be installed to support Reddit TOTP authentication."
            ) from exc

        remaining = 30 - (int(time.time()) % 30)
        if remaining < 10:
            time.sleep(remaining + 1)

        totp = pyotp.TOTP(self.totp_secret)
        return f"{self.password}:{totp.now()}"


class RedditPost(BaseModel):
    """Minimal view of a Reddit submission."""

    id: str = Field(..., description="Reddit post identifier without fullname prefix.")
    created_utc: datetime = Field(..., description="UTC timestamp of creation.")
    subreddit: str = Field(..., description="Subreddit name without r/ prefix.")
    title: str = Field(..., description="Submission title.")
    score: int = Field(..., description="Net score.")
    num_comments: int = Field(..., description="Comment count.")
    upvote_ratio: Optional[float] = Field(None, description="Upvote ratio.")
    permalink: str = Field(..., description="Permanent link path.")

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api_payload(cls, payload: dict) -> "RedditPost":
        """Convert a Reddit listing child payload into a typed model."""
        data = payload.get("data", {})
        created_raw = data.get("created_utc")
        if created_raw is None:
            raise ValueError("Reddit post payload missing created_utc.")

        return cls(
            id=data.get("id"),
            created_utc=datetime.fromtimestamp(float(created_raw), tz=timezone.utc),
            subreddit=data.get("subreddit"),
            title=data.get("title"),
            score=data.get("score", 0),
            num_comments=data.get("num_comments", 0),
            upvote_ratio=data.get("upvote_ratio"),
            permalink=data.get("permalink"),
        )


class RedditListing(BaseModel):
    """Container for paginated Reddit submission listings."""

    posts: list[RedditPost] = Field(default_factory=list)
    after: Optional[str] = Field(None, description="Pagination token.")

    model_config = ConfigDict(extra="forbid")


class RedditSubmitResponse(BaseModel):
    """Response from Reddit's submit endpoint."""

    id: str = Field(..., description="Reddit post identifier.")
    name: str = Field(..., description="Fullname of the post.")
    url: str = Field(..., description="Full URL to the submitted post.")

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api_payload(cls, payload: dict) -> "RedditSubmitResponse":
        """Parse the submit API response."""
        json_data = payload.get("json", {})
        data = json_data.get("data", {})
        post_id = data.get("id", "")
        return cls(
            id=post_id,
            name=data.get("name", f"t3_{post_id}"),
            url=data.get("url", f"https://reddit.com/comments/{post_id}"),
        )


class RedditMediaUploadLease(BaseModel):
    """Lease information for uploading media to Reddit."""

    asset_id: str = Field(..., description="Asset identifier for uploaded media.")
    upload_url: str = Field(..., description="S3 URL to upload media to.")
    upload_fields: dict = Field(default_factory=dict, description="Multipart fields.")
    websocket_url: Optional[str] = Field(None, description="Optional websocket URL.")

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_api_payload(cls, payload: dict) -> "RedditMediaUploadLease":
        """Parse the media upload lease response."""
        args = payload.get("args", {})
        fields = {field["name"]: field["value"] for field in args.get("fields", [])}
        return cls(
            asset_id=payload.get("asset", {}).get("asset_id", ""),
            upload_url=args.get("action", ""),
            upload_fields=fields,
            websocket_url=payload.get("asset", {}).get("websocket_url"),
        )


class PrawSubmitResponse(BaseModel):
    """Response from a PRAW submission."""

    id: str = Field(..., description="Reddit post identifier.")
    url: str = Field(..., description="Full URL to the submitted post.")
    title: str = Field(..., description="Post title.")
    permalink: str = Field(..., description="Permalink to the post.")

    model_config = ConfigDict(extra="forbid")


class GalleryImage(BaseModel):
    """Configuration for one image in a Reddit gallery submission."""

    image_path: str = Field(..., description="Local file path to the image.")
    caption: Optional[str] = Field(None, description="Optional caption.")
    outbound_url: Optional[str] = Field(None, description="Optional clickthrough URL.")

    model_config = ConfigDict(extra="forbid")

    def to_praw_dict(self) -> dict:
        """Convert to the dictionary format expected by PRAW."""
        result: dict = {"image_path": self.image_path}
        if self.caption:
            result["caption"] = self.caption
        if self.outbound_url:
            result["outbound_url"] = self.outbound_url
        return result


class FlairTemplate(BaseModel):
    """Typed representation of a subreddit flair template."""

    flair_id: str = Field(..., description="Unique flair template identifier.")
    flair_text: str = Field(..., description="Display text of the flair.")
    flair_text_editable: bool = Field(False, description="Whether flair text is editable.")
    flair_css_class: Optional[str] = Field(None, description="Associated CSS class.")
    background_color: Optional[str] = Field(None, description="Background color hex code.")
    text_color: Optional[str] = Field(None, description="Text color mode.")

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_praw_template(cls, template: dict) -> "FlairTemplate":
        """Convert a PRAW flair template dictionary to a typed model."""
        return cls(
            flair_id=template.get("id", ""),
            flair_text=template.get("text", ""),
            flair_text_editable=template.get("text_editable", False),
            flair_css_class=template.get("css_class"),
            background_color=template.get("background_color"),
            text_color=template.get("text_color"),
        )
