# Agent Test Matrix Template

Use this matrix to validate the CLI contract before release.

## Contract Tests

| ID | Scenario | Command | Expected Exit | Assertions |
| --- | --- | --- | --- | --- |
| CT-01 | Success path | `tool op --json ...` | `0` | `status=ok`, valid `schema_version`, `data` present, `error=null` |
| CT-02 | Validation failure | `tool op --json` (missing required input) | `2` | `status=error`, `error.code` set, actionable `error.hint` |
| CT-03 | Dependency timeout | simulate dependency timeout | `5` | `retryable=true`, stable timeout code |
| CT-04 | Auth failure | invalid credentials | `3` | stable auth error code, no secret leakage |
| CT-05 | Interrupted run | send Ctrl-C during execution | `5` | immediate interruption handling, clean termination |

## Mode Tests

| ID | Scenario | Command | Expected |
| --- | --- | --- | --- |
| MT-01 | Non-TTY default | `tool op` with piped stdout | machine-readable output |
| MT-02 | Force JSON | `tool op --json` | machine-readable output |
| MT-03 | Force human | `tool op --human` | concise human output |
| MT-04 | No input mode | `tool op --no-input` | no prompts; fast failure if inputs missing |

## Stability Tests

| ID | Scenario | Command | Expected |
| --- | --- | --- | --- |
| ST-01 | Repeated identical run | same command twice | same shape and stable keys |
| ST-02 | Backward compatibility | older automation invocation | unchanged behavior or explicit deprecation warning |
| ST-03 | Error contract stability | trigger same failure twice | same `error.code` and exit code |

## Security Tests

| ID | Scenario | Command | Expected |
| --- | --- | --- | --- |
| SEC-01 | Secret via flag attempt | `tool login --password ...` | rejected with guidance |
| SEC-02 | Secret redaction | debug/logging path | no secret values in output |
| SEC-03 | Secret input path | file/stdin secret input | accepted securely |
