# Reddit Workflow

## What this skill packages

- Subreddit flair discovery.
- Reddit gallery, image, link, and self-post submission.
- Optional first-comment posting without browser automation.
- Authenticated profile-submission fetches for lightweight analytics.
- Native Reddit video posting.
- A portable JSON plan format that can live in any repo.

## Runtime dependencies

The Reddit clients expect machine-local credentials at:
- `~/.secrets/reddit/env`

The active Python interpreter should have:
- `praw`
- `httpx`
- `pydantic`
- `pyotp` only when Reddit 2FA automation is needed
- `ffmpeg` only for native Reddit video uploads

On a fresh boot, start with:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/native_video_cli.py status
```

## Keep state outside the skill

Do not store campaign drafts, assets, or trackers inside the skill folder.

Keep them in the active repo or project that owns the content:
- post bodies
- comment drafts
- image assets
- subreddit notes
- posting logs

For recurring topic families, keep only the project-local Reddit files that materially help future posting. Usually that means:
- one notes file for topic-specific subreddit guidance or quirks
- the current first-comment draft if it will likely be reused
- per-subreddit plan files only while the campaign is active
- final URLs and outcomes in the project tracker when the posts actually go live

Do not create extra structure unless it is helping.
The skill should stay reusable; the campaign should stay local to the work.

## Recommended workflow

1. Create or gather the content assets in the active project.
2. Inspect runtime status first.
3. Inspect flairs with:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-flairs --subreddit LocalLLaMA
```

4. Prepare a single plan JSON file when the post is non-trivial.
5. Dry-run the plan before live submission.
6. Submit the post.
7. Update the project-local tracker with the final URL, comment URL, and any moderation outcome.

## Dry-run first

Use `submit-plan --dry-run` whenever:
- the subreddit is strict
- the gallery has many images
- relative file paths are involved
- the first comment is long

Dry-run resolves relative paths and file-backed text without posting.

For native video, use `post --dry-run` first whenever the targets file, comment file, or video path changed.

## Platform fit rules

- Prefer gallery posts when the content is inherently visual and the subreddit allows it.
- Prefer self-posts when the community disallows galleries or expects substantive text.
- Avoid external links in strict communities unless the user explicitly wants a link-first strategy.
- When the format is unclear, confirm with the user before posting.

## Commands

Status:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/native_video_cli.py status
```

List flairs:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-flairs --subreddit OpenAI
```

List recent submissions:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-submissions --max-items 20 --days 7
```

Submit a plan:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json
```

Native Reddit video posting:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/native_video_cli.py post --targets-file /abs/path/targets.json --comment-file /abs/path/comment.md --video-path /abs/path/demo.mp4 --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/native_video_cli.py post --targets-file /abs/path/targets.json --comment-file /abs/path/comment.md --video-path /abs/path/demo.mp4
```

## Analytics scope

The built-in analytics support is intentionally lightweight:
- fetch recent submissions for the authenticated user
- filter by time window
- support quick checks like "did I already post this?"

It is not yet a full reporting layer. If you later want subreddit-level performance summaries, richer dedupe logic, or campaign dashboards, extend the skill rather than rebuilding analytics ad hoc in a repo.
