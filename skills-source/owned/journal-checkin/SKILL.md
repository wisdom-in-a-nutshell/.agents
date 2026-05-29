---
name: journal-checkin
description: Run a structured journaling and check-in workflow and store results under `journal/daily/`. Use when the user wants to journal, wants to check in, sends a morning/evening/night reflection, sends a voice note or speech-to-text journal dump, asks to save a reflection, or when the agent needs to read/query recent journal entries for continuity or synthesis.
---

# Journal Check-In

This skill has two jobs:

- **Write**: run a short, mode-specific check-in and save it
- **Read**: retrieve and format past entries for agent consumption or synthesis

## Data Layout

Entries live under `journal/daily/YYYY-MM-DD/` relative to the workspace root.

Each day directory can contain:

| File | Format | Contents |
|---|---|---|
| `morning.json` | JSON object | Structured morning check-in: sleep, energy, mood (each with `score_10` and optional `notes`), `grateful` (array), `one_thing_that_matters`, `show_up_as`, `raw_input` |
| `night.json` | JSON object | Structured night check-in: mood, energy (each with `score_10` and optional `notes`), `went_well`, `could_have_been_improved`, `actions_to_improve_tomorrow`, `raw_input` |
| `general.md` | Markdown | Timestamped freeform journal sections, each with summary, tags, and optional mood/energy/raw-input |

All JSON entries also carry metadata: `agent`, `date`, `kind`, `tz`, `captured_at`, `source`.

Monthly synthesis files may exist in `journal/monthly/`.

## Writing

### Mode references

Read only the mode file you need:

- [morning.md](./references/morning.md)
- [night.md](./references/night.md)
- [general.md](./references/general.md)

### Workflow

1. Determine the mode.
2. Ask only the prompt set for that mode.
3. If required information is missing, nudge until the mode is complete.
4. If the user gives a rough block of text in their own format, extract what you can first instead of forcing your prompt order.
5. Normalize the content into the right storage shape for the mode.
6. Write the entry with the helper script.
7. Confirm what was saved and where.

### Mode Selection

- Use the explicitly named mode if the user gives one.
- If they just say "journal", "check in", or similar, infer from local time:
  - before `12:00`: `morning`
  - `12:00` to `16:59`: `general`
  - `17:00` or later: `night`
- State the inferred mode briefly when you had to infer it.

### Prompting Rules

- Keep prompts short.
- Prefer one compact block over a long reflective questionnaire.
- If the user sends a voice note or speech-to-text dump, extract what you can first, then ask only for what is missing.
- If the user sends text in a distinct existing format, preserve that intent and map it into the structured schema.
- State notes are optional. Infer them from raw text only when they are clear; otherwise omit them.
- When information is incomplete, ask for the missing fields directly instead of re-running the whole check-in.
- Treat `morning` and `night` as complete check-ins by default.
- Treat `general` as a flexible capture mode.

### Storage Rules

- Store entries under `journal/daily/YYYY-MM-DD/` relative to the active workspace root.
- Use one stable file per day for:
  - `morning.json`
  - `night.json`
  - `general.md`
- Append multiple flexible journal captures for the same day into `general.md` instead of creating fragmented timestamped JSON files.
- Keep `raw_input` when the source text was dictated, messy, or useful for later reinterpretation.
- Preserve continuity by glancing at nearby entries when the user asks follow-up questions or wants synthesis.

### Write script

Use the helper script like this:

```bash
python3 .agents/skills/journal-checkin/scripts/write_journal_entry.py \
  --kind morning \
  --date 2026-03-12 \
  --source "chat:text" \
  --payload-file /tmp/morning.json
```

By default the script writes relative to the current workspace root. Only pass `--workspace-root` when you intentionally want to write somewhere else.

Use `--allow-partial` only when the user explicitly wants a rough capture saved even though the required fields are not complete yet.

## Querying And Synthesis

Use the read script to retrieve past entries. It outputs **markdown by default** (best for agent context windows) or structured JSON.

### Read script

```bash
# Last 7 days, all kinds, markdown output
python3 .agents/skills/journal-checkin/scripts/read_journal_entries.py --last 7

# Specific date range, only morning entries, as JSON
python3 .agents/skills/journal-checkin/scripts/read_journal_entries.py \
  --from 2026-03-01 --to 2026-03-15 --kind morning --format json

# Last 3 days, night entries only
python3 .agents/skills/journal-checkin/scripts/read_journal_entries.py --last 3 --kind night
```

**Flags:**

| Flag | Description |
|---|---|
| `--from YYYY-MM-DD` | Start date (inclusive) |
| `--to YYYY-MM-DD` | End date (inclusive), defaults to today |
| `--last N` | Shorthand for "last N days" (alternative to --from/--to) |
| `--kind morning\|night\|general\|all` | Filter by entry type, default `all` |
| `--format markdown\|json` | Output format, default `markdown` |
| `--workspace-root` | Optional, auto-detects like the write script |

**Exit codes:** 0 = success, 1 = error, 2 = no entries found.

**Output contracts:**
- `--format markdown`: readable markdown to stdout with dates as `# Journal: YYYY-MM-DD` headers, entry types as `##` sub-headers, scores and fields as list items.
- `--format json`: a JSON array of entry objects to stdout, each with `date`, `kind`, and the full entry data.
- Errors go to stderr; stdout stays clean on failure.

### When to use

- Use this skill when later work needs recent journal context.
- Prefer the read script over manual file reading — it handles format normalization and date filtering.
- Read only the relevant recent entries, not the whole journal tree.
- Use monthly files in `journal/monthly/` for broader synthesis when they exist.

## Resources

- [morning.md](./references/morning.md)
- [night.md](./references/night.md)
- [general.md](./references/general.md)
- [write_journal_entry.py](./scripts/write_journal_entry.py)
- [read_journal_entries.py](./scripts/read_journal_entries.py)
- [validate](./scripts/validate) — validates structured `morning.json` and `night.json` entries for workspace checks
