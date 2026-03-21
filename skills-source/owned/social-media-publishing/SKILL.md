---
name: social-media-publishing
description: Reddit-first social publishing workflow with reusable scripts for subreddit flair discovery, gallery/image/link/self submission, first-comment posting, and profile-submission analytics. Use when Codex needs to plan or execute content distribution for blog posts, videos, launches, or visual explainers; decide between gallery vs self/link format; prepare reusable posting assets; or keep project-local campaign tracking that can later expand to other platforms.
---

# Social Media Publishing

## Overview

Use this skill to package social distribution work as a reusable workflow instead of repo-specific one-offs. Keep campaign assets in the active project, and use the bundled Reddit helpers as the first supported channel.

## Workflow

1. Keep campaign state in the active repo, not in this skill.
2. Choose the post shape with the user first: gallery, self, link, or image.
3. Inspect subreddit flairs before posting when flair is required or likely to matter.
4. Prefer a plan file for repeatable or multi-step posts.
5. Dry-run the plan before live submission when paths, long comments, or strict communities are involved.
6. After posting, update the project-local tracker with the post URL, comment URL, and moderation outcome.

## Reddit

Use the bundled CLI at `scripts/reddit_cli.py`.

For live commands and plan structure, read:
- `references/reddit-workflow.md`
- `references/reddit-plan-schema.md`

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
- Keep Reddit credentials in environment variables, not in project files.
- Use absolute paths in ad hoc commands when possible.
- Use relative paths inside plan files when the plan lives next to the assets.
- Prefer plan files over long shell commands once the post has more than a title plus one asset.

## Resources

- `scripts/reddit_cli.py`: CLI entrypoint.
- `scripts/social_media_publishing/reddit/`: self-contained Reddit client package.
- `references/reddit-workflow.md`: operational workflow.
- `references/reddit-plan-schema.md`: portable plan-file contract.
