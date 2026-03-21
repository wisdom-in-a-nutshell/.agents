---
name: subagent-workflows
description: Design and execute explicit Codex subagent workflows for the current task. Use when the user already wants subagents or parallel agent work and Codex needs to decide how to split the task, choose between built-in `explorer`, managed `external_researcher`, `worker`, or custom agents, assign bounded ownership, and synthesize the results.
---

# Subagent Workflows

## Overview

Use this skill when subagent use is already desired and the main question is how to split the current task well.

Keep the main agent focused on requirements, decisions, and final synthesis. Use subagents to handle bounded side work and return condensed results instead of raw logs or exploratory noise.

## Read Order

1. Read [references/role-split.md](references/role-split.md) to choose the right role split.
2. Read [references/prompt-patterns.md](references/prompt-patterns.md) when you need concrete delegation patterns.

## Core Rules

- If this skill is invoked, assume subagents are desired.
- Prefer read-heavy delegation first: exploration, docs verification, tests, triage, and summarization.
- Be conservative with write-heavy parallelism. Only split implementation across workers when file ownership is clear and coordination cost is low.
- Return summaries, not raw intermediate output, back to the main thread.
- Use built-in `explorer` for inside-the-repo codebase questions.
- Use managed `external_researcher` for information outside the repo/runtime.
- Use built-in `worker` or a repo-specific custom role only when delegated implementation is bounded and the write scope is clear.

## Workflow

1. Read the current task and identify which parts can be worked independently.
2. Keep urgent critical-path work local when delegation would block the next move.
3. Split off bounded side work that benefits from context isolation or parallelism.
4. Choose roles with clear boundaries.
5. Give each subagent a concrete objective, expected output shape, and ownership boundary.
6. Keep the parent thread moving on non-overlapping work while subagents run.
7. Synthesize results in the main thread and decide the next action.

## Splitting Heuristics

- Split by question when multiple independent facts need to be gathered.
- Split by specialty when local code mapping, outside verification, and implementation are distinct tasks.
- Split by file ownership only when worker write scopes are clearly separable.
- Keep shared-contract or shared-file work sequential unless there is a strong reason not to.
- Avoid spawning agents for tiny tasks that can be answered locally in one pass.

## Output Contract

- State the role split.
- State why that split is useful for the current task.
- State which parts stay on the parent thread.
- State whether to wait for all subagents before continuing.
- After subagents return, integrate their results into one concise synthesis.

## Use This Skill Well

- Prefer narrow, opinionated subagents over broad general helpers.
- Do not create custom roles just to rename a built-in unless the custom role adds real operational constraints.
- Favor stable role names and clear boundaries over large role catalogs.
- If a role split keeps causing confusion, fix the boundary in the role name or description rather than adding more prose.

## References

- `references/role-split.md`
- `references/prompt-patterns.md`
