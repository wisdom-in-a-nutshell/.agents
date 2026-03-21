# Prompt Patterns

Use these patterns as starting points. Keep them short and bounded.

## Parallel Review

```text
Review this branch with parallel subagents. Spawn one subagent for security risks, one for test gaps, and one for maintainability. Wait for all of them, then summarize findings by category with file references.
```

## Explorer + External Researcher

```text
Investigate this change with subagents. Have `explorer` map the affected code paths and have `external_researcher` verify any external APIs, docs, or current behavior the patch depends on. Wait for both, then summarize the result with facts, sources, and open questions.
```

## Bounded Worker Implementation

```text
Use parallel subagents. Keep orchestration in the main thread. Spawn one `worker` for the backend validation changes in `server/validation/*` and one `worker` for the UI wiring in `app/settings/*`. Tell both workers they are not alone in the codebase, they must not revert others' edits, and they should keep changes confined to their assigned files. Wait for both before integrating.
```

## Prompt Checklist

- Name the role split explicitly.
- Explain why the split is useful for the current task.
- State whether to wait for all agents.
- State the expected output shape.
- Give workers clear ownership when files may be edited.
- Tell subagents what not to do when boundaries matter.
