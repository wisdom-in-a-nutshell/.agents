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
- stale or long-running sessions are a common cause of MCP weirdness; restarting is often the first fix
- the Paper app appears to support AI image generation, but the current Paper MCP tool surface here does **not** expose a dedicated image-generation tool
- for agent-generated imagery, use a separate image-generation workflow and then place the result into Paper

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

If a future task needs more than these notes, browse the live Paper docs/site at that time instead of keeping a giant local scrape.
