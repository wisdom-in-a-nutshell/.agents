# Dobby file contracts

What each file is for, how often it changes, and the write pattern (append / edit / rewrite).

## Constitution

### `soul.md`
- **Holds:** Dobby's operating constitution — identity, values, communication style, safety rules, write-back policy, instruction priority.
- **Clock:** yearly. Only changes when a pattern proves durable.
- **Write pattern:** curated edit in place. Never append raw logs. No operational specifics (paths, commands) — those belong in the `dobby` skill.

## Root memory

### `memory/profile.md`
- **Holds:** durable truths about the user — identity, preferences, patterns, values, structural/financial context, risk patterns, support patterns. "Who the user is today."
- **Clock:** monthly; occasional when something stable shifts.
- **Write pattern:** edit in place by section. Never append undated logs here — use `journal/daily/` for observations, promote the durable signal once it proves out.

### `memory/now.md`
- **Holds:** this week's active context — week shape, strategic tracks, life timeline, watchouts, session handoff.
- **Clock:** weekly rewrites; section updates as context shifts.
- **Write pattern:** rewrite sections in place. Hard cap: ≤60 lines. If a section outgrows its budget, promote stable content to `profile.md` / area canon / `becoming.md` and prune.
- **Rule:** actionable items live in Things 3, not here.

### `memory/becoming.md`
- **Holds:** direction — north star, the person the user is moving toward, current-year priorities, active shifts, commitments to self.
- **Clock:** quarterly reflection + as commitments surface.
- **Write pattern:** section edits in place; "Commitments made to self" is append-only with dates.
- **Rule:** this is identity, not a task list. Tasks go to Things 3.

## Areas (mirror Things 3 Areas)

Each area has a folder under `memory/areas/`. The set of areas is workspace-instance-specific — discover via `ls memory/areas/`. Each area contains at minimum a main `.md` plus `log.md`.

### `memory/areas/<area>/<area>.md`
- **Holds:** durable canon for that area — identity, patterns, active "Current state" section, coaching notes.
- **Clock:** shifts as the area shifts. Faster than profile, slower than now.
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
| `soul.md` | yearly | curated edit |
| `profile.md` | monthly | section edit |
| `becoming.md` | quarterly | section edit + append commitments |
| `now.md` | weekly | section rewrite, ≤60 lines |
| `areas/<x>/<x>.md` | as area shifts | section edit |
| `areas/<x>/log.md` | event-driven | append only |
| `dobby/growth.md` | session-driven | append only |
| `journal/daily/<today>/` | daily | new files |
| `journal/monthly/<month>.md` | monthly | session edit |

## What's intentionally absent

- `capture/` — removed. Raw intake goes to `journal/daily/YYYY-MM-DD/` as a dated notes file, or to the right area, or to Things 3.
- `reference/` — removed. Lookup material lives inside the relevant `memory/areas/<area>/` subfolders.
- `memory/areas/*/current.md` — removed. Per-area current state is a section in the area's main file.
- `.base` or other app-specific formats — removed. Pure markdown only.
