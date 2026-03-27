# LinkedIn personal posting setup

Use this when Adi wants to publish his own blog posts or personal updates to LinkedIn from local tooling.

## What this setup covers

This is the simplest useful local setup for personal LinkedIn posting:
- OAuth app bootstrap
- machine-local secret storage
- local token storage
- text posts
- article or URL shares, which is the main case for blog posts

It does not yet cover images, video, company pages, or multi-user auth.

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

## Secret lane

Use the machine-local shared lane.

Do not put LinkedIn app secrets in this repo.

Store them under:
- `~/.secrets/linkedin/env`
- `~/.secrets/linkedin/personal-posting.tokens.json`

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
- `scripts/linkedin_personal_cli.py`

### Authorize

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin_personal_cli.py authorize
```

What it does:
- opens the LinkedIn OAuth consent flow
- listens on the local callback URL
- exchanges the auth code for a token
- calls the LinkedIn userinfo endpoint
- stores the token JSON locally

### Confirm identity

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin_personal_cli.py whoami
```

### Dry-run a blog post share

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin_personal_cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are." \
  --dry-run
```

### Publish for real

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin_personal_cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are."
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

## Next likely upgrade

If this becomes a real repeated workflow, the next useful additions are:
1. image share support
2. a small wrapper that reads blog metadata directly from `blog-personal`
3. a small wrapper that reads blog metadata directly from `blog-personal`
