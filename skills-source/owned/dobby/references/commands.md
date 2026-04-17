# Dobby commands — CLI first, direct-ops fallback

The CLI (`scripts/dobby/dobby`) is the preferred path. Use `Edit`/`Write` tools only when the CLI can't do what's needed.

## Boot

Pull full context at session start.

```bash
scripts/dobby/dobby memory boot
```
Returns: `profile.md` + `now.md` + `becoming.md` content + lazy area manifest (file names, sizes, mtimes — not content).

Add `--json` for structured output.

## Read a specific file

```bash
dobby memory read --section profile
dobby memory read --section now
dobby memory read --section becoming
dobby memory read --section area.<name>              # concatenates all .md in that area
dobby memory read --section area.<name>.<file>       # single file (without .md)
```

Fallback (when you only need one file and don't want CLI overhead):
```
Read memory/profile.md
```

## Append to a file (CLI-preferred)

The CLI auto-stamps a timestamped header — ideal for log-style appends.

```bash
echo "- 2026-04-17 — event" | \
  dobby memory write --section area.<name>.log --message "short label"
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
dobby tasks today
dobby tasks inbox
dobby tasks overdue

dobby tasks add "Task title" --when today --area <Area>
dobby tasks add "Task title" --when "next monday" --area <Area> \
  --checklist "step one, step two, step three"

dobby tasks done <id-prefix>
dobby tasks cancel <id-prefix>
dobby tasks delete <id-prefix>

dobby tasks doctor                    # 5-point health check
```

`--when` accepts natural-language dates: `today`, `tomorrow`, `next monday`, `in 3 days`, specific dates.
`--area` is case-sensitive and must match an existing Things 3 Area.

## Diff and history

```bash
dobby memory diff --since "24 hours ago"
dobby memory diff --since "1 week ago"
```

Wraps `git log -p memory/` with date filtering.

## JSON mode

Every CLI command supports `--json` for a stable envelope:
```bash
dobby memory boot --json
dobby tasks today --json
dobby tasks doctor --json
```

See `docs/references/dobby-cli.md` for the full envelope schema.

## Typical session-start pattern

```bash
dobby memory boot                     # full context
dobby tasks today                     # live task state
dobby tasks overdue
dobby tasks inbox
# then respond with counts surfaced: "Today N, overdue M, inbox K (notes)"
```

## Permissions reminder

Standing permission: write to memory files without asking. Note a one-liner in your response so the user sees what changed. Do NOT post publicly, send messages, or make irreversible external changes without confirmation.
