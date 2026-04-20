# CLI Interface Contract

Use this page when adding or changing command-line interfaces in this repo.

The repo has three CLI classes:

- Agent-facing clients: stable commands that agents may call directly as productized repo operations.
- Machine-facing orchestration scripts: deterministic bootstrap, sync, check, and reconcile helpers called by automation.
- Runtime helpers: narrow scripts for Ghostty, lifecycle hooks, shell startup, or machine-local setup.

Because agents are the primary operators of this repo, new top-level feature commands should default to the agent-facing client contract unless they are clearly internal renderers or runtime helpers.

## Agent-Facing Clients

Current agent-facing clients:

- `scripts/bootstrap-skill.sh`
- `scripts/bootstrap-plugin.sh`

Recommended promotion priority:

- New feature entrypoints that agents call directly should be born as agent-facing clients.
- Existing bootstrap/import commands should be promoted when agents need to inspect structured outcomes programmatically.
- Aggregate validation may stay plain-text while it is used as a pass/fail gate; add JSON only when another tool needs to consume detailed status.
- Low-level renderers and runtime helpers should stay simple unless their output becomes a machine data API.

These commands must follow the machine-primary contract:

- Default output is one JSON object on `stdout`.
- JSON includes `schema_version`, `command`, `status`, `data`, `error`, and `meta`.
- Errors use stable `error.code`, `error.message`, `error.retryable`, and `error.hint`.
- Exit codes use the shared model:
  - `0`: success
  - `1`: generic failure
  - `2`: invalid usage or validation failure
  - `3`: authentication or authorization failure
  - `4`: dependency unavailable or child command failure
  - `5`: timeout or interruption
- `--plain` is available for operator inspection.
- `--no-input` is accepted and normal operation never prompts.
- State-changing behavior is explicit through `--apply`; default mode is dry-run.
- Long child commands have configurable timeout behavior.
- Secrets must not be accepted through flags or environment variables, and outputs must not reveal secrets.

When adding a new agent-facing client, add contract tests for:

- JSON success shape.
- JSON validation error shape.
- Stable exit code for validation errors.
- `--plain` inspection output.
- `--no-input` non-interactive behavior.

## Machine-Facing Orchestration Scripts

Examples:

- `scripts/bootstrap-machine-agent-control-planes.sh`
- `scripts/auto-apply-agent-control-planes.sh`
- `scripts/check-agent-control-planes.sh`
- `scripts/sync-skills-registry.sh`
- `scripts/sync-plugins-registry.sh`
- `codex/scripts/bootstrap-machine-codex.sh`
- `claude/scripts/bootstrap-machine-claude.sh`

These scripts are automation surfaces, but they are not required to expose the full JSON contract unless they become productized agent-facing clients or another command needs to consume their detailed output.

They must still be agent-safe:

- Support fully non-interactive execution.
- Provide `-h` or `--help` when they accept options.
- Use stable non-zero exit codes through `set -euo pipefail` or explicit handling.
- Send errors to `stderr`.
- Keep state-changing actions behind `--apply`, unless the script is explicitly an auto-reconcile hook.
- Provide `--dry-run` where a state-changing operation can be inspected safely.
- Avoid prompt-required flows.
- Avoid secrets in flags and environment variables.

If automation needs to consume one of these scripts as a data API, promote that command to the agent-facing client contract instead of scraping prose output.

## Runtime Helpers

Runtime helpers can stay narrow and shell-native, but they should still be predictable:

- Keep behavior non-interactive unless the helper is explicitly UI-bound.
- Do not write disposable logs or backups into tracked source paths.
- Keep machine-local state under `~/.local/state/...`.
- Keep canonical source in this repo and render or link runtime copies through the documented sync scripts.

## Future Rule

When a new feature adds a CLI, decide its class before implementation. If agents will call it directly to make decisions, use the agent-facing JSON contract from the start. If the command only applies or validates control-plane state as part of a larger wrapper, keep it deterministic, non-interactive, and easy to test.
