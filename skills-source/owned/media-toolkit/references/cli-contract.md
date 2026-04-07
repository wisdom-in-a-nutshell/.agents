# Media Toolkit Contract

## Purpose

`media_toolkit.py` is the machine-primary toolkit for the canonical media job endpoints.

Use it when an agent needs one command surface for:
- local file upload
- media URL submission
- image and video segmentation
- job polling
- job status inspection
- JSON result-file writing for later agent steps

## Commands

- `upload`
  - Backend: shared local `~/GitHub/scripts/bin/upload-media` wrapper
  - Inputs: `--file`
  - Optional file output: `--output`
- `transcribe`
  - Endpoint: `POST /media/transcribe`
  - Inputs: exactly one of `--file` or `--url`
  - Optional file output: `--output`
- `segment image`
  - Endpoint: `POST /media/segment/image`
  - Inputs: exactly one of `--file` or `--url`
  - Optional file output: `--output`
- `segment video`
  - Endpoint: `POST /media/segment/video`
  - Inputs: exactly one of `--file` or `--url`
  - Optional file output: `--output`
- `transform`
  - Endpoint: `POST /media/transform`
  - Inputs: exactly one of `--file` or `--url`
  - Optional file output: `--output`
- `matte`
  - Endpoint: `POST /media/matte`
  - Inputs: exactly one of `--file` or `--url`
  - Optional file output: `--output`
- `status`
  - Endpoint: `GET /jobs/{job_id}`
  - Inputs: `--job-id`
  - Optional file output: `--output`

## Behavioral Rules

- JSON is the default output contract.
- `--plain` is only for quick operator inspection.
- Progress belongs on `stderr`, never on `stdout`.
- Long waits can be controlled with `--progress auto|off|plain|jsonl`.
- `upload` writes a local file through the shared local uploader and returns upload metadata including the public URL.
- Submit commands wait for terminal state by default.
- `--no-wait` returns the submitted `job_id` without polling.
- `status --wait` polls until the job reaches a terminal state.
- Local files are uploaded to R2 before submission and then passed to the API as `media_url`.
- `segment video` accepts optional SAM 3.1 initialization controls:
  - `--anchor-seconds`
  - `--anchor-frame-index`
  - `--window-start-seconds`
  - `--window-start-frame-index`
  - `--window-end-seconds`
  - `--window-end-frame-index`
  - `--propagation-direction`
  - `--max-frame-num-to-track`
- `--output` writes the final JSON envelope to disk for later steps.

## Output Contract

Each execution returns one JSON object on stdout:

- `schema_version`
- `command`
- `status`
- `data`
- `error`
- `meta`

Success:
- `status = "ok"`
- `data.upload` contains upload metadata for the `upload` command
- `data.job` contains submitted or fetched job information
- `data.input` contains input metadata for submit commands
- `data.result` contains the terminal job result when available
- `meta.output_path` is present when `--output` is used

Failure:
- `status = "error"`
- `error.code` is stable
- `error.message` is concise
- `error.retryable` indicates whether a retry is sensible
- `error.hint` gives the next useful action

## Progress Contract

- Progress is emitted to `stderr` only.
- `--progress off` disables progress output.
- `--progress plain` emits compact key-value progress lines.
- `--progress jsonl` emits one JSON progress object per line.
- `--progress auto` currently behaves like compact plain progress for waiting commands.
- Progress is additive inspection output and does not change the final `stdout` result envelope.

## Stable Exit Codes

- `0`: success
- `1`: job or generic failure
- `2`: validation or invalid usage
- `3`: authentication or authorization failure
- `4`: network, upload, or API dependency failure
- `5`: timeout or interruption
