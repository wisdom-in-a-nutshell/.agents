# Dobby commands — CLI first, direct-ops fallback

The skill-bundled scripts are the preferred path. They are agent-first: JSON envelopes by default, `--plain` for operator inspection, no prompts, and stable error envelopes for validation/runtime failures. Use `Edit`/`Write` tools only when the scripts cannot do what is needed. Run from a Dobby workspace root, or set `DOBBY_WORKSPACE=/path/to/workspace`.

## Boot

Boot context is delivered by the repo's `SessionStart` hook
(`scripts/hooks/session_start.py`). This CLI no longer exposes a `boot`
subcommand. The workspace user's durable identity lives in `soul.md` under
that workspace's `## About <User>` section and arrives via the
wrapper-composed system prompt.

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

The CLI only appends. For replacing a section in `now.md`, an area main file, or `## About <User>` in `soul.md`, use `Edit`:

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

## Shelf Open Loops

Shelf is the workspace-local personal open-loop surface. It is the only task
state Dobby workspace operations use:

```text
state/shelf.json
```

Use Shelf for work assigned to the user: follow-ups, reminders, purchases,
small tasks, and concrete one-off actions. Use Symphony for work assigned to
Dobby as an agent.

When working through the iPhone boundary, use the mobile-gateway endpoints:

```bash
curl -sS "http://127.0.0.1:8787/v1/shelf?surfaceKey=ios:local-smoke"

curl -sS -X POST http://127.0.0.1:8787/v1/shelf/items \
  -H 'content-type: application/json' \
  --data '{"surfaceKey":"ios:local-smoke","title":"Book dentist","showAt":"2026-05-04"}'
```

When working directly inside the workspace, read/write the JSON carefully:

- `status`: only `open`, `done`, `dropped`
- `kind`: only `do`, `buy`, `remember`
- `showAt`: when it surfaces
- `dueAt`: when it is owed
- `isNow`: uncapped soft focus signal
- defer: keep `status: "open"`, update `showAt`, increment `deferCount`, set `lastDeferredAt`
- drop: set `status: "dropped"` and add `dropReason` when meaningful

Increment `revision` and update top-level `updatedAt` on every write.
If many open items are `isNow: true`, name the overload and help the user choose;
do not reject the write or auto-bump items.

## Calendar

Calendar operations use `dobby-calendar` (EventKit via the native Dobby Calendar Bridge LaunchAgent/socket helper, with Homebrew `ical` fallback). The default calendar name is required via the `DOBBY_CALENDAR_DEFAULT` env var (set per-workspace in `scripts/local/secrets/static_env_defaults.env`); there is no hardcoded fallback. Commands that need a specific calendar fail fast with a clear error when unset. Search/list commands must be date-bounded.

Backend diagnostics:

```bash
DOBBY_CALENDAR_BACKEND=bridge $HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
DOBBY_CALENDAR_BACKEND=ical $HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar doctor
~/.agents/skills-source/owned/dobby/scripts/dobby_calendar/bridge/install --request-access
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

The Dobby skill test runner is cheap/non-mutating by default. Live suites are opt-in because they may create temporary real Calendar events before cleanup. Shelf backend tests live in `~/GitHub/codexclaw/services/mobile-gateway`.

```bash
# Default: cheap suites only. Does not run */live.sh.
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh

# Include all live integration/smoke suites.
RUN_LIVE=1 bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh

# Run only a specific live suite.
bash $HOME/.agents/skills-source/owned/dobby/tests/run.sh calendar live
```

Rules for agents:
- Run the default cheap suite for normal Dobby script/doc changes.
- Run Dobby live suites only when touching Calendar writes, backend integration, or before closing a risky refactor.
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
$HOME/.agents/skills-source/owned/dobby/scripts/dobby-calendar week
```

The scripts emit a stable JSON envelope (`schema_version`, `command`, `status`, `data`, `error`, `meta`) by default. Use `--plain` for markdown/text inspection.

Timeout configuration:
- `DOBBY_MEMORY_GIT_TIMEOUT_SECS` — memory diff git timeout, default `15`
- `DOBBY_CALENDAR_TIMEOUT_SECS` — calendar `ical` timeout, default `20`
- `DOBBY_CALENDAR_BACKEND` — calendar backend, `auto|bridge|ical`, default `auto`
- `DOBBY_CALENDAR_BRIDGE_BIN` — optional explicit path to `DobbyCalendarBridge` helper for install/doctor discovery
- `DOBBY_CALENDAR_BRIDGE_SOCKET` — optional explicit Unix socket path for the bridge server
- `DOBBY_CALENDAR_BRIDGE_TIMEOUT_SECS` — native bridge timeout, default `20`

Secrets are never accepted via flags.

## Typical session-start pattern

Boot context is delivered automatically by `scripts/hooks/session_start.py`.
You do not need to invoke anything manually. Surface the hook's `# shelf`
counts naturally in your first response.

## Permissions reminder

Standing permission: write to memory files without asking. Note a one-liner in your response so the user sees what changed. Do NOT post publicly, send messages, or make irreversible external changes without confirmation.
