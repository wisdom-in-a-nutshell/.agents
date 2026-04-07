---
name: media-toolkit
description: Use when an agent needs media processing from a local file or URL. This skill provides one machine-primary client that prepares the input, runs the requested media operation, and returns structured results.
---

# Media Toolkit

## Overview

Use this skill when the goal is to run media processing from either a local file or a remote media URL. The toolkit handles the required input preparation internally, including local-file upload when needed, and returns stable structured results by default while optionally writing the same JSON result envelope to disk for later steps.

## When To Use

- The user wants a transcript, segmentation result, foreground matte, or transformed video from a local file or URL.
- The user needs an uploaded media URL from a local file.
- Another skill or repo-local workflow needs a machine-primary media client instead of direct Python imports.
- You need the final job result, not manual queue or worker inspection.
- You need to inspect an existing media job with its `job_id`.

## Workflow

1. Use the client script:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh ...
```

2. Prefer the canonical subcommands:
- `transcribe`
- `segment`
- `transform`
- `matte`
- `upload`
- `status`

`upload` is a first-class subcommand. It uses the shared local `upload-media` tool underneath and returns structured upload metadata, including the uploaded URL.

3. Prefer one input locator:
- `--file $HOME/media/video.mp4`
- `--url https://...`

4. Default to JSON output. Use `--plain` only for quick shell inspection.

5. Let the toolkit wait unless the caller specifically wants async handling:
- default: wait for terminal job state and return final result
- `--no-wait`: return the submitted `job_id`
- `status --job-id ... [--wait]`: inspect or poll an existing job
- `--output /path/result.json`: write the final JSON envelope to a file

## Common Commands

Upload a local file and return the uploaded media URL:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  upload --file $HOME/media/video.mp4 \
  --output /tmp/upload.json
```

Transcribe a local file:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  transcribe --file $HOME/media/audio.mp3 \
  --output /tmp/transcribe.json
```

Segment an image:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  segment image --file $HOME/media/image.png \
  --prompt "black ball" \
  --output /tmp/segment-image.json
```

Segment a video:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  segment video --file $HOME/media/video.mp4 \
  --prompt "black ball" \
  --init-timestamp-seconds 14 \
  --output /tmp/segment-video.json
```

Transform a remote video:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  transform --url https://example.com/video.mp4 \
  --scale-width 1280 \
  --scale-height 720
```

Create a foreground matte and dump the manifest:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  matte --file $HOME/media/video.mp4 \
  --output /tmp/matte-result.json
```

Inspect a job:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  status --job-id VIDEO_TRANSFORM_123 --wait
```

## Rules

- Keep this skill thin. The toolkit script is the deterministic source of behavior.
- Do not call the media-processing Python internals directly when the job API is the appropriate contract.
- Use JSON output as the default contract.
- Keep file output simple: `--output` writes the same JSON envelope returned on stdout.
- Keep secrets out of flags and stdout. API base URL configuration is allowed; credentials must stay in repo/runtime config.
- Read [references/cli-contract.md](references/cli-contract.md) when you need the command map or output contract details.
