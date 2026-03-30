# Visual review harness for Paper work

Use this only when the Paper task is visually sensitive enough that normal edit-and-check is not enough:
- social carousels
- taste-heavy explainers
- concept boards with multiple plausible directions
- panels that feel stuck after a few meaningful revisions

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

5. **Evaluator decision**
   - If the remaining question is mostly taste, hierarchy, or narrative clarity, consider an independent evaluator sub-agent.

6. **Simplify**
   - Remove anything that is not load-bearing.

## Independent evaluator rule

Use an evaluator selectively when:
- the panel has already gone through 2–3 meaningful revisions
- the creator is looping or attached to a direction
- the remaining issue is subjective rather than mechanical

Do not use an evaluator for:
- tiny spacing nudges
- obvious clipping/overflow bugs
- small text corrections

The evaluator should review screenshots, not vague descriptions.

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

## Variant lane pattern

When one panel is stuck:
- keep the canonical story panels in the main lane (`1`, `2`, `3`, ...)
- create horizontal variants beside the stuck panel (`3A`, `3B`, `3C`)
- keep everything on the same page so the user can see both the main story and the active explorations

This preserves visible iteration history without corrupting the canonical sequence.

### Layout meaning
- main lane = the current story
- variant lane = exploration for one panel only
- evaluator = compare variants against an explicit rubric

Do not let variant lanes sprawl forever. Collapse back to one winner.

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
