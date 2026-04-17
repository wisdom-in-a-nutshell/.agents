---
name: dobby
description: Canonical contract for operating a Dobby workspace — a personal-agent repo where memory, direction, per-area canon, journal, and tasks are held as the user's externalized mind. Use whenever the user wants to store, read, update, or route personal memory; check or update task state; reflect or journal; answer "where does this go"; or run any operation that touches `memory/`, `dobby/`, `journal/`, or Things 3. Triggers include "remember this", "store this", "add to memory", "save for later", "I want to become...", "what's on today", "what's overdue", "what's in my inbox", "what do you know about that area", "where does this go", "add a task", "mark done", "I need to...", and any routing decision about new information surfaced in conversation. This skill holds the write-decision tree, file contracts, command recipes, and hygiene rules so operating the workspace is deterministic across agents.
---

# Dobby

## Overview

Dobby is a companion that lives in a git repo. The workspace itself is Dobby — `memory/`, `journal/`, `dobby/`, plus a task surface (Things 3). This skill is the operator's manual: what to read, where to write, how to keep the workspace coherent across agents.

Soul lives in `/soul.md` (Dobby's character). Operations live here.

## Boot

On any fresh session:

1. `soul.md` is loaded automatically by the harness.
2. Load memory context via `scripts/dobby/dobby memory boot` (returns `profile.md` + `now.md` + `becoming.md` + lazy area manifest with mtimes).
3. Check task state: `scripts/dobby/dobby tasks today`, `tasks overdue`, `tasks inbox`.
4. Surface overdue count, today count, and inbox count naturally in the first response.
5. Read deeper files only when the task actually needs them. Areas under `memory/areas/` load on demand.

## Prefer the CLI

The Dobby CLI (`scripts/dobby/dobby`) is the preferred path for reads, appends, and tasks. It is deterministic, timestamped, and tested.

**Reach for the CLI first.** Fall through to the `Edit`/`Write` tools only when the CLI cannot do what's needed — surgical mid-file section rewrites, or creating a new file. Both are legitimate; the CLI is simply the default.

Examples:
- Boot: `dobby memory boot`
- Read a file: `dobby memory read --section profile` / `--section area.<name>.<file>`
- Append to a log: `echo "- date — event" | dobby memory write --section area.<name>.log --message "label"`
- Mid-file section edit in `profile.md`: use `Edit` tool (CLI can't replace sections)
- New journal file: use `Write` tool (CLI `write` appends, doesn't create)

See `references/commands.md` for full recipes.

## Write-decision tree

When new information surfaces, route it to exactly one canonical home. Never duplicate; point instead.

| Signal | Home | Operation |
|---|---|---|
| Actionable item (to do, follow up, remind me) | **Things 3** | `dobby tasks add "..." --when ... --area <Area>` |
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

- Add: `dobby tasks add "..." --when today|tomorrow|"next monday" --area <Area> --checklist "a,b,c"`
- List: `dobby tasks today | inbox | overdue`
- Complete: `dobby tasks done <id-prefix>`
- Doctor: `dobby tasks doctor` (5-point health check)

Habits are not Things 3 tasks. Structured check-ins are handled by a journaling skill if one is installed; recurring physical habits (running, etc.) are Things 3 recurring tasks set once in the UI; behavioral nudges happen inside conversation.

Default for ambiguous new tasks: drop into Things 3 Inbox. The user sorts during morning review.

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
