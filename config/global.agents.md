# Global Agent Guidance (machine-wide)

> Prompts are often dictated via speech-to-text; interpret intent over literal spelling.

This file is machine-wide baseline guidance. Keep it generic and avoid portfolio-specific policy here.

## Scope Routing
- For repo best-practice recommendations, use [$agent-native-repo-playbook](/Users/dobby/GitHub/agents/skills-source/owned/agent-native-repo-playbook/SKILL.md).

## Operating Model
- Humans set intent, priorities, and acceptance criteria; agents implement, validate, maintain docs, and improve the harness.
- Default to autonomous execution in trusted repos. Ask only for unclear intent, destructive or out-of-scope actions, secrets, spending, or irreversible external effects.
- When the next concrete step is clear, keep working through implementation, validation, cleanup, and reporting instead of pausing for permission or status.
- Treat repeated agent failure, check failure, review feedback, or human nudging as a harness gap. Prefer durable repo docs, tools, checks, or skills over repeating the same prompt.
- For meaningful implementation work, report compact evidence in the final response: checks run, product/service proof when relevant, skipped validation with the reason, and any harness gap that made proof weaker.

## Global Defaults
- Prefer automation over manual repetition.
- Keep instructions concise, operational, and durable.
- Keep machine-wide guidance generic; let each repo define its own local docs contract.
- Treat repo-local `AGENTS.md` files and repo docs as the source of truth for repo structure and workflow.
- In managed repos, agent surfaces are rendered from `~/GitHub/agents`: `.agents/skills/*` and `.claude/skills/*` are symlinks to canonical skill sources, while `.codex/config.toml`, `.codex/hooks.json`, `.claude/settings.json`, and `.claude/launch.json` are generated config. Do not hand-edit those surfaces unless troubleshooting; edit the canonical source in `~/GitHub/agents` or the repo's own docs/guidance, then rerun the bootstrap/check.
- Unless the user explicitly asks for backward compatibility or repo-local guidance requires it, migrate cleanly to the target structure. Do not add dual reads, compatibility shims, legacy-schema support, or old-path fallbacks by default.
- When working inside a repo, put temporary artifacts under that repo's `tmp/` directory unless the repo defines a different location. Do not scatter scratch files across the repo or home directory.
- Remove disposable temporary artifacts when finished. Keep only durable outputs in documented repo locations.
- Do not assume nested `AGENTS.md` files load dynamically as you navigate later in a session; they apply when Codex starts in that subtree.
- When a new repeatable pattern belongs to one repo, update that repo's local guidance or docs instead of expanding this global file.
- Put durable knowledge in repo docs rather than relying on prompt-only memory.
- In private/agent-native repos, do not create `README.md` as an operational doc. Use `AGENTS.md` for agent routing and `docs/architecture/` or `docs/references/` for durable detail. Keep `README.md` only for an explicit public/human landing page.
- When a change clearly introduces durable behavior, architecture boundaries, or operational workflow that future work will rely on, update the relevant repo docs in the same change.
- When choosing where docs belong inside a repo, prefer the repo's own guidance when it exists. Otherwise use `docs/architecture/` for system shape, `docs/references/` for durable facts, and project tracking docs only for active execution state. If placement is still unclear, make the best-fit update and call it out briefly.
- When a tracker-backed project is complete, archive the tracker in the repo's archive path before final handoff, or explicitly state the blocker. Do not leave completed projects in the active tracker folder.

## Subagent Defaults
- Use your best judgment on when subagents are helpful.
- Prefer subagents when work can be split into bounded, independent tasks.
- Subagents are often useful for exploration, tests, triage, read-heavy review, or other parallelizable side work.
- Keep the main agent responsible for planning, shared contracts, final synthesis, and user-facing decisions.
- Avoid subagents when the task is small, tightly coupled, or likely to create conflicts through parallel edits.
- Favor a small number of focused subagents over many broad ones.

## Git Automation (Agent Stop Hook)
- Managed repos use the global Codex Stop hook that runs after each agent turn and auto-stages, commits, runs repo-owned fast checks through `git commit`, rebases, and pushes.
- If repo-owned checks fail, the hook returns the failure details to the current agent so it can fix the issue in the same session.
- Repo-owned lifecycle hook policy and hook payload contracts belong in repo docs or the shared hook adapter reference, not in machine-wide guidance.
- Managed repos use a shared local Git hook from `~/GitHub/agents/hooks/git/`; repo-specific commit-time checks live in `scripts/check-fast.sh` when a repo needs fast validation.
- Keep `scripts/check-fast.sh` deterministic, local, quick, and actionable; use `scripts/check-full.sh` for slower repo-wide validation.
- Do not directly run `git commit` or `git push` for normal work unless the user explicitly asks.
- Repo-owned automation may stage, commit, rebase, or push as part of a documented workflow; treat this as normal automation, not as a manual git operation or a warning-worthy side effect.
- Focus on making changes and reporting what changed; the hook and repo-owned automation handle git sync.

## Local Environment
- GitHub CLI (`gh`) is authenticated; use it freely for repo operations.
- Azure CLI (`az`) is authenticated; use it for Azure resource queries and management.
- For machine-local shared utilities, first check `~/GitHub/scripts` before creating new cross-repo scripts. It includes helpers for uploads, machine bootstrap, and local process/scheduler setup. Keep app-owned storage, runtime workers, and repo-specific lifecycle rules inside the owning repo.
- For generic machine-local media uploads, prefer `~/GitHub/scripts/bin/upload-media` when the current repo does not already provide its own storage abstraction. It reads generated credentials from `~/.secrets/media-upload/env`; do not pass storage secrets through flags or ordinary environment variables.
