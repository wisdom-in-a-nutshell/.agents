---
name: social-media-publishing
description: Reddit-first social publishing workflow plus blog-post publication prep and LinkedIn/X posting support. Use when Codex needs to publish or distribute a blog post, video, launch, or visual explainer; prepare blog assets; decide between gallery, image, self, or link format; post to Reddit; publish the source post before distribution; or authenticate and publish LinkedIn or X posts through the channel CLI.
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

Keep durable repo-specific publishing mechanics in the owning repo and in the reference file, not in this top-level skill body.

## Reddit

Use the bundled CLI at `scripts/reddit/cli.py`.

For live commands and plan structure, read:
- `references/reddit/workflow.md`
- `references/reddit/plan-schema.md`

Core commands:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-flairs --subreddit OpenAI
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py list-submissions --max-items 20 --days 7
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/reddit/cli.py submit-plan --plan /abs/path/post-plan.json
```

The CLI supports:
- flair discovery
- gallery submission
- image submission
- link submission
- self-post submission
- optional first-comment posting
- authenticated submission history lookup

## LinkedIn

Use the bundled LinkedIn CLI at `scripts/linkedin/cli.py` for local LinkedIn publishing.

Read first:
- `references/linkedin/posting.md`
- `references/linkedin/copy.md`

Only if setup or re-auth is needed:
- `references/linkedin/auth.md`

Current supported flow:
- local OAuth authorization
- runtime/auth inspection via `status`
- identity check
- text posts
- article or URL shares
- single-image posts
- multi-image posts
- comments on posts
- machine-readable JSON output by default, plus optional `--plain` inspection mode

Core commands:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py authorize
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py whoami
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post --text-file /abs/path/body.txt --url https://example.com/post --title "Post title" --description "Short description" --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-image --text-file /abs/path/body.txt --image /abs/path/cover.jpg --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py post-images --text-file /abs/path/body.txt --image /abs/path/slide-1.jpg --image /abs/path/slide-2.jpg --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py comment --post-urn urn:li:ugcPost:... --text-file /abs/path/comment.txt --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/linkedin/cli.py --json list-posts --count 5
```

This helper uses machine-local generated secrets under `~/.secrets/linkedin/` and should stay one-user until the workflow is more mature.


## X

Use the bundled X CLI at `scripts/x/cli.py` for local X posting.

Read first:
- `references/x/posting.md`
- `references/x/copy.md`

Only if setup is still missing:
- `references/x/auth.md`

Current supported flow:
- runtime/auth inspection via `status`
- text posts
- machine-readable JSON output by default, plus optional `--plain` inspection mode

Core commands:

```bash
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py status
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post --text-file /abs/path/body.txt --dry-run
python3 ~/.agents/skills-source/owned/social-media-publishing/scripts/x/cli.py post --text-file /abs/path/body.txt
```

## Packaging Rules

- Keep the skill reusable and the campaign local.
- Keep credentials in environment variables or the user's authenticated tools, not in project files.
- Use absolute paths in ad hoc commands when possible.
- Use relative paths inside plan files when the plan lives next to the assets.
- Prefer plan files over long shell commands once the post has more than a title plus one asset.
- If the social post depends on a live blog URL, publish and verify the blog post first.

## Resources

- `scripts/reddit/cli.py`: Reddit CLI entrypoint.
- `scripts/reddit/`: self-contained Reddit helpers and models.
- `references/blog/publishing.md`: blog publication workflow before distribution.
- `references/reddit/workflow.md`: operational Reddit workflow.
- `references/reddit/plan-schema.md`: portable Reddit plan-file contract.
- `scripts/linkedin/cli.py`: local LinkedIn posting CLI.
- `references/linkedin/posting.md`: LinkedIn posting setup and usage.
- `references/linkedin/copy.md`: LinkedIn copy defaults and reusable post baselines.
- `scripts/x/cli.py`: local X posting CLI.
- `references/x/posting.md`: X posting setup and usage.
- `references/x/copy.md`: X copy defaults.
