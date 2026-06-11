# Dobby Shelf Reference

## Purpose

Shelf is for visible personal loops assigned to the user: one-off actions,
purchases, and recurring habits.

Not Shelf:

- durable identity, values, preferences, or patterns → memory / `memory/profile.md` or `dobby/constitution.md`
- dated reflection or raw capture → journal
- calendar event with a start/end time → calendar
- work assigned to Dobby/agents → Symphony
- pure context with no action → memory/journal, not Shelf

## Storage contract

Canonical file:

```text
<workspace>/state/shelf.json
```

Top-level shape:

```ts
type ShelfState = {
  schemaVersion: 2
  revision: number
  timezone: string
  updatedAt: string
  items: ShelfItem[]
}
```

### One-off items

```ts
type SingleShelfItem = {
  id: string
  type: "do" | "buy"
  title: string
  state: "active" | "completed" | "dropped"
  showOn?: string // YYYY-MM-DD; surface date
  dueOn?: string  // YYYY-MM-DD; real deadline only
  note?: string
  source?: { type: "chat" | "ui" | "agent"; ref?: string }
  deferCount: number
  lastDeferredAt?: string
  completedAt?: string
  droppedAt?: string
  dropReason?: string
  createdAt: string
  updatedAt: string
  clientMutationId?: string
}
```

### Habit items

```ts
type HabitShelfItem = {
  id: string
  type: "habit"
  title: string
  state: "active" | "paused" | "dropped"
  schedule: {
    cadence: "daily" | "weekly"
    startOn: string
    endOn?: string
    daysOfWeek?: Array<"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun">
  }
  completions: Array<{ occurrenceKey: string; completedAt: string }>
  note?: string
  source?: { type: "chat" | "ui" | "agent"; ref?: string }
  createdAt: string
  updatedAt: string
  droppedAt?: string
  dropReason?: string
  clientMutationId?: string
}
```

Habits are not terminally completed. Completing a habit records the current occurrence in `completions`; the habit remains active and returns on the next scheduled occurrence.

## Derived views

The backend/CLI derives views and returns cards:

- `today` — one-off `showOn <= localDate` plus due habit occurrences for today.
- `upcoming` — future one-off `showOn` plus next future habit occurrence.
- `later` — active one-off items with no `showOn`.

There is no `now`, `focus`, `remember`, `kind`, `status`, `showAt`, `dueAt`, or `isNow` in v2.

## CLI

Preferred command surface:

```bash
dobby-shelf snapshot [--mode boot|plan-day|full]
dobby-shelf list --view today|upcoming|later|active|archive|completed|dropped|all
dobby-shelf add --title <title> [--type do|buy] [--show-on YYYY-MM-DD] [--due-on YYYY-MM-DD] [--note ...]
dobby-shelf habit add --title <title> --cadence daily --start-on YYYY-MM-DD [--end-on YYYY-MM-DD]
dobby-shelf habit add --title <title> --cadence weekly --start-on YYYY-MM-DD --days mon,thu
dobby-shelf complete <id-or-card-id>
dobby-shelf defer <id-or-prefix> --show-on YYYY-MM-DD
dobby-shelf update <id-or-prefix> [--title ...] [--type do|buy] [--show-on ...|--clear-show] [--due-on ...|--clear-due] [--note ...|--clear-note]
dobby-shelf note <id-or-prefix> --set|--append|--clear
dobby-shelf drop <id-or-prefix> [--reason ...]
```

Selectors resolve by exact id, unique id prefix, exact title, or visible card id where supported. Use full ids when ambiguous.

## Mutations

### Add one-off

Use `state: active`. If no date is implied, omit `showOn` so it lands in Later.

### Add habit

Use `type: habit`, `state: active`, a simple daily/weekly schedule, and an empty `completions` array.

### Complete

- `do`/`buy`: set `state: completed`, set `completedAt`, preserve archive item.
- `habit`: append `{ occurrenceKey, completedAt }` for the current visible occurrence; do not change the habit's state.

### Defer

Only for `do`/`buy`: keep `state: active`, set new `showOn`, increment `deferCount`, and set `lastDeferredAt`.

### Drop

Set `state: dropped`, update `updatedAt`, and include `dropReason` when useful.

## Coaching signals

Repeated deferrals, overdue due dates, a bloated Today list, and a large Later backlog are useful context. Name the pattern plainly and help the user choose; do not silently reshuffle the list.
