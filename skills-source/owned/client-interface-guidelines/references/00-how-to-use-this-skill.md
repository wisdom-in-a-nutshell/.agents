# How To Use This Skill

Use this skill whenever designing or reviewing a command-line client tool that is primarily called by agents.

## Primary Workflow (Machine-Primary)

1. Read `09-agent-first-contract.md`.
2. Apply `10-agent-must-should-checklist.md`.
3. Validate with `11-agent-test-matrix-template.md`.
4. Use section files `02` to `07` for deeper design choices.
5. Use `08-quick-review-checklist.md` as extended coverage.

## Working Modes

### Mode A: Design a new CLI

1. Define the machine contract first (`09`).
2. Choose required MUST items (`10`).
3. Draft tests before implementation (`11`).
4. Add only the minimum operator inspection paths needed from `02` and `03`.

### Mode B: Review an existing CLI

1. Run MUST checklist (`10`).
2. Build a gap report with severity:
   - `high`: breaks agent automation or reliability.
   - `medium`: degrades operability, recoverability, or inspection.
   - `low`: polish/documentation gaps that do not change the machine contract.
3. Confirm with targeted tests (`11`).

## Which Reference File To Load

- `01-philosophy.md`: principles and tradeoff framing.
- `02-basics-help-docs.md`: parser, exit codes, help, docs.
- `03-output-errors.md`: output modes, stderr/stdout, error UX.
- `04-arguments-interactivity-subcommands.md`: flags, prompts, subcommands.
- `05-robustness-future-signals.md`: responsiveness, recovery, deprecation, Ctrl-C.
- `06-configuration-environment.md`: precedence, environment, secrets.
- `07-naming-distribution-analytics.md`: naming, packaging, analytics.
- `08-quick-review-checklist.md`: full CLIG-derived checklist.
- `09-agent-first-contract.md`: required agent contract.
- `10-agent-must-should-checklist.md`: agent-focused quality gate.
- `11-agent-test-matrix-template.md`: validation template.

## Output Requirement

Always end with:

- MUST checklist status.
- key SHOULD gaps.
- concrete next implementation steps.
- any interface behavior that still changes semantically based on TTY or human assumptions.
