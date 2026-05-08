# Reddit Workflow

## What this skill packages

- Subreddit flair discovery.
- Reddit gallery, image, link, and self-post submission.
- Optional first-comment posting without browser automation.
- Standalone commenting on existing Reddit posts.
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

## Subreddit cultural fit (read before posting)

A post can pass technical validation (correct flair, correct format, allowed link) and still flop because it offends the subreddit's culture. Validation only checks rules; culture decides whether the post lands or gets buried.

Before suggesting a subreddit, do a fit check on:

- **Tooling stance.** Does the sub favor open-source/local/free tools or paid/cloud/proprietary tools? Posting paid-cloud workflows in open-source-leaning subs gets downvoted, regardless of content quality.
- **Audience identity.** Subs named after specific tools (r/StableDiffusion, r/LocalLLaMA, r/comfyui) are usually built around that specific tool's community. Off-tool content reads as misplaced even when topically adjacent.
- **Self-promo tolerance.** Some subs welcome creator showcases, others actively dislike them. Read the sidebar and pinned mod posts before assuming.
- **Content-type expectations.** Workflow posts, output showcase posts, and discussion posts often perform very differently in the same sub. Match the post shape to what the audience clicks on.

Surface the fit risk to the user **before posting**, not after. If a sub looks technically valid but culturally questionable, name the concern and let the user choose. Better to skip a sub than burn karma on a bad fit.

### Known sub-fit notes (extend as patterns surface)

- **r/StableDiffusion** — strongly biased toward open-source / local / free tooling. Posts featuring paid cloud pipelines (Kling, Runway, Sora, OpenAI image APIs, Suno, etc.) tend to get downvoted regardless of output quality, often with a comment along the lines of "this could be done with local/free tools." Skip unless the workflow is at least partly Stable-Diffusion-based or open-source.
- **r/aivideo** — link whitelist restricted to `x.ai` only (xAI/Grok), text posts blocked. Effectively only accepts xAI-sourced video.
- **r/Anthropic** — small audience focused on Claude usage and API workflows. Off-target for content where Claude is peripheral (e.g. orchestrator in a multi-tool media pipeline).

### Operator account state (Adi)

Account-specific state that affects which subs to attempt:

- **r/singularity — banned.** Submission attempts return `SUBREDDIT_NOTALLOWED_BANNED`. Skip in any campaign.

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

Add a comment to an existing post:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py comment --post-url https://reddit.com/r/OpenAI/comments/abc123/example/ --text-file /abs/path/comment.md --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py comment --post-id abc123 --text "Short follow-up"
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
