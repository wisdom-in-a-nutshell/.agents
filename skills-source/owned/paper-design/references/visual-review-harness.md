# Visual review harness for Paper work

Use this when the Paper task is a real visual deliverable rather than a one-shot tweak:
- social carousels
- explainers
- concept boards with multiple plausible directions
- new panels that need shaping before they are worth showing

Do **not** turn every Paper task into a heavy harness.

## Why this exists

The failure mode is predictable:
- a direction starts to feel promising
- the creator gets attached to it
- self-review softens
- visible issues remain
- iteration becomes hidden rewrite churn instead of clear comparison

This harness keeps the work legible and skeptical.

## Default loop

1. **Panel thesis**
   - What is the one idea this panel must communicate?

2. **Visual thesis**
   - What is the one dominant visual move?

3. **Build**
   - Make the panel in Paper.

4. **Screenshot review**
   - Take a screenshot.
   - Check for obvious failures first: clipping, crushing, overlap, weak hierarchy, unreadable labels, broken spacing.
   - Also check small-detail visibility explicitly: icon contrast, icon size, low-contrast strokes, and other elements that can disappear against dark surfaces.

5. **Evaluator decision**
   - For non-one-shot visual work, assume the visual review pattern by default rather than treating evaluator review as a rare escalation.

6. **Simplify**
   - Remove anything that is not load-bearing.

7. **Presentation gate**
   - Do not show the user every plausible intermediate.
   - Keep iterating until the panel is directionally strong and you would personally feel good presenting it.
   - Only surface rougher intermediate states when the user explicitly wants live co-design or micro-iteration.


## Independent evaluator rule

Use an evaluator by default for non-one-shot visual work, and selectively for everything else.

The strongest fit is when:
- the panel is a real visual deliverable
- the creator is looping or attached to a direction
- the remaining issue is more about taste, hierarchy, or narrative clarity than mechanics

If the runtime exposes a dedicated screenshot-review agent such as `visual_reviewer`, prefer that first for Paper panel review. If it is unavailable, fall back to another independent sub-agent rather than relying on self-review alone.

Do not use an evaluator for:
- tiny spacing nudges
- obvious clipping/overflow bugs
- small text corrections

The evaluator should review screenshots, not vague descriptions.

Use the dedicated `visual_reviewer` agent for screenshot-based Paper critique. It is a better fit than a generic evaluator for layout, hierarchy, spacing, readability, icon visibility, and visual coherence checks.

### Evaluator handoff pattern

If you use an independent evaluator, make the handoff auditable:

1. generator creates or updates the panel
2. generator captures the current screenshot
3. evaluator sub-agent reviews the screenshot
4. evaluator writes a short review artifact
5. parent agent reads that artifact and decides what to do next

Do **not** treat the generator's own memory of the evaluator feedback as sufficient.

Suggested artifact locations:
- project-local review note if the project already has a learnings/logs area
- otherwise a temporary file under `capture/tmp/`

The review artifact should be short and structured:
- panel name
- intended idea
- scores or pass/fail by small rubric
- 3 concrete criticisms
- 2 specific recommendations
- keep polishing vs branch variants

If the user explicitly wants an evaluator-driven loop, do not stop after one pass. Continue through at least 3 meaningful iterations (or 3-4 if needed) and keep going until the evaluator is generally happy or the active rubric categories are roughly 8+.

Even when the user does not explicitly say this, default to finishing a few strong internal iterations before presenting the panel back if the work is not a one-shot and the first pass is not ready.

## Variant lane pattern

When one panel is stuck:
- keep the canonical story panels in the main lane (`1`, `2`, `3`, ...)
- create horizontal variants beside the stuck panel (`3A`, `3B`, `3C`)
- keep everything on the same page so the user can see both the main story and the active explorations
- do **not** keep overwriting the same canonical panel once the work has already had a couple of meaningful revisions and the remaining feedback is conceptual, compositional, or evaluator-driven
- if a panel has already gone through roughly 2 meaningful revision cycles and is still not landing, branch by default instead of continuing hidden rewrite churn on the canonical artboard

This preserves visible iteration history without corrupting the canonical sequence.

### Layout meaning
- main lane = the current story
- variant lane = exploration for one panel only
- evaluator = compare variants against an explicit rubric

Do not let variant lanes sprawl forever. Collapse back to one winner.

### Marking the winner / finalized panel

Use a simple state convention:
- during active comparison: keep the variants as `3A`, `3B`, `3C`
- when one variant is clearly winning but not fully locked: mark it as the **winner** in conversation or rename it with a light suffix like `- Winner`
- once the user accepts it as final for now: promote that version back to the canonical panel name (`Panel 3 - Recommended path`) and keep older variants nearby only if they are still useful for comparison

Practical default:
- canonical/main panel name = the finalized version
- variant suffixes = exploration history
- optional project note = record which variant won

This keeps the page readable and avoids leaving three competing “final” states on the same canvas.

## Panel-specific rubric

Do not rely on a generic “does this feel good?” test.

For each stuck panel, define a small rubric before comparing variants.

Typical criteria:
- hierarchy: is the main idea obvious in one glance?
- narrative clarity: does the visual advance the story clearly?
- taste/originality: does it avoid generic card soup or overbuilt sludge?
- source fidelity: are claims and quote treatments honest?
- visual integrity: no awkward overlap, clipping, hidden text, or broken spacing

Use only the criteria that matter for that panel.

## Recommended posture

- Keep the harness lightweight.
- Prefer one clear variant over many weak ones.
- Use explicit comparison, not vague memory.
- Simplify aggressively once the winning direction becomes clear.
