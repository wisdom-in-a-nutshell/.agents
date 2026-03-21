# Role Split

Use this reference to choose a clean role split before spawning subagents.

## Default Split

- `explorer`: built-in role for local codebase and runtime exploration.
- `external_researcher`: managed custom role for information outside the local repo and runtime.
- `worker`: built-in role for bounded implementation work when the write scope is clear.

## Keep These Boundaries Sharp

- `explorer` answers: what is true inside this codebase?
- `external_researcher` answers: what is true outside this codebase?
- `worker` answers: what bounded implementation work can be executed safely in parallel?

## When Not To Delegate

- The next parent action is blocked on one urgent result and parallelism adds no value.
- The work is tightly coupled and likely to cause merge conflicts.
- The task is small enough that delegation overhead is higher than doing it locally.

## Custom Role Guidance

- Add a custom role only when it adds a real durable constraint, workflow, or tool surface.
- Do not override a built-in role name unless the override adds clear value and you want to diverge from upstream behavior intentionally.
- Prefer repo-local custom roles when the role is only useful in one repo.

## Long-Running Project Rule

- For `$project` work, the top-level run is the orchestrator.
- Subagents can gather evidence, verify docs, review code, or implement bounded slices.
- Subagents must not edit `docs/projects/<project>/tasks.md` directly.
