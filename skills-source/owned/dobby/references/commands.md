# Dobby commands — CLI first, direct-ops fallback

The skill-bundled scripts are the preferred path. They are agent-first: JSON envelopes by default, `--plain` for operator inspection, no prompts, and stable error envelopes for validation/runtime failures. Use `Edit`/`Write` tools only when the scripts cannot do what is needed. Run from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

## Boot

Pull full context at session start.

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot
```
Returns: `profile.md` + `now.md` + `becoming.md` content + lazy area manifest (file names, sizes, mtimes — not content).

JSON is the default output contract. Add `--plain` for markdown inspection.

## Read a specific file

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section profile
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section becoming
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>              # concatenates all .md in that area
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>.<file>       # single file (without .md)
```

Add `--plain` when you want raw markdown content on stdout.

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

The CLI does NOT create files. The target must already exist. Content must arrive on stdin; commands do not prompt.

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
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks done <id-prefix> --log-now  # optional immediate Logbook move
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks cancel <id-prefix>
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks delete <id-prefix>

/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor                    # 5-point health check
```

`--when` accepts natural-language dates: `today`, `tomorrow`, `next monday`, `in 3 days`, specific dates.
`--area` is case-sensitive and must match an existing Things 3 Area.
Read commands return a fast summary shape by default. Use `--verbose` only when full fields such as notes and timestamps are needed. Create commands avoid slow read-back by default; pass `--resolve` when full created-object data is worth the latency.
Add `--plain` for compact inspection output.

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

## Tests

The Dobby skill test runner is cheap/non-mutating by default. Live suites are opt-in because they may create temporary real Things 3 tasks or Calendar events before cleanup.

```bash
# Default: cheap suites only. Does not run */live.sh.
bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh

# Include all live integration/smoke suites.
RUN_LIVE=1 bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh

# Run only a specific live suite.
bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh tasks live
bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh calendar live

# Cleanup stale open Things 3 DOBBY-TEST-* artifacts without running live suites.
SWEEP_THINGS=1 bash /Users/adi/.agents/skills-source/owned/dobby/tests/run.sh
```

Rules for agents:
- Run the default cheap suite for normal Dobby script/doc changes.
- Run live suites only when touching Things 3 writes, Calendar writes, backend integration, or before closing a risky refactor.
- Live Things tests use `DOBBY-TEST-*` task titles and sweep open leftovers before/after selected live task runs.
- Do not mark synthetic Things test tasks `done`: Things keeps completed items in Logbook and AppleScript cannot reliably purge them one-by-one.
- Do not add real external writes to non-live test files. Put write-path coverage in `*/live.sh`.

## Diff and history

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "24 hours ago"
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "1 week ago"
```

Wraps `git log -p memory/` with date filtering.

## Output contract

Every CLI command defaults to a stable JSON envelope and also accepts explicit `--json`:
```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks today
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor
```

The scripts emit the standard Dobby JSON envelope (`schema_version`, `command`, `status`, `data`, `error`, `meta`) by default. Use `--plain` for markdown/text inspection.

Timeout configuration:
- `DOBBY_MEMORY_GIT_TIMEOUT_SECS` — memory diff git timeout, default `15`
- `DOBBY_THINGS_OSASCRIPT_TIMEOUT_SECS` — Things JXA/AppleScript timeout, default `15`
- `DOBBY_THINGS_OPEN_TIMEOUT_SECS` — Things URL open timeout, default `10`
- `DOBBY_THINGS_URL_SETTLE_SECS` — post-URL settle delay, default `0.5`
- `DOBBY_CALENDAR_TIMEOUT_SECS` — calendar `ical` timeout, default `20`

Secrets are never accepted via flags. Things URL auth uses the workspace `.env` file provisioned by the local secret bootstrap; the token is not emitted in outputs.

## Typical session-start pattern

```bash
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-memory boot                     # full context
/Users/adi/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot                 # today + overdue + inbox
# then respond with counts surfaced: "Today N, overdue M, inbox K (notes)"
```

## Permissions reminder

Standing permission: write to memory files without asking. Note a one-liner in your response so the user sees what changed. Do NOT post publicly, send messages, or make irreversible external changes without confirmation.
