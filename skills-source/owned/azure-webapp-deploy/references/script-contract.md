# Script Contract

The scripts in this skill are agent-first helpers, not interactive operator UIs.

## Required Behavior

- Output one JSON object on stdout by default.
- Put diagnostics and progress on stderr.
- Support `--no-input`.
- Do not prompt.
- Do not accept secret values through flags or environment variables.
- Use stable exit codes:
  - `0`: success
  - `1`: operation or verification failure
  - `2`: invalid usage or validation failure
  - `3`: auth/authorization failure
  - `4`: dependency or network unavailable
  - `5`: timeout/interruption

## JSON Shape

```json
{
  "schema_version": "1.0",
  "command": "script-name",
  "status": "ok",
  "data": {},
  "error": null,
  "meta": {
    "request_id": "...",
    "timestamp_utc": "...",
    "duration_ms": 123
  }
}
```

Failures use:

```json
{
  "status": "error",
  "error": {
    "code": "E_STABLE_CODE",
    "message": "Concise summary.",
    "retryable": false,
    "hint": "Actionable next step."
  }
}
```

## Design Note

The skill conversation can be flexible and collaborative. The scripts should not
be. Agents ask the user for missing decisions, then invoke scripts with explicit
arguments.
