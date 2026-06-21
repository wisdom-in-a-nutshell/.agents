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
- single-video posts
- multi-image organic posts for personal profile publishing
- comments on posts
- comment read-back
- organization/page role lookup
- member post and video analytics
- machine-readable CLI output for agent use

It assumes auth is already in place.

It does not yet cover company pages or multi-user auth. If a task involves company pages, Community Management API access, analytics, or permission/read-back expansion, read `community-management.md`.

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
- Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-03
- Videos API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api?view=li-lms-2025-07
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
- `--progress auto|off|plain` controls stderr-only progress for long-running commands such as video upload
- non-zero exit codes are classified by failure type
- `authorize --scope-preset community` requests the documented Community Management scope set
- `community-status` reports configured/granted scopes plus non-mutating Community Management probes

Default behavior is JSON. Use `--plain` only when you explicitly want a lighter inspection view.
Global flags such as `--json`, `--plain`, and `--progress` should be passed before the subcommand.

### First command on a fresh boot

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py status
```

What it surfaces:
- resolved env file and token file
- whether the current token is present and still valid
- which LinkedIn identity is connected
- whether non-mutating read-back permissions appear to work for this app
- configured vs granted Community Management scopes

Stable exit code model:
- `0` success
- `2` invalid usage or validation failure
- `3` authentication or authorization failure
- `4` network, dependency, or rate-limit failure
- `5` timeout

### Re-authorize with Community Management scopes

After LinkedIn provisions Community Management API access for the app, re-authorize once:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize --scope-preset community
```

This requests the Community Management scope preset without changing command semantics for normal posting. The saved token must include the new scopes before analytics, organization ACLs, or REST comment read-back can work.

If browser auto-open is undesirable, pass `--no-browser`; the CLI prints the authorization URL to stderr and waits for the local callback. `--no-input` intentionally fails fast for `authorize` because OAuth consent cannot complete non-interactively.

### Inspect Community Management capability state

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py community-status
```

This reports:
- configured app id and scope set
- token/granted scope coverage
- non-mutating probes for member post read-back, member post analytics, and organization ACLs
- next action when the token still needs re-authorization

## Text format rule

LinkedIn post commentary should be treated as plain text, not Markdown.

Practical rule:
- paragraphs and line breaks are fine
- raw URLs are optional, not required
- normal Markdown such as `**bold**` or `[label](url)` should not be used as if LinkedIn will render it

LinkedIn's newer Posts API describes commentary as text stored in `little` text format. That format is mainly for plain text plus LinkedIn-specific constructs such as mentions and hashtags, not general Markdown rendering.

### Dry-run a blog post share

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are." \
  --dry-run
```

### Publish for real

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post \
  --text-file /abs/path/body.txt \
  --url https://adithyan.io/blog/codex-plugins-visual-explainer \
  --title "Codex plugins, visually explained" \
  --description "A seven-panel visual guide to what Codex plugins are."
```

### Dry-run a single-image post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-image \
  --text-file /abs/path/body.txt \
  --image /abs/path/cover.jpg \
  --dry-run
```

### Dry-run a video post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-video \
  --text-file /abs/path/body.txt \
  --video /abs/path/video.mp4 \
  --title "Clear public-facing video title" \
  --dry-run
```

### Dry-run a video post from a public direct URL

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-video \
  --text-file /abs/path/body.txt \
  --video-url https://example.com/video.mp4 \
  --title "Clear public-facing video title" \
  --dry-run
```

### Publish a video post for real

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --progress plain post-video \
  --text-file /abs/path/body.txt \
  --video /abs/path/video.mp4 \
  --title "Clear public-facing video title"
```

By default the client:
- uploads the local video
- finalizes the upload
- waits for LinkedIn to report the asset as `AVAILABLE`
- creates the post only after the video is ready

The post body is the main text input. For polished video posts, pass `--title`; LinkedIn displays it as the media title below the player. If `--title` is omitted, the helper leaves the media title unset instead of deriving one from a local or temporary filename.

If you use `--video-url`, the client first downloads the public direct file to a temporary local path, then performs the same native LinkedIn upload flow.

Important distinction:
- `post-video --video-url ...` still becomes a native LinkedIn video upload
- `post --url ...` is only a link share, not a native LinkedIn video post

Operational note:
- `--video-url` now sends browser-like download headers to reduce false blocks from source hosts
- never rely on `--video-url` temporary filenames for public display; always pass `--title` when the title should be visible
- if the source host still rejects the download, the CLI reports a source-download error rather than a misleading LinkedIn auth error
- when in doubt, download the file locally and use `--video`
- transfer operations use adaptive retries and can increase per-attempt timeout on retry, while keeping the normal base request timeout short
- LinkedIn processing wait now defaults to an adaptive value based on video size unless you explicitly pass `--video-processing-timeout-seconds`

Useful knobs:
- `--video-poll-interval-seconds 2`
- `--video-processing-timeout-seconds 900` to override the adaptive default explicitly
- `--no-wait-for-video` if you explicitly want to skip the readiness wait

### Dry-run a multi-image post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --image /abs/path/slide-3.jpg \
  --dry-run
```

Optional alt text can be passed once per image in the same order:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --alt-text "Title slide for Codex plugins visual explainer." \
  --alt-text "Slide explaining skills, apps, and MCP servers." \
  --dry-run
```

### Publish a multi-image post for real

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images \
  --text-file /abs/path/body.txt \
  --image /abs/path/slide-1.jpg \
  --image /abs/path/slide-2.jpg \
  --image /abs/path/slide-3.jpg
```

### Dry-run a comment / first comment

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py comment \
  --post-urn urn:li:ugcPost:1234567890 \
  --text-file /abs/path/comment.txt \
  --dry-run
```

Comment route behavior:
- `comment` defaults to `--comment-route auto`
- auto currently selects LinkedIn's legacy `/v2/socialActions/{urn}/comments` route
- the newer `/rest/socialActions/{urn}/comments` route can fail for this app with `ACCESS_DENIED partnerApiSocialActions.CREATE`
- if you explicitly need to test the newer REST route, pass `--comment-route rest`

Dry-run and live comment results include `requested_route`, `selected_route`, `routes`, `result.state`, and `next_action` so agents can see exactly which route was used or skipped.

### List comments on a post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py list-comments \
  --post-urn urn:li:ugcPost:1234567890 \
  --count 20
```

This uses the Community Management REST `socialActions/{postUrn}/comments` read path. If it returns `403`, check `community-status` and re-authorize with the Community Management scope preset.

### List organization/page roles

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py organization-acls \
  --role ADMINISTRATOR
```

Use this before any organization/page publishing work. It shows which LinkedIn organization URNs the authenticated member can administer.

### Fetch member post analytics

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py member-post-analytics \
  --post-urn urn:li:share:1234567890 \
  --metric IMPRESSION \
  --metric REACTION \
  --aggregation TOTAL
```

If `--post-urn` is omitted, the command requests aggregated analytics for the authenticated member.

### Fetch member video analytics

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py member-video-analytics \
  --post-urn urn:li:ugcPost:1234567890 \
  --metric VIDEO_PLAY \
  --aggregation TOTAL
```

### Fetch one post by URN

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json get-post \
  --post-urn urn:li:ugcPost:1234567890
```

### List recent posts

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json list-posts --count 5
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

Video posts use LinkedIn's `/rest/videos` plus `/rest/posts` endpoints:
- initialize upload with the local file size
- upload each byte range returned by LinkedIn
- finalize the upload with the returned part IDs
- poll `/rest/videos/{videoUrn}` until the status is `AVAILABLE`
- create one organic `media` post that references the returned video URN

When `--video-url` is used, the current client adds one convenience step before that flow:
- download the public direct video URL to a temporary local file

Comments use LinkedIn's legacy `/v2/socialActions/{postUrn}/comments` endpoint by default because it works with the current member-social app permissions. The newer `/rest/socialActions/{postUrn}/comments` endpoint remains available behind `comment --comment-route rest`, but it may require LinkedIn partner social-actions permission.

Single-image posts use the same image upload path as multi-image posts, but publish a `media` payload instead of `multiImage`.

The CLI defaults `Linkedin-Version` to `202603` for those `/rest` calls and exposes `--linkedin-version` if LinkedIn changes the required version later.

If the source draft starts in Markdown, convert it to plain text before posting.

If auth stops working, re-run the setup in `references/linkedin/auth.md`.

## Current permission caveat

With the current LinkedIn app used in this workspace, posting works, but read-back endpoints may still return `403 ACCESS_DENIED`. If Community Management API access has been provisioned or scopes change, read `community-management.md` before changing CLI defaults.

That means:
- `post`, `post-image`, `post-video`, `post-images`, and likely `comment` are the most reliable day-to-day commands
- `get-post`, `list-posts`, `list-comments`, `organization-acls`, `member-post-analytics`, and `member-video-analytics` require the token to be re-authorized with the approved Community Management scopes
- personal member comment read-back can still be more restricted than organization/page comment read-back, depending on which scopes LinkedIn grants to the app

Treat the read-back commands as best-effort until LinkedIn confirms the right product/scope path for this app.

## Next likely upgrade

If this becomes a real repeated workflow, the next useful additions are:
1. image thumbnail support for article shares using the Images API
2. a small wrapper that reads blog metadata directly from `blog-personal`
3. a higher-level command that packages one blog URL plus selected gallery assets into a LinkedIn post automatically
