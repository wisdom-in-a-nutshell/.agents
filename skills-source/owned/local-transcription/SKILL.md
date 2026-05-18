---
name: local-transcription
description: Transcribe, diarize, inspect, or validate local audio files through the machine-local Superwhisper transcription repo. Use when the user asks Codex to transcribe local audio, produce transcript text, add speaker labels, diarize a meeting, run readiness checks, return JSON transcription output, or save transcript files from local audio such as .wav, .m4a, .mp3, or .aac using /Users/dobby/GitHub/local-transcription/bin/transcribe.
---

# Local Transcription

## Overview

Use the local transcription repo as the stable interface for local audio transcription. Keep Superwhisper as the provider boundary: fast transcription uses Superwhisper Cloud, and diarization uses Superwhisper's brokered ElevenLabs Scribe V2 route.

## Workflow

1. Use the stable command:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe --audio /path/to/audio.wav
```

2. Prefer JSON output for agent workflows. It is the default stdout contract and includes `schema_version`, `command`, `status`, `data`, `error`, and `meta`.

3. Use `--plain` only when the user wants quick readable transcript text or a shell pipeline:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe --audio /path/to/audio.wav --plain
```

4. Use `--diarize` when the user asks for speakers, speaker labels, meeting separation, or "who said what":

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe --audio /path/to/meeting.wav --diarize
```

5. Use `--diarize --no-words` for long audio when the caller only needs transcript text plus speaker segments:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe --audio /path/to/meeting.wav --diarize --no-words
```

6. Write durable outputs only when useful for downstream work:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe \
  --audio /path/to/audio.wav \
  --out /path/to/transcript.txt \
  --json-out /path/to/provider-response.json
```

## Readiness

Run `doctor` when auth, cache state, or provider readiness is uncertain:

```bash
/Users/dobby/GitHub/local-transcription/bin/transcribe doctor
/Users/dobby/GitHub/local-transcription/bin/transcribe doctor --require fast
/Users/dobby/GitHub/local-transcription/bin/transcribe doctor --require diarize
/Users/dobby/GitHub/local-transcription/bin/transcribe doctor --require all
```

If readiness fails, report the structured error and hint. Do not print or request token values.

## Rules

- Treat `/Users/dobby/GitHub/local-transcription/bin/transcribe` as the public interface.
- Do not call Superwhisper or ElevenLabs APIs directly for this workflow.
- Do not add a direct ElevenLabs route unless the user explicitly changes the provider strategy.
- Keep `bin/superwhisper` for debugging or explicit provider-level checks only.
- Keep secrets file-based. Do not pass secret values through flags, ordinary environment variables, chat, or logs.
- Keep stdout reserved for the final transcript contract. Progress and diagnostics belong on stderr.
- Use `--progress off` when command chatter would interfere with surrounding automation.
- Use repo-local docs only when the command contract is unclear: `/Users/dobby/GitHub/local-transcription/docs/references/cli-contract.md`.

## Output Handling

After running JSON mode, parse stdout before summarizing. On success, use `data.transcript` as the transcript text and inspect `data.diarization` for speaker segments. On failure, preserve `error.code`, `error.message`, and `error.hint` in the user-facing summary.
