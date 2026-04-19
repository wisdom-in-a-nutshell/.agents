# Dobby commands — CLI first, direct-ops fallback

The skill-bundled scripts are the preferred path. Use `Edit`/`Write` tools only when the scripts cannot do what is needed. Run from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

## Boot

Pull full context at session start.

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot
```
Returns: `profile.md` + `now.md` + `becoming.md` content + lazy area manifest (file names, sizes, mtimes — not content).

Add `--json` for structured output.

## Read a specific file

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section profile
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section becoming
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>              # concatenates all .md in that area
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>.<file>       # single file (without .md)
```

Fallback (when you only need one file and don't want CLI overhead):
```
Read memory/profile.md
```

## Append to a file (CLI-preferred)

The CLI auto-stamps a timestamped header — ideal for log-style appends.

```bash
echo "- 2026-04-17 — event" | \
  /Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory write --section area.<name>.log --message "short label"
```

The CLI does NOT create files. The target must already exist.

## Mid-file section rewrite (Edit tool only)

The CLI only appends. For replacing a section in `profile.md`, `now.md`, or an area main file, use `Edit`:

```
Edit memory/now.md
  old_string: "## This week's shape\n\n- old content"
  new_string: "## This week's shape\n\n- new content"
```

Read the target first to avoid duplicating content already there.

## New file (Write tool only)

CLI `memory write` does not create files. Use `Write` for:
- Journal entries: ensure `journal/daily/YYYY-MM-DD/` exists first (`mkdir -p`), then write the file.
- New area sub-files.
- Any first-time file.

## Tasks (Things 3)

No file-based alternative — always via CLI.

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot   # today + overdue + inbox in one JXA call
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks today
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks inbox
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks overdue
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks search "Beach"
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks search "Beach" --verbose  # slower, full fields

/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks add "Task title" --when today --area <Area>
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks add "Task title" --when "next monday" --area <Area> \
  --checklist "step one, step two, step three"

/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks done <id-prefix>
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks cancel <id-prefix>
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks delete <id-prefix>

/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor                    # 5-point health check
```

`--when` accepts natural-language dates: `today`, `tomorrow`, `next monday`, `in 3 days`, specific dates.
`--area` is case-sensitive and must match an existing Things 3 Area.
Read commands return a fast summary shape by default. Use `--verbose` only when full fields such as notes and timestamps are needed. Create commands avoid slow read-back by default; pass `--resolve` when full created-object data is worth the latency.

## Calendar

Calendar operations use `dobby-calendar` (EventKit via `ical`). Default calendar: `adithyan@wisdominanutshell.academy`. Search/list commands should be date-bounded.

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar calendars
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar week
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "Birthday" --from 2026-01-01 --to 2026-12-31
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "Neha" --from 2025-01-01 --to 2027-12-31 --all-calendars
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar add-event --title "Sassnitz / Rügen trip" --start 2026-04-30 --end 2026-05-06 --all-day --location "Ummanzer Str. 10, 18546 Sassnitz, Germany" --dry-run
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-calendar upsert-event --title "Sassnitz / Rügen trip" --start 2026-04-30 --end 2026-05-06 --all-day --match-from 2026-04-01 --match-to 2026-05-31
```

Do not use AppleScript for broad calendar search/audits; it can hang on Google-backed calendars. Use `dobby-calendar` or export/parse `.ics` for migrations.

## Diff and history

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "24 hours ago"
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "1 week ago"
```

Wraps `git log -p memory/` with date filtering.

## JSON mode

Every CLI command supports `--json` for a stable envelope:
```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot --json
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot --json
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks today --json
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor --json
```

The scripts emit the standard Dobby JSON envelope (`schema_version`, `command`, `status`, `data`, `error`, `meta`) when `--json` is used or for JSON-default calendar commands.

## Typical session-start pattern

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot                     # full context
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot                 # today + overdue + inbox
# then respond with counts surfaced: "Today N, overdue M, inbox K (notes)"
```

## Permissions reminder

Standing permission: write to memory files without asking. Note a one-liner in your response so the user sees what changed. Do NOT post publicly, send messages, or make irreversible external changes without confirmation.
