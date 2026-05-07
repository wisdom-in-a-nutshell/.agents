---
name: fal-seedance
description: "Use for fal.ai Seedance video generation in this repo, especially Seedance 2.0 reference-to-video runs with multiple image references, prompt canaries, local file uploads, generated MP4 downloads, and JSON receipts."
---

# fal Seedance

Use this skill when a task involves fal.ai Seedance, reference-to-video, image-to-video, or Seedance canaries for storyboard/style exploration.

## Default Lane

- Endpoint: `bytedance/seedance-2.0/fast/reference-to-video`
- Secret lane: machine-local shared integration `fal`
- Secret mapping: `/Users/dobby/GitHub/scripts/sync/machine-secrets/fal.env.map`
- Generated secret file: `~/.secrets/fal/env`
- CLI: `node scripts/fal_seedance_ref2v.mjs`
- Client contract: `docs/references/fal-seedance-client.md`

The CLI reads `~/.secrets/fal/env` directly. Do not pass fal keys through flags, tracked files, or chat-visible shell commands.

## Workflow

1. Start with `--dry-run` for every new prompt or reference set.
2. Use `--project <id>` so outputs stay under `projects/<id>/seedance/`.
3. Pass local reference images with repeated `--ref`; the CLI uploads them to fal CDN during real runs.
4. Refer to inputs in prompts as `@Image1`, `@Image2`, etc.
5. For visual canaries, default to `--no-generate-audio`, 4-5 seconds, `720p`, and a restrained prompt.
6. Keep each successful run's JSON receipt with the MP4; use the receipt to regenerate or compare drift.

## Commands

Validate the local secret bootstrap:

```bash
node scripts/fal_seedance_ref2v.mjs validate
```

Verify fal provider connectivity without video inference:

```bash
node scripts/fal_seedance_ref2v.mjs doctor --remote
```

Dry-run a canary:

```bash
node scripts/fal_seedance_ref2v.mjs run \
  --project <project-id> \
  --name portrait-motion-canary \
  --ref projects/<project-id>/storyboard/frame-01.png \
  --prompt "Animate @Image1 as a calm studio portrait. Gentle smile, subtle breathing, one natural blink, tiny head turn, soft key light, locked camera, no face reshaping." \
  --duration 4 \
  --aspect-ratio 1:1 \
  --dry-run
```

Run after the dry-run looks right by removing `--dry-run`.

Multi-reference storyboard canary:

```bash
node scripts/fal_seedance_ref2v.mjs run \
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
- For longer clips, write timed segments. For storyboard/image canaries, keep the first test short and restrained.
- Avoid asking for a morph or multi-shot story until the single-frame motion canary is acceptable.
- Treat Ref2V as a shot generator with labeled anchors, not a deterministic storyboard renderer. Generate one short clip per storyboard beat and stitch accepted clips later.
- Do not copy Replicate examples directly; fal uses `image_urls` / `video_urls` / `audio_urls` and `@Image1` handles.

## Output Contract

The CLI prints one JSON object to stdout by default:

- `status`: `ok` or `error`
- `data.video.url`: fal output URL on success
- `data.local_video.path`: downloaded MP4 path when download is enabled
- `data.receipt_path`: JSON receipt path
- `error.code`: stable error code on failure

Progress and provider logs go to stderr only.
