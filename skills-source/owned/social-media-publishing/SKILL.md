---
name: social-media-publishing
description: Multi-channel social publishing workflow plus blog-post publication prep and channel CLIs for Reddit, LinkedIn, X, YouTube, Instagram, and TikTok. Use when Codex needs to publish or distribute a blog post, video, launch, or visual explainer; prepare blog assets; decide between gallery, image, self, link, or native video format; publish the source post before distribution; post to Reddit; publish LinkedIn text/link/image/video posts; post X text/video posts; or prepare Instagram/TikTok posts through dry-run channel CLIs.
---

# Social Media Publishing

## Overview

Use this skill to package publishing and distribution work as a reusable workflow instead of repo-specific one-offs.

Keep campaign assets in the active project. Keep durable repo-specific publishing conventions in the owning repo. The current bundled channel helpers cover Reddit, LinkedIn, X, Modal-backed YouTube uploads, and initial dry-run scaffolds for Instagram and TikTok.

## Workflow

1. Decide whether the content needs to be published at the source first, for example in a blog repo.
2. Keep campaign state in the active repo, not in this skill.
3. Choose the post shape with the user first: gallery, self, link, or image.
4. Inspect subreddit flairs before posting when flair is required or likely to matter.
5. Prefer a plan file for repeatable or multi-step posts.
6. Dry-run the plan before live submission when paths, long comments, or strict communities are involved.
7. After posting, update the project-local tracker with the post URL, comment URL, and moderation outcome.
8. For source-post workflows, default to publishing the post publicly (set `hidden: false` in frontmatter unless the user explicitly asks for a private/draft post).

## Blog-backed publishing

If the user asks to publish the source post itself before distribution, read:
- `references/blog/publishing.md`

Keep durable repo-specific publishing mechanics in the owning repo and in the reference file, not in this top-level skill body.

## Reddit

Use the bundled CLI at `scripts/reddit/cli.py`.

For live commands and plan structure, read:
- `references/reddit/workflow.md`
- `references/reddit/plan-schema.md`

If the content is Codex / App Server / coding-agent-internals related and you expect repeated Reddit distribution, also read:
- `references/reddit/topics/codex.md`

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-flairs --subreddit OpenAI
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-submissions --max-items 20 --days 7
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py comment --post-url https://reddit.com/r/OpenAI/comments/abc123/example/ --text-file /abs/path/comment.md --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json
```

The CLI supports:
- flair discovery
- gallery submission
- image submission
- link submission
- self-post submission
- optional first-comment posting
- standalone commenting on existing posts
- authenticated submission history lookup

## LinkedIn

Use the bundled LinkedIn CLI at `scripts/linkedin/cli.py` for local LinkedIn publishing.

Read first:
- `references/linkedin/posting.md`
- `references/linkedin/copy.md`

If LinkedIn app product access changes, company pages are involved, or analytics/read-back is needed:
- `references/linkedin/community-management.md`

Only if setup or re-auth is needed:
- `references/linkedin/auth.md`

Current supported flow:
- local OAuth authorization
- runtime/auth inspection via `status`
- identity check
- text posts
- article or URL shares
- single-image posts
- single-video posts
- multi-image posts
- comments on posts
- machine-readable JSON output by default, plus optional `--plain` inspection mode
- stderr-only progress for long-running video uploads via `--progress`

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py whoami
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post --text-file /abs/path/body.txt --url https://example.com/post --title "Post title" --description "Short description" --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-image --text-file /abs/path/body.txt --image /abs/path/cover.jpg --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-video --text-file /abs/path/body.txt --video /abs/path/video.mp4 --title "Public video title" --thumbnail /abs/path/thumbnail.png --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-video --text-file /abs/path/body.txt --video-url https://example.com/video.mp4 --title "Public video title" --thumbnail /abs/path/thumbnail.png --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images --text-file /abs/path/body.txt --image /abs/path/slide-1.jpg --image /abs/path/slide-2.jpg --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py comment --post-urn urn:li:ugcPost:... --text-file /abs/path/comment.txt --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json list-posts --count 5
```

For polished LinkedIn native video posts, always pass `--title`; LinkedIn shows it as the media title below the player. Pass `--thumbnail` when a custom cover is available. If `--title` is omitted, the helper leaves the media title unset instead of deriving one from a temporary download filename.

This helper uses machine-local generated secrets under `~/.secrets/linkedin/` and should stay one-user until the workflow is more mature.

## Instagram

Use the bundled Instagram CLI at `scripts/instagram/cli.py` for local Instagram publishing preparation.

Read first:
- `references/instagram/posting.md`

Current supported flow:
- runtime/config inspection via `status`
- dry-run validation for image posts, video/Reel posts, and carousel posts
- machine-readable JSON output by default, plus optional `--plain` inspection mode
- live publishing intentionally disabled pending Meta app/account/token setup

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-image --text-file /abs/path/caption.txt --image-url https://example.com/image.jpg --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-video --text-file /abs/path/caption.txt --video-url https://example.com/video.mp4 --reel --share-to-feed --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-carousel --text-file /abs/path/caption.txt --media-url https://example.com/1.jpg --media-url https://example.com/2.jpg --dry-run
```

## TikTok

Use the bundled TikTok CLI at `scripts/tiktok/cli.py` for local TikTok publishing preparation.

Read first:
- `references/tiktok/posting.md`

Current supported flow:
- runtime/config inspection via `status`
- dry-run validation for video posts and photo-mode posts
- machine-readable JSON output by default, plus optional `--plain` inspection mode
- live publishing intentionally disabled pending TikTok developer app/OAuth/API review setup

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-video --text-file /abs/path/caption.txt --video-url https://example.com/video.mp4 --privacy SELF_ONLY --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-video --text "Short caption" --source FILE_UPLOAD --video /abs/path/video.mp4 --ai-generated --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-photos --title "Photo title" --description-file /abs/path/description.txt --photo-url https://example.com/1.jpg --photo-url https://example.com/2.jpg --cover-index 0 --privacy SELF_ONLY --dry-run
```


## YouTube

Use the bundled YouTube CLI at `scripts/youtube/cli.py` for local YouTube publishing through the existing Modal upload engine.

Read first:
- `references/youtube/posting.md`

Current supported flow:
- runtime/config inspection via `status`
- upload from a public direct `--video-url` through Modal
- upload from a local `--video` by staging into the Modal cache volume, then calling Modal
- intentionally small upload surface: video, title, description, optional thumbnail, optional privacy
- machine-readable JSON output by default, plus optional `--plain` inspection mode
- stderr-only progress via `--progress`

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py upload-video --video /abs/path/video.mp4 --title "Video title" --description-file /abs/path/description.md --privacy private --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py --progress plain upload-video --video /abs/path/video.mp4 --title "Video title" --description-file /abs/path/description.md --privacy unlisted
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py upload-video --video-url https://example.com/video.mp4 --title "Video title" --description-file /abs/path/description.md --privacy unlisted --dry-run
```

YouTube is Modal-backed by design. The CLI is personal-account-first: credentials id `ADITHYAN`, notify subscribers on, made-for-kids off, embeddable on. Do not import WIN or duplicate the local YouTube uploader in this skill unless Modal becomes a proven bottleneck.


## X

Use the bundled X CLI at `scripts/x/cli.py` for local X posting.

Read first:
- `references/x/posting.md`
- `references/x/copy.md`

Only if setup is still missing:
- `references/x/auth.md`

Current supported flow:
- runtime/auth inspection via `status`
- text posts
- native video posts from a local file or public direct video URL
- machine-readable JSON output by default, plus optional `--plain` inspection mode
- stderr-only progress for long-running video uploads via `--progress`

Core commands:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post --text-file /abs/path/body.txt --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post-video --text-file /abs/path/body.txt --video /abs/path/video.mp4 --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post-video --text-file /abs/path/body.txt --video-url https://example.com/video.mp4 --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post --text-file /abs/path/body.txt
```

## Packaging Rules

- Keep the skill reusable and the campaign local.
- Draft assets go in `<repo>/tmp/social/<channel>/<slug>/` (gitignored, throwaway). Do not put drafts in `capture/` or other tracked folders.
- Keep credentials in environment variables or the user's authenticated tools, not in project files.
- Use absolute paths in ad hoc commands when possible.
- Use relative paths inside plan files when the plan lives next to the assets.
- Prefer plan files over long shell commands once the post has more than a title plus one asset.
- If the social post depends on a live blog URL, publish and verify the blog post first.

## Resources

- `scripts/reddit/cli.py`: Reddit CLI entrypoint.
- `scripts/reddit/`: self-contained Reddit helpers and models.
- `references/blog/publishing.md`: blog publication workflow before distribution.
- `references/reddit/workflow.md`: operational Reddit workflow.
- `references/reddit/plan-schema.md`: portable Reddit plan-file contract.
- `scripts/youtube/cli.py`: Modal-backed YouTube upload CLI.
- `references/youtube/posting.md`: YouTube upload workflow and route contract.
- `scripts/linkedin/cli.py`: local LinkedIn posting CLI.
- `references/linkedin/posting.md`: LinkedIn posting setup and usage.
- `references/linkedin/copy.md`: LinkedIn copy defaults and reusable post baselines.
- `references/linkedin/community-management.md`: Community Management API access, tiers, and next upgrade path.
- `scripts/x/cli.py`: local X posting CLI.
- `references/x/posting.md`: X posting setup and usage.
- `references/x/copy.md`: X copy defaults.
- `scripts/instagram/cli.py`: Instagram dry-run publishing prep CLI.
- `references/instagram/posting.md`: Instagram setup, provider constraints, and dry-run usage.
- `scripts/tiktok/cli.py`: TikTok dry-run publishing prep CLI.
- `references/tiktok/posting.md`: TikTok setup, provider constraints, and dry-run usage.
