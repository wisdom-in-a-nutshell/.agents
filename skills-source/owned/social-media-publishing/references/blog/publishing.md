# Blog post publishing

Use this when the user is not just asking for social copy, but wants the source post published first.

## Default pattern

1. Identify the owning blog repo.
2. Read that repo's `AGENTS.md` and publishing-related docs first.
3. Add the post content in the repo's canonical content location.
4. Add images or media assets in the repo's canonical public asset location.
5. If the repo has a reusable gallery or sequence component pattern, use that instead of inventing a one-off render path.
6. Make the post public in frontmatter or repo-specific metadata.
7. Run the repo's verification commands.
8. Push and confirm deployment.
9. Only then prepare link-first social distribution if the URL matters.

## What to document after doing it once

If a repo-specific workflow clearly repeats, codify it in that repo, not only in this skill.

Good homes for that durable knowledge:
- the repo's `AGENTS.md`
- a repo-local reference doc
- a repo-local project tracker when it is truly a live multi-step project

## `blog-personal` workflow

This is the concrete pattern used for Adi's personal blog at `../blog-personal/`.

### Read first

1. `AGENTS.md`
2. `docs/AGENTS.md`
3. `docs/architecture/site-architecture.md`
4. `docs/references/content-verification.md`

### Content pattern

- Source of truth lives in `content/*.mdx`
- Public assets live under `public/blog/<slug>/`
- Reusable visual explainers can use `app/components/blog/<slug>/sequence.tsx`
- Shared sequence renderer lives at `app/components/blog/image-sequence.tsx`
- Register new MDX components in `app/components/mdx.tsx`

### Visual sequence post pattern

For panel-by-panel explainers:

1. Create `content/<slug>.mdx`
2. Copy exported images to `public/blog/<slug>/`
3. Create `app/components/blog/<slug>/sequence.tsx`
4. Register the sequence in `app/components/mdx.tsx`
5. Render the sequence near the top of the post
6. Keep the surrounding text short and useful
7. Set `hidden: false`

`blog-personal` now also documents this locally in:
- `docs/references/visual-sequence-posts.md`

### Verification

Run at minimum:

```bash
pnpm run -s check:fast
pnpm run -s verify:guidelines:content
pnpm run -s build
```

### Publish

- Push the repo's default branch
- Watch the GitHub Actions deploy if the user asked for actual publication
- Confirm the expected public URL if the repo has a stable route pattern

For `blog-personal`, posts typically land at:
- `https://adithyan.io/blog/<slug>`
