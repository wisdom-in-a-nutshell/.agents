---
name: fal-seedance
description: "Use for fal.ai Seedance video generation in this repo, especially Seedance 2.0 reference-to-video runs with multiple image references, prompt canaries, local file uploads, generated MP4 downloads, and JSON receipts."
---

# fal Seedance

Use this skill when a task involves fal.ai Seedance, reference-to-video, image-to-video, or Seedance canaries for storyboard/style exploration.

## Default Lane

- **ref2v** endpoint: `bytedance/seedance-2.0/reference-to-video` (full quality, supports 1080p, multi-action shots, director-level camera control). Pass `--endpoint bytedance/seedance-2.0/fast/reference-to-video` for the cheaper/faster variant when iterating on prompts cheaply.
- **i2v** (image-to-video, deterministic start→end morph) supports both Seedance and Kling families:
  - Seedance: `bytedance/seedance-2.0/image-to-video` (default), `bytedance/seedance-2.0/fast/image-to-video`
  - Kling O3: `fal-ai/kling-video/o3/standard/image-to-video` (clean baseline), `fal-ai/kling-video/o3/pro/image-to-video` (higher quality, recommended when standard output looks soft/weird), `fal-ai/kling-video/o3/4k/image-to-video` (highest tier)
  - Kling V3: `fal-ai/kling-video/v3/standard/image-to-video`, `fal-ai/kling-video/v3/pro/image-to-video`
  - Kling endpoints don't accept `--resolution` or `--generate-audio`; the CLI strips them automatically.
  - Switch from Seedance to Kling when Seedance shows chroma-noise on smooth/cream backgrounds.
- Default resolution: `1080p` (Seedance only). Drop to `720p` or `480p` for cheaper canaries on the full endpoint, or use the fast endpoint (capped at 720p).
- Secret lane: machine-local shared integration `fal`
- Secret mapping: `/Users/dobby/GitHub/scripts/sync/machine-secrets/fal.env.map`
- Generated secret file: `~/.secrets/fal/env`
- CLI: `python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py` (Python, uses the official `fal-client` PyPI SDK)
- Client contract: `.agents/skills/fal-seedance/references/client.md`

The CLI reads `~/.secrets/fal/env` directly. Do not pass fal keys through flags, tracked files, or chat-visible shell commands.

If `fal-client` isn't installed: `python3 -m pip install --user --break-system-packages fal-client`.

## Workflow

1. Start with `--dry-run` for every new prompt or reference set.
2. Use `--project <id>` so outputs stay under `projects/<id>/seedance/`.
3. Pass local reference images with repeated `--ref`; the CLI uploads them to fal CDN during real runs.
4. Refer to inputs in prompts as `@Image1`, `@Image2`, etc.
5. For visual canaries, default to `--no-generate-audio` and a restrained prompt. Resolution defaults to 1080p — drop to 720p or 480p (or use `--endpoint .../fast/...`) when iterating cheaply on prompts.
6. Keep each successful run's JSON receipt with the MP4; use the receipt to regenerate or compare drift.

## Commands

Validate the local secret bootstrap:

```bash
python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py validate
```

Verify fal provider connectivity without video inference:

```bash
python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py doctor --remote
```

Dry-run a canary:

```bash
python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py run \
  --project <project-id> \
  --name portrait-motion-canary \
  --ref projects/<project-id>/storyboard/frame-01.png \
  --prompt "Animate @Image1 as a calm studio portrait. Gentle smile, subtle breathing, one natural blink, tiny head turn, soft key light, locked camera, no face reshaping." \
  --duration 4 \
  --aspect-ratio 1:1 \
  --dry-run
```

Run after the dry-run looks right by removing `--dry-run`.

Image-to-video (deterministic start→end morph) on Kling O3 Pro:

```bash
python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py i2v \
  --project <project-id> \
  --name <beat-name> \
  --start-image projects/<project-id>/keyframes/start.png \
  --end-image projects/<project-id>/keyframes/end.png \
  --endpoint fal-ai/kling-video/o3/pro/image-to-video \
  --duration 5 --aspect-ratio 1:1 \
  --prompt "<phased timing prompt>" \
  --dry-run
```

Drop `--dry-run` to render. Use `o3/standard` for cheaper iterations and `o3/pro` once the prompt is locked and you want production quality. Long prompts can be passed via `--prompt-file` instead of `--prompt`.

Multi-reference storyboard canary:

```bash
python3 .agents/skills/fal-seedance/scripts/fal_seedance_ref2v.py run \
  --project <project-id> \
  --name anchored-portrait-motion \
  --ref projects/<project-id>/storyboard/primary-frame.png \
  --ref projects/<project-id>/storyboard/identity-anchor-01.png \
  --ref projects/<project-id>/storyboard/style-anchor-01.png \
  --prompt "Animate @Image1 as the primary frame. Use @Image2 and @Image3 only as identity and style anchors. Subtle breathing, one natural blink, tiny head turn, soft studio light, locked camera, no face reshaping, no outfit change." \
  --duration 4 \
  --aspect-ratio 1:1 \
  --dry-run
```

## Prompt Rules

- Use `@ImageN` handles, matching fal's Seedance schema.
- `@Image1` should usually be the primary frame to animate. Additional image refs should be described as identity, style, object, or environment anchors so Seedance does not treat them as a morph target by accident.
- Explicitly assign every reference a role in the prompt: primary frame, character identity, style, outfit, environment, camera movement, action choreography, rhythm, or sound.
- Describe the exact camera move and the amount of motion.
- For identity canaries, explicitly say no age change, no outfit change, no face reshaping, and locked or near-locked camera.
- For longer clips, write timed segments (`[0-2s] ... [2-5s] ...`). The full Seedance 2.0 endpoint handles continuous multi-action shots within one take (e.g. open object → camera dolly → action → state change). Reserve the "atomic canary, then stitch" approach for cases where the model demonstrably struggles with the continuous shot — don't pre-fragment by default.
- For deterministic morph between two specific states (e.g. real photo → illustrated portrait), pass the start state as `@Image1` (primary frame) and the target state as `@Image2` (style/end-state anchor). Describe the transformation explicitly in the prompt.
- Do not copy Replicate examples directly; fal uses `image_urls` / `video_urls` / `audio_urls` and `@Image1` handles.

## Output Contract

The CLI prints one JSON object to stdout by default:

- `status`: `ok` or `error`
- `data.video.url`: fal output URL on success
- `data.local_video.path`: downloaded MP4 path when download is enabled
- `data.receipt_path`: JSON receipt path
- `error.code`: stable error code on failure

Progress and provider logs go to stderr only.
