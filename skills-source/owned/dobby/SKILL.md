---
name: dobby
description: Canonical contract for operating a Dobby workspace — a personal-agent repo where memory, direction, per-area canon, journal, tasks, and calendar are held as the user's externalized mind. Use whenever the user wants to store, read, update, or route personal memory; check or update task state; reflect or journal; inspect, search, or add calendar events; answer "where does this go"; or run any operation that touches `memory/`, `dobby/`, `journal/`, Things 3, or calendar. Triggers include "remember this", "store this", "add to memory", "what's on today", "what's overdue", "what's in my inbox", "what's on my calendar/week", "add this to calendar", "schedule this", "add a task", "mark done", and routing decisions about new information surfaced in conversation.
---

# Dobby

## Overview

Dobby is a companion that lives in a git repo. The workspace itself is Dobby — `memory/`, `journal/`, `dobby/`, plus a task surface (Things 3). This skill is the operator's manual: what to read, where to write, how to keep the workspace coherent across agents.

Soul lives in `/soul.md` (Dobby's character). Operations live here.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`), not by this skill. That repo hook is a
thin delegate to the skill-bundled hook, which reads `now.md`, walks
`memory/areas/`, and calls the shared `things-client snapshot`
and skill-bundled `dobby-calendar upcoming` in parallel. The workspace user's
durable identity is part of `soul.md` under that workspace's `## About <User>`
section and arrives via the wrapper-composed system prompt.

What you can rely on being in context at session start:

1. `soul.md` (identity, values, voice, `## About <User>`) — from the system prompt.
2. `now.md` — full contents.
3. Task snapshot (overdue / today / inbox counts + top items).
4. Calendar (next 2 days).
5. Area manifest (area names + file lists, content on demand).

Surface overdue / today / inbox counts naturally in the first response.
Read deeper files only when the task actually needs them. Areas under
`memory/areas/` load on demand.

## Prefer the CLI

The preferred command surfaces are deterministic, timestamped, tested, and agent-first: JSON envelopes by default, `--plain` only for operator inspection. Use `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory` for memory, `$HOME/.agents/skills-source/owned/things-client/scripts/things-client` for Things 3 tasks, and `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar` for calendar. **Do not first look for repo-local `scripts/dobby-*` wrappers.** Invoke the skill-bundled scripts directly, from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

**Reach for the CLI first.** Fall through to the `Edit`/`Write` tools only when the CLI cannot do what's needed — surgical mid-file section rewrites, or creating a new file. Both are legitimate; the CLI is simply the default.

Examples:
- Read a file: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now` / `--section area.<name>.<file>`
- Append to a log: `echo "- date — event" | $HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory write --section area.<name>.log --message "label"`
- Mid-file section edit in `now.md` or an area file: use `Edit` tool (CLI can't replace sections)
- Edit durable identity (`## About <User>` in `soul.md`): use `Edit` tool directly on `soul.md`
- New journal file: use `Write` tool (CLI `write` appends, doesn't create)

See `references/commands.md` for full recipes.

## Testing

Use the skill test runner for Dobby memory/calendar script changes. It is cheap/non-mutating by default; live suites that may create temporary Calendar events are opt-in. Things 3 integration tests live with the shared `things-client` skill.

- Normal check: `bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh`
- Live smoke: `RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh`
- Specific live smoke: `bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh calendar live`

Do not add real external writes to non-live tests. Put write-path coverage in `*/live.sh`.

## Write-decision tree

When new information surfaces, route it to exactly one canonical home. Never duplicate; point instead.

| Signal | Home | Operation |
|---|---|---|
| Actionable item (to do, follow up, remind me) | **Things 3** | `$HOME/.agents/skills-source/owned/things-client/scripts/things-client add "..." --when ... --area <Area>` |
| Durable truth about the user (identity, pattern, preference) | `soul.md` `## About <User>` | Edit in place (section) |
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

- Add: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client add "..." --when today|tomorrow|"next monday" --area <Area> --checklist "a,b,c"`
- Boot snapshot: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client snapshot`
- List: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client today | inbox | overdue`
- Search: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client search "..."`
- Inspect a task/project: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client inspect "Personal AI / agent system"`
- Complete: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client done <id-prefix>`
- Doctor: `$HOME/.agents/skills-source/owned/things-client/scripts/things-client doctor` (health check)

Read commands default to an `auto` backend: fast read-only SQLite first, then
JXA fallback if the local database is unavailable. Agents should not choose a
backend in normal use. Use `--backend sqlite|jxa|auto` only for diagnostics.

Habits are not Things 3 tasks. Structured check-ins are handled by a journaling skill if one is installed; recurring physical habits (running, etc.) are Things 3 recurring tasks set once in the UI; behavioral nudges happen inside conversation.

Default for ambiguous new tasks: drop into Things 3 Inbox. The user sorts during morning review.

## Journal

Dobby owns routing to `journal/`; the dedicated `journal-checkin` skill owns structured check-ins and guided reflections. For raw dated capture, create a file under `journal/daily/YYYY-MM-DD/` after reading enough context to avoid duplication. Do not turn journal entries into Things tasks unless there is an explicit action.

## Calendar

Calendar operations go through the skill-bundled EventKit wrapper: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar`. It prefers the native Dobby Calendar Bridge helper (`~/Applications/Dobby Calendar Bridge.app` via its user-only LaunchAgent socket) and falls back to Homebrew `ical`. The bridge is the durable path for Codex.app/Claude/Terminal because macOS grants Calendar access to the bridge's stable bundle identity instead of whichever caller app spawned the command. The default calendar is required via the `DOBBY_CALENDAR_DEFAULT` env var (no hardcoded fallback) — set it per-workspace via `scripts/local/secrets/static_env_defaults.env` so it lands in `.env` on bootstrap. Commands that need a specific calendar fail fast with a clear message when unset. Use this CLI for date-bounded reads and safe writes; do not use AppleScript for broad calendar search/audits.

- List calendars: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar calendars`
- Week view: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar week`
- Date-bounded search: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "Neha" --from 2026-01-01 --to 2026-12-31 --all-calendars`
- Safe write: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar upsert-event --title "Trip" --start 2026-04-30 --end 2026-05-06 --all-day --match-from 2026-04-01 --match-to 2026-05-31`
- Doctor: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor`

## Hygiene

- **One canonical home.** Never write the same fact to two places. Use pointers when cross-reference is needed.
- **Read before you write.** Don't duplicate content that already exists.
- **Respect the clocks.** `soul.md` (including `## About <User>`) is slow (monthly–yearly). `now.md` is weekly. Area canon shifts as needed. Don't churn slow files with fast content.
- **No `current.md` files.** Per-area active state lives as a "Current state" section at the top of the area's main file, or in `now.md` if it's cross-cutting this week.
- **Actionable ≠ memory.** If it's a to-do, it goes to Things 3, full stop.
- **Preserve continuity on rewrites.** When slimming or consolidating, don't lose content silently — fold into another file, or append to `journal/daily/YYYY-MM-DD/` before removing.
- **Standing permission for memory writes.** The user has granted direct write-back permission — don't ask before updating memory when something durable surfaces. Note the write inline so they see what happened.
- **Keep repo docs thin.** Workspace repo docs may describe repo-specific facts
  such as area names, host topology, local secret mapping, and setup steps. Do
  not duplicate command recipes, CLI internals, backend behavior, or task/client
  policy there; keep those in this skill or the shared `things-client` skill and
  point repo docs here.

## Delegation

Check for and delegate to other installed skills when the user's intent matches one of theirs more precisely — especially for structured reflections/check-ins, memory consolidation passes, or domain-specific work (health data, CV, voice writing). Do not reinvent workflows a specialized skill already owns.

## Reference files (load on demand)

- `references/files.md` — file-by-file contract: purpose, edit frequency, append-vs-edit-vs-rewrite.
- `references/commands.md` — CLI recipes and direct-ops fallbacks.
- `references/scenarios.md` — user intent → exact action mappings.
- `references/calendar.md` — calendar CLI, bridge ownership, runtime state, and setup.
