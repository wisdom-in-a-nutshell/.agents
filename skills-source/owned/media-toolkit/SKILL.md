---
name: media-toolkit
description: Use when an agent needs a generic media toolkit backed by WIN media processing. This owned skill provides one command surface for transcription, video transform, foreground matting, result-file writing, submission, polling, and job status inspection from a local file, media URL, or job_id across linked repos.
---

# Media Toolkit

## Overview

Use this skill when the goal is to run WIN media processing without knowing backend internals. The toolkit uploads local files when needed, submits the canonical media job endpoints, waits for completion by default, and returns stable JSON to stdout while optionally writing the same JSON result envelope to disk for later steps.

## When To Use

- The user wants a transcript, foreground matte, or transformed video from a local file or URL.
- Another skill or repo-local workflow needs a machine-primary media client instead of direct Python imports.
- You need the final job result, not manual queue or worker inspection.
- You need to inspect an existing media job with its `job_id`.

## Workflow

1. Use the shell entrypoint:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh ...
```

2. Prefer the canonical subcommands:
- `transcribe`
- `transform`
- `matte`
- `status`

3. Prefer one input locator:
- `--file /abs/path/video.mp4`
- `--url https://...`

4. Default to JSON output. Use `--plain` only for quick shell inspection.

5. Let the toolkit wait unless the caller specifically wants async handling:
- default: wait for terminal job state and return final result
- `--no-wait`: return the submitted `job_id`
- `status --job-id ... [--wait]`: inspect or poll an existing job
- `--output /path/result.json`: write the final JSON envelope to a file

## Common Commands

Transcribe a local file:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  transcribe --file /absolute/path/audio.mp3 \
  --output /tmp/transcribe.json
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
  matte --file /absolute/path/video.mp4 \
  --output /tmp/matte-result.json
```

Inspect a job:

```bash
.agents/skills/media-toolkit/scripts/media_toolkit.sh \
  status --job-id VIDEO_TRANSFORM_123 --wait
```

## Rules

- Keep this skill thin. The toolkit script is the deterministic source of behavior.
- The shell wrapper is the portable entrypoint across linked repos.
- Do not call the media-processing Python internals directly when the job API is the appropriate contract.
- Use JSON output as the default contract.
- Keep file output simple: `--output` writes the same JSON envelope returned on stdout.
- Keep secrets out of flags and stdout. API base URL configuration is allowed; credentials must stay in repo/runtime config.
- Read [references/cli-contract.md](references/cli-contract.md) when you need the command map or output contract details.
