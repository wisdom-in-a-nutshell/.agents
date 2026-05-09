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
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf list --view open
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf add --title "Buy oats" --kind buy --show-at 2026-05-10
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf done <id-or-prefix>
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf defer <id-or-prefix> --show-at 2026-05-12
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf drop <id-or-prefix> --reason "no longer relevant"
$HOME/.agents/skills-source/owned/dobby-shelf/scripts/dobby-shelf focus <id-or-prefix> --on
```

The CLI emits JSON envelopes by default; use `--plain` only for operator inspection.

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
