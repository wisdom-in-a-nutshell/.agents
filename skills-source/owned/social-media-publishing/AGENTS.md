# AGENTS.md - social-media-publishing

Use this skill for reusable publishing workflows that should travel across repos.

## What belongs here

- channel automation and helper CLIs
- channel-specific setup notes
- durable publishing heuristics that are not tied to one repo

## What does not belong here

- campaign state for a single launch or post
- repo-local blog architecture details
- secrets themselves

## First places to look

- skill contract -> `SKILL.md`
- blog source-publishing flow -> `references/blog/publishing.md`
- Reddit flow -> `references/reddit/workflow.md`
- LinkedIn setup and copy defaults -> `references/linkedin/`
- X setup and copy defaults -> `references/x/`
- YouTube upload flow -> `references/youtube/posting.md`
- Instagram setup and dry-run flow -> `references/instagram/posting.md`
- TikTok setup and dry-run flow -> `references/tiktok/posting.md`
- For LinkedIn on a fresh boot, prefer `scripts/linkedin/cli.py status` before guessing what is configured or permitted.
- For X on a fresh boot, prefer `scripts/x/cli.py status` before guessing what is configured or permitted.
- For YouTube on a fresh boot, prefer `scripts/youtube/cli.py status` before guessing Modal/runtime configuration.
- For Instagram on a fresh boot, prefer `scripts/instagram/cli.py status` before guessing Meta account/API configuration.
- For TikTok on a fresh boot, prefer `scripts/tiktok/cli.py status` before guessing TikTok app/OAuth/audit configuration.

## Write-back rule

When a channel workflow becomes repeatable, add or update a reference under the matching channel folder and mention it in `SKILL.md`.
