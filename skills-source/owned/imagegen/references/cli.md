# CLI reference (`scripts/image_gen.py`)

This file contains the “command catalog” for the bundled image generation CLI. Keep `SKILL.md` as overview-first; put verbose CLI details here.

## What this CLI does
- `generate`: generate new images from a prompt
- `edit`: edit an existing image (optionally with a mask) — inpainting / background replacement / “change only X”
- `generate-batch`: run many jobs from a JSONL file (one job per line)

Real API calls require **network access**. `--dry-run` does not.

## Quick start (works from any repo)
Set a stable path to the managed global skill CLI:

```
export IMAGE_GEN="${IMAGE_GEN:-$HOME/.agents/skills/imagegen/scripts/image_gen.py}"
```

Real API calls use the shared LiteLLM proxy environment: `LLM_API_ENDPOINT` and
`LLM_API_KEY`. On managed machines these are sourced from
`~/.secrets/litellm/env`, which is generated from the local canonical secret store.

Dry-run (no API call; no network required; does not require the `openai` package):

```
python "$IMAGE_GEN" generate --prompt "Test" --dry-run
```

Generate (requires network):

```
python "$IMAGE_GEN" generate --prompt "A cozy alpine cabin at dawn"
```

Use your normal `python3` environment for this owned skill.

```
python "$IMAGE_GEN" generate --prompt "A cozy alpine cabin at dawn"
```

## Guardrails (important)
- Use `python "$IMAGE_GEN" ...` (or equivalent full path) for generations/edits/batch work.
- Do **not** create one-off runners (e.g. `gen_images.py`) unless the user explicitly asks for a custom wrapper.
- This is an owned fork. Modify `scripts/image_gen.py` only for deliberate durable behavior changes, and keep the docs in sync when you do.

## Defaults (unless overridden by flags)
- Model: `gpt-image-2`
- Size: `1536x864`
- Saved output aspect ratio: `none` (preserve the API-native output)
- Quality: `auto`
- Output format: `png`
- Background: unspecified (API default). `gpt-image-2` supports opaque/auto backgrounds, not transparent alpha.

Practical size convention:
- The API request defaults to native 16:9 (`1536x864`) and the CLI preserves
  the returned image by default. It does not crop unless `--aspect-ratio 16:9`
  is explicitly passed.
- For `gpt-image-2`, arbitrary `WIDTHxHEIGHT` sizes are accepted when both
  dimensions are divisible by 16, the aspect ratio is between 1:3 and 3:1, and
  the size is within model limits. Useful native 16:9 sizes include `1536x864`,
  `2048x1152`, and `2560x1440`.
- `1920x1080` is not valid for `gpt-image-2` because `1080` is not divisible by
  16. Use `2048x1152` for a nearby native 16:9 request.
- For comic/story/explainer visuals (`illustration-story`) with a panel-like layout, prefer a native wide request such as `1536x864` unless square or portrait is clearly better.
- For tall vertical compositions, use `1024x1536`.

## Quality
- `--quality` works for `generate`, `edit`, and `generate-batch`: `low|medium|high|auto`.

Example:
```
python "$IMAGE_GEN" edit --image input.png --prompt "Change only the background" --quality high
```

## Masks (edits)
- Use a **PNG** mask; an alpha channel is strongly recommended.
- The mask should match the input image dimensions.
- In the edit prompt, repeat invariants (e.g., “change only the background; keep the subject unchanged”) to reduce drift.

## Optional deps
Install into your normal `python3` environment when missing:

```
python3 -m pip install --user --break-system-packages openai pillow
```

## Common recipes

Generate + also write a downscaled copy for fast web loading:

```
python3 "$IMAGE_GEN" generate \
  --prompt "A cozy alpine cabin at dawn" \
  --downscale-max-dim 1024
```

Notes:
- Downscaling writes an extra file next to the original (default suffix `-web`, e.g. `output-web.png`).
- Downscaling requires Pillow in your normal `python3` environment.

Generate with augmentation fields:

```
python "$IMAGE_GEN" generate \
  --prompt "A minimal hero image of a ceramic coffee mug" \
  --use-case "landing page hero" \
  --style "clean product photography" \
  --composition "centered product, generous negative space" \
  --constraints "no logos, no text"
```

Generate multiple prompts concurrently (async batch):

```
mkdir -p tmp/imagegen
cat > tmp/imagegen/prompts.jsonl << 'EOF'
{"prompt":"Cavernous hangar interior with a compact shuttle parked center-left, open bay door","use_case":"game concept art environment","composition":"wide-angle, low-angle, cinematic framing","lighting":"volumetric light rays through drifting fog","constraints":"no logos or trademarks; no watermark","size":"1536x1024"}
{"prompt":"Gray wolf in profile in a snowy forest, crisp fur texture","use_case":"wildlife photography print","composition":"100mm, eye-level, shallow depth of field","constraints":"no logos or trademarks; no watermark","size":"1024x1024"}
EOF

python "$IMAGE_GEN" generate-batch --input tmp/imagegen/prompts.jsonl --out-dir tmp/imagegen --concurrency 5

# Cleanup (recommended)
rm -f tmp/imagegen/prompts.jsonl
```

Notes:
- Use `--concurrency` to control parallelism (default `5`). Higher concurrency can hit rate limits; the CLI retries on transient errors.
- Per-job overrides are supported in JSONL (e.g., `size`, `quality`, `background`, `output_format`, `n`, and prompt-augmentation fields).
- `--n` generates multiple variants for a single prompt; `generate-batch` is for many different prompts.
- Treat the JSONL file as temporary: write it under `tmp/` and delete it after the run (don’t commit it).

Edit:

```
python "$IMAGE_GEN" edit --image input.png --mask mask.png --prompt "Replace the background with a warm sunset"
```

## CLI notes
- Supported API sizes for `gpt-image-2`: `auto`, standard sizes such as
  `1024x1024`, `1536x1024`, `1024x1536`, and arbitrary valid `WIDTHxHEIGHT`
  strings such as `1536x864` or `2048x1152`.
- Supported saved output aspect ratios: `none` or `16:9`; default is `none`.
- `gpt-image-2` does not currently support transparent backgrounds. Use a clean plain background for cutout prep, then post-process alpha separately when needed.
- The CLI default is `output.png`, so pass `--out tmp/imagegen/<name>.png` or `--out-dir tmp/imagegen`.
- Do not leave loose `output.png` or top-level `output/` artifacts.
- Use `--no-augment` to skip prompt augmentation.

## See also
- API parameter quick reference: `references/image-api.md`
- Prompt examples: `references/sample-prompts.md`
- Secondary deterministic finishing: `references/post-processing.md`
