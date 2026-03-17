# Style systems for recurring image work

Use this when image work is no longer a one-off prompt and has become a reusable visual system:
- multi-panel comic
- recurring blog illustrations
- mascot-based explainer series
- brand-like illustration family
- repeated product-art direction

## Principle

Do not bury durable style decisions in one prompt thread.

When a visual direction becomes stable, promote it into:
1. a **project-local style guide** for the specific series
2. optionally, a **generic workflow note** in the skill if the pattern itself is reusable

Keep this file focused on **style canon**, not on the generic image-iteration process.
The generic process belongs in `references/working-mode.md`.
Generic prompting principles belong in `references/prompting.md`.
Copy/paste recipes belong in `references/sample-prompts.md`.

## What belongs in a project-local style guide

- series thesis / purpose
- mascot or subject canon
- style rules
- world-language rules
- do / avoid lists
- canonical selected output per panel or asset
- reusable base prompt
- naming conventions and file locations
- any user-specific taste decisions that should not be rediscovered

## What belongs in the skill

- only the generic guidance for when to create or update a style guide
- how to separate project-specific canon from skill-level guidance

Do **not** put project-specific canon into the generic skill unless it truly generalizes.

## Recommended file pattern for a comic / recurring series

At the project level:

```text
reference/comic-style-guide.md
image-1-*.md
image-2-*.md
image-3-*.md
...
reference/<final-assets>.png
```

## What a style guide should not try to do

Do not turn the style guide into:
- a generic prompting manual
- a full working log
- a copy of `references/prompting.md`
- a copy of `references/working-mode.md`

The style guide should answer:
- what this visual family is
- what makes it recognizably the same system
- what should remain stable across future generations

## Reusable base prompt pattern

When a visual system stabilizes, store a short reusable base prompt such as:

```text
Use case: illustration-story
Style/medium: <shared style>
Subject: <shared mascot or subject canon>
Constraints: preserve the same visual family as earlier approved panels
Avoid: <known failure modes>
```

Then layer only the panel-specific scene/problem/action on top.

## Decision rule

If the user says things like:
- “store this so we don’t rediscover it”
- “this is now the style”
- “document what we learned”
- “use this look going forward”

then create or update the project-local style guide immediately.
