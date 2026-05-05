# Agent MUST/SHOULD Checklist

Use this checklist for agent-native CLI quality gates.

## MUST

- [ ] Supports fully non-interactive execution.
- [ ] Supports `--json` with stable contract fields, or defaults to an equivalent machine-readable contract.
- [ ] Uses stable non-zero exit codes for key failure classes.
- [ ] Emits primary machine output to `stdout` only.
- [ ] Emits diagnostics and logs to `stderr`.
- [ ] Provides deterministic machine output shape.
- [ ] Honors `--no-input`.
- [ ] Avoids prompt-required flows.
- [ ] Documents timeout behavior and supports configuration.
- [ ] Classifies errors with stable machine codes.
- [ ] Redacts secrets from all outputs.
- [ ] Avoids secrets in flags and environment variables.
- [ ] Supports retry-safe or resumable behavior for long operations.
- [ ] Keeps interface changes additive, or documents deprecation before breaking.
- [ ] Does not change the semantic shape of the primary result based on TTY detection.
- [ ] For multi-route delivery commands, reports requested route, selected route, considered routes, route reason codes, and final delivery state.

## SHOULD

- [ ] Provides `--plain` mode for shell pipelines or quick operator inspection.
- [ ] Provides dedicated inspection commands such as `status`, `get`, `list`, `inspect`, or `validate` when state visibility matters.
- [ ] Includes command suggestions on recoverable user errors.
- [ ] Includes dry-run for destructive or high-impact operations.
- [ ] Prints progress for operations that exceed short latency without corrupting stdout.
- [ ] Sends progress to `stderr` only and keeps the final machine result on `stdout`.
- [ ] Uses a stable progress control such as `--progress auto|off|plain|jsonl` when long waits are normal.
- [ ] Uses a sparse default heartbeat for long waits, around `60s` unless richer state-change events are available.
- [ ] Suppresses per-poll duplicate progress lines when the observable state has not changed, while still emitting sparse long-wait heartbeats.
- [ ] Provides clear post-action state summary.
- [ ] Provides route inspection or doctor commands when delivery depends on device, host, provider, or credential availability.
- [ ] Keeps help examples focused on common tasks first.
- [ ] Includes compact terminal docs plus richer web docs.
