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
- For LinkedIn on a fresh boot, prefer `scripts/linkedin/cli.py status` before guessing what is configured or permitted.

## Write-back rule

When a channel workflow becomes repeatable, add or update a reference under the matching channel folder and mention it in `SKILL.md`.
