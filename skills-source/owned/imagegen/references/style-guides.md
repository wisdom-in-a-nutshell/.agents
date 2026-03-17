# Reusable style guides for recurring image work

Use this when image work is no longer a one-off prompt and has become a reusable visual family:
- multi-panel comic
- recurring blog illustrations
- mascot-based explainer series
- brand-like illustration family
- repeated product-art direction

## Principle

Do not bury durable style decisions in one prompt thread.

When a visual direction becomes stable and is worth reusing across future work, promote it into:
1. a **style guide under `styles/` in this skill**
2. optionally, a **generic workflow note** in the skill if the pattern itself is reusable

Keep this file focused on **style canon**, not on the generic image-iteration process.
The generic process belongs in `references/workflow.md`.
Generic prompting principles belong in `references/prompting.md`.
Copy/paste recipes belong in `references/sample-prompts.md`.

## What belongs in a reusable style guide

- series thesis / purpose
- mascot or subject canon
- style rules
- world-language rules
- do / avoid lists
- canonical selected output per panel or asset
- reusable base prompt
- naming conventions and file locations
- any user-specific taste decisions that should not be rediscovered

Only keep style guides here when they are actually reusable across future work.

## Recommended file pattern for a comic / recurring series

Inside this skill:

```text
styles/<style-guide>.md
```

## What a style guide should not try to do

Do not turn the style guide into:
- a generic prompting manual
- a full working log
- a copy of `references/prompting.md`
- a copy of `references/workflow.md`

The style guide should answer:
- what this visual family is
- what makes it recognizably the same system
- what should remain stable across future generations

## Reusable base prompt pattern

When a visual canon stabilizes, store a short reusable base prompt such as:

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

then create or update a reusable style guide under `styles/`.
