---
name: things-client
description: Use when an agent needs to read, inspect, or update Things 3 tasks through a reusable local CLI. Applies to Things 3 task discovery, tag-based queues, task note write-back, and health checks across repos without using Dobby-specific memory or routing policy.
---

# Things Client

## Overview

This skill provides a reusable Things 3 client for agents. It is the generic task-access layer; personal routing policy belongs in Dobby/Adi, and engineering orchestration belongs in DevWorker.

## CLI

Use the bundled CLI directly:

```bash
$HOME/.agents/skills-source/owned/things-client/scripts/things-client list --tag devworker
$HOME/.agents/skills-source/owned/things-client/scripts/things-client inspect <task-id-or-title>
$HOME/.agents/skills-source/owned/things-client/scripts/things-client edit <task-id-or-title> --append-notes "..."
$HOME/.agents/skills-source/owned/things-client/scripts/things-client complete <task-id-or-title>
$HOME/.agents/skills-source/owned/things-client/scripts/things-client doctor
```

Output is a stable JSON envelope by default. Use `--plain` only for human inspection.

## Boundaries

- Reads auto-discover the local Things SQLite database and open it read-only. If SQLite is unavailable, read commands fall back to bounded JXA against the running Things app.
- Writes use supported Things URL-scheme operations.
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
- `DOBBY_THINGS_SQLITE_PATH`

Explicit paths are overrides. If an explicit path is missing or broken, the command fails instead of silently using another database. Without an explicit path, read commands use auto-discovered read-only SQLite first and bounded JXA as a fallback.

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
