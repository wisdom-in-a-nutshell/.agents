---
name: ai-podcasting
description: Submit AI Podcasting episodes and update intro/title/thumbnail copy through AIP frontend API routes. Use when clients want agent-driven episode operations without using the GUI, including listing episodes with rich metadata and published-state filters, submitting a new episode, patching intro copy for an existing episode, or clarifying whether an ambiguous "submit" request means main episode submission vs intro update.
---

# AI Podcasting

Use this skill for client-facing, agent-driven episode operations in this repository.

## What This Skill Runs

Run the main CLI at `scripts/ai_podcasting_client.py` for episode operations:

1. `list-episodes`:
   List `TCR` episodes with rich per-episode summaries and filters for `published`, `unpublished`,
   or `all`.
2. `submit-episode`:
   Create a new episode via `/api/episodes/submit`.
3. `update-intro-copy`:
   Patch intro/title/thumbnail/outro assets for an existing unpublished episode via
   `/api/episodes/{sourceId}/intro`.

This skill calls the AIP frontend API routes at `https://app.aipodcast.ing/api/...`, which proxy the
upstream episode APIs. Do not automate the browser UI for these flows.
The frontend API requires bearer auth. The scripts read the token from
`~/.secrets/aipodcasting/env` by default, or from `AIPODCASTING_API_KEY_FILE` when that file
path is overridden. Environment fallbacks (`AIPODCASTING_API_KEY` or the first value in
`AIPODCASTING_API_KEYS`) are supported for deployed/runtime contexts, but do not pass secrets on
command lines.

## Auth Setup

Never paste the actual API key into this skill, a payload JSON file, a command argument, or chat.
Store it in the user's local environment before running the client.

Recommended local setup:

```bash
mkdir -p ~/.secrets/aipodcasting
printf 'AIPODCASTING_API_KEY=<key-from-Adi>\n' > ~/.secrets/aipodcasting/env
chmod 600 ~/.secrets/aipodcasting/env
```

Alternative for one shell session:

```bash
export AIPODCASTING_API_KEY=<key-from-Adi>
```

If the secret file lives somewhere else, set `AIPODCASTING_API_KEY_FILE` to that absolute path.
For direct raw API usage, send the same key as `Authorization: Bearer <key-from-Adi>`.

Use `scripts/aip_local_upload_helper.py` only when the user gives a local file path for a file-like
field and no source URL is available. For TCR main episode submissions, prefer a Descript web URL
copied from Descript for the main source when one exists; do not export or upload an MP4 just to
create a source link. The helper uploads the file and returns a public URL for the main CLI to use.
Keep this implicit in chat unless the user asks.

## Media Source Rule For TCR

When a Descript project/composition/source URL exists, use that URL as the source. Do not export,
upload, or submit an MP4 just to create a source file.

Use these shapes:

```json
{
  "files": {
    "main": {
      "raw": "https://web.descript.com/01234567-89ab-4cde-8f01-23456789abcd"
    }
  }
}
```

For intro updates, use the Descript URL as `recordingLink` or `introFile`:

```json
{
  "recordingLink": "https://web.descript.com/01234567-89ab-4cde-8f01-23456789abcd"
}
```

`recordingLink` is the friendly input name for the intro source; the client normalizes it to
`introFile`, and the backend stores it as `files.intro.raw`.

MP4 URLs and local MP4 paths are fallback inputs only. If both a Descript URL and an MP4 are known,
submit the Descript URL and omit the MP4.

All script and reference paths in this skill are relative to the skill directory itself, not the
repository root. Do not run `scripts/...` from the repo root unless you first `cd` into this skill
directory. When in doubt, use the absolute skill path shown by the harness.

## Quick Start

1. List episodes to find the target ID:

```bash
python3 scripts/ai_podcasting_client.py \
  --json list-episodes
```

To include the sanitized upstream episode payload under each item:

```bash
python3 scripts/ai_podcasting_client.py \
  --json list-episodes \
  --publication-state published \
  --include-raw
```

To narrow to unpublished episodes in a date range:

```bash
python3 scripts/ai_podcasting_client.py \
  --json list-episodes \
  --publication-state unpublished \
  --start-date 2026-01-01 \
  --end-date 2026-01-31
```

2. Submit a new episode (creates a new episode; no `source_id` input needed):

```bash
python3 scripts/ai_podcasting_client.py \
  --json submit-episode \
  --payload-file references/submit-episode.example.json
```

3. Update intro copy for an existing episode (`source_id` required):

```bash
python3 scripts/ai_podcasting_client.py \
  --json update-intro-copy \
  --source-id <EPISODE_SOURCE_ID> \
  --payload-file references/update-intro-copy-tcr.example.json
```

4. Upload a local file and get a public URL:

```bash
python3 scripts/aip_local_upload_helper.py \
  --json /absolute/path/to/file.png
```

## Interface Notes

- Fixed endpoint: `https://app.aipodcast.ing`
- Fixed show: `TCR`
- Auth: bearer token from `~/.secrets/aipodcasting/env` or `AIPODCASTING_API_KEY_FILE`
- The CLI does not accept base-url overrides or env-based base URL changes.
- The CLI does not accept show selection; all submit/list operations are locked to `TCR`.
- JSON is the default output contract. Use `--plain` or `--human` only for operator inspection.
- `list-episodes` returns a rich summary by default in JSON mode. Each item now includes
  fields such as `thumbnailText`, publishing metadata, preview text for long fields, normalized
  file links, and other lightweight episode context.
- `list-episodes` defaults to `--publication-state all`.
- `list-episodes` supports `--publication-state all|published|unpublished`, plus optional
  `--start-date` and `--end-date` filters.
- Results are sorted newest-first before `--limit` is applied, so `--limit 5` returns the latest
  five matching episodes.
- Use `--include-raw` when the agent needs the sanitized upstream episode object in addition to the
  default summary.
- JSON mode returns a stable envelope with:
  - `schema_version`
  - `command`
  - `status`
  - `data`
  - `error`
  - `meta`

## Required Vs Optional Inputs

1. `list-episodes`:
   Required: none.
   Optional: `--publication-state`, `--start-date`, `--end-date`, `--limit`, `--include-raw`.
   `--publication-state` choices:
   - `all` (default)
   - `published`
   - `unpublished`
   Default JSON output includes a rich per-episode summary with fields such as:
   - `source_id`, `title`, `show`, `status`, `thumbnailText`
   - `created_at`, `updated_at`, publishing metadata, and guest-review flags
   - preview text plus lengths for long copy fields like show notes or editor notes
   - normalized file links, artwork links, deliverable links, processed-asset links, ads, and
     other lightweight metadata when present
   Items are sorted newest-first before `limit` is applied.
   The `data` payload also echoes the applied `filters` object and `matched_count`.
   With `--include-raw`, each item also includes `raw_episode` containing the sanitized upstream
   payload.
2. `submit-episode`:
   Required: `--payload-file` with at least one main episode source link.
   Show handling: always forced to `TCR` by the CLI.
   The main source link may be either:
   - a public HTTP/HTTPS URL
   - a local file path, which the helper uploads first
   Prefer a Descript web URL in `files.main.raw` when a Descript project/composition/source is
   available. The app accepts MP4 URLs and local MP4 paths, but the CLI will warn because those are
   fallback inputs for TCR, not the preferred source. If both a Descript web URL and an exported
   MP4 are known, put the Descript web URL in `files.main.raw` and omit the MP4. Do not require a
   specific Descript path shape; use the Descript web URL the user or browser provides.
   TCR main episode submissions reject `.mp3` main-source inputs. Use the original recording,
   session, or video source link instead, such as Riverside, YouTube, or a direct non-MP3 media
   URL. This is not a Riverside-only allowlist.
   For plain-English payloads, the CLI accepts `mainEpisodeFile` and normalizes it to the backend
   submit shape automatically.
   `assetUrls` may also be public URLs or local file paths; local paths are uploaded first.
   Optional: any additional backend-supported episode fields. Use `customNewsletterDraftUrl` for
   a client-provided Ghost newsletter draft, preview, editor, or slug URL. The client preserves
   richer payloads such as `deliverables.thumbnails.options`,
   `deliverables.thumbnails.video.variants`, and `files.episode_outro`.
3. `update-intro-copy`:
   Required (command): `--source-id`, `--payload-file`.
   Intended target: an existing unpublished episode.
   The client supports the current app intro payload directly.
   For conversation-driven usage, prefer these user-facing fields:
   There are no required patch fields beyond `source_id`.
   Common patch fields: `recordingLink`, `title`, `videoThumbnails`, `thumbnailText`,
   `transcript`, `instructionsToEditor`, `customNewsletterDraftUrl`, `audioThumbnailLink`,
   `outroMusicLink`.
   For TCR intro source updates, prefer a Descript web URL in `recordingLink`/`introFile` when one
   exists. Do not export, upload, or submit an MP4 for the intro source when a Descript URL is
   available.
   `customNewsletterDraftUrl` stores a client-provided Ghost newsletter draft link under episode
   submission metadata. It does not publish or replace the generated newsletter by itself.
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
   1. submit a new main episode source
   2. update intro/title/thumbnail assets for an existing episode

   Reply with 1 or 2."
   Only continue into submit or intro-specific prompts after the user picks one.
3. For submit flow, ask for the missing required submit value, but in that same first reply also
   surface the common optional fields the user may want to set up front.
   Required submit value:
   1. main episode source link as either a public HTTP/HTTPS URL or a local file path.
   Prefer a Descript web URL for TCR when available. MP4 URLs and local MP4 paths are accepted but
   should be described as fallback inputs, not the preferred source. Do not export, upload, or
   submit an MP4 when a Descript web URL is available.
   Common optional submit values to mention in the same first prompt:
   1. title
   2. showNotes
   3. assetUrls
   4. editorNotes
   5. thumbnailText
   6. priority
   7. scheduledDate
   8. needsGuestReview
   9. guests
   10. customNewsletterDraftUrl
4. Use this default submit prompt shape when the source is missing:
   "Send the main episode source as a Descript web URL if you have one. If not, send another
   public HTTP/HTTPS source URL or a local absolute file path.

   You can also include any of these optional fields now if you want them set on creation:
   1. title
   2. showNotes
   3. assetUrls
   4. editorNotes
   5. thumbnailText
   6. priority
   7. scheduledDate
   8. needsGuestReview
   9. guests
   10. customNewsletterDraftUrl

   If you send them together, I can submit the episode in one pass."
5. Intro updates are only for unpublished episodes.
6. For intro updates without `source_id`, immediately run `list-episodes` with
   `--publication-state unpublished`.
   If the user already provided `startDate` and `endDate`, include them.
   Do not ask the user for publication scope first.
7. Ask the user which episode to target using an enumerated list, not raw ids only.
   Render exactly:
   `1. <short title> — <source_id>`
   `2. <short title> — <source_id>`
   `...`
   Then ask: `Reply with the episode number or source_id.`
   If the user replies with a number (for example `4`), map that number to the corresponding `source_id` and continue without asking them to repeat the full id.
8. Ask only for the fields the user wants to change.
9. Enforce a strict two-step prompt sequence for intro updates when `source_id` is missing:
   - Step 1 message: episode list + `Reply with the episode number or source_id.`
   - Step 2 message (only after episode is selected): required/optional field collection.
10. For intro updates, use one prompt shape by default:
   "Episode selected: <source_id>.
   Provide any fields you want to update.

   Common fields:
   1. recordingLink (prefer a Descript web URL for TCR intro source updates)
   2. title
   3. videoThumbnails (give one URL or multiple URLs)
   4. thumbnailText
   5. transcript
   6. instructionsToEditor
   7. customNewsletterDraftUrl
   8. audioThumbnailLink
   9. outroMusicLink

   You only need to send the fields you want to change, and I will patch just those."
   Never ask the user to pick an episode id again after step 1 is completed.
11. If optional values are unclear, omit them instead of guessing.
12. Use `--dry-run` only if the user explicitly wants a preview before the write call.
    It is an internal preview/debug tool, not a normal client-facing step.
13. For `customNewsletterDraftUrl`, provide a public HTTP/HTTPS Ghost draft, preview, editor, or
   slug URL. It is not a local file upload field.
14. For file-type fields (`recordingLink`, `videoThumbnails`, `audioThumbnailLink`, `outroMusicLink`, submit main file link, and submit `assetUrls` entries):
   - The client accepts either public HTTP/HTTPS URLs or local file paths.
   - If the user provides a local file path, run `scripts/aip_local_upload_helper.py` first and use its returned public URL.
   - Do not pass unresolved local filesystem paths to the episode API payload.

## Resources

- `scripts/ai_podcasting_client.py`: Single client interface with subcommands.
- `scripts/aip_local_upload_helper.py`: Upload helper for local file paths; returns public URLs.
- `references/submit-episode.example.json`: Example payload for submit flow.
- `references/update-intro-copy.example.json`: Example payload for intro/copy patch flow.
- `references/update-intro-copy-tcr.example.json`: Example payload for TCR-style final title/thumbnail updates.
