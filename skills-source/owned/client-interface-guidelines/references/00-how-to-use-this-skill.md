# How To Use This Skill

Use this skill whenever designing or reviewing a command-line client tool.

## Working Modes

### Mode A: Design a new CLI

1. Read `08-quick-review-checklist.md`.
2. Read the section files relevant to the command being designed.
3. Produce a CLI contract before coding:
   - command/subcommand map
   - flags/args map
   - help behavior
   - stdout/stderr contract
   - error contract
   - interactivity rules
   - config/env/secrets model

### Mode B: Review an existing CLI

1. Read `08-quick-review-checklist.md`.
2. Open only section files related to detected gaps.
3. Output a gap report:
   - violated guideline
   - concrete fix
   - severity (`high`, `medium`, `low`)

## Which Reference File To Load

- `01-philosophy.md`: design principles and tradeoff framing.
- `02-basics-help-docs.md`: parser, exit codes, help, and documentation.
- `03-output-errors.md`: output formats, stderr/stdout, and error UX.
- `04-arguments-interactivity-subcommands.md`: flags, prompts, and subcommand patterns.
- `05-robustness-future-signals.md`: responsiveness, recoverability, deprecation, Ctrl-C behavior.
- `06-configuration-environment.md`: precedence, XDG, environment variable practices, secrets.
- `07-naming-distribution-analytics.md`: naming, packaging, uninstall, analytics policy.

## Output Requirement

Always end with a compliance checklist: `pass` / `fail` per key guideline group.
