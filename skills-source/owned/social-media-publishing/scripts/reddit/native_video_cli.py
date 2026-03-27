#!/usr/bin/env python3
"""Entry point for native Reddit video posting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

if __package__ in {None, ""}:
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from reddit import (
        NativeRedditVideoPostingWorkflow,
        RedditVideoPostingConfig,
        RedditVideoPostTarget,
        encode_video_for_reddit_native_upload,
    )
else:
    from . import (
        NativeRedditVideoPostingWorkflow,
        RedditVideoPostingConfig,
        RedditVideoPostTarget,
        encode_video_for_reddit_native_upload,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Post a native Reddit video with serial upload, media readiness polling, "
            "and first-comment publishing."
        )
    )
    parser.add_argument("--video-url", help="Optional source URL to download.")
    parser.add_argument("--video-path", help="Optional local source video path.")
    parser.add_argument("--work-dir", default="tmp/reddit_uploads")
    parser.add_argument("--skip-encode", action="store_true")
    parser.add_argument("--poll-timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-interval-seconds", type=int, default=15)
    parser.add_argument("--sleep-between-posts-seconds", type=int, default=45)
    parser.add_argument("--retry-attempts", type=int, default=2)
    parser.add_argument(
        "--targets-file",
        required=True,
        help="JSON file containing a list of {subreddit,title,flair_keywords?} objects.",
    )
    parser.add_argument(
        "--comment-file",
        required=True,
        help="Markdown/text file used as the first comment after the video goes live.",
    )
    return parser.parse_args()


def _download_video(*, url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        with output_path.open("wb") as file_obj:
            for chunk in response.iter_bytes():
                file_obj.write(chunk)
    return output_path


def _resolve_source_video(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.video_path:
        return Path(args.video_path).expanduser().resolve()
    if not args.video_url:
        raise ValueError("Provide --video-path or --video-url.")
    return _download_video(url=args.video_url, output_path=work_dir / "reddit-native-video-source.mp4")


def main() -> int:
    args = _parse_args()
    work_dir = Path(args.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    source_video = _resolve_source_video(args, work_dir)
    upload_video = source_video
    if not args.skip_encode:
        upload_video = work_dir / "reddit-native-video-encoded.mp4"
        encode_video_for_reddit_native_upload(input_path=source_video, output_path=upload_video)

    targets_raw = json.loads(Path(args.targets_file).read_text())
    targets = [RedditVideoPostTarget.model_validate(item) for item in targets_raw]
    config = RedditVideoPostingConfig(
        video_path=upload_video,
        first_comment_text=Path(args.comment_file).read_text().strip(),
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

    print(json.dumps([result.model_dump() for result in results], indent=2))
    failed = [result for result in results if result.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
