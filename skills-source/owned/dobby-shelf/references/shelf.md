# Dobby Shelf Reference

## Purpose

Shelf is for visible personal loops assigned to the user: one-off actions,
follow-ups, purchases, reminders, and small commitments.

Not Shelf:

- durable identity, values, preferences, or patterns → memory / `soul.md`
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
