# LinkedIn Community Management API

Use this when LinkedIn app/product access changes, when company pages are involved, or when normal LinkedIn publishing needs analytics/read-back beyond simple posting.

## What this access is for

LinkedIn Community Management is the vetted Marketing API product for managing brand/community presence. It is broader than the self-serve personal posting flow.

Useful capabilities, subject to app tier and OAuth scopes:
- Company/Page management: organization lookup, page/admin access checks, organization posts, comments, reactions, and moderation-style engagement.
- Page analytics: follower, page, share/post, social action, and video analytics.
- Member/profile publishing and analytics: post/comment/reaction management and post statistics for authorized members.
- Employee advocacy: organization social action notifications and people typeahead for mentions.

Official docs to check before implementation because versioning and permission names move:
- Overview: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview?view=li-lms-2026-06
- Migration / access tiers / permissions: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-api-migration-guide?view=li-lms-2026-06
- Product page: https://developer.linkedin.com/product-catalog/marketing/community-management-api

## Development tier reality

Development Tier is useful for proving the integration, not for a production tool.

Current documented constraints:
- 500 API calls per app per 24 hours.
- 100 API calls per app member per 24 hours.
- no `BATCH_GET` calls.
- Social Actions webhooks/push notifications disabled.
- Standard Tier requires a working implementation plus a short screencast demonstrating the approved use cases.

Do not build a heavy analytics crawler or multi-user product against Development Tier. Build the smallest proof path first.

## How this relates to the local LinkedIn CLI

The current `scripts/linkedin/cli.py` is Community Management-first for Adi's approved AI Podcasting app. It uses:
- generated machine-local app config from the `linkedin--...` Key Vault family
- local OAuth with Community Management scopes
- member author URN from OIDC `/userinfo` when available, falling back to `/v2/me` with `r_basicprofile`
- Posts/UGC/image/video endpoints for publishing as Adi
- Community Management comments, organization ACLs, and member analytics probes

The approved Community Management app can publish member posts and read member analytics, but it does **not** include restricted `r_member_social`. LinkedIn requires that restricted scope for listing member-authored posts through `posts?q=author`, so `community-status` reports `member_posts_read` as an expected skip unless that scope is separately granted.

Community Management access does not automatically make an old token more capable. After changing app credentials or scopes, move the old token aside and re-authorize with the approved app.

The CLI now exposes Community Management plumbing:

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize --scope-preset community
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py community-status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py list-comments --post-urn urn:li:ugcPost:...
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py organization-acls
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py member-post-analytics --post-urn urn:li:share:... --metric IMPRESSION
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py member-video-analytics --post-urn urn:li:ugcPost:... --metric VIDEO_PLAY
```

Bundled scope presets:
- `basic`: legacy self-serve personal posting scope. Use only if Adi explicitly restores that app path.
- `community-member`: `r_basicprofile`, personal posting/social-feed write, and member profile/post analytics scopes.
- `community-organization`: organization/page admin, social, follower, and organization social-feed scopes.
- `community`: the combined Community Management preset and the normal current setup.

Treat scope names as live-doc facts: check the current Microsoft Learn page before changing the CLI defaults.

## Best next increment for Adi's workflow

Do not jump straight to a full scheduler or agency tool.

Current useful path:
1. Re-authorize with `authorize --scope-preset community`.
2. Run `community-status` and inspect which probes pass or are expected skips.
3. Use `member-post-analytics` / `member-video-analytics` for measurable publishing.
4. Use `organization-acls` before any company-page workflow.
5. Only then consider company-page posting for AIP or any new company page.

Why this is useful:
- turns LinkedIn from fire-and-forget posting into measurable publishing;
- replaces brittle posting analytics/comment checks with explicit Community Management probes;
- enables company-page workflows if Adi later wants an AIP/new-company brand presence;
- provides evidence for a Standard Tier screencast if a real product use emerges.

## Guardrails

- Keep it explicit-user-action-first. Do not add auto-like/comment/follow automation or engagement spam.
- Store app credentials only through the normal secret lane described in `auth.md`.
- Keep user OAuth tokens machine-local/runtime-local; do not commit tokens.
- Keep app-specific facts such as app IDs and verified company pages out of this reusable skill unless they are needed for a local private reference.
- Standard Tier requires a demonstrated product use. If there is no near-term product, preserve the access and avoid overbuilding.
