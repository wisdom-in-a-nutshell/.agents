---
name: dobby-shelf
description: "Operate Dobby Shelf, the repo-local personal open-loop surface in `state/shelf.json`. Use for tasks, reminders, purchases, follow-ups, deferrals, \"what's on my shelf/today/later/now\", \"add a task\", \"mark done\", \"drop this\", and any personal actionable item assigned to the user. Do not use for agent work queues; use Symphony for work assigned to agents."
---

# Dobby Shelf

Shelf is Dobby's personal open-loop surface: small tasks, follow-ups, reminders,
purchases, and concrete one-off actions assigned to the user.

Canonical state lives in the active Dobby workspace:

```text
state/shelf.json
```

## Core rule

Actionable personal open loops go to Shelf, not memory or journal. Work assigned
to an agent goes to Symphony, not Shelf.

## Item contract

The file shape is:

```json
{
  "schemaVersion": 1,
  "revision": 0,
  "updatedAt": "1970-01-01T00:00:00.000Z",
  "items": []
}
```

Item statuses are only `open`, `done`, or `dropped`. There is no `snoozed`;
deferring keeps the item open, updates `showAt`, increments `deferCount`, and
sets `lastDeferredAt`.

`isNow` is an uncapped soft focus signal. If many open items are marked Now,
surface the overload and help the user choose; do not reject or auto-bump items.

## Views

- **Now** — open items with `isNow: true`.
- **Today** — open items surfaced today or earlier.
- **Upcoming** — open items with future `showAt`.
- **Later** — open items with no `showAt`.

Default for ambiguous new Shelf items: add a plain `open` item with no `showAt`
so it lands in Later. Use `showAt` for when it should surface and `dueAt` only
for a real deadline.

## CLI first

Use the skill-bundled CLI for ordinary Shelf operations:

```bash
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot --mode boot
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot --mode full
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf list --view open
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf add --title "Buy oats" --kind buy --show-at 2026-05-10
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf done <id-or-prefix>
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf defer <id-or-prefix> --show-at 2026-05-12
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf note <id-or-prefix> --set "Replacement note"
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf note <id-or-prefix> --append "Additional note"
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf note <id-or-prefix> --clear
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf drop <id-or-prefix> --reason "no longer relevant"
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf focus <id-or-prefix> --on
```

The CLI emits JSON envelopes by default; use `--plain` only for operator inspection.

### Default agent picture

For default Dobby reasoning, day planning, boot context, and questions like
"what should I work on?", use:

```bash
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf snapshot
```

`snapshot` is a read-only decision surface, not an archive view. It groups open
loops into `now`, `today`, `upcoming`, and `later`, returns compact item
projections, hides long notes and done/dropped history, and includes signals
such as overdue due dates, focus overload, and today overload.

Modes:

- `--mode boot` — minimal context for startup prompts.
- `--mode plan-day` — default surface for choosing what to do today.
- `--mode full` — all open items grouped by decision view.

Use `list --view ...` when you need an exact view, `done`/`dropped` archive
inspection, or full item payloads. Do not read raw `state/shelf.json` for
ordinary orientation unless debugging storage shape.

For workspace checks, use the skill-owned validator:

```bash
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/validate --workspace-root /path/to/workspace state/shelf.json
```

## Operating rules

- Read `state/shelf.json` before writing.
- Preserve schema, `revision`, and timestamps.
- Increment `revision` on every write and set `updatedAt` to current UTC ISO.
- Prefer the mobile-gateway Shelf endpoints when operating through the app/client
  boundary. Inside the same workspace, use the CLI; direct JSON edits are only the fallback.
- Do not turn journal entries into Shelf items unless there is an explicit action.

## Testing

```bash
bash $HOME/.agents/skills-source/owned/dobby-shelf/tests/run.sh
```

For examples and edge cases, read `references/shelf.md`.
