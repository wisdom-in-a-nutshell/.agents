---
name: paper-design
description: Collaborate in Paper using the live Paper MCP and answer practical questions about how Paper works. Use when the user wants to create or edit a Paper canvas, inspect artboards or nodes, make visual collateral in Paper, troubleshoot the Paper MCP, or ask practical product questions about Paper such as image generation, shortcuts, current limitations, or design-to-code workflow.
---

# Paper Design

## Overview

This skill is intentionally small.

The live Paper MCP already provides the real tool surface. This skill only adds the small amount of context that is useful **beyond** the MCP schema:
- what Paper is trying to be
- how to collaborate with the user in Paper cleanly
- what is true about the current Paper workflow but not obvious from the tool names
- a few verified shortcut notes
- current limitations and caveats

Start with `references/overview.md`.
If the task is taste-heavy visual iteration, evaluator loops, or variant comparison work, also load `references/visual-review-harness.md`.

## What the live MCP already gives you

Trust the live Paper MCP for the actual current tool surface.

In this environment, the Paper MCP already gives Dobby the core design-file operations:
- orient in the file
- inspect selection, nodes, tree, styles, screenshots, fonts, and JSX
- create artboards
- write HTML into the canvas
- update text, names, and styles
- duplicate and delete nodes

Do not duplicate the full tool list here unless the runtime actually changes and the skill needs a note about it.

## What this skill adds

### 1. Collaborative Paper workflow

Default flow when editing a Paper file together:
Use a review loop by default: make a change, take a screenshot, inspect for layout or clarity issues, fix them, and only present the result to the user when it is directionally solid and obvious bugs are gone.

1. orient with `get_basic_info`
2. check `get_selection` if the user may already be pointing at something
3. confirm the correct Paper page before creating anything; if the intended page is unclear or the currently open page looks wrong, explicitly ask the user to switch to the right page first
4. if the work is intended for publication, ask the primary destination early (for example Reddit, LinkedIn, X, blog, presentation) and choose artboard ratio from that
5. inspect before large edits
6. when creating multi-panel work such as a carousel, default to one artboard at a time unless the user explicitly asks for batch creation
7. make small incremental changes
8. verify visually with screenshots
9. for non-one-shot visual work, default to the visual review pattern rather than showing the first plausible version to the user
10. visual review pattern = build, screenshot review, evaluator handoff, revise, repeat
11. when using an evaluator, do not rely on the generator's memory of the critique; have the evaluator produce a short review artifact first, then synthesize from that artifact
11a. use the `visual_reviewer` sub-agent as the independent screenshot reviewer for Paper work
11b. if that reviewer is somehow unavailable in a future runtime, fall back to another independent evaluator agent rather than self-review alone
12. keep iterating until the work is directionally strong and you would personally feel good putting it in front of the user; do not bounce every intermediate version back to the human unless they explicitly want live micro-iteration
13. if the user explicitly wants evaluator-driven iteration, continue for at least 3 meaningful iterations (or 3-4 if needed) and keep going until the evaluator is generally happy or the review scores are roughly 8+ across the active rubric categories
14. for a newly created visual panel that is not a one-shot, do not present the first-pass composition as the answer before it has gone through the visual review pattern, unless the user explicitly asks to see rough first passes live

### Variant iteration lane

For taste-heavy visual work, a useful optional pattern is:
- keep the canonical story panels in one main vertical sequence (`1`, `2`, `3`, ...)
- place each new canonical panel directly below the previous canonical panel by default; do not rely on Paper's auto-placement as the intended story layout
- keep that main sequence readable on the same Paper page so the current narrative is always visible at a glance
- create horizontal variants for a single stuck panel (`3A`, `3B`, `3C`) beside that panel instead of overwriting it immediately
- use an evaluator pass to compare variants against a small explicit rubric
- once one variant clearly wins, either promote it into the main panel slot or keep the older one nearby until the user is comfortable deleting it

Use this selectively when:
- the panel concept is still unclear
- multiple visual directions are plausible
- the team wants visible iteration history instead of hidden rewrite churn

Do not turn every panel into a variant explosion. Prefer this for stuck, high-leverage panels only.

When using this pattern, make the layout logic obvious:
- main/canonical panels = the primary reading lane
- variants = adjacent exploration lane for one panel only
- evaluator rubric = explicit and panel-specific, not generic

### 2. Practical product notes

Use this skill when the user asks how Paper works, not just when editing the canvas.

Local convention for this workspace:
- if the Paper work is repo-scoped, default the Paper file name to the repo name
- use pages for workstreams or themes inside that repo
- use artboards for the individual outputs

Important non-obvious truths:
- For social or publishing collateral, determine the primary destination early because aspect ratio and layout should be chosen from the publishing surface, not guessed later. If the destination is unclear, ask.
- Paper Desktop needs to be open with a file loaded for the MCP to work
- the MCP operates on the currently open Paper file
- In the current MCP surface here, Dobby can create artboards and edit nodes in the currently open page, but does not have a dedicated page-creation/switching tool. So page choice is controlled by the page the human currently has open in Paper.
- Because of that limitation, on the first Paper action for a project or whenever page context is ambiguous, explicitly confirm the intended page with the user before creating or editing artboards.
- For multi-artboard deliverables, default to creating and iterating one artboard at a time unless the user explicitly asks for all panels or a batch upfront.
- Before showing a Paper result to the user, run at least one screenshot-based self-review pass and fix visible issues (overflow, hidden text, broken hierarchy, obvious alignment bugs) when they are easy to correct.
- A panel is not ready just because the direction feels good; core legibility and visual integrity still need to be checked explicitly in the screenshot.
- For non-one-shot visual work, the default should be the visual review pattern, not first-pass presentation.
- Do not make external evaluation the default for every tiny spacing tweak; use it when the panel is a real visual deliverable rather than a one-shot micro-fix.
- stale or long-running sessions are a common cause of MCP weirdness; restarting is often the first fix
- the Paper app appears to support AI image generation, but the current Paper MCP tool surface here does **not** expose a dedicated image-generation tool
- When writing HTML into Paper, prefer padding, gap, and explicit positioning over margins for placement; margin-based layout is more fragile in practice here.
- for agent-generated imagery, use a separate image-generation workflow and then place the result into Paper
- for icons in Paper work, use one consistent family per panel
- default conceptual/system icons to **Lucide-style outline SVGs**
- default brand/product/client marks to **official SVG logos**, not Lucide
- if the repo does not already vendor the needed icons, fetch only the specific SVGs needed and stage them locally rather than pulling a huge icon repo

### 3. Design-to-code guidance

Paper is strongest when the user wants to work close to code.

If the Paper task is specifically a polished landing page, app surface, or web UI with strong art direction, pair this skill with `frontend-skill`. Keep `paper-design` broader than web UI alone: it also covers visual collateral, concept boards, layout exploration, and other canvas-based visual work.

For design-to-code tasks, Paper's own docs suggest:
- using flex layouts and containers
- selecting the target frame clearly
- starting with smaller scoped sections before full pages

## Shortcuts and UI caveat

Paper's public docs do **not** currently appear to provide a full canonical shortcut sheet.

So:
- do not invent shortcuts
- use `references/known-shortcuts.md` for the small verified list
- say plainly when the docs are incomplete

## Resources

- `references/overview.md` — the distilled working notes
- `references/known-shortcuts.md` — the small verified shortcut list
- `references/visual-review-harness.md` — optional workflow for screenshot review, evaluator passes, and variant lanes

If a future task needs more than these notes, browse the live Paper docs/site at that time instead of keeping a giant local scrape.
