# Reddit Workflow

## What this skill packages

- Subreddit flair discovery.
- Reddit gallery, image, link, and self-post submission.
- Optional first-comment posting without browser automation.
- Authenticated profile-submission fetches for lightweight analytics.
- A portable JSON plan format that can live in any repo.

## Runtime dependencies

The active Python environment should have:
- `praw`
- `httpx`
- `pydantic`
- `pyotp` only when Reddit 2FA automation is needed
- `ffmpeg` only for native Reddit video uploads

## Keep state outside the skill

Do not store campaign drafts, assets, or trackers inside the skill folder.

Keep them in the active repo or project that owns the content:
- post bodies
- comment drafts
- image assets
- subreddit notes
- posting logs

The skill should stay reusable; the campaign should stay local to the work.

## Recommended workflow

1. Create or gather the content assets in the active project.
2. Inspect flairs with:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py list-flairs --subreddit LocalLLaMA
```

3. Prepare a single plan JSON file when the post is non-trivial.
4. Dry-run the plan before live submission.
5. Submit the post.
6. Update the project-local tracker with the final URL, comment URL, and any moderation outcome.

## Dry-run first

Use `submit-plan --dry-run` whenever:
- the subreddit is strict
- the gallery has many images
- relative file paths are involved
- the first comment is long

Dry-run resolves relative paths and file-backed text without posting.

## Platform fit rules

- Prefer gallery posts when the content is inherently visual and the subreddit allows it.
- Prefer self-posts when the community disallows galleries or expects substantive text.
- Avoid external links in strict communities unless the user explicitly wants a link-first strategy.
- When the format is unclear, confirm with the user before posting.

## Commands

List flairs:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py list-flairs --subreddit OpenAI
```

List recent submissions:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py list-submissions --max-items 20 --days 7
```

Submit a plan:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py submit-plan --plan /abs/path/post-plan.json --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py submit-plan --plan /abs/path/post-plan.json
```

Native Reddit video posting:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_native_video_cli.py --targets-file /abs/path/targets.json --comment-file /abs/path/comment.md --video-path /abs/path/demo.mp4
```

## Analytics scope

The built-in analytics support is intentionally lightweight:
- fetch recent submissions for the authenticated user
- filter by time window
- support quick checks like "did I already post this?"

It is not yet a full reporting layer. If you later want subreddit-level performance summaries, richer dedupe logic, or campaign dashboards, extend the skill rather than rebuilding analytics ad hoc in a repo.
