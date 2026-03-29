# Paper working notes for Dobby

This is the only Paper reference note that should normally be loaded.

## What Paper is

Paper is a connected visual canvas built close to web standards. The useful mental model is:
- canvas for spatial thinking
- collaborative surface for human + agent work
- closer to HTML/CSS/React than a traditional static mock tool

## Local file/page convention

When Paper work is mostly tied to one git repo, default to this structure:
- Paper file name = repo name
- pages = major themes or workstreams in that repo
- artboards = individual diagrams, visuals, mockups, or screens

Example for this repo:
- file: `adi`
- pages: `agent architecture`, `health`, `blog visuals`

Use a broader file name only when the Paper file is intentionally cross-repo or general-purpose.

## Current MCP audit

The live MCP already covers the real tool surface.

What matters most in practice:
- file orientation
- selection / node inspection
- screenshots and verification
- artboard creation
- HTML-to-canvas writing
- text/style/name updates
- duplication and deletion

So the skill should **not** try to restate the whole MCP schema.

## The useful extra facts beyond the MCP schema

- Paper Desktop must be open with a file loaded; that starts the MCP server.
- The MCP acts on the currently open Paper file.
- If Paper feels disconnected or stale, restarting the Paper app and/or the agent session is often the first fix.
- The Paper app appears to support AI image generation, but the current Paper MCP tool surface here does not expose a dedicated image-generation tool.
- For agent-generated images, use a separate image-generation workflow and then place the result into Paper.
- Paper's public docs are sparse on shortcuts; use the verified notes only.

## Good default collaboration flow

When the user is making collateral for a channel or publication surface, ask the primary destination early (for example Reddit, LinkedIn, X, blog, presentation). Use that to choose the initial artboard ratio instead of defaulting blindly. If the destination is still unclear, ask before laying out the canvas.

Because the MCP only acts on the currently open page, confirm the intended page explicitly at the start of a project or whenever there is page ambiguity. If the wrong page is open, ask the user to switch before creating artboards.

For multi-panel work like carousels, do not create the whole set by default. Start with the first artboard, iterate with the user, and only create additional panels as the work progresses unless the user explicitly asks for a batch.

Default review behavior: after each meaningful Paper edit, take a screenshot and inspect it. Keep iterating until the direction is coherent and obvious bugs are fixed before asking the user for feedback.

Do not stop the review loop just because the overall idea is promising. If a core element is still visibly overlapped, crushed, clipped, misaligned, or hard to read in the screenshot, keep fixing it before presenting the panel as ready.

1. inspect the current file first
2. work on the selected node/frame when possible
3. make small visual moves, not giant blind rewrites
4. verify after changes with screenshots
5. if the user asks how Paper works, answer from these notes first and only go to the live site when needed

## Design-to-code note

When Paper is being used as a bridge to code, results are better when the design is already structured like code:
- clear containers
- flex layouts
- explicit target frames
- smaller scoped sections first

## Keep this note small

If something is already obvious from the live MCP schema, do not duplicate it here.
If something is only needed rarely, look it up live instead of bloating this note.


## Review escalation
- Start with screenshot-based self-review.
- If visual iteration stalls or the question becomes mainly one of taste, hierarchy, or narrative clarity, consider an independent evaluator sub-agent to review screenshots.
- Keep this selective; obvious mechanical fixes should still be handled locally without extra coordination overhead.
