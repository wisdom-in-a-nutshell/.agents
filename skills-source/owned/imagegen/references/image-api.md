# Image API quick reference

## Endpoints
- Generate: `POST /v1/images/generations` (`client.images.generate(...)`)
- Edit: `POST /v1/images/edits` (`client.images.edit(...)`)

## Models
- Default: `gpt-image-2`
- Legacy overrides: `gpt-image-1.5` for existing validated workflows, `gpt-image-1-mini` for faster/lower-cost generation.

## Core parameters (generate + edit)
- `prompt`: text prompt
- `model`: image model
- `n`: number of images (1-10)
- `size`: `1024x1024`, `1536x1024`, `1024x1536`, or `auto`
- `quality`: `low`, `medium`, `high`, or `auto`
- `background`: `opaque` or `auto` for `gpt-image-2`. Transparent alpha is not currently supported by the default model.
- `output_format`: `png` (default), `jpeg`, `webp`
- `output_compression`: 0-100 (jpeg/webp only)
- `moderation`: `auto` (default) or `low`

## Edit-specific parameters
- `image`: one or more input images (first image is primary)
- `mask`: optional mask image (same size, alpha channel required)
- `input_fidelity`: legacy edit parameter (`low` or `high`) for older GPT image models. Do not pass it for `gpt-image-2`.

## Output
- `data[]` list with `b64_json` per image

## Limits & notes
- Input images and masks must be under 50MB.
- Use edits endpoint when the user requests changes to an existing image.
- Masking is prompt-guided; exact shapes are not guaranteed.
- Large sizes and high quality increase latency and cost.
- For fast iteration or latency-sensitive runs, start with `quality=low`; raise to `high` for text-heavy or detail-critical outputs.
- For strict `gpt-image-2` edits, repeat invariants in the prompt instead of using `input_fidelity`.
- For alpha cutouts, generate a clean plain-background cutout first, then use deterministic post-processing or an explicit legacy model override if required.
