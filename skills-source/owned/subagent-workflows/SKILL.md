---
name: subagent-workflows
description: Design and apply explicit Codex subagent workflows for parallel, bounded work. Use when deciding whether to spawn subagents, choosing between built-in `explorer`, managed `external_researcher`, `worker`, or custom agents, drafting delegation prompts, reviewing subagent role splits, or encoding repo-specific subagent conventions and prompt patterns.
---

# Subagent Workflows

## Overview

Use this skill when you want a durable playbook for explicit Codex subagent use: when to delegate, how to split work, how to keep the parent thread clean, and how to map work onto built-in and custom roles.

Keep the main agent focused on requirements, decisions, and final synthesis. Use subagents to handle bounded side work and return condensed results instead of raw logs or exploratory noise.

## Read Order

1. Read [references/role-split.md](references/role-split.md) to choose the right role split.
2. Read [references/prompt-patterns.md](references/prompt-patterns.md) when you need prompt templates or concrete delegation patterns.
3. Fetch current official Codex docs when exact current built-in roles, config semantics, or model guidance matters.

## Core Rules

- Subagents are explicit. Do not assume delegation unless the user asks for subagents or parallel agent work.
- Prefer read-heavy delegation first: exploration, docs verification, tests, triage, and summarization.
- Be conservative with write-heavy parallelism. Only split implementation across workers when file ownership is clear and coordination cost is low.
- Return summaries, not raw intermediate output, back to the main thread.
- Keep one orchestrator. For long-running work under `$project`, the top-level run owns `docs/projects/<project>/tasks.md`; subagents must not edit the tracker directly.
- Use built-in `explorer` for inside-the-repo codebase questions.
- Use managed `external_researcher` for information outside the repo/runtime.
- Use built-in `worker` or a repo-specific custom role only when delegated implementation is bounded and the write scope is clear.

## Workflow

1. Decide whether the work benefits from parallelism or context isolation.
2. Decide which parts stay local on the parent thread and which parts can be delegated independently.
3. Choose roles with clear boundaries.
4. Write a delegation prompt that names the split, whether to wait for all agents, and the expected output shape.
5. Keep the parent thread moving on non-overlapping work while subagents run.
6. Synthesize results in the main thread and update durable project state there if needed.

## Use This Skill Well

- Prefer narrow, opinionated subagents over broad general helpers.
- Do not create custom roles just to rename a built-in unless the custom role adds real operational constraints.
- When exact current product behavior matters, verify against current official docs instead of relying only on this skill.
- Favor stable role names and clear boundaries over large role catalogs.
- If a role split keeps causing confusion, fix the boundary in the role name or description rather than adding more prose.

## Fetch First For

- Current built-in role list and wording
- Current `agents.<name>` config semantics
- Current model recommendations for subagents
- Any question phrased as latest, current, official, or exact

## References

- `references/role-split.md`
- `references/prompt-patterns.md`
