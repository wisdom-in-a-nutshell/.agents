---
name: "imagegen"
description: "Generate and edit images with AI, including image generation, inpainting, background removal or replacement, compositing, text-in-image edits, batch variants, and related AI image model tasks. Use this skill for model-based image generation/editing, not for purely local image layout, captioning, or other non-model image processing."
---

# Image Generation Skill

Generates or edits images for the current project (e.g., website assets, game assets, UI mockups, product mockups, wireframes, logo design, photorealistic images, infographics, or comic/explainer panels). Defaults to `gpt-image-1.5` and the OpenAI Image API for model-based work.

## When to use
- Generate a new image (concept art, product shot, cover, website hero)
- Edit an existing image with the model (inpainting, masked edits, lighting or weather transformations, background replacement, object removal, compositing, transparent background)
- Batch runs (many prompts, or many variants across prompts)
- Unless the user explicitly asks for raw first-pass outputs, rough explorations, or a faster lighter-touch flow, use the default workflow for non-trivial image work: inspect outputs, keep a project-local worklog, and iterate before presenting the strongest version.

## Decision tree (generate vs edit vs batch)
- If the user provides an input image (or says “edit/retouch/inpaint/mask/translate/localize/change only X”) → **edit**
- Else if the user needs many different prompts/assets → **generate-batch**
- Else → **generate**

## Workflow (default for non-trivial image work)
1. Decide intent: generate vs edit vs batch (see decision tree above).
2. Check `styles/` inside this skill for an existing relevant visual family before inventing a new direction.
3. Collect inputs up front.
   - For generate/edit/batch: prompt(s), exact text (verbatim), constraints/avoid list, and any input image(s)/mask(s). For multi-image edits, label each input by index and role; for edits, list invariants explicitly.
4. If batch: write a temporary JSONL under `tmp/` (one job per line), run once, then delete the JSONL.
5. Augment the prompt into a short labeled spec using `references/prompting.md` and `references/sample-prompts.md` without inventing new creative requirements.
6. Run the model-based tool: `scripts/image_gen.py` (see `references/cli.md`).
7. For non-trivial or iterative work, create or reuse a project-local worklog and record per version:
   - prompt used
   - output path
   - short self-review: what worked, what feels off, what should change next
8. Inspect outputs yourself and validate: subject, style, composition, text accuracy, and invariants/avoid items.
9. Iterate deliberately:
   - use **edit** when preserving an already-good composition/style/character is the priority
   - use a **fresh generation** when the concept is wrong or edits keep drifting composition, aspect ratio, or clarity
10. Unless the user explicitly wants raw roughs, privately iterate a few times and present the strongest version.
11. Save/return final outputs and note the final prompt + flags used; keep one canonical selected output once the user chooses a version.

## Iterative continuity rule

For non-trivial image work where continuity, taste, or multi-step refinement matters, do not treat each generation as a fresh isolated attempt.

Default to this stronger pattern:
- create or reuse a durable markdown worklog in the project
- record version outputs, self-review, and next-step hypotheses there
- keep iterating privately until there is a genuinely strong candidate, not just a plausible first pass
- prefer showing the user the strongest candidate rather than every weak intermediate

When continuity matters across versions or panels:
- prefer **edit-from-previous-version** over fresh regeneration once you have a usable base
- use previously selected/canonical images as explicit reference anchors for style, character, and composition continuity
- use fresh generation mainly for the first base image or when the concept/composition is fundamentally wrong and edits keep drifting

This is especially important for:
- comics or panel sequences
- recurring mascots / characters
- visual families that should remain recognizably the same across assets
- any workflow the user may want to review later through a clear version history

This does **not** need to be done for every tiny throwaway image. Use judgment. The point is to make durable iterative image work legible and compounding by default.

Use this worklog format:

```md
## Self-review - Version N

Prompt used:
- ...

Output path:
- ...

What worked:
- ...

What feels off:
- ...

What should improve next:
- ...
```

Use a lighter-touch version of this workflow for one-off throwaway generations, fast exploratory batches, or tiny edits where a markdown worklog would add more friction than value.

When useful, expand the worklog beyond the minimal self-review format with:
- panel/asset role in the story or system
- prompt draft(s)
- version hypotheses
- why a new pass should be an edit vs a fresh generation

The goal is not paperwork. The goal is preserving iteration state so future turns can continue cleanly without re-discovering taste, continuity, or direction.

If the work stabilizes into a reusable visual family, create or update a style guide under `styles/`. Keep style canon there, not workflow/process. See `references/style-guides.md`.

## Temp and output conventions
- Do not rely on repo-local virtualenv auto-switching for this owned skill. Treat the runtime as machine-global.
- Use `tmp/imagegen/` only for truly temporary intermediate files (for example JSONL batches or disposable seed files), and delete them when done.
- Write final artifacts under `output/imagegen/` when working in this repo unless the project has a more specific destination.
- Use `--out` or `--out-dir` to control output paths; keep filenames stable and descriptive.

## Dependencies (install if missing)
Prefer the machine-global `python3` environment for this owned skill.

Python packages:
```
python3 -m pip install --user --break-system-packages openai pillow
```

If installation isn't possible in this environment, tell the user which dependency is missing and how to install it locally.

## Defaults & rules
- Use `gpt-image-1.5` unless the user explicitly asks for `gpt-image-1-mini` or explicitly prefers a cheaper/faster model.
- Assume the user wants a new image unless they explicitly ask for an edit.
- Unless the user specifies otherwise, call the CLI as if the default size is `1536x1024`.
- Default size should generally bias toward `1536x1024` unless the user clearly wants square or portrait.
- Use `1536x1024` by default for comic/story/explainer visuals (`illustration-story` with a panel-like composition).
- Use `1024x1024` when the image is primarily icon-like, avatar-like, or meant to crop square.
- Use the OpenAI Python SDK (`openai` package) for all API calls; do not use raw HTTP.
- If the user requests edits, use `client.images.edit(...)` and include input images (and mask if provided).
- Prefer the bundled AI CLI (`scripts/image_gen.py`) over writing new one-off scripts.
- This is an owned fork of the upstream skill. Keep behavioral changes here, not in the upstream external source.
- If the result isn’t clearly relevant or doesn’t satisfy constraints, iterate with small targeted prompt changes; only ask a question if a missing detail blocks success.

## Optional helper scripts
- `scripts/postprocess_image.py` is an optional deterministic finishing helper for things like title bands, subtitles, footers, bottom notes, crop-inset cleanup, borders, and emphasis underlines.
- Do **not** use it by default.
- Use it only when the user explicitly asks for deterministic post-processing after AI image generation/editing.
- Reference: `references/post-processing.md`

## Prompt augmentation
Reformat user prompts into a structured, production-oriented spec. Only make implicit details explicit; do not invent new requirements.

Aspect-ratio guidance:
- Prefer a wide landscape canvas and default to `1536x1024` unless the user specifies otherwise.
- Use `1024x1024` when the image is primarily icon-like, avatar-like, or meant to crop square.
- Use `1024x1536` when the user clearly wants a tall/portrait composition.

## Use-case taxonomy (exact slugs)
Classify each request into one of these buckets and keep the slug consistent across prompts and references.

Generate:
- photorealistic-natural — candid/editorial lifestyle scenes with real texture and natural lighting.
- product-mockup — product/packaging shots, catalog imagery, merch concepts.
- ui-mockup — app/web interface mockups that look shippable.
- infographic-diagram — diagrams/infographics with structured layout and text.
- logo-brand — logo/mark exploration, vector-friendly.
- illustration-story — comics, children’s book art, narrative scenes.
- stylized-concept — style-driven concept art, 3D/stylized renders.
- historical-scene — period-accurate/world-knowledge scenes.

Edit:
- text-localization — translate/replace in-image text, preserve layout.
- identity-preserve — try-on, person-in-scene; lock face/body/pose.
- precise-object-edit — remove/replace a specific element (incl. interior swaps).
- lighting-weather — time-of-day/season/atmosphere changes only.
- background-extraction — transparent background / clean cutout.
- style-transfer — apply reference style while changing subject/scene.
- compositing — multi-image insert/merge with matched lighting/perspective.
- sketch-to-render — drawing/line art to photoreal render.

Quick clarification (augmentation vs invention):
- If the user says “a hero image for a landing page”, you may add *layout/composition constraints* that are implied by that use (e.g., “generous negative space on the right for headline text”).
- Do not introduce new creative elements the user didn’t ask for (e.g., adding a mascot, changing the subject, inventing brand names/logos).

Template (include only relevant lines):
```
Use case: <taxonomy slug>
Asset type: <where the asset will be used>
Primary request: <user's main prompt>
Scene/background: <environment>
Subject: <main subject>
Style/medium: <photo/illustration/3D/etc>
Composition/framing: <wide/close/top-down; placement>
Lighting/mood: <lighting + mood>
Color palette: <palette notes>
Materials/textures: <surface details>
Quality: <low/medium/high/auto>
Input fidelity (edits): <low/high>
Text (verbatim): "<exact text>"
Constraints: <must keep/must avoid>
Avoid: <negative constraints>
```

Augmentation rules:
- Keep it short; add only details the user already implied or provided elsewhere.
- Always classify the request into a taxonomy slug above and tailor constraints/composition/quality to that bucket. Use the slug to find the matching example in `references/sample-prompts.md`.
- If the user gives a broad request (e.g., "Generate images for this website"), use judgment to propose tasteful, context-appropriate assets and map each to a taxonomy slug.
- For edits, explicitly list invariants ("change only X; keep Y unchanged").
- If any critical detail is missing and blocks success, ask a question; otherwise proceed.

## Examples

### Generation example (hero image)
```
Use case: stylized-concept
Asset type: landing page hero
Primary request: a minimal hero image of a ceramic coffee mug
Style/medium: clean product photography
Composition/framing: centered product, generous negative space on the right
Lighting/mood: soft studio lighting
Constraints: no logos, no text, no watermark
```

### Edit example (invariants)
```
Use case: precise-object-edit
Asset type: product photo background replacement
Primary request: replace the background with a warm sunset gradient
Constraints: change only the background; keep the product and its edges unchanged; no text; no watermark
```

## Prompting best practices (short list)
- Structure prompt as scene -> subject -> details -> constraints.
- Include intended use (ad, UI mock, infographic) to set the mode and polish level.
- Use camera/composition language for photorealism.
- Quote exact text and specify typography + placement.
- For tricky words, spell them letter-by-letter and require verbatim rendering.
- For multi-image inputs, reference images by index and describe how to combine them.
- For edits, repeat invariants every iteration to reduce drift.
- Iterate with single-change follow-ups.
- For latency-sensitive runs, start with quality=low; use quality=high for text-heavy or detail-critical outputs.
- For strict edits (identity/layout lock), consider input_fidelity=high.
- If results feel “tacky”, add a brief “Avoid:” line (stock-photo vibe; cheesy lens flare; oversaturated neon; harsh bloom; oversharpening; clutter) and specify restraint (“editorial”, “premium”, “subtle”).

More principles: `references/prompting.md`. Copy/paste specs: `references/sample-prompts.md`.

## Guidance by asset type
Asset-type templates (website assets, game assets, wireframes, logo) are consolidated in `references/sample-prompts.md`.

## CLI + environment notes
- Model-based CLI commands + examples: `references/cli.md`
- Optional deterministic post-processing helper: `references/post-processing.md`
- API parameter quick reference: `references/image-api.md`
- If network approvals / sandbox settings are getting in the way: `references/codex-network.md`
- The owned CLI now defaults to `1536x1024`; only override with `--size` when square/portrait is actually desired.

## Reference map
- **`references/cli.md`**: how to *run* AI image generation/edits/batches via `scripts/image_gen.py` (commands, flags, recipes).
- **`references/post-processing.md`**: optional deterministic post-processing via `scripts/postprocess_image.py` when the user explicitly asks for finishing steps after AI generation/editing.
- **`references/image-api.md`**: what knobs exist at the API level (parameters, sizes, quality, background, edit-only fields).
- **`references/prompting.md`**: prompting principles (structure, constraints/invariants, iteration patterns).
- **`references/sample-prompts.md`**: copy/paste prompt recipes (generate + edit workflows; examples only).
- **`references/style-guides.md`**: how to document and reuse a style guide / visual canon for a recurring comic family, mascot series, or brand-like illustration style.
- **`styles/`**: reusable visual families and style guides that should carry across future image work.
- **`references/codex-network.md`**: environment/sandbox/network-approval troubleshooting.
