# Dobby commands — CLI first, direct-ops fallback

The skill-bundled scripts are the preferred path. They are agent-first: JSON envelopes by default, `--plain` for operator inspection, no prompts, and stable error envelopes for validation/runtime failures. Use `Edit`/`Write` tools only when the scripts cannot do what is needed. Run from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`). This CLI no longer exposes a `boot`
subcommand. Adi's durable identity lives in `soul.md` under `## About Adi`
and arrives via the wrapper-composed system prompt.

## Read a specific file

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>              # concatenates all .md in that area
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section area.<name>.<file>       # single file (without .md)
```

Add `--plain` when you want raw markdown content on stdout.

Fallback (when you only need one file and don't want CLI overhead):
```
Read memory/now.md
```

## Append to a file (CLI-preferred)

The CLI auto-stamps a timestamped header — ideal for log-style appends.

```bash
echo "- 2026-04-17 — event" | \
  $HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory write --section area.<name>.log --message "short label"
```

The CLI does NOT create files. The target must already exist. Content must arrive on stdin; commands do not prompt.

## Mid-file section rewrite (Edit tool only)

The CLI only appends. For replacing a section in `now.md`, an area main file, or `## About Adi` in `soul.md`, use `Edit`:

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
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot   # today + overdue + inbox
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks today
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks inbox
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks overdue
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks search "Beach"
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks search "Beach" --verbose  # slower, full fields
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks inspect "Personal AI / agent system"

$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks add "Task title" --when today --area <Area>
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks add "Task title" --when "next monday" --area <Area> \
  --checklist "step one, step two, step three"

$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks done <id-prefix>
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks done <id-prefix> --log-now  # optional immediate Logbook move
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks cancel <id-prefix>
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks delete <id-prefix>

$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor                    # Things integration health check
```

`--when` accepts natural-language dates: `today`, `tomorrow`, `next monday`, `in 3 days`, specific dates.
`--area` is case-sensitive and must match an existing Things 3 Area.
Read commands return a fast summary shape by default. Use `--verbose` only when full fields such as notes and timestamps are needed. Create commands avoid slow read-back by default; pass `--resolve` when full created-object data is worth the latency.
Add `--plain` for compact inspection output.

Read commands use `--backend auto` by default: read-only SQLite first, JXA
fallback only if the local database is unavailable. Agents should normally not
set this flag; use `--backend sqlite|jxa|auto` only for diagnostics.

`delete` can remove open tasks by name/ID and completed Logbook tasks by exact ID. Use `search --include-completed` first when cleaning old test artifacts.
`done` and `cancel` use the Things URL scheme and are the reliable status-change path.
`delete` still requires Things AppleScript because the URL scheme does not expose Trash/delete; if `doctor` reports `applescript_task_access` degraded, prefer `cancel` unless true deletion is required.

## Calendar

Calendar operations use `dobby-calendar` (EventKit via the native Dobby Calendar Bridge LaunchAgent/socket helper, with Homebrew `ical` fallback). The default calendar name is required via the `DOBBY_CALENDAR_DEFAULT` env var (set per-workspace in `scripts/local/secrets/static_env_defaults.env`); there is no hardcoded fallback. Commands that need a specific calendar fail fast with a clear error when unset. Search/list commands must be date-bounded.

Backend diagnostics:

```bash
DOBBY_CALENDAR_BACKEND=bridge $HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
DOBBY_CALENDAR_BACKEND=ical $HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
~/.agents/skills-source/owned/dobby/scripts/install-dobby-calendar-bridge --request-access
```

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar calendars
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar week
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "Birthday" --from 2026-01-01 --to 2026-12-31
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar search "Neha" --from 2025-01-01 --to 2027-12-31 --all-calendars
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar add-event --title "Sassnitz / Rügen trip" --start 2026-04-30 --end 2026-05-06 --all-day --location "Ummanzer Str. 10, 18546 Sassnitz, Germany" --dry-run
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar upsert-event --title "Sassnitz / Rügen trip" --start 2026-04-30 --end 2026-05-06 --all-day --match-from 2026-04-01 --match-to 2026-05-31
```

Do not use AppleScript for broad calendar search/audits; it can hang on Google-backed calendars. Use `dobby-calendar` or export/parse `.ics` for migrations.

## Tests

The Dobby skill test runner is cheap/non-mutating by default. Live suites are opt-in because they may create temporary real Things 3 tasks or Calendar events before cleanup.

```bash
# Default: cheap suites only. Does not run */live.sh.
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh

# Include all live integration/smoke suites.
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh

# Run only a specific live suite.
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh tasks live
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh calendar live

# Cleanup stale Things 3 DOBBY-TEST-* artifacts without running live suites.
SWEEP_THINGS=1 bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh
```

Rules for agents:
- Run the default cheap suite for normal Dobby script/doc changes.
- Run live suites only when touching Things 3 writes, Calendar writes, backend integration, or before closing a risky refactor.
- Live Things tests use `DOBBY-TEST-*` task titles and sweep leftovers before/after selected live task runs.
- Do not mark synthetic Things test tasks `done`: even though known `DOBBY-TEST-*` IDs can be purged, live tests should avoid creating completed Logbook artifacts in the first place.
- Do not add real external writes to non-live test files. Put write-path coverage in `*/live.sh`.

## Diff and history

```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "24 hours ago"
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory diff --since "1 week ago"
```

Wraps `git log -p memory/` with date filtering.

## Output contract

Every CLI command defaults to a stable JSON envelope and also accepts explicit `--json`:
```bash
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-memory read --section now
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks snapshot
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks today
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-tasks doctor
```

The scripts emit the standard Dobby JSON envelope (`schema_version`, `command`, `status`, `data`, `error`, `meta`) by default. Use `--plain` for markdown/text inspection.

Timeout configuration:
- `DOBBY_MEMORY_GIT_TIMEOUT_SECS` — memory diff git timeout, default `15`
- `DOBBY_THINGS_OSASCRIPT_TIMEOUT_SECS` — Things JXA/AppleScript timeout, default `15`
- `DOBBY_THINGS_JXA_READ_TIMEOUT_SECS` — task read JXA backend/fallback timeout, default `5`
- `DOBBY_THINGS_JXA_PROBE_TIMEOUT_SECS` — doctor JXA health probe timeout, default `3`
- `DOBBY_THINGS_OPEN_TIMEOUT_SECS` — Things URL open timeout, default `10`
- `DOBBY_THINGS_URL_SETTLE_SECS` — post-URL settle delay, default `0.5`
- `DOBBY_THINGS_READ_BACKEND` — task read backend, `auto|sqlite|jxa`, default `auto`
- `DOBBY_THINGS_SQLITE_PATH` — optional explicit Things `main.sqlite` path for diagnostics
- `DOBBY_CALENDAR_TIMEOUT_SECS` — calendar `ical` timeout, default `20`
- `DOBBY_CALENDAR_BACKEND` — calendar backend, `auto|bridge|ical`, default `auto`
- `DOBBY_CALENDAR_BRIDGE_BIN` — optional explicit path to `DobbyCalendarBridge` helper for install/doctor discovery
- `DOBBY_CALENDAR_BRIDGE_SOCKET` — optional explicit Unix socket path for the bridge server
- `DOBBY_CALENDAR_BRIDGE_TIMEOUT_SECS` — native bridge timeout, default `20`

Secrets are never accepted via flags. Things URL auth uses the workspace `.env` file provisioned by the local secret bootstrap; the token is not emitted in outputs.

## Typical session-start pattern

Boot context is delivered automatically by `scripts/hooks/session_start.py`.
You do not need to invoke anything manually. Surface the overdue / today /
inbox counts from the hook's `# tasks` section in your first response.

## Permissions reminder

Standing permission: write to memory files without asking. Note a one-liner in your response so the user sees what changed. Do NOT post publicly, send messages, or make irreversible external changes without confirmation.
