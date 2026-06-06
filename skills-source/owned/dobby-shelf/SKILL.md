---
name: dobby-shelf
description: "Operate Dobby Shelf, the repo-local personal open-loop surface in `state/shelf.json`. Use for tasks, purchases, habits, follow-ups, deferrals, \"what's on my shelf/today/later\", \"add a task\", \"mark done\", \"drop this\", and any personal actionable item assigned to the user. Do not use for agent work queues; use Symphony for work assigned to agents."
---

# Dobby Shelf

Shelf is Dobby's personal open-loop surface: small actions, purchases, and recurring habits assigned to the user.

Canonical state lives in the active Dobby workspace:

```text
state/shelf.json
```

## Core rule

Actionable personal open loops go to Shelf, not memory or journal. Work assigned
to an agent goes to Symphony, not Shelf.

## v2 contract

The file shape is:

```json
{
  "schemaVersion": 2,
  "revision": 0,
  "timezone": "Europe/Berlin",
  "updatedAt": "1970-01-01T00:00:00.000Z",
  "items": []
}
```

Item types are only `do`, `buy`, and `habit`.

- `do` / `buy` states: `active`, `completed`, `dropped`.
- `habit` states: `active`, `paused`, `dropped`.
- One-off items use `showOn` and `dueOn` as date-only `YYYY-MM-DD` strings.
- Habits use `schedule` plus dated `completions`; completing a habit occurrence is not terminal.
- v2 has no `remember`, no `isNow`, and no Focus/Now bucket.

## Views

Views are derived by the Shelf core and exposed as cards:

- **Today** — active one-off items with `showOn <= localDate`, plus active habit occurrences for today.
- **Upcoming** — active one-off items with future `showOn`, plus the next future habit occurrence.
- **Later** — active one-off items with no `showOn`.

Default for ambiguous new Shelf items: add a plain `do` item with no `showOn` so it lands in Later. Use `showOn` for when it should surface and `dueOn` only for a real deadline.

## CLI first

Use the skill-bundled CLI for ordinary Shelf operations:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot --mode boot
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot --mode full
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf list --view active
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf add --title "Buy oats" --type buy --show-on 2026-06-10
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf habit add --title "Drink water" --cadence daily --start-on 2026-06-06
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf complete <id-or-card-id>
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf defer <id-or-prefix> --show-on 2026-06-12
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf update <id-or-prefix> --title "New title" --note "Replacement note"
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf note <id-or-prefix> --append "Additional note"
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf drop <id-or-prefix> --reason "no longer relevant"
```

The CLI emits JSON envelopes by default; use `--plain` only for operator inspection.

### Default agent picture

For default Dobby reasoning, day planning, boot context, and questions like
"what should I work on?", use:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot
```

`snapshot` is a read-only decision surface, not an archive view. It groups active
loops into `today`, `upcoming`, and `later`, returns compact cards, hides done/dropped
history, and includes signals such as overdue due dates and today overload.

Modes:

- `--mode boot` — minimal context for startup prompts.
- `--mode plan-day` — default surface for choosing what to do today.
- `--mode full` — all active cards grouped by decision view.

Use `list --view ...` when you need an exact view, archive inspection, or full item payloads. Do not read raw `state/shelf.json` for ordinary orientation unless debugging storage shape.

For workspace checks, use the skill-owned validator:

```bash
$HOME/GitHub/agents/skills-source/owned/dobby-shelf/scripts/validate --workspace-root /path/to/workspace state/shelf.json
```

## Operating rules

- Read through the CLI or backend adapter for normal operations.
- Preserve schema, `revision`, and timestamps.
- All writes go through the Shelf core's locked atomic write path.
- Prefer the mobile-gateway Shelf endpoints when operating through the app/client boundary. Inside the same workspace, use the CLI; direct JSON edits are only the fallback.
- Do not turn journal entries into Shelf items unless there is an explicit action.

## Testing

```bash
bash $HOME/GitHub/agents/skills-source/owned/dobby-shelf/tests/run.sh
```

For examples and edge cases, read `references/shelf.md`.
