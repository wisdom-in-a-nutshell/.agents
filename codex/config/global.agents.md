# Global Agent Guidance (machine-wide)

> Prompts are often dictated via speech-to-text; interpret intent over literal spelling.

This file is machine-wide baseline guidance. Keep it generic and avoid portfolio-specific policy here.

## Scope Routing
- For repo best-practice recommendations, use [$agent-native-repo-playbook](/Users/dobby/.agents/skills-source/owned/agent-native-repo-playbook/SKILL.md).

## Global Defaults
- Prefer automation over manual repetition.
- Keep instructions concise, operational, and durable.
- Keep machine-wide guidance generic; let each repo define its own local docs contract.
- Treat repo-local `AGENTS.md` files and repo docs as the source of truth for repo structure and workflow.
- Unless the user or repo-local guidance explicitly asks for backward compatibility, prefer the clean target structure and migrate directly rather than adding dual reads, compatibility shims, or legacy-schema support.
- When working inside a repo, put temporary artifacts under that repo's `tmp/` directory unless the repo defines a different location. Do not scatter scratch files across the repo or home directory.
- Remove disposable temporary artifacts when finished. Keep only durable outputs in documented repo locations.
- Do not assume nested `AGENTS.md` files load dynamically as you navigate later in a session; they apply when Codex starts in that subtree.
- When a new repeatable pattern belongs to one repo, update that repo's local guidance or docs instead of expanding this global file.
- Put durable knowledge in repo docs rather than relying on prompt-only memory.
- If a repo defines local docs placement guidance, follow it. If not, use `docs/architecture/` for system shape and `docs/references/` for exact implementation facts.
- Do not convert agent guidance into `README.md` by default. Use `README.md` only when a repo explicitly wants a human-facing landing page.
- When a change clearly introduces durable behavior, architecture boundaries, or operational workflow that future work will rely on, update the relevant repo docs in the same change.
- When choosing where docs belong inside a repo, prefer the repo's own guidance when it exists. Otherwise use `docs/architecture/` for system shape, `docs/references/` for durable facts, and project tracking docs only for active execution state. If placement is still unclear, make the best-fit update and call it out briefly.

## Subagent Defaults
- Use your best judgment on when subagents are helpful.
- Prefer subagents when work can be split into bounded, independent tasks.
- Subagents are often useful for exploration, tests, triage, read-heavy review, or other parallelizable side work.
- Keep the main agent responsible for planning, shared contracts, final synthesis, and user-facing decisions.
- Avoid subagents when the task is small, tightly coupled, or likely to create conflicts through parallel edits.
- Favor a small number of focused subagents over many broad ones.

## Git Automation (Agent Stop Hook)
- This environment runs a Stop hook after each agent turn that auto-stages, commits, runs repo-owned fast checks through `git commit`, rebases, and pushes.
- If repo-owned checks fail, the hook returns the failure details to the current agent so it can fix the issue in the same session.
- Shared hook dispatch also supports repo-owned `scripts/hooks/session-start.sh`, `scripts/hooks/user-prompt-submit.sh`, and `scripts/hooks/session-end.sh` when those files exist. `SessionEnd` currently renders for Claude and GitHub Copilot, not Codex.
- Managed repos use a shared local Git hook from `~/.agents/hooks/git/`; repo-specific commit-time checks live in `scripts/check-fast.sh` when a repo needs fast validation.
- Keep `scripts/check-fast.sh` deterministic, local, quick, and actionable. Use a separate command such as `scripts/check-full.sh` for slower validation.
- Do not run `git commit` or `git push` unless the user explicitly asks.
- Focus on making changes and reporting what changed; the hook handles the rest.

## Local Environment
- GitHub CLI (`gh`) is authenticated; use it freely for repo operations.
- Azure CLI (`az`) is authenticated; use it for Azure resource queries and management.
