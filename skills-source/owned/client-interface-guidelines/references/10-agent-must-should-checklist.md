# Agent MUST/SHOULD Checklist

Use this checklist for agent-native CLI quality gates.

## MUST

- [ ] Supports fully non-interactive execution.
- [ ] Supports `--json` with stable contract fields.
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

## SHOULD

- [ ] Provides `--human` mode for operator readability.
- [ ] Provides `--plain` mode for shell pipelines.
- [ ] Includes command suggestions on recoverable user errors.
- [ ] Includes dry-run for destructive or high-impact operations.
- [ ] Prints progress for operations that exceed short latency.
- [ ] Provides clear post-action state summary.
- [ ] Keeps help examples focused on common tasks first.
- [ ] Includes compact terminal docs plus richer web docs.
