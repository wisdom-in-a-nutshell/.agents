# Delivery Route Selection

Use this reference when a CLI needs to choose how to deliver, install, deploy, publish, or smoke-test an artifact across multiple possible routes.

Examples:

- direct local device install
- remote device install through a trusted host
- internal beta distribution such as TestFlight
- cloud build or hosted simulator/device run
- server deploy plus smoke test
- dry-run validation only

## Principle

The CLI may choose the best route automatically, but the choice must be explicit in the machine contract.

Agents need to know:

- which routes were considered
- why a route was selected
- why other routes were skipped
- whether the result is installed, uploaded, queued, processing, available, or blocked
- what the next reliable action is

Do not hide route selection behind prose logs or TTY-only prompts.

## Required Interface

For delivery commands, prefer this shape:

```json
{
  "schema_version": "1.0",
  "command": "tool deliver",
  "status": "ok",
  "data": {
    "selected_route": "direct_device",
    "requested_route": "auto",
    "artifact": {
      "kind": "ios_app",
      "version": "1.0",
      "build": "8"
    },
    "routes": [
      {
        "route": "direct_device",
        "status": "available",
        "decision": "selected",
        "reason_code": "DEVICE_REACHABLE"
      },
      {
        "route": "internal_beta",
        "status": "available",
        "decision": "not_selected",
        "reason_code": "LOWER_PRIORITY"
      }
    ],
    "result": {
      "state": "installed_launched",
      "url": null,
      "install_target": "Adithyan's iPhone"
    },
    "next_action": null
  },
  "error": null,
  "meta": {
    "request_id": "req_...",
    "duration_ms": 1234,
    "timestamp_utc": "2026-05-05T00:00:00Z"
  }
}
```

## Route Names

Use stable route identifiers.
Prefer generic names in reusable tooling and map provider-specific details in route metadata.

Suggested route identifiers:

- `direct_device`: local physical device or trusted remote host with a connected device.
- `simulator`: local simulator.
- `internal_beta`: internal beta distribution such as TestFlight internal testing.
- `external_beta`: externally reviewed beta distribution.
- `cloud_build`: remote build artifact creation.
- `cloud_device`: hosted physical device or simulator session.
- `server_smoke`: deploy or validate against a live server endpoint.
- `dry_run`: validation without state-changing delivery.

Avoid provider names such as `testflight` as the top-level route when the concept is broader.
Include provider-specific values in fields such as `provider`, `app_id`, `group_id`, `build_id`, or `dashboard_url`.

## Route Selection Flags

Support explicit route selection and a deterministic auto mode:

- `--route auto|direct-device|simulator|internal-beta|external-beta|cloud-build|cloud-device|server-smoke|dry-run`
- Optional convenience aliases such as `--direct-only` or `--testflight-only` are acceptable for human use, but the durable machine contract should normalize them into `requested_route`.
- `--dry-run` must validate route availability and report the route that would be used.
- `--no-input` must fail with a structured error if the selected route requires missing credentials, agreements, device trust, or interactive setup.

Auto mode should be stable and documented.
For mobile app delivery, a conservative default is:

1. `direct_device` when a target physical device is reachable.
2. `internal_beta` when direct install is unavailable and credentials are valid.
3. `simulator` only when the task is explicitly simulator-safe or physical install is not required.
4. fail with an actionable structured error when no route is available.

## Error Codes

Use route-specific stable error codes.

Suggested codes:

- `E_NO_DELIVERY_ROUTE`: no acceptable route is available.
- `E_DEVICE_UNAVAILABLE`: direct device route was requested but no eligible device was reachable.
- `E_REMOTE_HOST_UNAVAILABLE`: a required trusted host could not be reached.
- `E_BETA_AUTH`: beta provider credentials are missing or invalid.
- `E_BETA_AGREEMENT_REQUIRED`: provider account agreements block API or upload access.
- `E_BETA_PROCESSING_TIMEOUT`: upload succeeded but provider processing did not finish before timeout.
- `E_BUILD_EXPORT_FAILED`: artifact build or export failed.
- `E_ROUTE_UNSUPPORTED`: requested route is unknown or unsupported for this artifact.

Set `retryable` based on the actual condition.
For example, a transient network failure is retryable; a missing provider agreement is not retryable until the operator accepts it.

## Long-Running Delivery

Remote builds, uploads, and provider processing can take minutes.

Delivery CLIs should:

- print progress to `stderr` only
- keep final JSON on `stdout`
- support `--wait` and `--no-wait` when provider processing can continue asynchronously
- include provider build ids, dashboard urls, and polling hints in `data.result`
- emit sparse progress heartbeats or JSONL progress events for waits over roughly `60s`
- return a resumable `operation_id` or provider id when possible

Do not block forever waiting for beta processing.
Use a documented timeout and return `E_BETA_PROCESSING_TIMEOUT` with `retryable=true` plus a `status` command hint.

## Inspection Commands

Delivery tools should expose inspection separately from delivery:

- `routes` or `doctor`: reports route availability without building or uploading.
- `status`: reports provider/build/install status for a known operation or latest artifact.
- `logs`: fetches relevant local, remote host, or provider logs when available.
- `open`: opens the provider dashboard or install URL for an operator, if human inspection is needed.

These commands must still honor the same JSON contract.

## Provider-Specific Notes

For Apple/TestFlight-style routes:

- Treat internal beta delivery as a remote fallback, not a replacement for physical-device validation when the phone is reachable.
- Check App Store Connect API access before building when possible.
- Detect and classify missing agreements separately from authentication failures.
- Report app id, bundle id, build number, upload id/build id, processing state, internal group selection, and dashboard/install URL when available.
- Keep API keys in secret files or a secret manager; do not accept private key material in flags or ordinary environment variables.

For Expo/React-Native-style routes:

- Only recommend fast update routes when the app architecture actually supports over-the-air JavaScript updates.
- Do not present cloud build or OTA update as equivalent to native code delivery for Swift/Kotlin/native modules.
- Report whether a change requires a native rebuild or can be delivered as an update.
