# Agent Engineering 101 - Comic Style Guide

Purpose: preserve the visual system behind this comic series so future image work can reuse it without re-discovering the same decisions.

Source project:
- `capture/content/agent-engineering-101/`

## Series thesis

This is a visual story about helping a capable agent do its best work in a digital world.

Core arc:
- confused
- supported
- oriented
- capable
- connected

Deeper thesis:
- the agent is not weak; it is under-supported
- good agent engineering is environment design
- `AGENTS.md` improves navigation
- `SKILLS` load on-demand capability
- `MCP` connects the agent to the live world beyond the local map

## Visual identity

### Overall style
- black-and-white only
- minimalist hand-drawn webcomic energy
- thin slightly imperfect linework
- lots of white space
- calm diagram-comic hybrid
- understated technical humor
- avoid glossy infographic polish

### Mascot
Use one consistent mascot across the whole set.

Desired character:
- rounded-square white body
- black outline
- simple dark oval eyes
- small side tabs
- short legs
- cute, minimal, readable
- should feel like a little digital agent, not a generic stick figure

Avoid:
- visor-face robot drift
- humanoid stick figures
- heavy black silhouette unless there is a specific reason
- over-detailed gear or sci-fi armor

### World language
The environment should feel like a navigable digital landscape:
- files
- folders
- windows
- codebase landmarks
- tiled/panel-like digital surfaces

Avoid:
- overly literal outdoor scenery
- natural mountains or grassy hiking trails unless lightly borrowed as metaphor
- generic SaaS illustration vibe

## Narrative structure

### Panel 1 - Problem
Canonical:
- `capture/content/agent-engineering-101/reference/agents-wayfinding-v5.png`

Meaning:
- the agent is dropped into a digital world and is under-oriented

### Panel 2 - Toolkit preview
Canonical:
- `capture/content/agent-engineering-101/reference/agents-toolkit-v3.png`

Meaning:
- the three-part support system becomes visible:
  - `AGENTS.md`
  - `SKILLS`
  - `MCP`

### Panel 3 - `AGENTS.md`
Canonical:
- `capture/content/agent-engineering-101/reference/agents-agentsmd-v11.png`

Meaning:
- nested `AGENTS.md` waypoints progressively disclose how to navigate deeper into the system

### Panel 4 - `SKILLS`
Canonical:
- `capture/content/agent-engineering-101/reference/agents-skills-v4.png`

Meaning:
- the route is known, but the agent needs a temporary loaded capability to get through a specific obstacle

### Panel 5 - `MCP`
Current best working version:
- `capture/content/agent-engineering-101/reference/agents-mcp-v10.png`

Meaning:
- the local map is not enough; the agent now connects to live outside systems and current conditions

Note:
- MCP panel is conceptually approved as "good enough," but is still the weakest/most drift-prone panel in the set.

## Reusable base prompt

Use this as the shared style base for future panels in this series:

```text
Use case: illustration-story
Asset type: blog post supporting illustration
Style/medium: black-and-white only, minimalist hand-drawn webcomic energy, thin slightly imperfect linework, lots of white space, calm diagram-comic hybrid, understated technical humor
Subject: the same established digital agent mascot from the earlier approved panels, with a rounded-square white body, black outline, simple dark oval eyes, small side tabs, and short legs
Constraints: preserve the same visual family and mascot style as the earlier approved panels; keep the world digital, readable, and uncluttered; keep the image original; no watermark
Avoid: glossy infographic polish, cyberpunk excess, heavy clutter, visor-face robot drift, generic stick figures, border frames, corporate SaaS illustration vibe
```

## Series-specific prompt reminders

- state the meaning of the panel, not just the objects in it
- keep the emotional shift of the panel explicit
- keep the art text-light whenever possible
- preserve the same mascot and world language across panels

## Panel-specific conceptual shorthand

- `AGENTS.md` = where to go
- `SKILLS` = how to get through this part
- `MCP` = what is true out there right now

## Future use

If we create more visuals in this family:
- start from this guide
- reuse the same mascot and world language
- add new panels via new `image-N-*.md` files
- only change the visual system deliberately, not accidentally
