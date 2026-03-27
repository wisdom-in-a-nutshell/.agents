# LinkedIn copy defaults

Use this when repackaging something we already posted on Reddit and we want a LinkedIn version quickly.

## What belongs here

Keep only the durable heuristic here, not campaign-specific copy.

For concrete copy, store a plain text blob in the active project or campaign folder and pass it to the CLI with `--text-file`.

Do not treat LinkedIn post bodies as Markdown.

## Current default

For now, the default LinkedIn move is:

- reuse the same core text we already liked on Reddit
- remove the docs block and any raw URLs from the body
- avoid anything that LinkedIn might immediately resolve into an outbound link inside the post copy
- keep the post native-first when possible

This is a practical heuristic for reach, not a hard platform law.

## Recommended packaging shape

Keep the concrete post body as a simple text file near the campaign assets, for example:

- `capture/.../linkedin/body.txt`

That keeps:

- the reusable rule in this skill
- the actual post copy in the active campaign

## Packaging note

If the post also needs a blog link, do not force it into the main body by default.

Prefer one of these instead:

- add the link later in a comment if the surface supports it
- add the link in a follow-up manual step
- only add the link when the user explicitly wants link-first behavior
