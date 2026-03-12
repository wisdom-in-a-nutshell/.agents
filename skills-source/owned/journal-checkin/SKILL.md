---
name: journal-checkin
description: Run the personal journaling and check-in workflow for profile workspaces in `codexclaw-workspaces` and store results in a structured form under the active profile's `journal/entries/` tree. Use when Adi or Angie says they want to journal, wants to check in, sends a morning/evening/night reflection, sends a voice note or speech-to-text journal dump, asks to save a reflection, or when Codex needs to read/query recent journal entries for continuity or synthesis.
---

# Journal Check-In

Use this skill inside the `codexclaw-workspaces` repo for profile workspaces such as `adi/` and `angie/`.

This skill has two jobs:

- run a short, mode-specific check-in with the active profile user
- save the result as clean JSON in the journal tree so later synthesis and querying are easy

Read [checkin-modes.md](./references/checkin-modes.md) for the exact prompt shapes, required fields, schemas, and file naming rules.

Use [write_journal_entry.py](./scripts/write_journal_entry.py) to write or update structured entries instead of hand-editing JSON.

## Workflow

1. Determine the mode.
2. Ask only the prompt set for that mode.
3. If required information is missing, nudge until the mode is complete.
4. Normalize the content into structured JSON.
5. Identify the active profile root before writing:
   - use the current profile directory if the session is already inside `adi/` or `angie/`
   - if the session is at repo root or otherwise ambiguous, choose the intended profile explicitly and pass `--profile-root`
6. Write the entry with the helper script.
6. Confirm what was saved and where.

## Mode Selection

- Use the explicitly named mode if the user gives one.
- If he just says "journal", "check in", or similar, infer from local Berlin time:
  - before `12:00`: `morning`
  - `12:00` to `16:59`: `general`
  - `17:00` to `20:59`: `evening`
  - `21:00` or later: `night`
- State the inferred mode briefly when you had to infer it.

## Prompting Rules

- Keep prompts short.
- Prefer one compact block over a long reflective questionnaire.
- Match the style of the active profile's `AGENTS.md` when prompting.
- If the user sends a voice note or speech-to-text dump, extract what you can first, then ask only for what is missing.
- When information is incomplete, ask for the missing fields directly instead of re-running the whole check-in.
- Treat `morning`, `evening`, and `night` as complete check-ins by default.
- Treat `general` as a flexible capture mode.

## Storage Rules

- Store entries under `<profile>/journal/entries/YYYY-MM-DD/`.
- Use one stable file per day for:
  - `morning.json`
  - `evening.json`
  - `night.json`
- Use timestamped files for flexible captures:
  - `general-HHMMSS.json`
- Keep `raw_input` when the source text was dictated, messy, or useful for later reinterpretation.
- Preserve continuity by glancing at nearby entries when the user asks follow-up questions or wants synthesis.

## Writing

Use the helper script like this:

```bash
python3 .agents/skills/journal-checkin/scripts/write_journal_entry.py \
  --kind morning \
  --date 2026-03-12 \
  --profile-root /Users/dobby/GitHub/codexclaw-workspaces/adi \
  --source "chat:text" \
  --payload-file /tmp/morning.json
```

The script can auto-detect the profile root when you are already inside `adi/` or `angie/`. Use `--profile-root` whenever the current working directory is ambiguous.

Use `--allow-partial` only when the user explicitly wants a rough capture saved even though the required fields are not complete yet.

## Querying And Synthesis

- Use this skill when later work needs recent journal context.
- Read only the relevant recent entries, not the whole journal tree.
- Use monthly files in `<profile>/journal/monthly/` for broader synthesis when they exist.

## Resources

- [checkin-modes.md](./references/checkin-modes.md)
- [write_journal_entry.py](./scripts/write_journal_entry.py)
