# Imagegen working mode

Use this as the default operating pattern for non-trivial image work.

Unless the user explicitly asks otherwise, assume this is the working mode to use.

This is distinct from a **style system**:
- **working mode** = how to generate, inspect, review, iterate, and document
- **style system** = the reusable visual canon for a specific series or brand

## Default behavior

When the image task matters enough that quality and continuity matter:

1. create or reuse a project-local working markdown file
2. record per version:
   - prompt used
   - output path
   - self-review:
     - what worked
     - what feels off
     - what should improve next
3. inspect your own generated image before handing it back
4. if the direction is clear, iterate privately before showing the user the strongest version
5. keep one canonical selected output once chosen

## Why

This helps with:
- better quality before user review
- historical trace of how the image improved
- easier collaboration with the human
- less re-discovery of what already worked

## When to use

Use working mode when:
- the user wants polished outputs
- the image is part of a deliverable
- there will probably be multiple iterations
- continuity matters across turns

## When not to overdo it

Do not force a heavy markdown worklog for:
- trivial one-off edits
- disposable experiments
- quick “show me some rough options” requests

## Minimal self-review template

```md
## Self-review - Version N

What worked:
- ...

What feels off:
- ...

What should improve next:
- ...
```
