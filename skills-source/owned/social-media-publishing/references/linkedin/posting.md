# LinkedIn posting setup

Use this when Adi wants to publish his own blog posts or personal updates to LinkedIn from local tooling.

## What this setup covers

This is the simplest useful local setup for LinkedIn posting:
- OAuth app bootstrap
- machine-local secret storage
- local token storage
- text posts
- article or URL shares, which is the main case for blog posts
- multi-image organic posts for personal profile publishing

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

## Secret lane

Use the machine-local shared lane.

Do not put LinkedIn app secrets in this repo.

Store them under:
- `~/.secrets/linkedin/env`
- `~/.secrets/linkedin/posting.tokens.json`

If an older setup still has `~/.secrets/linkedin/personal-posting.tokens.json`, the CLI falls back to it automatically.

Generated env file after machine-secret sync:

```bash
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
```

The script defaults the redirect URI and scope, so those do not need to be stored as secrets.

## One-time LinkedIn app setup

1. Go to the LinkedIn Developer Portal and create an app.
2. Under the app's Auth settings, add this redirect URL exactly:
   - `http://127.0.0.1:8765/callback`
3. Under Products, add:
   - `Share on LinkedIn`
4. If you want the script to resolve your user identifier through OIDC as part of the same flow, also add:
   - `Sign In with LinkedIn using OpenID Connect`
5. Store the Client ID and Client Secret in Key Vault under the `linkedin--...` family, then sync machine secrets

## Local CLI

Script:
- `scripts/linkedin/cli.py`
- `references/linkedin/copy.md` for native-first copy defaults and reusable post text

## Text format rule

LinkedIn post commentary should be treated as plain text, not Markdown.

Practical rule:
- paragraphs and line breaks are fine
- raw URLs are optional, not required
- normal Markdown such as `**bold**` or `[label](url)` should not be used as if LinkedIn will render it

LinkedIn's newer Posts API describes commentary as text stored in `little` text format. That format is mainly for plain text plus LinkedIn-specific constructs such as mentions and hashtags, not general Markdown rendering.

### Authorize

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize
```

What it does:
- opens the LinkedIn OAuth consent flow
- listens on the local callback URL
- exchanges the auth code for a token
- calls the LinkedIn userinfo endpoint
- stores the token JSON locally

### Confirm identity

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py whoami
```

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

The CLI defaults `Linkedin-Version` to `202603` for those `/rest` calls and exposes `--linkedin-version` if LinkedIn changes the required version later.

If the source draft starts in Markdown, convert it to plain text before posting.

## Next likely upgrade

If this becomes a real repeated workflow, the next useful additions are:
1. image thumbnail support for article shares using the Images API
2. a small wrapper that reads blog metadata directly from `blog-personal`
3. a higher-level command that packages one blog URL plus selected gallery assets into a LinkedIn post automatically
