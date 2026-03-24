---
name: ai-podcasting
description: Submit AI Podcasting episodes and update intro/title/thumbnail copy through AIP frontend API routes. Use when clients want agent-driven episode operations without using the GUI, including listing non-published episodes to get source_id, submitting a new episode, patching intro copy for an existing episode, or clarifying whether an ambiguous "submit" request means main episode submission vs intro update.
---

# AI Podcasting

Use this skill for client-facing, agent-driven episode operations in this repository.

## What This Skill Runs

Run the main CLI at `scripts/ai_podcasting_client.py` for episode operations:

1. `list-backlog-episodes`:
   Get non-published `TCR` episodes and return `source_id` values.
2. `submit-episode`:
   Create a new episode via `/api/episodes/submit`.
3. `update-intro-copy`:
   Patch intro/title/thumbnail/outro assets for an existing episode via `/api/episodes/{sourceId}/intro`.

This skill calls backend API routes directly. Do not automate the browser UI for these flows.

Use `scripts/aip_local_upload_helper.py` only when the user gives a local file path for a file-like
field. The helper uploads the file and returns a public URL for the main CLI to use. Keep this
implicit in chat unless the user asks.

## Quick Start

1. List backlog episodes to find the target ID:

```bash
python3 .agents/skills/ai-podcasting/scripts/ai_podcasting_client.py \
  --json list-backlog-episodes
```

2. Submit a new episode (creates a new episode; no `source_id` input needed):

```bash
python3 .agents/skills/ai-podcasting/scripts/ai_podcasting_client.py \
  --json submit-episode \
  --payload-file .agents/skills/ai-podcasting/references/submit-episode.example.json
```

3. Update intro copy for an existing episode (`source_id` required):

```bash
python3 .agents/skills/ai-podcasting/scripts/ai_podcasting_client.py \
  --json update-intro-copy \
  --source-id <EPISODE_SOURCE_ID> \
  --payload-file .agents/skills/ai-podcasting/references/update-intro-copy-tcr.example.json
```

4. Upload a local file and get a public URL:

```bash
python3 .agents/skills/ai-podcasting/scripts/aip_local_upload_helper.py \
  --json /absolute/path/to/file.png
```

## Interface Notes

- Fixed endpoint: `https://app.aipodcast.ing`
- Fixed show: `TCR`
- The CLI does not accept base-url overrides or env-based base URL changes.
- The CLI does not accept show selection; all submit/list operations are locked to `TCR`.
- Use `--dry-run` for request preview without state changes.
- JSON mode returns a stable envelope with:
  - `schema_version`
  - `command`
  - `status`
  - `data`
  - `error`
  - `meta`

## Required Vs Optional Inputs

1. `list-backlog-episodes`:
   Required: none.
   Optional: `--start-date`, `--end-date`, `--limit`.
2. `submit-episode`:
   Required: `--payload-file` with at least one main file link (`files.main.raw` or `fileUrl`).
   Show handling: always forced to `TCR` by the CLI.
   The main file link may be either:
   - a public HTTP/HTTPS URL
   - a local file path, which the helper uploads first
   Optional: any additional backend-supported episode fields. The client preserves richer payloads such as `deliverables.thumbnails.options`, `deliverables.thumbnails.video.variants`, and `files.episode_outro`.
3. `update-intro-copy`:
   Required (command): `--source-id`, `--payload-file`.
   The client supports the current app intro payload directly.
   For conversation-driven usage, prefer these user-facing fields:
   There are no required patch fields beyond `source_id`.
   Common patch fields: `recordingLink`, `title`, `videoThumbnails`, `thumbnailText`, `transcript`, `instructionsToEditor`, `audioThumbnailLink`, `outroMusicLink`.
   `videoThumbnails` may be either:
   - one public HTTP/HTTPS URL
   - a list of public HTTP/HTTPS URLs
   The client normalizes `videoThumbnails` into the app's thumbnail shape:
   - `deliverables.thumbnails.video.url` = first thumbnail URL
   - `deliverables.thumbnails.video.variants` = ordered list of all provided thumbnail URLs
   The client also accepts the full current app payload if the agent already has it.
   Local paths are allowed for file-like fields. The helper uploads them and the client uses the
   returned public URLs.

## Conversation Policy

When values are missing in chat context, follow this flow:

1. Before asking follow-up questions, scan the current chat thread and reuse any values the user already provided.
   Do not ask again for values that are already clear in context.
2. First disambiguate the operation when the user's wording does not make it clear whether they mean a new main episode submission or an intro update for an existing episode.
   Do not assume that "submit", "this episode", or similar phrasing means `submit-episode`.
   If the intent is ambiguous, ask exactly:
   "Do you want to:
   1. submit a new main episode file
   2. update intro/title/thumbnail assets for an existing episode

   Reply with 1 or 2."
   Only continue into submit or intro-specific prompts after the user picks one.
3. For submit flow, ask only for missing required submit values.
   Required submit value:
   1. main episode file link (`files.main.raw` or `fileUrl`) as either a public HTTP/HTTPS URL or a local file path.
   Optional submit values:
   1. showNotes
   2. assetUrls
   3. editorNotes
   4. title
   5. thumbnailText
   6. priority
   7. scheduledDate
   8. needsGuestReview
   9. guests
4. For intro updates without `source_id`, run `list-backlog-episodes` first.
5. Ask the user which episode to target using an enumerated list, not raw ids only.
   Render exactly:
   `1. <short title> — <source_id>`
   `2. <short title> — <source_id>`
   `...`
   Then ask: `Reply with the episode number or source_id.`
   If the user replies with a number (for example `4`), map that number to the corresponding `source_id` and continue without asking them to repeat the full id.
6. Ask only for the fields the user wants to change.
7. Enforce a strict two-step prompt sequence for intro updates:
   - Step 1 message: episode list + `Reply with the episode number or source_id.`
   - Step 2 message (only after episode is selected): required/optional field collection.
8. For intro updates, use one prompt shape by default:
   "Episode selected: <source_id>.
   Provide any fields you want to update.

   Common fields:
   1. recordingLink
   2. title
   3. videoThumbnails (give one URL or multiple URLs)
   4. thumbnailText
   5. transcript
   6. instructionsToEditor
   7. audioThumbnailLink
   8. outroMusicLink

   You only need to send the fields you want to change, and I will patch just those."
   Never ask the user to pick an episode id again after step 1 is completed.
9. If optional values are unclear, omit them instead of guessing.
10. Use `--dry-run` if the user wants confirmation before the write call.
11. For file-type fields (`recordingLink`, `videoThumbnails`, `audioThumbnailLink`, `outroMusicLink`, and submit main file link):
   - The client accepts either public HTTP/HTTPS URLs or local file paths.
   - If the user provides a local file path, run `scripts/aip_local_upload_helper.py` first and use its returned public URL.
   - Do not pass unresolved local filesystem paths to the episode API payload.

## Resources

- `scripts/ai_podcasting_client.py`: Single client interface with subcommands.
- `scripts/aip_local_upload_helper.py`: Upload helper for local file paths; returns public URLs.
- `references/submit-episode.example.json`: Example payload for submit flow.
- `references/update-intro-copy.example.json`: Example payload for intro/copy patch flow.
- `references/update-intro-copy-tcr.example.json`: Example payload for TCR-style final title/thumbnail updates.
