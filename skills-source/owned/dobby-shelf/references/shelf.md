# Dobby Shelf Reference

## Purpose

Shelf is for visible personal loops assigned to the user: one-off actions,
follow-ups, purchases, reminders, and small commitments.

Not Shelf:

- durable identity, values, preferences, or patterns → memory / `memory/profile.json` or `dobby/constitution.json`
- dated reflection or raw capture → journal
- calendar event with a start/end time → calendar
- work assigned to Dobby/agents → Symphony

## Field conventions

Common item fields:

- `id` — stable unique id.
- `title` — short human title.
- `kind` — usually `do`, sometimes `buy` or `remember`.
- `status` — `open`, `done`, or `dropped`.
- `showAt` — when the item surfaces.
- `dueAt` — real deadline only.
- `isNow` — soft focus flag.
- `createdAt`, `updatedAt` — UTC timestamps.
- `deferCount`, `lastDeferredAt` — deferral history.
- `dropReason` — short explanation when dropped.

## CLI

Preferred command surface:

```bash
dobby-shelf list --view open|now|today|upcoming|later|done|dropped|all
dobby-shelf add --title <title> [--kind do|buy|remember] [--show-at YYYY-MM-DD] [--due-at ...] [--note ...] [--now]
dobby-shelf done <id-or-prefix>
dobby-shelf defer <id-or-prefix> --show-at YYYY-MM-DD
dobby-shelf drop <id-or-prefix> [--reason ...]
dobby-shelf focus <id-or-prefix> --on|--off
```

Selectors resolve by exact id, unique id prefix, or exact title. Use full ids when ambiguous.

## Mutations

### Add

Use `status: open`. If no date is implied, omit `showAt` so it lands in Later.

### Defer

Keep `status: open`, set new `showAt`, increment `deferCount`, and set
`lastDeferredAt`.

### Done

Set `status: done`, update `updatedAt`, and preserve the item.

### Drop

Set `status: dropped`, update `updatedAt`, and include `dropReason` when useful.

## Coaching signals

Repeated deferrals and overloaded Now lists are useful context. Name the pattern
plainly and help the user choose; do not silently reshuffle the list.
