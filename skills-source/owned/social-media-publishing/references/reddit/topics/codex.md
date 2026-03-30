# Codex / App-Server Reddit Distribution

Use this reference when the content is primarily about Codex, Codex App Server, Codex CLI/App Server architecture, agent-loop internals, building your own Codex client, or similar builder-facing explainers.

Keep active campaign state in the project-local `resources/reddit/` folder. Keep only durable target-selection guidance here.

## Recommended subreddit order

### Strongest fit
- `r/codex` — first stop for Codex-native explainers, App Server internals, harness discussions, and builder walkthroughs.
- `r/OpenAI` — broadest high-signal OpenAI audience; good for polished explainers and visual guides.
- `r/OpenaiCodex` — strong fit for Codex-specific builder content, integration notes, and App Server material.

### Good secondary fit
- `r/ChatGPTPro` — good for power-user / workflow-heavy technical explainers when framed as a guide.
- `r/ChatGPT` — broader audience; keep framing more educational and less niche than `r/codex`.
- `r/vibecoding` — useful when the angle is builder workflow, tool composition, or practical agent-native software building.

### Contextual / optional
- `r/ClaudeCode` — only when the post is relevant to agent engineering or coding-agent architecture more broadly, not only Codex-specific usage.
- `r/singularity` — only when the post has broader AI-systems or industry-interest framing.
- `r/LocalLLaMA` — only when there is a real systems / infra / agent-runtime angle that fits the community, not just product usage.

## Simple project notes pattern for recurring Reddit distribution

For recurring topic families, keep only the project-local Reddit files that materially help future posting.
Usually that means:

- one notes file for topic-specific subreddit guidance and quirks
- the current first-comment draft if you expect to reuse it
- per-subreddit plan files only while the campaign is active
- final URLs and outcomes in the project tracker

This is useful because the same asset set often gets reposted to multiple subreddits with only small changes.

## Practical rules

- As you post and learn something real, keep self-documenting the useful bits in the project notes file instead of relying on memory.
- Reuse one canonical asset set and one canonical first-comment draft unless a subreddit clearly needs different framing.
- Prefer separate per-subreddit plan files over mutating one plan in place once more than one subreddit is involved.
- Capture flair ids and any posting quirks in the project-local notes after the first successful submission.
- If flair lookup fails but the subreddit is still worth testing, try a no-flair dry-run before giving up.
- Keep relative paths in plan files when the plans live next to the assets/comments.
- Treat subreddit-specific outcomes as campaign-local evidence, not as permanent universal truth.
