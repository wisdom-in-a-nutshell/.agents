#!/usr/bin/env python3
"""Machine-first Reddit publishing CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

def _load_cli_support():
    support_path = Path(__file__).resolve().with_name("cli_support.py")
    spec = importlib.util.spec_from_file_location("reddit_cli_support", support_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Reddit CLI support from {support_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


_support = _load_cli_support()
DEFAULT_ENV_PATH = _support.DEFAULT_ENV_PATH
CliError = _support.CliError
emit_error = _support.emit_error
emit_success = _support.emit_success
make_request_id = _support.make_request_id
make_status_payload = _support.make_status_payload
read_text_file = _support.read_text_file
require_runtime_dependencies = _support.require_runtime_dependencies
resolve_path = _support.resolve_path
seed_env_from_file = _support.seed_env_from_file
to_jsonable = _support.to_jsonable

RUNTIME_DEPENDENCIES = ["pydantic", "httpx", "praw"]


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to machine-local Reddit credentials env file.")
    mode = common.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="Emit machine-readable JSON output. This is also the default.")
    mode.add_argument("--plain", action="store_true", help="Emit stable plain text for shell pipelines or quick operator inspection.")
    common.add_argument("--no-input", action="store_true", help="Disable any future interactive behavior.")

    parser = argparse.ArgumentParser(description="Reddit publishing CLI for the social-media-publishing skill.", parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Inspect Reddit runtime/auth state.", parents=[common])
    status.set_defaults(func=command_status, command_path="reddit status")

    list_flairs = subparsers.add_parser("list-flairs", help="List flair templates.", parents=[common])
    list_flairs.add_argument("--subreddit", required=True)
    list_flairs.set_defaults(func=command_list_flairs, command_path="reddit list-flairs")

    list_submissions = subparsers.add_parser("list-submissions", help="List recent submissions for the authenticated user.", parents=[common])
    list_submissions.add_argument("--username")
    list_submissions.add_argument("--max-items", type=int, default=10)
    list_submissions.add_argument("--days", type=int)
    list_submissions.add_argument("--include-hidden", action="store_true")
    list_submissions.set_defaults(func=command_list_submissions, command_path="reddit list-submissions")

    submit_plan = subparsers.add_parser("submit-plan", help="Submit a plan file and optionally add a first comment.", parents=[common])
    submit_plan.add_argument("--plan", required=True)
    submit_plan.add_argument("--dry-run", action="store_true")
    submit_plan.set_defaults(func=command_submit_plan, command_path="reddit submit-plan")

    submit_self = subparsers.add_parser("submit-self", help="Submit a self post.", parents=[common])
    _add_common_submit_args(submit_self)
    submit_self.add_argument("--selftext")
    submit_self.add_argument("--selftext-file")
    submit_self.add_argument("--comment-text")
    submit_self.add_argument("--comment-file")
    submit_self.add_argument("--dry-run", action="store_true")
    submit_self.set_defaults(func=command_submit_self, command_path="reddit submit-self")

    submit_link = subparsers.add_parser("submit-link", help="Submit a link post.", parents=[common])
    _add_common_submit_args(submit_link)
    submit_link.add_argument("--url", required=True)
    submit_link.add_argument("--comment-text")
    submit_link.add_argument("--comment-file")
    submit_link.add_argument("--dry-run", action="store_true")
    submit_link.set_defaults(func=command_submit_link, command_path="reddit submit-link")

    submit_image = subparsers.add_parser("submit-image", help="Submit an image post.", parents=[common])
    _add_common_submit_args(submit_image)
    submit_image.add_argument("--image-path", required=True)
    submit_image.add_argument("--comment-text")
    submit_image.add_argument("--comment-file")
    submit_image.add_argument("--dry-run", action="store_true")
    submit_image.set_defaults(func=command_submit_image, command_path="reddit submit-image")

    submit_gallery = subparsers.add_parser("submit-gallery", help="Submit a gallery post from a JSON or text file.", parents=[common])
    _add_common_submit_args(submit_gallery)
    submit_gallery.add_argument("--images-file", required=True, help="JSON file with image objects or newline-delimited image paths.")
    submit_gallery.add_argument("--comment-text")
    submit_gallery.add_argument("--comment-file")
    submit_gallery.add_argument("--dry-run", action="store_true")
    submit_gallery.set_defaults(func=command_submit_gallery, command_path="reddit submit-gallery")

    return parser


def _add_common_submit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subreddit", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--flair-id")
    parser.add_argument("--flair-text")
    parser.add_argument("--nsfw", action="store_true")
    parser.add_argument("--spoiler", action="store_true")
    parser.add_argument("--no-send-replies", action="store_true")


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    return make_status_payload(
        env_path=Path(args.env_file).expanduser(),
        supported_commands=[
            "status",
            "list-flairs",
            "list-submissions",
            "submit-plan",
            "submit-self",
            "submit-link",
            "submit-image",
            "submit-gallery",
        ],
        dependency_names=RUNTIME_DEPENDENCIES,
    )


def command_list_flairs(args: argparse.Namespace) -> dict[str, Any]:
    seed_env_from_file(Path(args.env_file).expanduser())
    require_runtime_dependencies(RUNTIME_DEPENDENCIES)
    PrawClient = _load_praw_client()
    try:
        client = PrawClient()
        flairs = client.get_subreddit_flairs(args.subreddit)
        return {"subreddit": args.subreddit, "flairs": to_jsonable(flairs)}
    except Exception as exc:
        raise _classify_runtime_error(exc, hint="Verify Reddit credentials and subreddit access.") from exc


def command_list_submissions(args: argparse.Namespace) -> dict[str, Any]:
    seed_env_from_file(Path(args.env_file).expanduser())
    require_runtime_dependencies(RUNTIME_DEPENDENCIES)
    RedditClient = _load_reddit_client()
    cutoff = None
    if args.days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    try:
        posts = []
        with RedditClient() as client:
            for post in client.iter_user_submissions(username=args.username, max_items=args.max_items, include_hidden=args.include_hidden):
                data = to_jsonable(post)
                created = getattr(post, "created_utc", None)
                if cutoff and created and created < cutoff:
                    continue
                posts.append(data)
        return {
            "username": args.username,
            "max_items": args.max_items,
            "days": args.days,
            "include_hidden": args.include_hidden,
            "posts": posts,
        }
    except Exception as exc:
        raise _classify_runtime_error(exc, hint="Verify Reddit credentials and the authenticated account.") from exc


def command_submit_plan(args: argparse.Namespace) -> dict[str, Any]:
    plan_path = resolve_path(args.plan)
    try:
        raw = json.loads(plan_path.read_text())
    except FileNotFoundError as exc:
        raise CliError(f"Plan file not found: {plan_path}", code="E_INVALID_INPUT", exit_code=2) from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"Plan file is not valid JSON: {plan_path}", code="E_INVALID_INPUT", exit_code=2, details={"line": exc.lineno, "column": exc.colno}) from exc
    plan = _validate_plan(raw)
    return _execute_plan(plan, base_dir=plan_path.parent, dry_run=args.dry_run, env_file=Path(args.env_file).expanduser())


def command_submit_self(args: argparse.Namespace) -> dict[str, Any]:
    plan = {
        "kind": "self",
        "subreddit": args.subreddit,
        "title": args.title,
        "selftext": args.selftext,
        "selftext_file": args.selftext_file,
        "flair_id": args.flair_id,
        "flair_text": args.flair_text,
        "nsfw": args.nsfw,
        "spoiler": args.spoiler,
        "send_replies": not args.no_send_replies,
        "comment_text": args.comment_text,
        "comment_file": args.comment_file,
        "resubmit": True,
    }
    return _execute_plan(_validate_plan(plan), base_dir=Path.cwd(), dry_run=args.dry_run, env_file=Path(args.env_file).expanduser())


def command_submit_link(args: argparse.Namespace) -> dict[str, Any]:
    plan = {
        "kind": "link",
        "subreddit": args.subreddit,
        "title": args.title,
        "url": args.url,
        "flair_id": args.flair_id,
        "flair_text": args.flair_text,
        "nsfw": args.nsfw,
        "spoiler": args.spoiler,
        "send_replies": not args.no_send_replies,
        "comment_text": args.comment_text,
        "comment_file": args.comment_file,
        "resubmit": True,
    }
    return _execute_plan(_validate_plan(plan), base_dir=Path.cwd(), dry_run=args.dry_run, env_file=Path(args.env_file).expanduser())


def command_submit_image(args: argparse.Namespace) -> dict[str, Any]:
    plan = {
        "kind": "image",
        "subreddit": args.subreddit,
        "title": args.title,
        "image_path": args.image_path,
        "flair_id": args.flair_id,
        "flair_text": args.flair_text,
        "nsfw": args.nsfw,
        "spoiler": args.spoiler,
        "send_replies": not args.no_send_replies,
        "comment_text": args.comment_text,
        "comment_file": args.comment_file,
        "resubmit": True,
    }
    return _execute_plan(_validate_plan(plan), base_dir=Path.cwd(), dry_run=args.dry_run, env_file=Path(args.env_file).expanduser())


def command_submit_gallery(args: argparse.Namespace) -> dict[str, Any]:
    images_file = resolve_path(args.images_file)
    plan = {
        "kind": "gallery",
        "subreddit": args.subreddit,
        "title": args.title,
        "images": _load_gallery_images(images_file, images_file.parent),
        "flair_id": args.flair_id,
        "flair_text": args.flair_text,
        "nsfw": args.nsfw,
        "spoiler": args.spoiler,
        "send_replies": not args.no_send_replies,
        "comment_text": args.comment_text,
        "comment_file": args.comment_file,
        "resubmit": True,
    }
    return _execute_plan(_validate_plan(plan), base_dir=Path.cwd(), dry_run=args.dry_run, env_file=Path(args.env_file).expanduser())


def _validate_plan(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CliError("Submission plan must be a JSON object.", code="E_INVALID_INPUT", exit_code=2)
    plan = dict(raw)
    kind = plan.get("kind")
    if kind not in {"link", "self", "image", "gallery"}:
        raise CliError("Submission kind must be one of: link, self, image, gallery.", code="E_INVALID_INPUT", exit_code=2)
    for field in ["subreddit", "title"]:
        if not isinstance(plan.get(field), str) or not str(plan.get(field)).strip():
            raise CliError(f"Submission plan is missing required field: {field}", code="E_INVALID_INPUT", exit_code=2)
    if kind == "link" and not plan.get("url"):
        raise CliError("Link posts require url.", code="E_INVALID_INPUT", exit_code=2)
    if kind == "self" and not (plan.get("selftext") or plan.get("selftext_file")):
        raise CliError("Self posts require selftext or selftext_file.", code="E_INVALID_INPUT", exit_code=2)
    if kind == "image" and not plan.get("image_path"):
        raise CliError("Image posts require image_path.", code="E_INVALID_INPUT", exit_code=2)
    if kind == "gallery":
        images = plan.get("images")
        if not isinstance(images, list) or not images:
            raise CliError("Gallery posts require a non-empty images list.", code="E_INVALID_INPUT", exit_code=2)
        normalized = []
        for item in images:
            if not isinstance(item, dict) or not item.get("image_path"):
                raise CliError("Each gallery image must be an object with image_path.", code="E_INVALID_INPUT", exit_code=2)
            normalized.append({
                "image_path": item.get("image_path"),
                "caption": item.get("caption"),
                "outbound_url": item.get("outbound_url"),
            })
        plan["images"] = normalized
    plan.setdefault("flair_id", None)
    plan.setdefault("flair_text", None)
    plan["nsfw"] = bool(plan.get("nsfw", False))
    plan["spoiler"] = bool(plan.get("spoiler", False))
    plan["send_replies"] = bool(plan.get("send_replies", True))
    plan["resubmit"] = bool(plan.get("resubmit", True))
    return plan


def _execute_plan(plan: dict[str, Any], *, base_dir: Path, dry_run: bool, env_file: Path) -> dict[str, Any]:
    payload = _resolved_payload(plan, base_dir)
    if dry_run:
        return {"dry_run": True, "payload": payload}

    seed_env_from_file(env_file)
    require_runtime_dependencies(RUNTIME_DEPENDENCIES)
    PrawClient = _load_praw_client()
    client = PrawClient()
    kind = payload["kind"]
    try:
        if kind == "self":
            response = client.submit_self(
                subreddit=payload["subreddit"],
                title=payload["title"],
                selftext=payload.get("selftext", ""),
                flair_id=payload.get("flair_id"),
                flair_text=payload.get("flair_text"),
                nsfw=payload["nsfw"],
                spoiler=payload["spoiler"],
                send_replies=payload["send_replies"],
            )
        elif kind == "link":
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
        elif kind == "image":
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
        elif kind == "gallery":
            response = client.submit_gallery(
                subreddit=payload["subreddit"],
                title=payload["title"],
                images=payload["images"],
                flair_id=payload.get("flair_id"),
                flair_text=payload.get("flair_text"),
                nsfw=payload["nsfw"],
                spoiler=payload["spoiler"],
                send_replies=payload["send_replies"],
            )
        else:
            raise CliError(f"Unsupported post kind: {kind}", code="E_INVALID_INPUT", exit_code=2)

        result: dict[str, Any] = {"kind": kind, "submission": to_jsonable(response)}
        comment_text = payload.get("comment_text")
        if comment_text:
            comment_url = client.add_comment(post_id=getattr(response, "id", None), text=comment_text)
            result["comment"] = {"url": comment_url}
        return result
    except CliError:
        raise
    except Exception as exc:
        raise _classify_runtime_error(exc, hint="Verify Reddit credentials, subreddit policy, and media assets.") from exc


def _resolved_payload(plan: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    payload = dict(plan)
    if payload.get("selftext_file"):
        payload["selftext"] = read_text_file(payload["selftext_file"], base_dir=base_dir)
    if payload.get("comment_file"):
        payload["comment_text"] = read_text_file(payload["comment_file"], base_dir=base_dir)
    if payload.get("image_path"):
        payload["image_path"] = str(resolve_path(payload["image_path"], base_dir=base_dir))
    if payload.get("images"):
        payload["images"] = [
            {
                **image,
                "image_path": str(resolve_path(image["image_path"], base_dir=base_dir)),
            }
            for image in payload["images"]
        ]
    return payload


def _load_gallery_images(path: Path, base_dir: Path) -> list[dict[str, Any]]:
    try:
        raw_text = path.read_text().strip()
    except FileNotFoundError as exc:
        raise CliError(f"Images file not found: {path}", code="E_INVALID_INPUT", exit_code=2) from exc
    if not raw_text:
        raise CliError("Images file is empty.", code="E_INVALID_INPUT", exit_code=2)
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return [{"image_path": str(resolve_path(line.strip(), base_dir=base_dir))} for line in raw_text.splitlines() if line.strip()]
    if not isinstance(parsed, list):
        raise CliError("Gallery images file must decode to a JSON list.", code="E_INVALID_INPUT", exit_code=2)
    images: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("image_path"):
            raise CliError("Each gallery image must be an object with image_path.", code="E_INVALID_INPUT", exit_code=2)
        images.append(
            {
                "image_path": str(resolve_path(item["image_path"], base_dir=base_dir)),
                "caption": item.get("caption"),
                "outbound_url": item.get("outbound_url"),
            }
        )
    return images


def _load_praw_client():
    if __package__ in {None, ""}:
        from reddit.praw_client import PrawClient
    else:
        from .praw_client import PrawClient
    return PrawClient


def _load_reddit_client():
    if __package__ in {None, ""}:
        from reddit.client import RedditClient
    else:
        from .client import RedditClient
    return RedditClient


def _classify_runtime_error(exc: Exception, *, hint: str) -> CliError:
    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    if isinstance(exc, FileNotFoundError):
        return CliError(message, code="E_INVALID_INPUT", exit_code=2, hint=hint)
    if "forbidden" in lower or "unauthorized" in lower or "invalid_grant" in lower or "authentication" in lower:
        return CliError(message, code="E_AUTH", exit_code=3, hint=hint)
    if "timed out" in lower or "timeout" in lower:
        return CliError(message, code="E_TIMEOUT", exit_code=5, retryable=True, hint=hint)
    if any(token in lower for token in ["connection", "network", "dns", "temporar", "rate limit", "http"]):
        return CliError(message, code="E_NETWORK", exit_code=4, retryable=True, hint=hint)
    return CliError(message, code="E_GENERIC", exit_code=1, hint=hint)


def main(argv: list[str] | None = None) -> int:
    start_time = time.time()
    request_id = make_request_id()
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command_path", f"reddit {args.command}")
    try:
        data = args.func(args)
        return emit_success(args, command, data, start_time=start_time, request_id=request_id)
    except CliError as exc:
        return emit_error(args, command, exc, start_time=start_time, request_id=request_id)
    except KeyboardInterrupt:
        return emit_error(args, command, CliError("Interrupted.", code="E_TIMEOUT", exit_code=5, retryable=True), start_time=start_time, request_id=request_id)


if __name__ == "__main__":
    raise SystemExit(main())
