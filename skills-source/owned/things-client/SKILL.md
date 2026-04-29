---
name: things-client
description: Use when an agent needs to read, inspect, or update Things 3 tasks through a reusable local CLI. Applies to Things 3 task discovery, tag-based queues, task note write-back, and health checks across repos without using Dobby-specific memory or routing policy.
---

# Things Client

## Overview

This skill provides the reusable Things 3 client for agents. It is the generic task-access layer; personal routing policy belongs in Dobby-style workspace skills, and engineering orchestration belongs in DevWorker.

## CLI

Use the bundled CLI directly:

```bash
THINGS="$HOME/.agents/skills-source/owned/things-client/scripts/things-client"

$THINGS snapshot
$THINGS today | inbox | overdue
$THINGS list --tag agent --verbose
$THINGS inspect <task-id-or-title>
$THINGS add "Task title" --when today --area <Area>
$THINGS edit <task-id-or-title> --append-notes "..."
$THINGS done <task-id-or-title>
$THINGS doctor
```

Output is a stable JSON envelope by default. Use `--plain` only for human inspection.

## Package Structure

The executable path is stable, but the implementation is split underneath it:

- `scripts/things-client` — thin executable wrapper.
- `scripts/things_client/` — Python package for CLI wiring, envelopes, config, SQLite reads, JXA fallback reads, URL-scheme writes, AppleScript maintenance, and formatting.
- `tests/contract.sh` — import, wrapper, and token lookup contract.
- `tests/sqlite.sh` — cheap SQLite-backed behavior tests.
- `tests/live.sh` — opt-in real Things 3 write smoke.

## Command Surface

- Read tasks: `snapshot`, `today`, `inbox`, `upcoming`, `anytime`, `someday`, `overdue`, `logbook`, `list`, `search`, `inspect`.
- Read structure: `projects`, `areas`, `tags`.
- Write tasks: `add`, `edit`, `schedule`, `done`, `complete` (alias), `cancel`, `delete --yes`, `show`.
- Write structure/admin: `project-new`, `area-new`, `log-completed`, `empty-trash --yes`.
- Health: `doctor`.

## Boundaries

- Reads auto-discover the local Things SQLite database and open it read-only. If SQLite is unavailable, read commands fall back to bounded JXA against the running Things app.
- Writes use supported Things URL-scheme operations.
- Deletion and Logbook maintenance use bounded AppleScript because the Things URL scheme does not expose those operations.
- Do not write directly to the Things SQLite database.
- Do not encode Dobby memory, journal, calendar, or area-routing policy here.
- Keep DevWorker-specific parsing such as `repo:codexclaw` in DevWorker.

## Token Lookup

Task note updates need the Things URL-scheme auth token. Reads do not need this token.

The token is read only from files. The lookup order is intentionally small:

1. `THINGS_CLIENT_ENV_FILE` pointing at a simple `.env` file
2. `$DOBBY_WORKSPACE/.env`
3. the current working directory `.env`

`THINGS_CLIENT_ENV_FILE` is only for callers that are not running from the repo
or Dobby workspace whose `.env` should be used. Most workspace agents should not
set it.

The file should contain `THINGS3_AUTH_TOKEN=...`. The CLI does not accept the
token directly from the process environment.

The token is never printed.

## SQLite Reads

The CLI normally discovers the newest non-backup Things database under the Things app-group directory. To force a specific database path for diagnostics, set one of:

- `THINGS_CLIENT_SQLITE_PATH`
- `THINGS_SQLITE_PATH`

Explicit paths are overrides. If an explicit path is missing or broken, the command fails instead of silently using another database. Without an explicit path, read commands use auto-discovered read-only SQLite first and bounded JXA as a fallback.

Useful diagnostic knobs:

- `THINGS_CLIENT_READ_BACKEND=auto|sqlite|jxa`
- `THINGS_CLIENT_JXA_TIMEOUT_SECS`
- `THINGS_CLIENT_JXA_PROBE_TIMEOUT_SECS`
- `THINGS_CLIENT_OPEN_TIMEOUT_SECS`
- `THINGS_CLIENT_URL_SETTLE_SECS`

## Common Patterns

For local intake queues, prefer a caller-owned Things tag such as `agent`, then let the caller interpret task notes:

```bash
things-client list --tag agent --verbose
```

When a task has been promoted to a durable tracker item, append the URL to the notes:

```bash
things-client edit <task-id> --append-notes "https://github.com/owner/repo/issues/123"
```

When the durable tracker work completes successfully, complete the Things task:

```bash
things-client complete <task-id>
```

If a command fails, inspect the JSON `error.code` and `error.hint`; do not scrape prose output.

## Testing

- Cheap/non-mutating full check: `$HOME/.agents/skills-source/owned/things-client/tests/run.sh`
- Contract only: `$HOME/.agents/skills-source/owned/things-client/tests/contract.sh`
- SQLite behavior only: `$HOME/.agents/skills-source/owned/things-client/tests/sqlite.sh`
- Opt-in live write smoke: `RUN_LIVE=1 $HOME/.agents/skills-source/owned/things-client/tests/run.sh`

The live suite creates uniquely prefixed test tasks and cancels them during cleanup. Do not run it unless real local Things writes are acceptable.
