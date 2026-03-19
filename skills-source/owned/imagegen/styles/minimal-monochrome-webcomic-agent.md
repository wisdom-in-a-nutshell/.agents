# Minimal Monochrome Webcomic - Digital Agent Style Guide

Purpose: reusable visual guideline for simple black-and-white explainer comics and diagram-comic illustrations built around a small digital-agent mascot.

Directional reference:
- xkcd-inspired in spirit: minimal, monochrome, sparse, hand-drawn, technical, human
- do not rely only on the reference name in prompts; prefer explicit visual traits

## Best use cases

- explainer comics
- blog illustrations
- technical diagram-comic hybrids
- recurring mascot-based visual stories

## Visual identity

### Overall style
- black-and-white only
- minimalist hand-drawn webcomic energy
- thin slightly imperfect linework
- lots of white space
- calm diagram-comic hybrid
- understated technical humor
- readable at a glance

Avoid:
- glossy infographic polish
- cyberpunk excess
- dramatic sci-fi rendering
- painterly shading
- corporate SaaS illustration vibe

### Mascot
Use one consistent digital-agent mascot across a set when continuity matters.

Canonical reference asset inside this skill:
- `styles/assets/agent-mascot-reference.png` -> primary cute outlined mascot reference for preserving the approved comic character across generations

Default mascot:
- rounded-square white body
- black outline
- simple dark oval eyes
- small side tabs
- short legs
- cute, minimal, readable
- should feel like a little software agent, not a generic person

Avoid:
- visor-face robot drift
- humanoid stick figures
- heavy black silhouette unless intentionally needed
- over-detailed armor or gadget clutter

## World language

The environment should feel digitally navigable rather than purely decorative.

Good elements:
- files
- folders
- windows
- signs
- paths
- codebase landmarks
- tiled or panel-like digital surfaces
- simple external nodes like apps, docs, or connectors

Avoid:
- overly literal outdoor scenery unless lightly used as metaphor
- natural mountains/grass dominating the frame
- dense clutter
- generic empty abstraction with no readable structure

## Reusable prompt base

Use this as the shared style base:

```text
Use case: illustration-story
Style/medium: black-and-white only, minimalist hand-drawn webcomic energy, thin slightly imperfect linework, lots of white space, calm diagram-comic hybrid, understated technical humor
Subject: a small digital-agent mascot with a rounded-square white body, black outline, simple dark oval eyes, small side tabs, and short legs
Constraints: preserve the same visual family and mascot style across the set; keep the world readable and uncluttered; original image only; no watermark
Avoid: glossy infographic polish, cyberpunk excess, heavy clutter, visor-face robot drift, generic stick figures, border frames, corporate SaaS illustration vibe
```

## Prompt reminders

- state the meaning of the image, not just the objects in it
- keep the emotional shift explicit
- keep the art text-light whenever possible
- preserve the same mascot and world language across related panels
- when mascot continuity matters, use `styles/assets/agent-mascot-reference.png` as the primary explicit input reference instead of relying only on prompt wording
- if a style name is used as a directional cue, still spell out the actual traits

## What this guide is for

Use this guide when the user wants a recurring visual family with:
- a simple monochrome comic look
- a technical or builder-friendly tone
- a reusable digital mascot

If a project later develops stronger project-specific rules on top of this base, store those separately in a project worklog or a new reusable style guide only if they are worth reusing elsewhere.
