# LinkedIn posting

Use this when Adi wants to publish his own blog posts or personal updates to LinkedIn from local tooling.

If LinkedIn is already authenticated on this machine, start here.

If not, use `references/linkedin/auth.md` once and then come back.

On a fresh boot, run `status` first so the client can surface what is actually usable on this machine right now.

## What this covers

This is the simplest useful local workflow for day-to-day LinkedIn posting:
- text posts
- article or URL shares, which is the main case for blog posts
- single-image posts
- multi-image organic posts for personal profile publishing
- comments on posts
- machine-readable CLI output for agent use

It assumes auth is already in place.

It does not yet cover video, company pages, or multi-user auth.

## Why this shape

For Adi's use case, the best first version is a one-user local script, not a whole service.

That keeps it:
- private
- reversible
- easy to debug
- good enough for publishing personal posts that link back to the blog

## Official LinkedIn docs to follow

- Authorization Code Flow (3-legged OAuth): https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- Share on LinkedIn: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
- Programmatic refresh tokens: https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens
- Sign In with LinkedIn using OpenID Connect: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
- Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2025-11
- Images API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api?view=li-lms-2026-02
- MultiImage API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/multiimage-post-api?view=li-lms-2026-03

## Local CLI

Script:
- `scripts/linkedin/cli.py`
- `references/linkedin/copy.md` for native-first copy defaults and reusable post text
- `references/linkedin/auth.md` only if setup or re-auth is needed

## Interface contract

The LinkedIn CLI now follows a more agent-first contract:

- `--json` returns one structured JSON object
- `--plain` returns stable plain text for shell pipelines
- `--no-input` disables browser auto-open and any interactive input assumptions
- non-zero exit codes are classified by failure type

Default behavior is JSON. Use `--plain` only when you explicitly want a lighter inspection view.

### First command on a fresh boot

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py status
```

What it surfaces:
- resolved env file and token file
- whether the current token is present and still valid
- which LinkedIn identity is connected
- whether non-mutating read-back permissions appear to work for this app

Stable exit code model:
- `0` success
- `2` invalid usage or validation failure
- `3` authentication or authorization failure
- `4` network, dependency, or rate-limit failure
- `5` timeout

## Text format rule

LinkedIn post commentary should be treated as plain text, not Markdown.

Practical rule:
- paragraphs and line breaks are fine
- raw URLs are optional, not required
- normal Markdown such as `**bold**` or `[label](url)` should not be used as if LinkedIn will render it

LinkedIn's newer Posts API describes commentary as text stored in `little` text format. That format is mainly for plain text plus LinkedIn-specific constructs such as mentions and hashtags, not general Markdown rendering.

### Dry-run a blog post share

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are." \
  --dry-run
```

### Publish for real

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are."
```

### Dry-run a single-image post

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-image \
  --text-file /abs/path/body.txt \
  --image /abs/path/cover.jpg \
  --dry-run
```

### Dry-run a multi-image post

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --image /abs/path/slide-3.jpg \
  --dry-run
```

Optional alt text can be passed once per image in the same order:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --alt-text "Title slide for Codex plugins visual explainer." \
  --alt-text "Slide explaining skills, apps, and MCP servers." \
  --dry-run
```

### Publish a multi-image post for real

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --image /abs/path/slide-3.jpg
```

### Dry-run a comment / first comment

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py comment \
  --post-urn urn:li:ugcPost:1234567890 \
  --text-file /abs/path/comment.txt \
  --dry-run
```

### Fetch one post by URN

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json get-post \
  --post-urn urn:li:ugcPost:1234567890
```

### List recent posts

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json list-posts --count 5
```

## Important implementation note

The script uses LinkedIn's `ugcPosts` endpoint for member shares.

For article shares, it sends:
- commentary text
- the blog URL
- optional title
- optional description

The script currently derives the member author URN from the OIDC `sub` field as:
- `urn:li:person:<sub>`

That is the practical interpretation implied by LinkedIn's docs, but treat it as an implementation assumption worth re-checking if LinkedIn changes this behavior.

Multi-image posts use LinkedIn's newer `/rest/images` and `/rest/posts` endpoints:
- initialize one upload per image
- upload each binary file
- create one organic `multiImage` post that references the returned image URNs

Comments use LinkedIn's `/rest/socialActions/{postUrn}/comments` endpoint.

Single-image posts use the same image upload path as multi-image posts, but publish a `media` payload instead of `multiImage`.

The CLI defaults `Linkedin-Version` to `202603` for those `/rest` calls and exposes `--linkedin-version` if LinkedIn changes the required version later.

If the source draft starts in Markdown, convert it to plain text before posting.

If auth stops working, re-run the setup in `references/linkedin/auth.md`.

## Current permission caveat

With the current LinkedIn app used in this workspace, posting works, but read-back endpoints may still return `403 ACCESS_DENIED`.

That means:
- `post`, `post-image`, `post-images`, and likely `comment` are the most reliable day-to-day commands
- `get-post` and `list-posts` may require additional LinkedIn access that this app does not currently have

Treat the read-back commands as best-effort until LinkedIn confirms the right product/scope path for this app.

## Next likely upgrade

If this becomes a real repeated workflow, the next useful additions are:
1. image thumbnail support for article shares using the Images API
2. a small wrapper that reads blog metadata directly from `blog-personal`
3. a higher-level command that packages one blog URL plus selected gallery assets into a LinkedIn post automatically
