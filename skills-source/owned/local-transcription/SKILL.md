---
name: local-transcription
description: Transcribe local files or media URLs through the WIN cloud transcription job path, returning transcript text and cached artifact URLs. Use when the user asks Codex to transcribe audio/video, diarize a meeting, produce transcript text, inspect transcription jobs, or run readiness checks. The legacy machine-local Superwhisper CLI remains an explicit offline/debug fallback only.
---

# Local Transcription

## Overview

Use the skill-local client as the default interface for transcription. It sends both local files and remote URLs through the WIN job API so transcript state, cache, DB records, and object-storage artifacts stay consolidated.

The old `/Users/dobby/GitHub/local-transcription/bin/transcribe` Superwhisper path still exists, but treat it as an explicit offline/debug fallback. Do not use it for normal agent transcription work when the WIN API path is available.

## Workflow

1. Use the skill client:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  transcribe --file /path/to/audio-or-video.m4a
```

2. For remote media, pass a URL directly:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  transcribe --url https://example.com/audio-or-video.mp4
```

3. Prefer JSON output for agent workflows. It is the default stdout contract and includes `schema_version`, `command`, `status`, `data`, `error`, and `meta`.

4. On success, use `data.transcript` as the transcript text. Use `data.artifacts.transcript_url`, `data.artifacts.words_url`, and `data.artifacts.sentences_url` when downstream work needs the cached bucket artifacts.

5. Use `--plain` only when the user wants quick readable transcript text or a shell pipeline:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  transcribe --file /path/to/audio.wav --plain
```

6. Diarization is enabled by default because the current preferred provider is WIN `local_transcription`, which routes to the Mac-hosted ElevenLabs Scribe path. Use `--no-diarize` only when the caller explicitly wants no speaker separation:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  transcribe --file /path/to/meeting.wav --no-diarize
```

7. Use `--no-wait` when the caller only wants the submitted job id:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  transcribe --url https://example.com/audio.mp3 --no-wait
```

8. Inspect an existing job:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py \
  status --job-id TRANSCRIPTION_ARTIFACTS_abc123 --wait
```

## Readiness

Run `doctor` when local helper readiness is uncertain:

```bash
/Users/dobby/.agents/skills-source/owned/local-transcription/scripts/local_transcription.py doctor
```

If readiness fails, report the structured error and hint. Do not print or request token values.

## Rules

- Treat the skill-local client as the public agent interface.
- For local files, let the client upload to R2 `cache/`, then call WIN `/media/transcribe/artifacts`.
- For URLs, pass the URL to WIN directly. Do not call local audio extraction from the skill.
- Do not call Superwhisper, ElevenLabs, or the Mac service directly for normal agent transcription.
- Keep `/Users/dobby/GitHub/local-transcription/bin/transcribe` and `bin/superwhisper` for offline/debug fallback or explicit provider-level checks only.
- Keep secrets file-based. Do not pass secret values through flags, ordinary environment variables, chat, or logs.
- Keep stdout reserved for the final transcript contract. Progress and diagnostics belong on stderr.
- Use `--progress off` when command chatter would interfere with surrounding automation.
- Use the skill contract reference when the command shape is unclear: `references/cloud-client-contract.md`.

## Output Handling

After running JSON mode, parse stdout before summarizing. On success, use `data.transcript` as the transcript text and inspect `data.artifacts` for cached result URLs. On failure, preserve `error.code`, `error.message`, and `error.hint` in the user-facing summary.

## Fallback

Only use the local provider CLI when the user explicitly asks for offline/local Superwhisper behavior or when WIN/cloud/R2 is unavailable and an offline fallback is acceptable:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe --audio /path/to/audio.wav --diarize
```
