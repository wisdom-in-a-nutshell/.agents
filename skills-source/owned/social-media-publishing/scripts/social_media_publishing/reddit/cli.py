"""CLI helpers for Reddit-first publishing workflows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from social_media_publishing.reddit import GalleryImage, PrawClient, RedditClient


class SubmissionPlan(BaseModel):
    """Portable plan file for a single Reddit submission."""

    kind: str = Field(..., description="One of: link, self, image, gallery.")
    subreddit: str = Field(..., description="Subreddit without r/ prefix.")
    title: str = Field(..., description="Submission title.")
    url: Optional[str] = Field(None, description="Link destination for link posts.")
    selftext: Optional[str] = Field(None, description="Body text for self posts.")
    selftext_file: Optional[str] = Field(
        None, description="Optional file path to Markdown body for self posts."
    )
    image_path: Optional[str] = Field(
        None, description="Local image path for image posts."
    )
    images: list[GalleryImage] = Field(
        default_factory=list, description="Gallery images for gallery posts."
    )
    flair_id: Optional[str] = None
    flair_text: Optional[str] = None
    nsfw: bool = False
    spoiler: bool = False
    send_replies: bool = True
    resubmit: bool = True
    comment_text: Optional[str] = Field(
        None, description="Optional first comment body to add after posting."
    )
    comment_file: Optional[str] = Field(
        None, description="Optional file path to first comment body."
    )

    model_config = ConfigDict(extra="forbid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reddit publishing CLI for the social-media-publishing skill."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_flairs = subparsers.add_parser("list-flairs", help="List flair templates.")
    list_flairs.add_argument("--subreddit", required=True)

    list_submissions = subparsers.add_parser(
        "list-submissions", help="List recent submissions for the authenticated user."
    )
    list_submissions.add_argument("--username")
    list_submissions.add_argument("--max-items", type=int, default=10)
    list_submissions.add_argument("--days", type=int)
    list_submissions.add_argument("--include-hidden", action="store_true")

    submit_plan = subparsers.add_parser(
        "submit-plan", help="Submit a plan file and optionally add a first comment."
    )
    submit_plan.add_argument("--plan", required=True)
    submit_plan.add_argument("--dry-run", action="store_true")

    submit_self = subparsers.add_parser("submit-self", help="Submit a self post.")
    _add_common_submit_args(submit_self)
    submit_self.add_argument("--selftext")
    submit_self.add_argument("--selftext-file")
    submit_self.add_argument("--comment-text")
    submit_self.add_argument("--comment-file")
    submit_self.add_argument("--dry-run", action="store_true")

    submit_link = subparsers.add_parser("submit-link", help="Submit a link post.")
    _add_common_submit_args(submit_link)
    submit_link.add_argument("--url", required=True)
    submit_link.add_argument("--comment-text")
    submit_link.add_argument("--comment-file")
    submit_link.add_argument("--dry-run", action="store_true")

    submit_image = subparsers.add_parser("submit-image", help="Submit an image post.")
    _add_common_submit_args(submit_image)
    submit_image.add_argument("--image-path", required=True)
    submit_image.add_argument("--comment-text")
    submit_image.add_argument("--comment-file")
    submit_image.add_argument("--dry-run", action="store_true")

    submit_gallery = subparsers.add_parser(
        "submit-gallery", help="Submit a gallery post from a JSON or text file."
    )
    _add_common_submit_args(submit_gallery)
    submit_gallery.add_argument(
        "--images-file",
        required=True,
        help="JSON file with image objects or newline-delimited image paths.",
    )
    submit_gallery.add_argument("--comment-text")
    submit_gallery.add_argument("--comment-file")
    submit_gallery.add_argument("--dry-run", action="store_true")

    return parser


def _add_common_submit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subreddit", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--flair-id")
    parser.add_argument("--flair-text")
    parser.add_argument("--nsfw", action="store_true")
    parser.add_argument("--spoiler", action="store_true")
    parser.add_argument("--no-send-replies", action="store_true")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-flairs":
        return _list_flairs(args.subreddit)
    if args.command == "list-submissions":
        return _list_submissions(
            username=args.username,
            max_items=args.max_items,
            days=args.days,
            include_hidden=args.include_hidden,
        )
    if args.command == "submit-plan":
        return _submit_plan(Path(args.plan), dry_run=args.dry_run)
    if args.command == "submit-self":
        plan = SubmissionPlan(
            kind="self",
            subreddit=args.subreddit,
            title=args.title,
            selftext=args.selftext,
            selftext_file=args.selftext_file,
            flair_id=args.flair_id,
            flair_text=args.flair_text,
            nsfw=args.nsfw,
            spoiler=args.spoiler,
            send_replies=not args.no_send_replies,
            comment_text=args.comment_text,
            comment_file=args.comment_file,
        )
        return _execute_plan(plan, base_dir=Path.cwd(), dry_run=args.dry_run)
    if args.command == "submit-link":
        plan = SubmissionPlan(
            kind="link",
            subreddit=args.subreddit,
            title=args.title,
            url=args.url,
            flair_id=args.flair_id,
            flair_text=args.flair_text,
            nsfw=args.nsfw,
            spoiler=args.spoiler,
            send_replies=not args.no_send_replies,
            comment_text=args.comment_text,
            comment_file=args.comment_file,
        )
        return _execute_plan(plan, base_dir=Path.cwd(), dry_run=args.dry_run)
    if args.command == "submit-image":
        plan = SubmissionPlan(
            kind="image",
            subreddit=args.subreddit,
            title=args.title,
            image_path=args.image_path,
            flair_id=args.flair_id,
            flair_text=args.flair_text,
            nsfw=args.nsfw,
            spoiler=args.spoiler,
            send_replies=not args.no_send_replies,
            comment_text=args.comment_text,
            comment_file=args.comment_file,
        )
        return _execute_plan(plan, base_dir=Path.cwd(), dry_run=args.dry_run)
    if args.command == "submit-gallery":
        images_file = Path(args.images_file).resolve()
        plan = SubmissionPlan(
            kind="gallery",
            subreddit=args.subreddit,
            title=args.title,
            images=_load_gallery_images(images_file, images_file.parent),
            flair_id=args.flair_id,
            flair_text=args.flair_text,
            nsfw=args.nsfw,
            spoiler=args.spoiler,
            send_replies=not args.no_send_replies,
            comment_text=args.comment_text,
            comment_file=args.comment_file,
        )
        return _execute_plan(plan, base_dir=Path.cwd(), dry_run=args.dry_run)
    raise RuntimeError(f"Unhandled command: {args.command}")


def _list_flairs(subreddit: str) -> int:
    client = PrawClient()
    flairs = client.get_subreddit_flairs(subreddit)
    print(json.dumps([flair.model_dump() for flair in flairs], indent=2))
    return 0


def _list_submissions(
    *,
    username: Optional[str],
    max_items: int,
    days: Optional[int],
    include_hidden: bool,
) -> int:
    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with RedditClient() as client:
        posts = []
        for post in client.iter_user_submissions(
            username=username,
            max_items=max_items,
            include_hidden=include_hidden,
        ):
            if cutoff and post.created_utc < cutoff:
                continue
            posts.append(post.model_dump(mode="json"))

    print(json.dumps(posts, indent=2))
    return 0


def _submit_plan(plan_path: Path, *, dry_run: bool) -> int:
    raw = json.loads(plan_path.read_text())
    try:
        plan = SubmissionPlan.model_validate(raw)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
    return _execute_plan(plan, base_dir=plan_path.parent, dry_run=dry_run)


def _execute_plan(plan: SubmissionPlan, *, base_dir: Path, dry_run: bool) -> int:
    payload = _resolved_payload(plan, base_dir)
    if dry_run:
        print(json.dumps({"dry_run": True, **payload}, indent=2))
        return 0

    client = PrawClient()
    result: dict[str, Any]
    if payload["kind"] == "self":
        response = client.submit_self(
            subreddit=payload["subreddit"],
            title=payload["title"],
            selftext=payload["selftext"],
            flair_id=payload.get("flair_id"),
            flair_text=payload.get("flair_text"),
            nsfw=payload["nsfw"],
            spoiler=payload["spoiler"],
            send_replies=payload["send_replies"],
        )
    elif payload["kind"] == "link":
        response = client.submit_link(
            subreddit=payload["subreddit"],
            title=payload["title"],
            url=payload["url"],
            flair_id=payload.get("flair_id"),
            flair_text=payload.get("flair_text"),
            nsfw=payload["nsfw"],
            spoiler=payload["spoiler"],
            send_replies=payload["send_replies"],
            resubmit=payload["resubmit"],
        )
    elif payload["kind"] == "image":
        response = client.submit_image(
            subreddit=payload["subreddit"],
            title=payload["title"],
            image_path=payload["image_path"],
            flair_id=payload.get("flair_id"),
            flair_text=payload.get("flair_text"),
            nsfw=payload["nsfw"],
            spoiler=payload["spoiler"],
            send_replies=payload["send_replies"],
        )
    elif payload["kind"] == "gallery":
        response = client.submit_gallery(
            subreddit=payload["subreddit"],
            title=payload["title"],
            images=[GalleryImage.model_validate(item) for item in payload["images"]],
            flair_id=payload.get("flair_id"),
            flair_text=payload.get("flair_text"),
            nsfw=payload["nsfw"],
            spoiler=payload["spoiler"],
            send_replies=payload["send_replies"],
        )
    else:
        raise SystemExit(f"Unsupported plan kind: {payload['kind']}")

    result = {"post": response.model_dump()}
    comment_text = payload.get("comment_text")
    if comment_text:
        result["comment_url"] = client.add_comment(
            post_url=response.url,
            text=comment_text,
        )

    print(json.dumps(result, indent=2))
    return 0


def _resolved_payload(plan: SubmissionPlan, base_dir: Path) -> dict[str, Any]:
    payload = plan.model_dump()
    kind = payload["kind"]
    if kind not in {"link", "self", "image", "gallery"}:
        raise SystemExit("kind must be one of: link, self, image, gallery.")

    if payload.get("selftext_file"):
        payload["selftext"] = _read_text_file(base_dir / payload["selftext_file"])
    if payload.get("comment_file"):
        payload["comment_text"] = _read_text_file(base_dir / payload["comment_file"])
    if payload.get("image_path"):
        payload["image_path"] = str((base_dir / payload["image_path"]).resolve())
    if payload.get("images"):
        payload["images"] = [
            _resolve_gallery_item(image, base_dir) for image in payload["images"]
        ]

    if kind == "link" and not payload.get("url"):
        raise SystemExit("url is required for link submissions.")
    if kind == "self":
        payload["selftext"] = payload.get("selftext") or ""
    if kind == "image" and not payload.get("image_path"):
        raise SystemExit("image_path is required for image submissions.")
    if kind == "gallery" and not payload.get("images"):
        raise SystemExit("images are required for gallery submissions.")
    return payload


def _resolve_gallery_item(image: GalleryImage | dict[str, Any], base_dir: Path) -> dict[str, Any]:
    if isinstance(image, GalleryImage):
        item = image.model_dump()
    else:
        item = dict(image)
    item["image_path"] = str((base_dir / item["image_path"]).resolve())
    return item


def _load_gallery_images(path: Path, base_dir: Path) -> list[GalleryImage]:
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text())
        if not isinstance(raw, list):
            raise SystemExit("Gallery JSON must contain a list.")
        items = []
        for item in raw:
            if isinstance(item, str):
                items.append(GalleryImage(image_path=str((base_dir / item).resolve())))
            else:
                payload = dict(item)
                payload["image_path"] = str((base_dir / payload["image_path"]).resolve())
                items.append(GalleryImage.model_validate(payload))
        return items

    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return [GalleryImage(image_path=str((base_dir / line).resolve())) for line in lines]


def _read_text_file(path: Path) -> str:
    return path.read_text().strip()


if __name__ == "__main__":
    raise SystemExit(main())
