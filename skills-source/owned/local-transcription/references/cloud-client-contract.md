# Local Transcription Cloud Client Contract

## Purpose

`scripts/local_transcription.py` is the machine-primary client for transcription through WIN's cloud job path.

Use it when an agent needs:

- transcript text from a local file
- transcript text from a media URL
- diarized transcript output by default
- cached transcript artifacts in R2
- job polling or inspection

## Commands

- `transcribe`
  - Inputs: exactly one of `--file` or `--url`
  - Local files are uploaded to R2 `cache/` through `upload-media`
  - Endpoint: `POST /media/transcribe/artifacts`
  - WIN returns a compact artifact manifest; the client fetches `transcript_url`
    when it needs to emit transcript text
  - Default provider: `local_transcription`
  - Default diarization: enabled
- `status`
  - Input: `--job-id`
  - Endpoint: `GET /jobs/{job_id}`
  - Optional `--wait`
- `doctor`
  - Checks local client and `upload-media` readiness

## Output Contract

Default stdout is one JSON object:

```json
{
  "schema_version": "1.0",
  "command": "local-transcription transcribe",
  "status": "ok",
  "data": {
    "transcript": "...",
    "artifacts": {
      "transcript_url": "https://...",
      "words_url": "https://...",
      "sentences_url": "https://..."
    },
    "source_id": "...",
    "provider": "local_transcription",
    "job": {
      "job_id": "TRANSCRIPTION_ARTIFACTS_...",
      "cached": false,
      "status": "completed",
      "endpoint": "/media/transcribe/artifacts"
    },
    "input": {
      "used_upload": true
    },
    "result": {
      "source_id": "...",
      "provider": "local_transcription",
      "word_count": 123,
      "sentence_count": 45,
      "transcript_url": "https://...",
      "words_url": "https://...",
      "sentences_url": "https://..."
    }
  },
  "error": null,
  "meta": {
    "request_id": "...",
    "duration_ms": 123,
    "timestamp_utc": "2026-05-25T00:00:00+00:00"
  }
}
```

## Rules

- JSON is the default contract.
- `--plain` is only for transcript-text inspection after a completed transcribe wait.
- Progress goes to `stderr` only.
- Final machine result goes to `stdout` only.
- No prompts; `--no-input` is supported and non-interactive.
- Do not pass secrets through flags or environment variables.
- Local upload storage prefix is always `cache`.
- The local Superwhisper CLI is fallback/debug only, not the default agent path.

## Exit Codes

- `0`: success
- `1`: job or generic failure
- `2`: validation or usage error
- `3`: authentication or authorization failure
- `4`: network, upload, or dependency failure
- `5`: timeout or interruption
