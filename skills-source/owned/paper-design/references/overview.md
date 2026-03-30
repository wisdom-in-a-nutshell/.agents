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
- For icons, keep one icon family per panel. Use Lucide-style outline SVGs for conceptual/system icons and official SVGs for brands/products/clients.
- There is no vendored general-purpose icon library in this repo right now. Fetch or stage only the specific SVGs you need instead of pulling a whole icon repo by default.

## Collaboration workflow

The step-by-step editing workflow now lives in:
- `references/collaboration-workflow.md`

Keep this file focused on Paper product truths and local conventions.

## Design-to-code note

When Paper is being used as a bridge to code, results are better when the design is already structured like code:
- clear containers
- flex layouts
- explicit target frames
- smaller scoped sections first

## Keep this note small

If something is already obvious from the live MCP schema, do not duplicate it here.
If something is only needed rarely, look it up live instead of bloating this note.


## Visual review workflows

For taste-heavy visual iteration, evaluator review, and variant lanes, see:
- `references/visual-review-harness.md`
