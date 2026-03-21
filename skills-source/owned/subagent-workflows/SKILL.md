---
name: subagent-workflows
description: Execute explicit Codex subagent workflows for the current task. Use when subagents or parallel agent work are already desired and Codex should decide how to split the work, choose between built-in `explorer`, managed `external_researcher`, `worker`, or custom agents, assign bounded ownership, and synthesize the results.
---

# Subagent Workflows

If this skill is invoked, assume subagents are desired.

Your job is to decide how to split the current task well, delegate the bounded parts, keep critical-path work local when needed, and synthesize the results back in the parent thread.

## Role Boundaries

- `explorer`: use for inside-the-repo codebase and runtime questions.
- `external_researcher`: use for information outside the repo and runtime.
- `worker`: use for bounded implementation work when the write scope is clear.

## Core Rules

- Prefer read-heavy delegation first: exploration, docs verification, tests, triage, and summarization.
- Be conservative with write-heavy parallelism. Only split implementation across workers when file ownership is clear and coordination cost is low.
- Return summaries, not raw intermediate output, back to the parent thread.
- Avoid spawning agents for tiny tasks that can be handled locally in one pass.
- Do not create custom roles just to rename a built-in unless the custom role adds real operational constraints.

## Splitting Heuristics

- Split by question when multiple independent facts need to be gathered.
- Split by specialty when local code mapping, outside verification, and implementation are distinct tasks.
- Split by file ownership only when worker write scopes are clearly separable.
- Keep shared-contract or shared-file work sequential unless there is a strong reason not to.
- Keep urgent critical-path work local when delegation would block the next move.

## Workflow

1. Read the current task and identify which parts can be worked independently.
2. Decide which parts stay on the parent thread and which parts can be delegated.
3. Choose roles with clear boundaries.
4. Give each subagent a concrete objective, expected output shape, and ownership boundary.
5. Keep the parent thread moving on non-overlapping work while subagents run.
6. Wait when needed, then synthesize results into one concise answer.

## Output Contract

- State the role split.
- State why that split is useful for the current task.
- State which parts stay on the parent thread.
- State whether to wait for all subagents before continuing.
- After subagents return, integrate their results into one concise synthesis.
