# fal Seedance Client Contract

This repo uses `scripts/fal_seedance_ref2v.mjs` as the machine-primary client for fal.ai Seedance reference-to-video runs.

## Purpose

Use the client when an agent needs to turn storyboard images or other local references into short Seedance clips through fal. The client owns:

- local reference validation,
- local file upload to fal storage,
- Seedance Ref2V request submission,
- generated MP4 download,
- JSON receipt writing,
- non-inference provider connectivity checks.

## Secret Lane

- Canonical secret: Azure Key Vault `fal--api-key`
- Mapping: `/Users/dobby/GitHub/scripts/sync/machine-secrets/fal.env.map`
- Generated local file: `~/.secrets/fal/env`
- Local env var inside that generated file: `FAL_KEY`

Refresh local credentials:

```bash
/Users/dobby/GitHub/scripts/sync/keyvault-sync-machine-secrets.sh --apply --integration fal
```

The client reads the generated file directly. Do not pass fal keys through flags or repo `.env` files.

## Commands

Local validation only:

```bash
node scripts/fal_seedance_ref2v.mjs validate
```

Provider connectivity without video inference:

```bash
node scripts/fal_seedance_ref2v.mjs doctor --remote
```

`doctor --remote` uploads a tiny text file to fal storage with immediate lifecycle expiry. It verifies the API key and provider connectivity without submitting a Seedance generation.

If `doctor --remote` returns `E_BILLING_REQUIRED`, the configured key reached fal, but the fal account is locked until the balance is topped up.

Dry-run a reference-to-video request:

```bash
node scripts/fal_seedance_ref2v.mjs run \
  --project <project-id> \
  --name <shot-name> \
  --ref projects/<project-id>/storyboard/frame-01.png \
  --prompt "Animate @Image1 as the primary frame. Subtle breathing, one natural blink, tiny head turn, locked camera." \
  --duration 4 \
  --aspect-ratio 1:1 \
  --dry-run
```

Run for real by removing `--dry-run`.

## Output Contract

Default stdout is one JSON object:

- `schema_version`: currently `1.0`
- `command`: canonical command name
- `status`: `ok` or `error`
- `data`: command result on success
- `error`: structured error object on failure
- `meta.request_id`: local command request id
- `meta.duration_ms`: command duration
- `meta.timestamp_utc`: completion timestamp

Progress and provider logs go to stderr only.

## Exit Codes

- `0`: success
- `1`: unexpected/provider output failure
- `2`: usage, validation, or missing local file
- `3`: missing/rejected credentials or account lock such as exhausted fal balance
- `4`: network/provider availability issue
- `5`: timeout or interruption

## Ref2V Schema

The client defaults to the full-quality endpoint:

`bytedance/seedance-2.0/reference-to-video`

Pass `--endpoint bytedance/seedance-2.0/fast/reference-to-video` to use the faster/cheaper variant. The full endpoint supports up to 1080p and is recommended for production renders; the fast variant caps at 720p and is recommended for cheap prompt iteration only.

Supported input limits from fal:

- `image_urls`: up to 9 images, JPEG/PNG/WebP, max 30 MB each
- `video_urls`: up to 3 videos, MP4/MOV, combined duration 2-15s, total under 50 MB
- `audio_urls`: up to 3 audio files, MP3/WAV, combined duration up to 15s
- total files across image/video/audio: up to 12
- `duration`: `auto` or 4-15 seconds
- `resolution`: `480p`, `720p`, or `1080p` (full endpoint only — fast caps at 720p)
- `aspect_ratio`: `auto`, `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`

## Reference Prompting Rules

- Refer to images as `@Image1`, `@Image2`, etc.
- Refer to videos as `@Video1`, `@Video2`, etc.
- Refer to audio as `@Audio1`, `@Audio2`, etc.
- Explicitly assign each reference a role: primary frame, character identity, style, outfit, environment, camera motion, action choreography, rhythm, or audio mood.
- For a storyboard frame, make `@Image1` the primary frame to animate. Use later images as anchors unless a transition or morph is intended.
- Use short canaries before batching. Resolution defaults to 1080p on the full endpoint; drop to 720p (or use `--endpoint .../fast/...`) for cheap prompt iteration.
- For 10s+ clips, write timed segments in the prompt.
- Do not copy Replicate payloads into this client. fal uses `image_urls` / `video_urls` / `audio_urls` and `@Image1` handles. Replicate uses different field names and bracket handles.

## Storyboard-To-Video Recipes

The full Seedance 2.0 endpoint can handle continuous multi-action shots within a single take (open object → camera dolly → action → state change), with director-level camera control. Use timed-segment prompts (`[0-2s] ... [2-5s] ...`) for those.

Treat the "one short clip per beat, stitch later" pattern as the fallback for cases where the model demonstrably struggles with a continuous shot — not the default.

### Single Storyboard Frame

Use when the storyboard frame already defines composition and you only need subtle motion:

```text
Animate @Image1 as the primary frame.
[0-4s]: locked medium close-up, subtle breathing, one natural blink, soft key light.
No face reshaping, no outfit change, no new characters.
```

### Identity + Style Anchors

Use when one frame is primary but consistency needs extra references:

```text
Animate @Image1 as the primary frame.
Use @Image2 only as the character identity anchor.
Use @Image3 only as the color/style anchor.
[0-4s]: locked camera, subtle breathing, one natural blink, tiny head turn.
No face reshaping, no outfit change, no age change, no new characters.
```

### Motion Transfer

Use a short reference video when camera or action matters more than static composition:

```text
Animate @Image1 as the character and visual style reference.
Reference @Video1 only for camera movement and action choreography.
[0-5s]: follow @Video1's motion timing, but preserve @Image1's face, outfit, and style.
```

### Time-Segmented Shot

Use for longer 8-15s generations:

```text
@Image1 is the primary character and first visual anchor.
@Image2 is the environment reference.
[0-4s]: medium close-up, calm expression, soft side light, locked camera.
[4-8s]: slow push-in, tiny head turn toward camera.
[8-12s]: expression warms slightly, lighting stays consistent.
No extra characters, no text, no abrupt cuts.
```

## Free Verification Boundary

Can verify without paid video generation:

- local secret file exists and can be parsed: `validate`
- fal auth/connectivity via storage only: `doctor --remote`
- local reference files exist and fit prompt handle order: `run --dry-run`
- reference counts and supported parameter values
- planned MP4 and receipt paths

Cannot verify without actual provider generation:

- identity retention
- prompt adherence
- motion quality
- provider safety rejection on the generation endpoint
- whether multi-reference roles are interpreted exactly as intended

## Output Files

With `--project <project-id>` and `--name <shot-name>`:

- MP4: `projects/<project-id>/seedance/renders/<shot-name>.mp4`
- receipt: `projects/<project-id>/seedance/receipts/<shot-name>.json`

Receipts include endpoint, prompt, prepared references, fal request id, provider output, local file hash, and local paths.

## Sources

- fal endpoint docs: `https://fal.ai/models/bytedance/seedance-2.0/fast/reference-to-video/api`
- fal queue docs: `https://fal.ai/docs/documentation/model-apis/inference/queue`
- fal JS client docs: `https://fal.ai/docs/api-reference/client-libraries/javascript`
- ByteDance Seedance 2.0 page: `https://seed.bytedance.com/en/seedance2_0`
- Seedance 2.0 model card: `https://arxiv.org/abs/2604.14148`
