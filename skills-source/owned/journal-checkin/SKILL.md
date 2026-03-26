---
name: journal-checkin
description: Run a structured journaling and check-in workflow and store results under `journal/entries/`. Use when the user wants to journal, wants to check in, sends a morning/evening/night reflection, sends a voice note or speech-to-text journal dump, asks to save a reflection, or when Codex needs to read/query recent journal entries for continuity or synthesis.
---

# Journal Check-In

This skill has two jobs:

- run a short, mode-specific check-in
- save the result in a durable format in the journal tree: JSON for structured morning/night check-ins, Markdown for flexible general journaling

Read only the mode file you need:

- [morning.md](./references/morning.md)
- [night.md](./references/night.md)
- [general.md](./references/general.md)

Use [write_journal_entry.py](./scripts/write_journal_entry.py) to write or update structured entries instead of hand-editing JSON.

## Workflow

1. Determine the mode.
2. Ask only the prompt set for that mode.
3. If required information is missing, nudge until the mode is complete.
4. If the user gives a rough block of text in their own format, extract what you can first instead of forcing your prompt order.
5. Normalize the content into the right storage shape for the mode.
6. Write the entry with the helper script.
7. Confirm what was saved and where.

## Mode Selection

- Use the explicitly named mode if the user gives one.
- If they just say "journal", "check in", or similar, infer from local time:
  - before `12:00`: `morning`
  - `12:00` to `16:59`: `general`
  - `17:00` or later: `night`
- State the inferred mode briefly when you had to infer it.

## Prompting Rules

- Keep prompts short.
- Prefer one compact block over a long reflective questionnaire.
- If the user sends a voice note or speech-to-text dump, extract what you can first, then ask only for what is missing.
- If the user sends text in a distinct existing format, preserve that intent and map it into the structured schema.
- State notes are optional. Infer them from raw text only when they are clear; otherwise omit them.
- When information is incomplete, ask for the missing fields directly instead of re-running the whole check-in.
- Treat `morning` and `night` as complete check-ins by default.
- Treat `general` as a flexible capture mode.

## Storage Rules

- Store entries under `journal/entries/YYYY-MM-DD/` relative to the active workspace root.
- Use one stable file per day for:
  - `morning.json`
  - `night.json`
  - `general.md`
- Append multiple flexible journal captures for the same day into `general.md` instead of creating fragmented timestamped JSON files.
- Keep `raw_input` when the source text was dictated, messy, or useful for later reinterpretation.
- Preserve continuity by glancing at nearby entries when the user asks follow-up questions or wants synthesis.

## Writing

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

- Use this skill when later work needs recent journal context.
- Read only the relevant recent entries, not the whole journal tree.
- Use monthly files in `journal/monthly/` for broader synthesis when they exist.

## Resources

- [morning.md](./references/morning.md)
- [night.md](./references/night.md)
- [general.md](./references/general.md)
- [write_journal_entry.py](./scripts/write_journal_entry.py)
