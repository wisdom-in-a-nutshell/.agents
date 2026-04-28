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
$HOME/.agents/skills-source/owned/things-client/scripts/things-client doctor
```

Output is a stable JSON envelope by default. Use `--plain` only for human inspection.

## Boundaries

- Reads use the local Things SQLite database in read-only mode.
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

## Common Patterns

For local intake queues, prefer a Things tag such as `devworker`, then let the caller interpret task notes:

```bash
things-client list --tag devworker --verbose
```

When a task has been promoted to a durable tracker item, append the URL to the notes:

```bash
things-client edit <task-id> --append-notes "GitHub: https://github.com/owner/repo/issues/123"
```

If a command fails, inspect the JSON `error.code` and `error.hint`; do not scrape prose output.
