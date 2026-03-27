#!/usr/bin/env python3
"""Machine-first native Reddit video posting CLI."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
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

    parser = argparse.ArgumentParser(description="Native Reddit video posting CLI.", parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Inspect native-video runtime/auth state.", parents=[common])
    status.set_defaults(func=command_status, command_path="reddit-native-video status")

    post = subparsers.add_parser("post", help="Post a native Reddit video with serial upload and readiness polling.", parents=[common])
    post.add_argument("--video-url", help="Optional source URL to download.")
    post.add_argument("--video-path", help="Optional local source video path.")
    post.add_argument("--work-dir", default="tmp/reddit_uploads")
    post.add_argument("--skip-encode", action="store_true")
    post.add_argument("--poll-timeout-seconds", type=int, default=600)
    post.add_argument("--poll-interval-seconds", type=int, default=15)
    post.add_argument("--sleep-between-posts-seconds", type=int, default=45)
    post.add_argument("--retry-attempts", type=int, default=2)
    post.add_argument("--targets-file", required=True, help="JSON file containing a list of {subreddit,title,flair_keywords?} objects.")
    post.add_argument("--comment-file", required=True, help="Markdown/text file used as the first comment after the video goes live.")
    post.add_argument("--dry-run", action="store_true")
    post.set_defaults(func=command_post, command_path="reddit-native-video post")

    return parser


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    return make_status_payload(
        env_path=Path(args.env_file).expanduser(),
        supported_commands=["status", "post"],
        dependency_names=RUNTIME_DEPENDENCIES,
        include_ffmpeg=True,
    )


def command_post(args: argparse.Namespace) -> dict[str, Any]:
    _validate_source_args(args)
    work_dir = resolve_path(args.work_dir)
    targets_path = resolve_path(args.targets_file)
    comment_path = resolve_path(args.comment_file)
    if args.dry_run:
        return {
            "dry_run": True,
            "video_url": args.video_url,
            "video_path": str(resolve_path(args.video_path)) if args.video_path else None,
            "work_dir": str(work_dir),
            "skip_encode": args.skip_encode,
            "targets_file": str(targets_path),
            "comment_file": str(comment_path),
            "comment_preview": read_text_file(comment_path)[:240],
            "targets": _load_targets_json(targets_path),
            "poll_timeout_seconds": args.poll_timeout_seconds,
            "poll_interval_seconds": args.poll_interval_seconds,
            "sleep_between_posts_seconds": args.sleep_between_posts_seconds,
            "retry_attempts": args.retry_attempts,
        }

    seed_env_from_file(Path(args.env_file).expanduser())
    require_runtime_dependencies(RUNTIME_DEPENDENCIES)
    workflow_mod = _load_workflow_bits()
    encode_video_for_reddit_native_upload = workflow_mod["encode"]
    NativeRedditVideoPostingWorkflow = workflow_mod["workflow"]
    RedditVideoPostingConfig = workflow_mod["config"]
    RedditVideoPostTarget = workflow_mod["target"]

    work_dir.mkdir(parents=True, exist_ok=True)
    source_video = _resolve_source_video(args, work_dir)
    upload_video = source_video
    if not args.skip_encode:
        upload_video = work_dir / "reddit-native-video-encoded.mp4"
        try:
            encode_video_for_reddit_native_upload(input_path=source_video, output_path=upload_video)
        except Exception as exc:
            raise _classify_runtime_error(exc, hint="Verify ffmpeg is installed and the source video is readable.") from exc

    try:
        targets_raw = _load_targets_json(targets_path)
        targets = [RedditVideoPostTarget.model_validate(item) for item in targets_raw]
        config = RedditVideoPostingConfig(
            video_path=upload_video,
            first_comment_text=read_text_file(comment_path),
            poll_timeout_seconds=args.poll_timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
            sleep_between_posts_seconds=args.sleep_between_posts_seconds,
            retry_attempts=args.retry_attempts,
            delete_failed_posts=True,
        )
        workflow = NativeRedditVideoPostingWorkflow(config=config)
        try:
            results = workflow.run(targets)
        finally:
            workflow.close()
        data = {
            "dry_run": False,
            "results": to_jsonable(results),
            "failed_count": sum(1 for result in results if getattr(result, "status", None) == "failed"),
        }
        return data
    except CliError:
        raise
    except Exception as exc:
        raise _classify_runtime_error(exc, hint="Verify Reddit auth, video inputs, and target subreddits.") from exc


def _validate_source_args(args: argparse.Namespace) -> None:
    if not args.video_path and not args.video_url:
        raise CliError("Provide --video-path or --video-url.", code="E_INVALID_INPUT", exit_code=2)
    if args.video_path and args.video_url:
        raise CliError("Use either --video-path or --video-url, not both.", code="E_INVALID_INPUT", exit_code=2)


def _resolve_source_video(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.video_path:
        return resolve_path(args.video_path)
    return _download_video(url=args.video_url, output_path=work_dir / "reddit-native-video-source.mp4")


def _download_video(*, url: str, output_path: Path) -> Path:
    import httpx

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        with output_path.open("wb") as file_obj:
            for chunk in response.iter_bytes():
                file_obj.write(chunk)
    return output_path


def _load_targets_json(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise CliError(f"Targets file not found: {path}", code="E_INVALID_INPUT", exit_code=2) from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"Targets file is not valid JSON: {path}", code="E_INVALID_INPUT", exit_code=2, details={"line": exc.lineno, "column": exc.colno}) from exc
    if not isinstance(raw, list):
        raise CliError("Targets file must decode to a JSON list.", code="E_INVALID_INPUT", exit_code=2)
    return raw


def _load_workflow_bits() -> dict[str, Any]:
    if __package__ in {None, ""}:
        from reddit.native_video import (
            NativeRedditVideoPostingWorkflow,
            RedditVideoPostingConfig,
            RedditVideoPostTarget,
            encode_video_for_reddit_native_upload,
        )
    else:
        from .native_video import (
            NativeRedditVideoPostingWorkflow,
            RedditVideoPostingConfig,
            RedditVideoPostTarget,
            encode_video_for_reddit_native_upload,
        )
    return {
        "workflow": NativeRedditVideoPostingWorkflow,
        "config": RedditVideoPostingConfig,
        "target": RedditVideoPostTarget,
        "encode": encode_video_for_reddit_native_upload,
    }


def _classify_runtime_error(exc: Exception, *, hint: str) -> CliError:
    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    if isinstance(exc, FileNotFoundError):
        return CliError(message, code="E_INVALID_INPUT", exit_code=2, hint=hint)
    if "forbidden" in lower or "unauthorized" in lower or "authentication" in lower or "invalid_grant" in lower:
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
    command = getattr(args, "command_path", f"reddit-native-video {args.command}")
    try:
        data = args.func(args)
        return emit_success(args, command, data, start_time=start_time, request_id=request_id)
    except CliError as exc:
        return emit_error(args, command, exc, start_time=start_time, request_id=request_id)
    except KeyboardInterrupt:
        return emit_error(args, command, CliError("Interrupted.", code="E_TIMEOUT", exit_code=5, retryable=True), start_time=start_time, request_id=request_id)


if __name__ == "__main__":
    raise SystemExit(main())
