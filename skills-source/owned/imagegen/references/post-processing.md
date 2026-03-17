# Post-processing reference (`scripts/postprocess_image.py`)

Use this only when the user explicitly asks for deterministic post-processing after AI image generation/editing. This helper is for packaging an existing image: title bands, subtitles, footers, borders, crop-inset cleanup, emphasis underlines/swash, and optional bottom notes/quotes.

## When to use `postprocess_image.py`
- The user explicitly asks for deterministic post-processing after AI image generation/editing
- Add a top title + subtitle band to an existing image
- Add a footer or small attribution mark
- Add a centered bottom note / quote / inner monologue
- Add hand-drawn-style emphasis underlines or marker swashes to key phrases
- Crop slightly inward to remove a source image border before packaging
- Re-render a matched panel set with consistent typography/layout

## When **not** to use it
- If the image content itself needs to change, use the model (`scripts/image_gen.py` edit flow)
- If you need inpainting, background replacement, object removal, or compositing new visual elements, use the model
- If the user is only asking for generic local image processing unrelated to AI image work, do not force this helper into the foreground; it is secondary to the AI workflow
- If the user did not explicitly ask for deterministic post-processing, do not reach for this automatically

## Quick start
Set stable paths from any repo:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export IMAGE_POST="$CODEX_HOME/skills/imagegen/scripts/postprocess_image.py"
```

Basic example:

```bash
python "$IMAGE_POST" \
  --image input/panel.png \
  --out output/panel-final.png \
  --title "A capable agent can still get lost." \
  --subtitle "Make the digital environment easier to navigate." \
  --footer "adithyan.io"
```

## Common recipes

### Add top band + footer

```bash
python "$IMAGE_POST" \
  --image input/panel.png \
  --out output/panel-framed.png \
  --title "MCP connects the agent to the outside world." \
  --subtitle "Give it access to live information and external tools." \
  --footer "adithyan.io"
```

### Add underlined emphasis to key phrases

```bash
python "$IMAGE_POST" \
  --image input/panel.png \
  --out output/panel-emphasis.png \
  --title "A capable agent can still get lost." \
  --subtitle "Make the digital environment easier to navigate." \
  --highlight-style underline \
  --highlight-title "capable agent||get lost" \
  --highlight-subtitle "easier to navigate" \
  --title-highlight-color "180,40,40,190" \
  --subtitle-highlight-color "40,140,70,190"
```

### Crop inward before packaging

```bash
python "$IMAGE_POST" \
  --image input/panel-with-border.png \
  --out output/panel-cropped.png \
  --title "A capable agent can still get lost." \
  --crop-px 90
```

### Add a bottom note / quote

```bash
python "$IMAGE_POST" \
  --image input/panel.png \
  --out output/panel-quoted.png \
  --title "AGENTS.md helps the agent find its bearings." \
  --subtitle "Document the terrain so it does not have to reorient from scratch every time." \
  --bottom-note "“Tools here, API there. Now I know where to go.”"
```

## Layout notes
- Defaults are tuned for monochrome explainer/webcomic-style panels but the script is reusable beyond that
- Keep copy short; this is packaging, not a layout engine for dense documents
- Prefer one consistent font across a panel set unless the user asks otherwise
- Use `--crop-px` conservatively; it rescales back to the original image size after cropping inward
- Use `--bottom-note` only when it genuinely helps readability; do not clutter every panel

## See also
- `references/cli.md` for AI image generation/edit/edit-batch flows
- `references/prompting.md` for model prompt shaping
- `references/style-guides.md` for recurring visual families
