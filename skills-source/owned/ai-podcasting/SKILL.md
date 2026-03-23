---
name: ai-podcasting
description: Submit AI Podcasting episodes and update intro/title/thumbnail copy through AIP frontend API routes. Use when clients want agent-driven episode operations without using the GUI, including listing non-published episodes to get source_id, submitting a new episode, patching intro copy for an existing episode, or clarifying whether an ambiguous "submit" request means main episode submission vs intro update.
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
   Patch intro/title/thumbnail/outro assets for an existing episode via `/api/episodes/{sourceId}/intro`.

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
  --payload-file .agents/skills/ai-podcasting/references/update-intro-copy-tcr.example.json
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
   Optional: any additional backend-supported episode fields. The client preserves richer payloads such as `deliverables.thumbnails.options`, `deliverables.thumbnails.video.variants`, and `files.episode_outro`.
3. `update-intro-copy`:
   Required (command): `--source-id`, `--payload-file`.
   Supported payload modes:
   1. Legacy alias mode:
      Required user-facing fields: `recordingLink`, `title`, `thumbnailText`.
      Optional user-facing fields: `transcript`, `instructionsToEditor`, `videoThumbnailLink`, `audioThumbnailLink`, `outroMusicLink`.
      API mapping: `recordingLink -> introFile`, `transcript -> introTranscript`, `instructionsToEditor -> editorInstructions`.
      TCR media mapping: `videoThumbnailLink -> deliverables.thumbnails.video.url`, `audioThumbnailLink -> deliverables.thumbnails.audio.url`, `outroMusicLink -> files.episode_outro.edited`.
   2. Raw backend patch mode:
      Pass backend-shaped fields directly when updating multiple thumbnails or richer media payloads.
      Prefer this mode for `deliverables.thumbnails.options`, `deliverables.thumbnails.video.variants`, `files.episode_outro`, or any nested patch the frontend already supports.

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
4. For intro updates without `source_id`, run `list-backlog-episodes` first.
5. Ask the user which episode to target using an enumerated list, not raw ids only.
   Render exactly:
   `1. <short title> — <source_id>`
   `2. <short title> — <source_id>`
   `...`
   Then ask: `Reply with the episode number or source_id.`
   If the user replies with a number (for example `4`), map that number to the corresponding `source_id` and continue without asking them to repeat the full id.
6. Ask only for missing required values.
7. Enforce a strict two-step prompt sequence for intro updates:
   - Step 1 message: episode list + `Reply with the episode number or source_id.`
   - Step 2 message (only after episode is selected): required/optional field collection.
8. For intro updates, choose the prompt shape that matches the user intent:
   - Alias mode:
     Use when the user is giving simple copy fields or single thumbnail URLs.
     Prompt:
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
   - Raw patch mode:
     Use when the user needs multiple thumbnails, thumbnail variants/options, or a richer `files` / `deliverables` patch.
     Prompt:
     "Episode selected: <source_id>.
     Provide the intro patch payload in any format you want.
     Prefer raw backend fields for multi-thumbnail or nested media updates, for example:
     - deliverables.thumbnails.options
     - deliverables.thumbnails.video.variants
     - files.episode_outro
     - introFile / introTranscript / editorInstructions

     I will convert it into the API payload."
   Never ask the user to pick an episode id again after step 1 is completed.
9. If optional values are unclear, omit them instead of guessing.
10. Use `--dry-run` if the user wants confirmation before the write call.
11. For file-type fields (`recordingLink`, `videoThumbnailLink`, `audioThumbnailLink`, `outroMusicLink`, raw thumbnail URLs, outro URLs, and submit main file link):
   - The current client expects publicly reachable HTTP/HTTPS URLs.
   - If the user provides a local file path, ask them to upload it to cloud storage first and share a public link.
   - Do not pass local filesystem paths to the API payload.

## Resources

- `scripts/ai_podcasting_client.py`: Single client interface with subcommands.
- `references/submit-episode.example.json`: Example payload for submit flow.
- `references/update-intro-copy.example.json`: Example payload for intro/copy patch flow.
- `references/update-intro-copy-tcr.example.json`: Example payload for TCR-style final title/thumbnail updates.
