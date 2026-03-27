---
name: client-interface-guidelines
description: "Design or review machine-primary command-line client interfaces for agent execution. Use when creating or improving CLI/client tools that require stable JSON contracts, deterministic outputs, structured errors, non-interactive operation, robust exit codes, secure secret handling, and operator inspection paths without turning the CLI into a human-first UI."
---

# Client Interface Guidelines

## Overview

Apply this skill as the default gate for agent-native CLI/client tools.

Optimize for machine reliability first.
Treat operator inspection as a secondary debugging and status layer, not as a co-equal interface mode.

## Workflow

1. Read `references/00-how-to-use-this-skill.md`.
2. Start with `references/09-agent-first-contract.md`.
3. Apply `references/10-agent-must-should-checklist.md`.
4. Validate using `references/11-agent-test-matrix-template.md`.
5. Use `references/02` to `07` for detailed guidance.
6. Optionally run `references/08-quick-review-checklist.md` for full coverage.

## Reference Files

- `references/00-how-to-use-this-skill.md`
- `references/01-philosophy.md`
- `references/02-basics-help-docs.md`
- `references/03-output-errors.md`
- `references/04-arguments-interactivity-subcommands.md`
- `references/05-robustness-future-signals.md`
- `references/06-configuration-environment.md`
- `references/07-naming-distribution-analytics.md`
- `references/08-quick-review-checklist.md`
- `references/09-agent-first-contract.md`
- `references/10-agent-must-should-checklist.md`
- `references/11-agent-test-matrix-template.md`

## Non-Negotiables

- Stable machine-readable contract and schema versioning.
- Non-interactive operation with `--no-input` support.
- Structured errors with stable codes and mapped exit codes.
- Strict stdout/stderr separation.
- Secure secret handling with no flag/env secret input.
- Additive interface evolution with explicit deprecation path.
- JSON is the default behavioral contract unless there is a strong reason otherwise.
