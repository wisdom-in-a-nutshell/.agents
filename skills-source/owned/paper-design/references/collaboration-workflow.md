# Paper collaboration workflow

Load this when you are actively editing the canvas.

## Default editing flow

1. orient with `get_basic_info`
2. check `get_selection` if the user may already be pointing at something
3. confirm the correct page if page context is ambiguous
4. if the work is for publication, ask the primary destination early so artboard ratio is chosen from the real surface
5. inspect before large edits
6. make small incremental changes
7. verify with screenshots after meaningful edits
8. review your own work before showing it to the user

## Default review behavior

Self-review is the normal workflow, not a special escalation.

For each meaningful edit:
- take a screenshot
- check hierarchy, clipping, overlap, hidden text, weak contrast, and broken spacing
- compare against neighboring canonical panels when the work is part of a sequence
- fix the obvious issues before presenting it

If a clear improvement is visible, keep going without asking the user whether to do “one more pass.” Human time is more expensive than agent iteration. Only interrupt when:
- the remaining issue depends on a real taste choice the user must make
- the next step is risky, destructive, or identity-representing
- you are blocked by missing context or by the tool/runtime

Only skip this when the user explicitly wants rough live iteration.

## Multi-panel work

- Default to one artboard at a time unless the user explicitly wants a batch.
- Place each new canonical panel directly below the previous canonical panel.
- Do not treat Paper auto-placement as intended story order.
- Keep the main story readable in one vertical lane.

## Presentation gate

- Do not show the first plausible version of a non-one-shot visual deliverable.
- Fix obvious issues before presenting: clipping, overlap, crushed hierarchy, hidden text, low-contrast details, broken spacing.
- A panel is not ready just because the direction feels good; screenshot review still has to clear the legibility bar.
- When the work needs a heavier loop than normal self-review, escalate into `references/visual-review-harness.md`.

## Continuity checks for a multi-panel series

When a panel belongs to an existing series, compare it against the neighboring canonical panels for:
- typography continuity
- connector language
- internal label style
- icon visibility and size
- overall visual weight

Do not judge a panel only in isolation if it lives inside a sequence.
