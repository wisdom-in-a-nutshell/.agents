# Dobby scenarios — user intent → action

Common phrasings mapped to the exact operation. Match intent, not literal words; the user often dictates, so expect typos and dropped words.

## Store / remember

**"Remember that I prefer X"** / "Note that I..."
→ Classify:
- Durable identity/preference? → `Edit soul.md` in the right subsection of `## About Adi`.
- Per-area canon? → `Edit memory/areas/<area>/<area>.md`.

Confirm in one line: "Added to `soul.md` `## About Adi` under Communication preferences."

**"Save this for later"** / "Keep this"
→ Actionable? → Things 3 Inbox via `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks add`. Content/reflection? → new file in `journal/daily/<today>/notes-<slug>.md`.

**"Add this to <area>"**
→ Durable canon? → `Edit memory/areas/<area>/<area>.md`. Event/completion? → append to `memory/areas/<area>/log.md` via CLI.

## Read

**"What's on today?"** / "What's my day look like?"
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot` for today + overdue + inbox in one call. Surface counts and the live list.

**"What's on my calendar / week?"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar week` or `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar today`. Use `--all-calendars` only when the user asks for an audit or cross-account search.

**"What's in my inbox?"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks inbox`. Flag anything stale.

**"What do you know about <area>?"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<area>.<area>` (single main file). Surface "Current state" section first. Load the log only if asked.

**"What's live right now?"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now`.

**"What happened yesterday / last week?"**
→ `ls journal/daily/` for recent dates; `Read` the relevant folder's `checkin.md` or reflections.

## Route

**"Where does this go?"**
→ Walk the write-decision tree:
- Actionable? → Things 3.
- Durable truth about the user? → `soul.md` `## About Adi`.
- Per-area? → `memory/areas/<area>/`.
- Dated reflection? → `journal/daily/<today>/`.

Propose the destination; do the write.

## Tasks

**"Add a task to X"** / "Remind me to X" / "I need to X"
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks add "X" --when <default: today> --area <best guess; ask if unclear>`.

**"Mark X done"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks done <id-prefix>`. If no id, use `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks search "X"` first.

**"What's overdue?"**
→ `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks overdue`. Name any drift from stated commitments directly.

## Calendar

**"Add this to calendar"** / "Block this time" / "Schedule this trip"
→ Use `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar upsert-event` when an event may already exist; include a match range to avoid duplicates. Default calendar comes from `DOBBY_CALENDAR_DEFAULT` (required; no fallback); override per-call with `--calendar`.

**"Search my calendar for X"**
→ Use `$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "X" --from <date> --to <date>`. Calendar searches must be date-bounded; use `--all-calendars` for migration/audit work.

## Reflect

**"Let's journal"** / "Morning check-in" / "Night reflection" / "I want to reflect"
→ If a structured check-in skill is installed (e.g., `journal-checkin`), delegate to it. Otherwise: `mkdir -p journal/daily/<today>` and `Write` a new reflection file with a descriptive slug.

**"I want to just note something"** (not a full journal)
→ `Write journal/daily/<today>/notes-<slug>.md`.

## Dobby's own growth

**"You were wrong about X"** / "Actually I prefer Y"
→ Append to `dobby/growth.md` under "Blindspots" with today's date, what was wrong, what's updated.

**"You're getting sharper at X"** / "That was a good instinct"
→ Append to `dobby/growth.md` under "Voice and instinct" with the specific pattern.

## Consolidation

**"Clean up memory"** / "This is getting messy"
→ If a memory-consolidation skill is installed, invoke it for the reflective pass. Otherwise: read the bloated file, propose the consolidation plan, execute with the user's go-ahead.

## Ambiguity resolution (default ordering)

When the route isn't obvious, try in order:

1. Actionable? → Things 3 (always wins).
2. Dated observation? → `journal/daily/<today>/`.
3. Tied to one area? → `memory/areas/<area>/`.
4. Cross-cutting, this week? → `memory/now.md`.
5. Durable and about the user? → `soul.md` `## About Adi`.
6. Unsure? → `journal/daily/<today>/notes-<slug>.md` as a safe holding ground; route properly during next consolidation.

## Read-before-write rule

For any substantive write (>2 lines into an existing file, or any edit to `soul.md` `## About Adi` or area canon), read the target first. Duplicates are the biggest drift source. Add "see also" pointers instead of restating.
