# YouTube Posting

Use this when Adi wants to upload a video to YouTube from local agent tooling.

The skill-owned interface is `scripts/youtube/cli.py`. The actual YouTube upload engine lives in `modal_functions` as `upload_youtube_video`; the skill stays a thin, stable, agent-facing client.

## Why Modal-backed

YouTube uploads are the channel where the hard part is the upload transport: resumable chunks, long runtime, timeout-aware HTTP, retry-on-stall, thumbnail/playlist post-processing, and YouTube description sanitization. Do not duplicate that locally unless Modal becomes a real bottleneck.

Current split:

- `social-media-publishing/scripts/youtube/cli.py`: JSON contract, validation, local-file staging, route reporting.
- `modal_functions/src/functions/integrations/youtube/upload`: YouTube Data API upload execution.
- `win`: product/client episode publishing workflows. Do not import WIN from this skill.

## Status

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py status
```

`status` checks local config paths and whether the current Python can import the Modal SDK. If the default Python cannot import Modal, upload commands re-run themselves with `/Users/dobby/GitHub/modal_functions/venv/bin/python` when available.

## Upload from a public direct video URL

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py upload-video \
  --video-url https://example.com/video.mp4 \
  --title "Video title" \
  --description-file /abs/path/description.md \
  --privacy unlisted \
  --credentials-id ADITHYAN \
  --dry-run
```

Remove `--dry-run` to publish for real.

## Upload from a local video file

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/youtube/cli.py --progress plain upload-video \
  --video /abs/path/video.mp4 \
  --title "Video title" \
  --description-file /abs/path/description.md \
  --privacy private \
  --credentials-id ADITHYAN
```

For local files, the CLI stages the video into the shared Modal `cache` volume and calls the Modal uploader with `video_volume_path`. This avoids temporary public URLs and avoids copying YouTube upload internals into the skill.

Optional thumbnail:

```bash
  --thumbnail /abs/path/thumb.jpg
```

or, for a public thumbnail:

```bash
  --thumbnail-url https://example.com/thumb.jpg
```

## Config

Optional non-secret config file:

`~/.secrets/youtube/env`

Supported keys:

```bash
YOUTUBE_DEFAULT_CREDENTIALS_ID=ADITHYAN
SOCIAL_YOUTUBE_MODAL_PYTHON=/Users/dobby/GitHub/modal_functions/venv/bin/python
SOCIAL_YOUTUBE_MODAL_APP=aip-processor
SOCIAL_YOUTUBE_MODAL_FUNCTION=upload_youtube_video
SOCIAL_YOUTUBE_MODAL_VOLUME=cache
```

Do not store OAuth secrets here. YouTube secrets remain in Modal secret `youtube-oauth`, sourced from the existing Modal/Key Vault flow.

## Output contract

Default output is one JSON object:

- `schema_version`
- `command`
- `status`
- `data`
- `error`
- `meta`

For upload commands, `data` includes:

- `requested_route`
- `selected_route`
- `routes`
- `artifact`
- `staging`
- `result`
- `next_action`

Progress goes to stderr only. Final JSON goes to stdout only.

## Safety defaults

- Default privacy is `private`.
- `--dry-run` validates and reports the selected route without publishing.
- Local staged files are removed from the Modal volume after successful upload unless `--keep-staged` is passed.
- On timeout/retry-exhausted errors, check YouTube Studio for a possible partial/private duplicate before retrying.
