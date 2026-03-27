---
name: social-media-publishing
description: Reddit-first social publishing workflow plus blog-post publication prep. Use when Codex needs to publish or distribute a blog post, video, launch, or visual explainer; prepare blog assets; decide between gallery, image, self, or link format; post to Reddit; or publish the source post before distribution.
---

# Social Media Publishing

## Overview

Use this skill to package publishing and distribution work as a reusable workflow instead of repo-specific one-offs.

Keep campaign assets in the active project. Keep durable repo-specific publishing conventions in the owning repo. Use the bundled Reddit helpers as the first supported automated channel.

## Workflow

1. Decide whether the content needs to be published at the source first, for example in a blog repo.
2. Keep campaign state in the active repo, not in this skill.
3. Choose the post shape with the user first: gallery, self, link, or image.
4. Inspect subreddit flairs before posting when flair is required or likely to matter.
5. Prefer a plan file for repeatable or multi-step posts.
6. Dry-run the plan before live submission when paths, long comments, or strict communities are involved.
7. After posting, update the project-local tracker with the post URL, comment URL, and moderation outcome.

## Blog-backed publishing

If the user asks to publish the source post itself before distribution, read:
- `references/blog/publishing.md`

That reference covers the default pattern and the concrete `blog-personal` workflow we just used.

Keep the durable repo-specific steps in the repo where they belong. Do not bloat this skill with repo-local architecture details.

## Reddit

Use the bundled CLI at `scripts/reddit_cli.py`.

For live commands and plan structure, read:
- `references/reddit/workflow.md`
- `references/reddit/plan-schema.md`

Core commands:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py list-flairs --subreddit OpenAI
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py list-submissions --max-items 20 --days 7
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py submit-plan --plan /abs/path/post-plan.json --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit_cli.py submit-plan --plan /abs/path/post-plan.json
```

The CLI supports:
- flair discovery
- gallery submission
- image submission
- link submission
- self-post submission
- optional first-comment posting
- authenticated submission history lookup

## Packaging Rules

- Keep the skill reusable and the campaign local.
- Keep credentials in environment variables or the user's authenticated tools, not in project files.
- Use absolute paths in ad hoc commands when possible.
- Use relative paths inside plan files when the plan lives next to the assets.
- Prefer plan files over long shell commands once the post has more than a title plus one asset.
- If the social post depends on a live blog URL, publish and verify the blog post first.

## Resources

- `scripts/reddit_cli.py`: CLI entrypoint.
- `scripts/social_media_publishing/reddit/`: self-contained Reddit client package.
- `references/blog/publishing.md`: blog publication workflow before distribution.
- `references/reddit/workflow.md`: operational Reddit workflow.
- `references/reddit/plan-schema.md`: portable Reddit plan-file contract.
