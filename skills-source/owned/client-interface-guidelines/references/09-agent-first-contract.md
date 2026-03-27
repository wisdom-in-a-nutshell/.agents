# Agent-First CLI Contract

Use this contract when the primary caller is an AI agent.
Operator inspection is supported as a secondary debugging and status path.

## Interface Modes

- `--json`: machine-readable output mode.
- `--plain`: stable plain-text mode for shell tooling or quick inspection.

Behavior defaults:

- Default to machine-readable output.
- Do not let TTY detection change the semantic shape of the main result.
- Explicit flags may request a secondary inspection view, but the primary contract remains JSON.

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
- Put operator guidance in `error.hint`, dedicated inspection commands, or explicit debug output, not in structured keys that should remain stable.

## Inspection Rules

- Prefer dedicated inspection commands such as `status`, `get`, `list`, `inspect`, and `validate`.
- Use `--plain` only as an operator convenience when JSON is too heavy for quick shell inspection.
- Do not invent a large parallel “human mode” surface unless the tool is genuinely used interactively by humans as a primary workflow.

## Anti-Patterns

- TTY-sensitive changes to output structure.
- Mixing structured results and free-form prose on stdout.
- Pretty tables or decorative formatting as the default result surface.
- Progress chatter on stdout.
- Commands that require prompts during normal operation.

## Security Rules

- Do not accept secrets via command flags.
- Do not accept secrets via environment variables.
- Accept secrets via files, stdin, or secret managers.
- Do not emit secrets in success, error, or debug output.
