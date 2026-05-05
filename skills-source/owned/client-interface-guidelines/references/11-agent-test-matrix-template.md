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

## Delivery Route Tests

| ID | Scenario | Command | Expected |
| --- | --- | --- | --- |
| DR-01 | Auto selects direct device | `tool deliver --route auto --json` with reachable device | `selected_route=direct_device`, other routes listed with reason codes |
| DR-02 | Auto falls back to internal beta | `tool deliver --route auto --json` with no device and valid beta credentials | `selected_route=internal_beta`, direct route marked unavailable |
| DR-03 | Explicit direct route unavailable | `tool deliver --route direct-device --json --no-input` with no device | non-zero exit, `error.code=E_DEVICE_UNAVAILABLE` |
| DR-04 | Beta agreement blocked | `tool deliver --route internal-beta --json --no-input` with provider agreement missing | non-zero exit, `error.code=E_BETA_AGREEMENT_REQUIRED`, actionable hint |
| DR-05 | Dry-run route plan | `tool deliver --route auto --dry-run --json` | no state-changing upload/install; reports route that would run |
| DR-06 | Async processing | `tool deliver --route internal-beta --no-wait --json` | returns provider ids/status URL and `result.state=uploaded_processing` |
