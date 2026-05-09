---
name: dobby-calendar
description: "Operate Dobby calendar reads and writes through the skill-bundled EventKit calendar CLI. Use for \"what's on my calendar\", today/week/upcoming views, date-bounded calendar search, scheduling, adding or upserting events, checking calendars, and debugging the Dobby Calendar Bridge or `dobby-calendar` CLI."
---

# Dobby Calendar

Calendar operations go through the skill-bundled CLI:

```bash
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar
```

Use it from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.
The CLI emits deterministic JSON envelopes by default; use `--plain` only for
operator inspection.

## Common commands

```bash
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar doctor
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar calendars
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar today
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar week
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar upcoming --days 14
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar search "Neha" --from 2026-01-01 --to 2026-12-31 --all-calendars
$HOME/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar upsert-event --title "Trip" --start 2026-04-30 --end 2026-05-06 --all-day --match-from 2026-04-01 --match-to 2026-05-31
```

## Rules

- Calendar search/list operations must be date-bounded.
- Use `upsert-event` when an event may already exist; include a match range.
- The default calendar comes from `DOBBY_CALENDAR_DEFAULT`; commands that need a
  target calendar fail fast when it is unset. Override per call with `--calendar`.
- Do not use AppleScript for broad calendar searches or audits; it can hang on
  Google-backed calendars.
- Ask before externally visible or materially risky calendar writes when user
  intent is ambiguous. For clearly requested personal scheduling, proceed.

## Bridge

The CLI prefers the native Dobby Calendar Bridge helper and falls back to
Homebrew `ical`. For setup/debugging, read `references/bridge.md`.

## Testing

```bash
bash $HOME/.agents/skills-source/owned/dobby-calendar/tests/run.sh
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby-calendar/tests/run.sh
bash $HOME/.agents/skills-source/owned/dobby-calendar/tests/run.sh calendar live
```
