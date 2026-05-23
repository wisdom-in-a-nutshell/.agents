# TikTok Posting

Initial integration status: scaffolded CLI with machine-readable status and dry-run request validation for video and photo-mode posts. Live publishing is intentionally disabled until TikTok developer setup, OAuth, and Content Posting API review/audit are complete.

Verified against official TikTok developer docs on 2026-05-23.

## Channel stance for Adi

TikTok is a discovery experiment, not a home base.

Use it for:
- short AI-build demos
- Mac mini / local AI / agent setup clips
- before-after workflow videos
- practical founder/building observations

Avoid making TikTok an attention trap. Post/reply deliberately; do not scroll as default entertainment.

## Provider reality

TikTok has a Content Posting API for videos and photos, but public direct posting is gated:

- TikTok developer app required.
- OAuth user access token required.
- `video.publish` is used for Direct Post.
- `video.upload` is used for inbox/upload flows.
- Direct Post requires querying creator info first so the app can present TikTok's required UI/metadata options.
- Unreviewed/unaudited clients are restricted to private viewing mode for Direct Post.
- `PULL_FROM_URL` requires provider-accessible public URLs and, for video upload flows, verified URL ownership/prefixes.
- Post status must be checked by polling status or receiving webhooks.

## Requirements

Credential/config file convention:

```bash
~/.secrets/tiktok/env
```

Supported keys:

```bash
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
TIKTOK_ACCESS_TOKEN=...
TIKTOK_CONTENT_POSTING_AUDIT_PASSED=false
```

## CLI

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-video --text-file /abs/path/caption.txt --video-url https://example.com/video.mp4 --privacy SELF_ONLY --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-video --text "Short caption" --source FILE_UPLOAD --video /abs/path/video.mp4 --ai-generated --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/tiktok/cli.py post-photos --title "Photo title" --description-file /abs/path/description.txt --photo-url https://example.com/1.jpg --photo-url https://example.com/2.jpg --cover-index 0 --privacy SELF_ONLY --dry-run
```

The CLI defaults to JSON and follows the agent-first contract:

- stable output envelope
- dry-run first
- no prompts
- no secrets in flags or stdout
- errors with stable codes
- explicit privacy and AI-generated flags for video
- explicit post mode for photo posts

## Implementation route still needed

Before live publishing:

1. Decide account strategy: Adi personal TikTok vs separate builder account.
2. Create TikTok developer app.
3. Add OAuth redirect/privacy/terms URLs as required by TikTok.
4. Request Content Posting API scopes.
5. Complete audit if public Direct Post is needed.
6. Implement provider route:
   - OAuth authorization and refresh handling
   - `creator_info/query`
   - Direct Post video init or inbox upload video init
   - photo content init
   - file upload or pull-from-url transfer
   - status polling and/or webhooks
   - audit-aware privacy gating
7. Add tests using dry-run fixtures and provider-mocked responses.

## Sources

- TikTok Direct Post video API: `https://developers.tiktok.com/doc/content-posting-api-reference-direct-post`
- TikTok Upload video API: `https://developers.tiktok.com/doc/content-posting-api-reference-upload-video`
- TikTok Photo post API: `https://developers.tiktok.com/doc/content-posting-api-reference-photo-post/`
- TikTok Get Post Status API: `https://developers.tiktok.com/doc/content-posting-api-reference-get-video-status`

## Current recommendation

Post manually for a 4-week experiment first. Use CLI dry-runs to shape captions/metadata. Add live publishing only if TikTok shows real signal.
