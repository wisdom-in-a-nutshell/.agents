---
name: client-interface-guidelines
description: "Design or review command-line client interfaces using a sectioned best-practice standard for help/docs, flags/args, stdout/stderr, output formats, error UX, interactivity, robustness, configuration/environment, secrets handling, naming, distribution, and analytics. Use when creating new CLI/client tools or improving existing ones."
---

# Client Interface Guidelines

## Overview

Apply this skill as the default quality gate for any CLI/client tool.
The goal is consistent, human-friendly interfaces that remain script-safe.

## Workflow

1. Read `references/00-how-to-use-this-skill.md`.
2. Start with `references/08-quick-review-checklist.md`.
3. Load only relevant reference sections (`01` to `07`).
4. Produce one of these outputs:
   - Design contract for a new CLI.
   - Gap report for an existing CLI.
5. End with pass/fail checklist status.

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

## Non-Negotiables

- Exit code `0` on success; non-zero on failure.
- `-h` and `--help` must work.
- Primary output to `stdout`; diagnostics/errors to `stderr`.
- Support non-interactive operation; honor `--no-input`.
- Do not accept secrets via flags or environment variables.
- Keep human output improvable; provide stable machine-readable modes.
