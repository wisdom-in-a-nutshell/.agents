# Agent-First CLI Contract

Use this contract when the primary caller is an AI agent.
Humans are supported as a secondary interaction mode.

## Interface Modes

- `--json`: machine-readable output mode.
- `--human`: human-readable output mode.
- `--plain`: stable plain-text mode for shell tooling.

Behavior defaults:

- If `stdout` is not a TTY, default to machine-readable output.
- If `stdout` is a TTY, default to concise human output.
- Explicit flags always override defaults.

## Machine Output Shape

Return one JSON object per command execution.

Required top-level fields:

- `schema_version`: output contract version (example: `"1.0"`).
- `command`: canonical command/subcommand path.
- `status`: `"ok"` or `"error"`.
- `data`: payload object for successful execution.
- `error`: object or `null`.
- `meta`: object with execution metadata.

`meta` should include:

- `request_id`: stable execution id.
- `duration_ms`: command duration.
- `timestamp_utc`: ISO-8601 UTC timestamp.

## Error Contract

On failure:

- Set `status` to `"error"`.
- Set non-zero exit code.
- Populate `error` with:
  - `code`: stable machine code (example: `"E_TIMEOUT"`).
  - `message`: concise human-readable summary.
  - `retryable`: boolean.
  - `hint`: actionable next step.

Avoid stack traces in default output.
Expose debug detail only with explicit debug flags.

## Exit Code Model

Use stable and documented exit codes.

Minimum mapping:

- `0`: success.
- `1`: generic failure.
- `2`: invalid usage or validation error.
- `3`: authentication/authorization failure.
- `4`: network or dependency unavailable.
- `5`: timeout or interruption.

## Agent Safety Rules

- Never require prompts for normal operation.
- Honor `--no-input` and fail fast when required inputs are missing.
- Make state-changing operations explicit; support dry-run when risk is non-trivial.
- Keep operations idempotent or resumable where feasible.
- Add configurable timeouts for remote calls.

## Determinism Rules

- Keep field names stable across versions.
- Prefer additive schema changes.
- Return consistently shaped objects for the same command class.
- Avoid embedding volatile text in machine fields.
- Put human narrative in `message` or human mode output, not in structured keys.

## Security Rules

- Do not accept secrets via command flags.
- Do not accept secrets via environment variables.
- Accept secrets via files, stdin, or secret managers.
- Do not emit secrets in success, error, or debug output.
