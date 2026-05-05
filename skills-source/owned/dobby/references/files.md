# Dobby file contracts

What each file is for, how often it changes, and the write pattern (append / edit / rewrite).

## Constitution

### `soul.md`
- **Holds:** Dobby's operating constitution — identity, values, communication style, safety rules, write-back policy, instruction priority.
- **Clock:** yearly. Only changes when a pattern proves durable.
- **Write pattern:** curated edit in place. Never append raw logs. No operational specifics (paths, commands) — those belong in the `dobby` skill.

## Root memory

Durable truths about the user — identity, preferences, patterns, values,
structural/financial context, risk patterns, support patterns — live in
`soul.md` under the workspace's `## About <User>` section. Edit in place by
section. "Who the user is today" arrives at session start via the
wrapper-composed system prompt; it is not served by the memory CLI.

### `memory/now.md`
- **Holds:** this week's active context — week shape, strategic tracks, life timeline, watchouts.
- **Clock:** weekly rewrites; section updates as context shifts.
- **Write pattern:** rewrite sections in place. Hard cap: ≤60 lines. If a section outgrows its budget, promote stable content to `soul.md` `## About <User>` or area canon and prune.
- **Rule:** actionable items live in `state/shelf.json`, not here.

### `memory/sessions/YYYY/MM/DD-HHMMSS.md`
- **Holds:** one short free-form prose note for an ended agent session — what happened, what came up, what was decided, and what is worth remembering next time.
- **Clock:** automatic at session end when the runtime exposes enough transcript context.
- **Write pattern:** append-only tree, one new file per session. Do not hand-edit into a template; the stored note body stays plain prose.
- **Boot rule:** session start injects the last 3 notes plus notes from the last 7 days, capped at 10 total. Durable decisions still get promoted to `now.md`, area canon, or `soul.md` as appropriate.

## Areas

Each area has a folder under `memory/areas/`. The set of areas is workspace-instance-specific — discover via `ls memory/areas/`. Each area contains at minimum a main `.md` plus `log.md`.

### `memory/areas/<area>/<area>.md`
- **Holds:** durable canon for that area — identity, patterns, active "Current state" section, coaching notes.
- **Clock:** shifts as the area shifts. Faster than `soul.md` `## About <User>`, slower than `now.md`.
- **Write pattern:** edit in place, by section.

### `memory/areas/<area>/log.md`
- **Holds:** append-only events and task completions tied to this area.
- **Write pattern:** append only. One-line dated entries: `- YYYY-MM-DD — <event>`. Never rewrite historical entries.

### Sub-files inside an area
Additional files are fine when an area has real internal structure — person files inside a relationship area, `career/` inside the builder area, and `metrics/` / `profile/` inside the health area. Keep them discoverable by listing the area folder.

Generated or synced data that is semantically part of an area still lives under that area. Do not recreate top-level `reference/` for health metrics, career packets, PDFs, or lookup material.

## Dobby's own layer

### `dobby/growth.md`
- **Holds:** Dobby's sharpening voice — instincts that have hardened, blindspots named, misfires caught. Entries are dated.
- **Clock:** session-driven. Append whenever a real pattern is named.
- **Write pattern:** append-only sections. Do not delete entries — this is the working ground for Dobby's character.
- **Promotion:** when a pattern holds long enough to earn canonization into `soul.md`, record the promotion here with evidence.

## Journal

### `journal/daily/YYYY-MM-DD/`
- **Holds:** whatever outputs that day produces — `morning.json`, `checkin.md`, `reflection-<slug>.md`, `night.md`, raw thinking notes.
- **Write pattern:** one folder per day, created on first write. Add new files with descriptive slugs. Never flatten back to loose `YYYY-MM-DD.md`.
- **Delegation:** for structured morning/evening check-ins, use a check-in skill if one is installed.

### `journal/monthly/YYYY/MM.md`
- **Holds:** monthly review — pattern recognition, drift observations, what stabilized enough to promote to durable memory.
- **Clock:** monthly.

### `journal/templates/`
- **Holds:** reusable scaffolds for journal entries. Not active journal content.

## Clock summary

| File | Clock | Write pattern |
|---|---|---|
| `soul.md` (incl. `## About <User>`) | yearly; `## About <User>` monthly | curated edit / section edit |
| `now.md` | weekly | section rewrite, ≤60 lines |
| `sessions/YYYY/MM/DD-HHMMSS.md` | session end | one new prose note |
| `areas/<x>/<x>.md` | as area shifts | section edit |
| `areas/<x>/log.md` | event-driven | append only |
| `dobby/growth.md` | session-driven | append only |
| `journal/daily/<today>/` | daily | new files |
| `journal/monthly/<month>.md` | monthly | session edit |

## Shelf

### `state/shelf.json`
- **Holds:** Dobby Shelf, the canonical local-first personal open-loop state.
- **Clock:** fast; changes whenever a task is added, completed, deferred, or dropped.
- **Write pattern:** structured JSON rewrite with `revision` increment and `updatedAt` update. Prefer the mobile-gateway Shelf API when acting through the app boundary; direct agent writes are acceptable inside the workspace if schema, revision, and timestamps are preserved.
- **Rule:** statuses are only `open`, `done`, and `dropped`. Deferral is not a status; keep the item open, update `showAt`, increment `deferCount`, and set `lastDeferredAt`.
- **Boundary:** Shelf is for work assigned to the user. Symphony is for work assigned to Dobby as an agent. Shelf has no project hierarchy.
- **Now:** `isNow` is an uncapped soft focus signal. Too many Now items is coaching context, not a schema violation.

## What's intentionally absent

- `capture/` — removed. Raw intake goes to `journal/daily/YYYY-MM-DD/` as a dated notes file, or to the right area, or to Shelf.
- `reference/` — removed. Lookup material lives inside the relevant `memory/areas/<area>/` subfolders.
- `memory/areas/*/current.md` — removed. Per-area current state is a section in the area's main file.
- `.base` or other app-specific formats — removed. Pure markdown only.
