# Media Toolkit Contract

## Purpose

`media_toolkit.sh` is the portable entrypoint and `media_toolkit.py` is the machine-primary implementation for the canonical WIN media job endpoints.

Use it when an agent needs one command surface for:
- local file upload
- media URL submission
- job polling
- job status inspection
- JSON result-file writing for later agent steps

## Commands

- `transcribe`
  - Endpoint: `POST /media/transcribe`
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
- Submit commands wait for terminal state by default.
- `--no-wait` returns the submitted `job_id` without polling.
- `status --wait` polls until the job reaches a terminal state.
- Local files are uploaded to R2 before submission and then passed to the API as `media_url`.
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

## Stable Exit Codes

- `0`: success
- `1`: job or generic failure
- `2`: validation or invalid usage
- `3`: authentication or authorization failure
- `4`: network, upload, or API dependency failure
- `5`: timeout or interruption
