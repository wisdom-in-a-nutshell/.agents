---
name: things-client
description: Use when an agent needs to read, inspect, or update Things 3 tasks through a reusable local CLI. Applies to Things 3 task discovery, tag-based queues, task note write-back, and health checks across repos without using Dobby-specific memory or routing policy.
---

# Things Client

## Overview

This skill provides the reusable Things 3 client for agents. It is the generic task-access layer; personal routing policy belongs in Dobby/Adi, and engineering orchestration belongs in DevWorker.

## CLI

Use the bundled CLI directly:

```bash
THINGS="$HOME/.agents/skills-source/owned/things-client/scripts/things-client"

$THINGS snapshot
$THINGS today | inbox | overdue
$THINGS list --tag devworker --verbose
$THINGS inspect <task-id-or-title>
$THINGS add "Task title" --when today --area <Area>
$THINGS edit <task-id-or-title> --append-notes "..."
$THINGS done <task-id-or-title>
$THINGS doctor
```

Output is a stable JSON envelope by default. Use `--plain` only for human inspection.

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

Task note updates need the Things URL-scheme auth token. The CLI looks for `THINGS3_AUTH_TOKEN` first, then simple `.env` files from:

1. `THINGS_CLIENT_ENV_FILE`
2. `THINGS3_ENV_FILE`
3. `$DOBBY_WORKSPACE/.env`
4. the current working directory `.env`
5. `/Users/dobby/GitHub/adi/.env`

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

For local intake queues, prefer a Things tag such as `devworker`, then let the caller interpret task notes:

```bash
things-client list --tag devworker --verbose
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
