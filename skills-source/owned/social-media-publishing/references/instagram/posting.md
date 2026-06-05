# Instagram Posting

Initial integration status: scaffolded CLI with machine-readable status and dry-run request validation. Live publishing is intentionally disabled until account/API setup is complete and a provider route is tested safely.

Verified against provider docs on 2026-05-23. The official Meta documentation URL is `https://developers.facebook.com/docs/instagram-platform/content-publishing/`; if the Meta docs site blocks automated fetches, use the linked Meta/Postman collection as a practical mirror for request shape.

## Channel stance for Adi

Instagram is a soft personal bridge, not the core builder network.

Use it for:
- behind-the-scenes builder updates
- short demos and Reels
- Mac mini / local setup visuals
- honest founder/building notes

Avoid turning Adi's personal/friend graph into generic AI-marketing spam. If posting to his existing personal Instagram, keep it human and occasional. If we want higher-volume builder distribution, create a separate public builder account.

## Provider reality

Instagram publishing is a two-step container flow:

1. Create a media container on `/{ig_user_id}/media` using a public media URL.
2. Publish that container through `/{ig_user_id}/media_publish` using the returned container id.

Relevant provider constraints:

- Instagram professional account required: Business or Creator.
- Meta developer app required.
- Permissions are currently in the Instagram Platform / Business Login family, commonly including `instagram_business_basic` and `instagram_business_content_publish`.
- Media must be reachable by Meta from a public HTTPS URL at publish time.
- Carousels are a parent container over child containers; API carousels are limited by provider rules.
- Video/Reel containers may need status polling before publish.

## Requirements

Credential/config file convention:

```bash
~/.secrets/instagram/env
```

Supported keys:

```bash
INSTAGRAM_IG_USER_ID=...
INSTAGRAM_ACCESS_TOKEN=...
META_GRAPH_VERSION=v23.0
```

`IG_USER_ID` and `META_ACCESS_TOKEN` are accepted aliases.

## CLI

```bash
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py status
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-image --text-file /abs/path/caption.txt --image-url https://example.com/image.jpg --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-video --text-file /abs/path/caption.txt --video-url https://example.com/video.mp4 --reel --share-to-feed --dry-run
python3 ~/GitHub/agents/skills-source/owned/social-media-publishing/scripts/instagram/cli.py post-carousel --text-file /abs/path/caption.txt --media-url https://example.com/1.jpg --media-url https://example.com/2.jpg --dry-run
```

The CLI defaults to JSON and follows the agent-first contract:

- stable output envelope
- dry-run first
- no prompts
- no secrets in flags or stdout
- errors with stable codes
- stdout reserved for the final machine result

## Implementation route still needed

Before live publishing:

1. Decide account strategy: Adi personal account vs separate builder account.
2. Set up Meta developer app and Instagram publishing permissions.
3. Store token/account id in `~/.secrets/instagram/env`.
4. Implement direct API route:
   - create media container
   - poll video/Reel container status where needed
   - publish media container
   - return post id/permalink when available
5. Add tests using dry-run fixtures and provider-mocked responses.

## Sources

- Meta official docs: `https://developers.facebook.com/docs/instagram-platform/content-publishing/`
- Meta/Postman Instagram API collection: `https://www.postman.com/meta/instagram/`
- Meta/Postman create media container request: `https://www.postman.com/meta/instagram/request/1u52b9b/create-an-image-container`
- Meta/Postman publish container request: `https://www.postman.com/meta/instagram/request/yi6ro4h/publish-the-container`

## Current recommendation

Start with manual posts or CLI dry-runs. Automate live posting only after we decide whether this is Adi's personal account or a separate builder account.
