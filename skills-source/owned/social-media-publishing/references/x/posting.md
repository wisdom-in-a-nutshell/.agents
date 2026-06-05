# X posting

Use this when Adi wants to publish personal posts to X from local tooling.

If X is already configured on this machine, start here.
If not, use `references/x/auth.md` once and then come back.

On a fresh boot, run `status` first.

## What this covers

Current minimal workflow:
- runtime/auth inspection via `status`
- text posting via `post`
- native video posting via `post-video`
- post deletion via `delete`
- machine-readable CLI output for agent use

This version does not yet cover image uploads, scheduling, or analytics.

## Video thumbnail / preview policy

For organic X video posts, prefer a native video upload. Do not publish only a
link to the video unless the user explicitly asks for a link post.

X Premium / Media Studio can expose custom video thumbnail controls in the UI,
but the current local API path used here only uploads media, waits for
processing, and attaches the returned `media_id` to a post. It does not have a
custom thumbnail field for organic video publishing.

Default agent behavior when the preview frame matters:
- Keep the master video unchanged.
- Create an X-only derivative video with the intended thumbnail/poster frame
  held at the very beginning.
- Use a short hold, normally `0.5s`, so X is likely to choose the intended frame
  while the viewer experience is only minimally delayed.
- Name the derivative clearly, for example
  `name-x-poster-hold-0p5s.mp4`.
- Publish the derivative with `post-video`.

Avoid this workaround when exact timing is mission-critical or when the video is
already designed to open on a strong thumbnail frame.

## Copy length policy

Keep API-published X posts under the standard short-post limit unless a long-post
endpoint is explicitly added and verified. Do not assume Premium account features
make long-form text available through this CLI.

When credits or context exceed the short-post limit:
- Prefer one native video post with the full intended copy when the user wants a
  single post.
- Dry-run first so the outgoing payload is inspectable.
- Do not treat an ellipsis in the API response text as proof that the live post
  is truncated; X may return a shortened representation. Verify the live post
  before deleting or splitting.
- Split into replies only when the API rejects the post, the live post is
  visibly truncated, or the user explicitly wants a thread.

## Local CLI

Script:
- `scripts/x/cli.py`

Related references:
- `references/x/auth.md` only if setup is needed
- `references/x/copy.md` for tone/defaults

## Interface contract

The X CLI follows the same machine-first pattern:
- JSON is the default output contract
- `--plain` is only for lighter operator inspection
- `--no-input` disables future interactive behavior
- `--progress auto|off|plain` controls stderr-only progress for long-running commands such as video download/upload/processing
- non-zero exit codes are classified by failure type

### First command on a fresh boot

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py status
```

What it surfaces:
- resolved env file
- whether the required OAuth 1.0a credentials are present
- whether a live `/2/users/me` probe works
- which X account is connected if the probe succeeds

### Dry-run a post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post \
  --text-file /abs/path/body.txt \
  --dry-run
```

### Publish for real

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post \
  --text-file /abs/path/body.txt
```

### Delete a post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py delete \
  --tweet-id 1234567890
```

### Dry-run a video post

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post-video \
  --text-file /abs/path/body.txt \
  --video /abs/path/video.mp4 \
  --dry-run
```

### Dry-run a video post from a public direct URL

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post-video \
  --text-file /abs/path/body.txt \
  --video-url https://example.com/video.mp4 \
  --dry-run
```

### Publish a video post for real

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/x/cli.py --progress plain post-video \
  --text-file /abs/path/body.txt \
  --video /abs/path/video.mp4
```

By default the client:
- uploads the video to X using chunked media upload
- finalizes the upload
- waits for X processing to succeed
- creates the post with the returned `media_id`

If you use `--video-url`, the client first downloads the public direct file to a temporary local path, then performs the same native X upload flow.

Important distinction:
- `post-video --video-url ...` still becomes a native X video upload
- a plain URL in the post text is only a link, not an attached native video

Operational note:
- `--video-url` sends browser-like download headers to reduce false blocks from source hosts
- if the source host still rejects the download, the CLI reports a source-download error rather than an X auth error
- transfer operations use adaptive retries and can increase per-attempt timeout on retry, while keeping the normal base request timeout short
- X processing wait defaults to an adaptive value based on video size unless you explicitly pass `--video-processing-timeout-seconds`

Useful knobs:
- `--video-poll-interval-seconds 2`
- `--video-processing-timeout-seconds 900` to override the adaptive default explicitly
- `--no-wait-for-video` if you explicitly want to skip the readiness wait

## What the client still needs from the user

Before posting will work, the machine needs X OAuth 1.0a user-context credentials in `~/.secrets/x/env`:
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

If those are missing, use `references/x/auth.md` and then come back to `status`.

## Official docs used

- X API quickstart for manage posts (`POST /2/tweets`): https://docs.x.com/x-api/posts/manage-tweets/quickstart
- OAuth 1.0a overview: https://docs.x.com/fundamentals/authentication/oauth-1-0a/overview
- Authenticated user lookup quickstart (`GET /2/users/me`): https://docs.x.com/x-api/users/lookup/quickstart/authenticated-lookup
- Media introduction: https://docs.x.com/x-api/media/introduction
- Chunked media upload quickstart: https://docs.x.com/x-api/media/quickstart/media-upload-chunked
- Media upload best practices: https://docs.x.com/x-api/media/quickstart/best-practices
