---
name: ai-podcasting
description: Submit AI Podcasting episodes and update intro/title/thumbnail copy through AIP frontend API routes. Use when clients want agent-driven episode operations without using the GUI, including listing non-published episodes to get source_id, submitting a new episode, or patching intro copy for an existing episode.
---

# AI Podcasting

Use this skill for client-facing, agent-driven episode operations in this repository.

## What This Skill Runs

Run a single CLI with three commands from `scripts/ai_podcasting_client.py`:

1. `list-backlog-episodes`:
   Get non-published `TCR` episodes and return `source_id` values.
2. `submit-episode`:
   Create a new episode via `/api/episodes/submit`.
3. `update-intro-copy`:
   Update intro/title/thumbnail/editor copy for an existing episode via `/api/episodes/{sourceId}/intro`.

This skill calls backend API routes directly. Do not automate the browser UI for these flows.

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
  --payload-file .agents/skills/ai-podcasting/references/update-intro-copy.example.json
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
   Required: `--payload-file` with at least one main file link (`files.main.raw` or `fileUrl`) as a public HTTP/HTTPS URL.
   Show handling: always forced to `TCR` by the CLI.
   Optional: show notes, asset URLs, editor notes, title, thumbnail text, priority, scheduling, guest review fields.
3. `update-intro-copy`:
   Required (command): `--source-id`, `--payload-file`.
   Required individual payload fields (user-facing): `recordingLink`, `title`, `thumbnailText`.
   Optional individual payload fields (user-facing): `transcript`, `instructionsToEditor`, `videoThumbnailLink`, `audioThumbnailLink`, `outroMusicLink`.
   API mapping: `recordingLink -> introFile`, `transcript -> introTranscript`, `instructionsToEditor -> editorInstructions`.
   TCR media mapping: `videoThumbnailLink -> deliverables.thumbnails.video.url`, `audioThumbnailLink -> deliverables.thumbnails.audio.url`, `outroMusicLink -> files.episode_outro.edited`.

## Conversation Policy

When values are missing in chat context, follow this flow:

1. Before asking follow-up questions, scan the current chat thread and reuse any values the user already provided.
   Do not ask again for values that are already clear in context.
2. For submit flow, ask only for missing required submit values.
   Required submit value:
   1. main episode file link (`files.main.raw` or `fileUrl`) as a public HTTP/HTTPS URL.
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
3. For intro updates without `source_id`, run `list-backlog-episodes` first.
4. Ask the user which episode to target using an enumerated list, not raw ids only.
   Render exactly:
   `1. <short title> — <source_id>`
   `2. <short title> — <source_id>`
   `...`
   Then ask: `Reply with the episode number or source_id.`
   If the user replies with a number (for example `4`), map that number to the corresponding `source_id` and continue without asking them to repeat the full id.
5. Ask only for missing required values.
6. Enforce a strict two-step prompt sequence:
   - Step 1 message: episode list + `Reply with the episode number or source_id.`
   - Step 2 message (only after episode is selected): required/optional field collection.
7. For intro updates, explicitly ask with required/optional labels:
   - Required: pick episode (`source_id`), `recordingLink`, `title`, `thumbnailText`.
   - Optional: `transcript`, `instructionsToEditor`, `videoThumbnailLink`, `audioThumbnailLink`, `outroMusicLink`.
   Use this exact prompt shape:
   "Episode selected: <source_id>.
   Mandatory fields:
   1. recordingLink
   2. title
   3. thumbnailText

   Optional fields:
   1. transcript
   2. instructionsToEditor
   3. videoThumbnailLink
   4. audioThumbnailLink
   5. outroMusicLink

   Provide values in any format you want, and I will set them in the episode."
   Never ask the user to pick an episode id again after step 1 is completed.
8. If optional values are unclear, omit them instead of guessing.
9. Use `--dry-run` if the user wants confirmation before the write call.
10. For file-type fields (`recordingLink`, `videoThumbnailLink`, `audioThumbnailLink`, `outroMusicLink`, and submit main file link):
   - The current client expects publicly reachable HTTP/HTTPS URLs.
   - If the user provides a local file path, ask them to upload it to cloud storage first and share a public link.
   - Do not pass local filesystem paths to the API payload.

## Resources

- `scripts/ai_podcasting_client.py`: Single client interface with subcommands.
- `references/submit-episode.example.json`: Example payload for submit flow.
- `references/update-intro-copy.example.json`: Example payload for intro/copy patch flow.
- `references/update-intro-copy-tcr.example.json`: Example payload for TCR-style final title/thumbnail updates.
