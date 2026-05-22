# Image API quick reference

## Endpoints
- Generate: `POST /v1/images/generations` (`client.images.generate(...)`)
- Edit: `POST /v1/images/edits` (`client.images.edit(...)`)

## Models
- Default: `gpt-image-2`

## Core parameters (generate + edit)
- `prompt`: text prompt
- `model`: `gpt-image-2`
- `n`: number of images (1-10)
- `size`: `auto`, standard sizes such as `1024x1024`, `1536x1024`, and
  `1024x1536`, or for `gpt-image-2` arbitrary valid `WIDTHxHEIGHT` strings
  such as `1536x864` or `2048x1152`
- `quality`: `low`, `medium`, `high`, or `auto`
- `background`: `opaque` or `auto` for `gpt-image-2`. Transparent alpha is not currently supported by the default model.
- `output_format`: `png` (default), `jpeg`, `webp`
- `output_compression`: 0-100 (jpeg/webp only)
- `moderation`: `auto` (default) or `low`

## Edit-specific parameters
- `image`: one or more input images (first image is primary)
- `mask`: optional mask image (same size, alpha channel required)

## Output
- `data[]` list with `b64_json` per image

## Limits & notes
- Input images and masks must be under 50MB.
- Use edits endpoint when the user requests changes to an existing image.
- Masking is prompt-guided; exact shapes are not guaranteed.
- Large sizes and high quality increase latency and cost.
- For `gpt-image-2`, requested width and height must both be divisible by 16,
  and the aspect ratio must be between 1:3 and 3:1. Native 16:9 examples:
  `1536x864`, `2048x1152`, `2560x1440`. `1920x1080` is not valid because
  `1080` is not divisible by 16.
- For fast iteration or latency-sensitive runs, start with `quality=low`; raise to `high` for text-heavy or detail-critical outputs.
- For strict edits, repeat invariants in the prompt.
- For alpha cutouts, generate a clean plain-background cutout first, then use deterministic post-processing if required.
