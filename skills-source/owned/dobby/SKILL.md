---
name: dobby
description: "Route and operate Dobby workspace memory: decide where information belongs across `soul.md`, `memory/`, journal, and Dobby growth notes. Use for \"remember/store this\", \"where should this live\", updating memory files, or cross-domain memory routing. For lifecycle hooks/boot/finalization use `dobby-lifecycle`; for tasks use `dobby-shelf`; for calendar use `dobby-calendar`; for structured reflections use `journal-checkin`."
---

# Dobby

Dobby is a repo-backed personal workspace. The workspace holds identity,
direction, per-area memory, dated journal history, Shelf open loops, calendar
context, and Dobby's own operating/growth notes.

This skill is now the **thin router and memory contract**. Load more specific
skills when the task is concrete:

- personal open loops, tasks, reminders, deferrals → `dobby-shelf`
- calendar reads/writes/search/debugging → `dobby-calendar`
- structured journaling/check-ins → `journal-checkin`
- health data → `health`
- lifecycle hooks, boot context, pre-compact, session finalization → `dobby-lifecycle`

## Boot assumptions

Session boot is handled by repo lifecycle hooks owned by `dobby-lifecycle`,
not by this skill. At session start you can usually rely on context containing:

1. `soul.md` / durable user identity from the system prompt.
2. `memory/now.md`.
3. Recent session notes.
4. Shelf snapshot.
5. Calendar snapshot.
6. Area manifest under `memory/areas/`.

Read deeper area files only when the task needs them.

## CLI-first memory operations

Use the skill-bundled memory CLI first for deterministic reads/appends:

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>.<file>
echo "- dated note" | $HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory write --section area.<name>.log --message "label"
```

Use direct file edits for section rewrites, new files, or `soul.md` edits.
See `references/commands.md` for memory command recipes.

## Write-decision tree

Route new information to exactly one canonical home. Do not duplicate; point
instead.

| Signal | Home | Operation |
|---|---|---|
| Personal actionable item / open loop assigned to the user | Shelf (`state/shelf.json`) | Use `dobby-shelf` |
| Calendar event, schedule, event search | Calendar | Use `dobby-calendar` |
| Durable truth about the user: identity, pattern, preference | `soul.md` `## About <User>` | Edit in place |
| This week's active context | `memory/now.md` | Rewrite relevant section, keep ≤60 lines |
| Session continuity / what happened last time | `memory/sessions/YYYY/MM/DD-HHMMSS.md` | Auto-written by `dobby-lifecycle` hooks |
| Per-area durable canon | `memory/areas/<area>/<area>.md` | Edit in place |
| Per-area event or task completion | `memory/areas/<area>/log.md` | Append dated one-liner via CLI |
| Dated reflection, check-in, or raw capture | `journal/daily/YYYY-MM-DD/` | Use `journal-checkin` for structured check-ins; otherwise create a dated note |
| Monthly pattern recognition | `journal/monthly/YYYY/MM.md` | Edit during monthly review |
| Dobby's own voice sharpening / blindspot named | `dobby/growth.md` | Append dated entry |

## Memory hygiene

- One canonical home per fact.
- Read before writing.
- Respect file clocks: `soul.md` is slow, `now.md` is weekly, area canon shifts
  as needed, logs are append-only.
- Do not put session handoff prose in `memory/now.md`; session notes live under
  `memory/sessions/`.
- No `current.md` files. Area active state belongs in the area's main file or
  cross-cutting `memory/now.md`.
- Standing permission exists for memory write-back when something durable
  surfaces. Write directly and note it inline.

## Reference files

Load on demand:

- `references/files.md` — file-by-file memory/journal contract.
- `references/commands.md` — Dobby memory CLI recipes and direct-edit fallback.
- `references/scenarios.md` — user intent to routing/action mappings.
- For lifecycle hook internals, load `dobby-lifecycle`.
