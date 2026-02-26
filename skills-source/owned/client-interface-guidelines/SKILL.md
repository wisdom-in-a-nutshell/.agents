---
name: client-interface-guidelines
description: "Design, implement, or review command-line/client-tool interfaces using the CLIG best-practice standard from clig.dev and cli-guidelines/cli-guidelines. Use when creating a new CLI/client tool or improving an existing one: command structure, help text, flags/args, stdout/stderr behavior, machine-readable output (`--json`/`--plain`), error UX, interactivity (`--no-input`), configuration/environment precedence, secrets handling, signals, robustness, and deprecation strategy."
---

# Client Interface Guidelines

## Overview

Use this skill as the default quality bar for CLI and client-facing terminal tools.
Prioritize human-first UX while preserving composability and stable script automation.

## Workflow

1. Choose mode:
   - Design mode: define the command contract before implementation.
   - Review mode: audit an existing CLI and report concrete gaps.
2. Load references:
   - Fast scan: `references/rule-index.md`
   - Full source of truth: `references/command-line-interface-guidelines.md`
   - Provenance/license: `references/source-snapshot.md`, `references/upstream-license-cc-by-sa-4.0.md`
3. Produce or audit a CLI contract that covers:
   - Command/subcommand naming and consistency
   - Arguments and flags (long + short forms, defaults, discoverability)
   - Help/docs behavior (`-h`, `--help`, examples, support link)
   - Output streams (`stdout` for primary/machine output, `stderr` for messages/errors)
   - Machine-readable output (`--json`, and `--plain` when rich output breaks parsing)
   - Error messages with clear recovery guidance
   - Interactivity rules (TTY-only prompts, `--no-input`, explicit confirms for dangerous actions)
   - Configuration and environment variable precedence
   - Security/privacy rules (no secrets in flags/env, explicit analytics consent)
   - Robustness and future-proofing (timeouts, Ctrl-C behavior, additive changes, deprecations)
4. Finish with a compliance checklist:
   - Confirm which rules are met.
   - List missing rules with exact implementation changes.

## Non-Negotiable Defaults

- Return exit code `0` on success and non-zero on failure.
- Support `-h` and `--help`; show concise help when required args are missing.
- Send primary output to `stdout`; send diagnostics/errors to `stderr`.
- Do not prompt in non-interactive mode; honor `--no-input`.
- Do not read secrets from command flags or environment variables.
- Provide stable machine-readable output for scripts.
- Keep interface changes additive when possible; otherwise provide deprecation warnings.

## References

- `references/command-line-interface-guidelines.md`: full upstream CLIG content.
- `references/rule-index.md`: extracted section/rule index for quick auditing.
- `references/defuddle-validation.md`: extraction coverage notes.
- `references/upstream-readme.md`: upstream repository context.
- `references/upstream-license-cc-by-sa-4.0.md`: CC BY-SA 4.0 text.
- `references/source-snapshot.md`: pinned upstream commit + refresh notes.

## Refresh Upstream Sources

Run:

```bash
bash scripts/sync_upstream.sh
```

This refreshes the guide markdown, README, license, rule index, and source snapshot from GitHub.
