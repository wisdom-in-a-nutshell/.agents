"""CLI helpers for Reddit-first publishing workflows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if __package__ in {None, ""}:
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from reddit import GalleryImage, PrawClient, RedditClient
else:
    from . import GalleryImage, PrawClient, RedditClient


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


def _list_submissions(*, username: Optional[str], max_items: int, days: Optional[int], include_hidden: bool) -> int:
    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with RedditClient() as client:
        posts = []
        for post in client.iter_user_submissions(username=username, max_items=max_items, include_hidden=include_hidden):
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
        response = client.submit_self(subreddit=payload["subreddit"], title=payload["title"], selftext=payload["selftext"], flair_id=payload.get("flair_id"), flair_text=payload.get("flair_text"), nsfw=payload["nsfw"], spoiler=payload["spoiler"], send_replies=payload["send_replies"])
    elif payload["kind"] == "link":
        response = client.submit_link(subreddit=payload["subreddit"], title=payload["title"], url=payload["url"], flair_id=payload.get("flair_id"), flair_text=payload.get("flair_text"), nsfw=payload["nsfw"], spoiler=payload["spoiler"], send_replies=payload["send_replies"])
    elif payload["kind"] == "image":
        response = client.submit_image(subreddit=payload["subreddit"], title=payload["title"], image_path=Path(payload["image_path"]), flair_id=payload.get("flair_id"), flair_text=payload.get("flair_text"), nsfw=payload["nsfw"], spoiler=payload["spoiler"], send_replies=payload["send_replies"])
    elif payload["kind"] == "gallery":
        response = client.submit_gallery(subreddit=payload["subreddit"], title=payload["title"], images=[GalleryImage.model_validate(item) for item in payload["images"]], flair_id=payload.get("flair_id"), flair_text=payload.get("flair_text"), nsfw=payload["nsfw"], spoiler=payload["spoiler"], send_replies=payload["send_replies"])
    else:
        raise SystemExit(f"Unsupported kind: {payload['kind']}")

    result = {"submission": response.model_dump(mode="json"), "kind": payload["kind"]}
    comment_text = payload.get("comment_text")
    if comment_text:
        comment = client.add_comment(response.name, comment_text)
        result["comment"] = comment.model_dump(mode="json")
    print(json.dumps(result, indent=2))
    return 0


def _resolved_payload(plan: SubmissionPlan, base_dir: Path) -> dict[str, Any]:
    payload = plan.model_dump(mode="json")
    if plan.selftext_file:
        payload["selftext"] = _resolve_text(Path(plan.selftext_file), base_dir)
    if plan.comment_file:
        payload["comment_text"] = _resolve_text(Path(plan.comment_file), base_dir)
    if plan.image_path:
        payload["image_path"] = str(_resolve_path(Path(plan.image_path), base_dir))
    if plan.images:
        payload["images"] = [
            {
                **image.model_dump(mode="json"),
                "image_path": str(_resolve_path(Path(image.image_path), base_dir)),
            }
            for image in plan.images
        ]
    return payload


def _resolve_text(path: Path, base_dir: Path) -> str:
    return _resolve_path(path, base_dir).read_text().strip()


def _resolve_path(path: Path, base_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (base_dir / expanded).resolve()


def _load_gallery_images(path: Path, base_dir: Path) -> list[GalleryImage]:
    raw_text = path.read_text().strip()
    if not raw_text:
        return []
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return [GalleryImage(image_path=str(_resolve_path(Path(line), base_dir))) for line in lines]

    if not isinstance(parsed, list):
        raise SystemExit("Gallery images file must decode to a JSON list.")

    images: list[GalleryImage] = []
    for item in parsed:
        try:
            image = GalleryImage.model_validate(item)
        except ValidationError as exc:
            raise SystemExit(str(exc)) from exc
        image.image_path = str(_resolve_path(Path(image.image_path), base_dir))
        images.append(image)
    return images


if __name__ == "__main__":
    raise SystemExit(main())
