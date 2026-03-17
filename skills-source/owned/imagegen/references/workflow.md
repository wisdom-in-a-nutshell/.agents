# Imagegen workflow

Use this as the default workflow for non-trivial image work.

Unless the user explicitly asks otherwise, assume this is the workflow to use.

## Default behavior

When the image task matters enough that quality and continuity matter:

1. check whether a relevant reusable style guide already exists under `styles/` in this skill
2. create or reuse a project-local working markdown file
3. record per version:
   - prompt used
   - output path
   - self-review:
     - what worked
     - what feels off
     - what should improve next
4. inspect your own generated image before handing it back
5. continue improving based on that self-review when the next fix is clear
6. use **edit** when preserving an already-good composition/style is the priority
7. use a **fresh generation** when the concept is wrong or edits keep drifting composition, aspect ratio, or clarity
8. if the direction is clear, iterate privately before showing the user the strongest version
9. keep one canonical selected output once chosen

## Why

This helps with:
- better quality before user review
- historical trace of how the image improved
- easier collaboration with the human
- less re-discovery of what already worked

## When to use

Use this workflow when:
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
