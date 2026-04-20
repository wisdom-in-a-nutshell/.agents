---
name: dobby
description: Canonical contract for operating a Dobby workspace — a personal-agent repo where memory, direction, per-area canon, journal, tasks, and calendar are held as the user's externalized mind. Use whenever the user wants to store, read, update, or route personal memory; check or update task state; reflect or journal; inspect, search, or add calendar events; answer "where does this go"; or run any operation that touches `memory/`, `dobby/`, `journal/`, Things 3, or calendar. Triggers include "remember this", "store this", "add to memory", "save for later", "I want to become...", "what's on today", "what's overdue", "what's in my inbox", "what's on my calendar/week", "add this to calendar", "schedule this", "search my calendar", "what do you know about that area", "where does this go", "add a task", "mark done", "I need to...", and any routing decision about new information surfaced in conversation. This skill holds the write-decision tree, file contracts, command recipes, and hygiene rules so operating the workspace is deterministic across agents.
---

# Dobby

## Overview

Dobby is a companion that lives in a git repo. The workspace itself is Dobby — `memory/`, `journal/`, `dobby/`, plus a task surface (Things 3). This skill is the operator's manual: what to read, where to write, how to keep the workspace coherent across agents.

Soul lives in `/soul.md` (Dobby's character). Operations live here.

## Boot

On any fresh session:

1. `soul.md` is loaded automatically by the harness.
2. Load memory context via this skill’s `scripts/dobby-memory boot` (returns `profile.md` + `now.md` + `becoming.md` + lazy area manifest with mtimes).
3. Check task state via `scripts/dobby-tasks snapshot` from this skill (one call returns today, overdue, and inbox).
4. Surface overdue count, today count, and inbox count naturally in the first response.
5. Read deeper files only when the task actually needs them. Areas under `memory/areas/` load on demand.

## Prefer the CLI

The skill-bundled Dobby scripts are the preferred path for reads, appends, tasks, and calendar operations. They live beside this file under `scripts/`: `dobby-memory`, `dobby-tasks`, and `dobby-calendar`. They are deterministic, timestamped, tested, and agent-first: JSON envelopes by default, `--plain` only for operator inspection. Run them from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

**Reach for the CLI first.** Fall through to the `Edit`/`Write` tools only when the CLI cannot do what's needed — surgical mid-file section rewrites, or creating a new file. Both are legitimate; the CLI is simply the default.

Examples:
- Boot: `scripts/dobby-memory boot` (JSON default; add `--plain` for markdown)
- Read a file: `scripts/dobby-memory read --section profile` / `--section area.<name>.<file>`
- Append to a log: `echo "- date — event" | scripts/dobby-memory write --section area.<name>.log --message "label"`
- Mid-file section edit in `profile.md`: use `Edit` tool (CLI can't replace sections)
- New journal file: use `Write` tool (CLI `write` appends, doesn't create)

See `references/commands.md` for full recipes.

## Testing

Use the skill test runner for script changes. It is cheap/non-mutating by default; live suites that may create temporary Things 3 tasks or Calendar events are opt-in.

- Normal check: `bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh`
- Live smoke: `RUN_LIVE=1 bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh`
- Specific live smoke: `bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh tasks live`

Do not add real external writes to non-live tests. Put write-path coverage in `*/live.sh`.

## Write-decision tree

When new information surfaces, route it to exactly one canonical home. Never duplicate; point instead.

| Signal | Home | Operation |
|---|---|---|
| Actionable item (to do, follow up, remind me) | **Things 3** | `scripts/dobby-tasks add "..." --when ... --area <Area>` |
| Durable truth about the user (identity, pattern, preference) | `memory/profile.md` | Edit in place (section) |
| Direction / future-self / commitment to self | `memory/becoming.md` | Edit in place, or append commitments |
| This week's active context / session handoff | `memory/now.md` | Rewrite the relevant section, keep ≤60 lines |
| Per-area durable canon | `memory/areas/<area>/<area>.md` | Edit in place |
| Per-area event or task completion | `memory/areas/<area>/log.md` | Append (dated one-liner), via CLI |
| Dated reflection, check-in, or noticing | `journal/daily/YYYY-MM-DD/` | New file in today's folder |
| Monthly pattern recognition | `journal/monthly/YYYY/MM.md` | Edit during monthly review |
| Dobby's own voice sharpening / blindspot named | `dobby/growth.md` | Append (dated entry) |
| Raw capture with no clear home yet | `journal/daily/YYYY-MM-DD/notes-<slug>.md` | New file — journal is the default holding ground; there is no separate `capture/` folder |

**Areas mirror the user's Things 3 Areas exactly.** A task tagged `Builder` and `memory/areas/builder/` are the same domain. Area names are discoverable via `ls memory/areas/`. Every workspace instance has its own set (identity-shaped, typically 3–5).

For the full file-by-file contract, see `references/files.md`.
For user-intent-to-action mappings, see `references/scenarios.md`.

## Tasks (Things 3)

Tasks always go through the CLI. There is no file-based alternative.

- Add: `scripts/dobby-tasks add "..." --when today|tomorrow|"next monday" --area <Area> --checklist "a,b,c"`
- Boot snapshot: `scripts/dobby-tasks snapshot`
- List: `scripts/dobby-tasks today | inbox | overdue`
- Search: `scripts/dobby-tasks search "..."` (fast summary by default; add `--verbose` only when full fields are needed)
- Complete: `scripts/dobby-tasks done <id-prefix>`
- Doctor: `scripts/dobby-tasks doctor` (5-point health check)

Habits are not Things 3 tasks. Structured check-ins are handled by a journaling skill if one is installed; recurring physical habits (running, etc.) are Things 3 recurring tasks set once in the UI; behavioral nudges happen inside conversation.

Default for ambiguous new tasks: drop into Things 3 Inbox. The user sorts during morning review.

## Journal

Dobby owns routing to `journal/`; the dedicated `journal-checkin` skill owns structured check-ins and guided reflections. For raw dated capture, create a file under `journal/daily/YYYY-MM-DD/` after reading enough context to avoid duplication. Do not turn journal entries into Things tasks unless there is an explicit action.

## Calendar

Calendar operations go through the skill-bundled EventKit wrapper: `scripts/dobby-calendar`. It uses `ical` as the backend and defaults to `adithyan@wisdominanutshell.academy`. Use it for date-bounded reads and safe writes. Do not use AppleScript for broad calendar search/audits.

- List calendars: `scripts/dobby-calendar calendars`
- Week view: `scripts/dobby-calendar week`
- Date-bounded search: `scripts/dobby-calendar search "Neha" --from 2026-01-01 --to 2026-12-31 --all-calendars`
- Safe write: `scripts/dobby-calendar upsert-event --title "Trip" --start 2026-04-30 --end 2026-05-06 --all-day --match-from 2026-04-01 --match-to 2026-05-31`
- Doctor: `scripts/dobby-calendar doctor`

## Hygiene

- **One canonical home.** Never write the same fact to two places. Use pointers when cross-reference is needed.
- **Read before you write.** Don't duplicate content that already exists.
- **Respect the clocks.** `profile.md` is slow (monthly–yearly). `becoming.md` is quarterly. `now.md` is weekly. Area canon shifts as needed. Don't churn slow files with fast content.
- **No `current.md` files.** Per-area active state lives as a "Current state" section at the top of the area's main file, or in `now.md` if it's cross-cutting this week.
- **Actionable ≠ memory.** If it's a to-do, it goes to Things 3, full stop.
- **Preserve continuity on rewrites.** When slimming or consolidating, don't lose content silently — fold into another file, or append to `journal/daily/YYYY-MM-DD/` before removing.
- **Standing permission for memory writes.** The user has granted direct write-back permission — don't ask before updating memory when something durable surfaces. Note the write inline so they see what happened.

## Delegation

Check for and delegate to other installed skills when the user's intent matches one of theirs more precisely — especially for structured reflections/check-ins, memory consolidation passes, or domain-specific work (health data, CV, voice writing). Do not reinvent workflows a specialized skill already owns.

## Reference files (load on demand)

- `references/files.md` — file-by-file contract: purpose, edit frequency, append-vs-edit-vs-rewrite.
- `references/commands.md` — CLI recipes and direct-ops fallbacks.
- `references/scenarios.md` — user intent → exact action mappings.
