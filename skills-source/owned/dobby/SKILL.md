---
name: dobby
description: Canonical contract for operating a Dobby workspace — a personal-agent repo where memory, direction, per-area canon, journal, Shelf open loops, and calendar are held as the user's externalized mind. Use whenever the user wants to store, read, update, or route personal memory; check or update Shelf state; reflect or journal; inspect, search, or add calendar events; answer "where does this go"; or run any operation that touches `memory/`, `dobby/`, `journal/`, `state/shelf.json`, or calendar. Triggers include "remember this", "store this", "add to memory", "what's on today", "what's on my shelf", "what's later", "what's on my calendar/week", "add this to calendar", "schedule this", "add a task", "mark done", and routing decisions about new information surfaced in conversation.
---

# Dobby

## Overview

Dobby is a companion that lives in a git repo. The workspace itself is Dobby: `memory/`, `journal/`, `dobby/`, and the Shelf open-loop file. This skill is the operator's manual: what to read, where to write, and how to keep the workspace coherent across agents.

Soul lives in `/soul.md` (Dobby's character and durable user context). Operational rules live here.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`), not by this skill. That repo hook is a
thin delegate to the skill-bundled hook, which reads `now.md`, `state/shelf.json`,
walks `memory/areas/`, and calls the skill-bundled `dobby-calendar upcoming` in
parallel. The workspace user's
durable identity is part of `soul.md` under that workspace's `## About <User>`
section and arrives via the wrapper-composed system prompt.

What you can rely on being in context at session start:

1. `soul.md` (identity, values, voice, `## About <User>`) — from the system prompt.
2. `now.md` — full contents.
3. Recent session notes — last 3 plus notes from the last 7 days, capped at 10.
4. Shelf snapshot (Now / Today / Upcoming / Later counts + top items).
5. Calendar (next 2 days).
6. Area manifest (area names + file lists, content on demand).

Surface Shelf counts naturally in the first response.
Read deeper files only when the task actually needs them. Areas under
`memory/areas/` load on demand.

## Session notes

Session continuity lives in `memory/sessions/YYYY/MM/DD-HHMMSS.md`, not in
`memory/now.md`. Repo-local `scripts/hooks/session_end.py` wrappers delegate to
the skill-bundled `scripts/hooks/session-end`, which keeps the hook fast by
writing a handoff record under `tmp/hooks/session-end/`, launching
`scripts/hooks/write-session-note` in the background, and exiting `0`.

The worker renders the transcript when the runtime provides `transcript_path`,
passes it to a note-generation placeholder, and writes one new note using the
session start timestamp in Berlin local time when a generator returns text. It
never blocks session shutdown. If transcript access or note generation fails,
the worker logs to stderr/`tmp/hooks/session-memory/worker.log` and exits `0`.

Operational limits:
- filename format: `memory/sessions/YYYY/MM/DD-HHMMSS.md` with numeric suffixes
  on collision
- boot context: last 3 notes plus notes from the last 7 days, capped at 10
- per-note boot cap: 2500 chars
- total recent-session boot block cap: 12000 chars

Stored notes stay plain prose. Do not add templates/frontmatter. Durable
decisions still get promoted to `now.md`, area canon, or `soul.md` as
appropriate.

No provider-specific SDK is wired yet. `scripts/hooks/write-session-note`
contains the placeholder where a future model client should be added after the
user chooses the API route. For smoke tests only, `DOBBY_SESSION_MEMORY_FAKE_NOTE`
or `--fake-note` can supply the note body.

## Prefer the CLI

The preferred command surfaces are deterministic, timestamped, tested, and agent-first: JSON envelopes by default, `--plain` only for operator inspection. Use `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory` for memory and `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar` for calendar. Shelf is `state/shelf.json`; the mobile gateway exposes it for phone/client access. **Do not first look for repo-local `scripts/dobby-*` wrappers.** Invoke the skill-bundled scripts directly, from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

**Reach for the CLI first.** Fall through to the `Edit`/`Write` tools only when the CLI cannot do what's needed — surgical mid-file section rewrites, or creating a new file. Both are legitimate; the CLI is simply the default.

Examples:
- Read a file: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now` / `--section area.<name>.<file>`
- Append to a log: `echo "- date — event" | $HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory write --section area.<name>.log --message "label"`
- Mid-file section edit in `now.md` or an area file: use `Edit` tool (CLI can't replace sections)
- Edit durable identity (`## About <User>` in `soul.md`): use `Edit` tool directly on `soul.md`
- New journal file: use `Write` tool (CLI `write` appends, doesn't create)

See `references/commands.md` for full recipes.

## Testing

Use the skill test runner for Dobby memory/calendar script changes. It is cheap/non-mutating by default; live suites that may create temporary Calendar events are opt-in. Shelf backend tests live in `~/GitHub/codexclaw/services/mobile-gateway`.

- Normal check: `bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh`
- Live smoke: `RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh`
- Specific live smoke: `bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh calendar live`

Do not add real external writes to non-live tests. Put write-path coverage in `*/live.sh`.

## Write-decision tree

When new information surfaces, route it to exactly one canonical home. Never duplicate; point instead.

| Signal | Home | Operation |
|---|---|---|
| Personal actionable item / open loop assigned to the user | **Shelf** (`state/shelf.json`) | Add/update one Shelf item; use the mobile-gateway API when acting through the app boundary, otherwise edit the JSON carefully. |
| Durable truth about the user (identity, pattern, preference) | `soul.md` `## About <User>` | Edit in place (section) |
| This week's active context | `memory/now.md` | Rewrite the relevant section, keep ≤60 lines |
| Session continuity / what happened last time | `memory/sessions/YYYY/MM/DD-HHMMSS.md` | Auto-written by the SessionEnd hook; do not put session handoff prose in `now.md` |
| Per-area durable canon | `memory/areas/<area>/<area>.md` | Edit in place |
| Per-area event or task completion | `memory/areas/<area>/log.md` | Append (dated one-liner), via CLI |
| Dated reflection, check-in, or noticing | `journal/daily/YYYY-MM-DD/` | New file in today's folder |
| Monthly pattern recognition | `journal/monthly/YYYY/MM.md` | Edit during monthly review |
| Dobby's own voice sharpening / blindspot named | `dobby/growth.md` | Append (dated entry) |
| Raw capture with no clear home yet | `journal/daily/YYYY-MM-DD/notes-<slug>.md` | New file — journal is the default holding ground; there is no separate `capture/` folder |

Shelf does not use a project hierarchy. Area names for memory remain discoverable via `ls memory/areas/`. Every workspace instance has its own set (identity-shaped, typically 3–5).

For the full file-by-file contract, see `references/files.md`.
For user-intent-to-action mappings, see `references/scenarios.md`.

## Tasks (Shelf)

Shelf is Dobby's personal open-loop surface. It holds things assigned to the user:
tasks, follow-ups, reminders, small purchases, and concrete one-off actions.
It is not chat history, memory canon, an external task-app database, or the
Symphony agent-work queue.

Canonical state lives in the workspace:

```text
state/shelf.json
```

The core contract is:

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

`isNow` is an uncapped soft focus signal, not a hard constraint. If many open
items are marked Now, treat that as useful coaching context: surface the overload
plainly and help the user choose, but do not reject or auto-bump items.

Use the mobile-gateway Shelf endpoints when the running gateway is the right
boundary, especially for phone/client behavior. From inside the same workspace,
agents may read/write `state/shelf.json` directly, preserving schema, revision,
and timestamps.

Use Symphony instead of Shelf when the item is work assigned to Dobby as an
agent. Shelf is for the user's visible personal loops; Symphony is for local
agent work.

Default for ambiguous new tasks: add a plain `open` Shelf item with no `showAt`
so it lands in Later. Use `showAt` for when it should surface and `dueAt` only
for a real deadline.

## Journal

Dobby owns routing to `journal/`; the dedicated `journal-checkin` skill owns structured check-ins and guided reflections. For raw dated capture, create a file under `journal/daily/YYYY-MM-DD/` after reading enough context to avoid duplication. Do not turn journal entries into Shelf items unless there is an explicit action.

## Calendar

Calendar operations go through the skill-bundled EventKit wrapper: `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar`. It prefers the native Dobby Calendar Bridge helper (`~/Applications/Dobby Calendar Bridge.app` via its user-only LaunchAgent socket) and falls back to Homebrew `ical`. The bridge is the durable path for Dobby because macOS grants Calendar access to the bridge's stable bundle identity instead of whichever caller app spawned the command. The default calendar is required via the `DOBBY_CALENDAR_DEFAULT` env var (no hardcoded fallback) — set it per-workspace via `scripts/local/secrets/static_env_defaults.env` so it lands in `.env` on bootstrap. Commands that need a specific calendar fail fast with a clear message when unset. Use this CLI for date-bounded reads and safe writes; do not use AppleScript for broad calendar search/audits.

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
- **Actionable ≠ memory.** If it's a personal to-do or open loop, it goes to Shelf. If it is work assigned to an agent, route it to Symphony.
- **Preserve continuity on rewrites.** When slimming or consolidating, don't lose content silently — fold into another file, or append to `journal/daily/YYYY-MM-DD/` before removing.
- **Standing permission for memory writes.** The user has granted direct write-back permission — don't ask before updating memory when something durable surfaces. Note the write inline so they see what happened.
- **Keep repo docs thin.** Workspace repo docs may describe repo-specific facts
  such as area names, host topology, local secret mapping, and setup steps. Do
  not duplicate command recipes, CLI internals, backend behavior, or task/client
  policy there; keep those in this skill and point repo docs here.

## Delegation

Check for and delegate to other installed skills when the user's intent matches one of theirs more precisely — especially for structured reflections/check-ins, memory consolidation passes, or domain-specific work (health data, CV, voice writing). Do not reinvent workflows a specialized skill already owns.

## Reference files (load on demand)

- `references/files.md` — file-by-file contract: purpose, edit frequency, append-vs-edit-vs-rewrite.
- `references/commands.md` — CLI recipes and direct-ops fallbacks.
- `references/scenarios.md` — user intent → exact action mappings.
- `references/calendar.md` — calendar CLI, bridge ownership, runtime state, and setup.
