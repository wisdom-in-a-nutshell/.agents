# Docs Structure and Maintenance (Solo Agent-Native)

Use one lightweight minimum docs contract across repositories unless there is a strong reason to deviate.

## Default docs layout

```text
docs/
  architecture/
    index.md                # Optional entry map for architecture docs
    ...                     # Domain/layer/boundary documents
  references/
    ...                     # Stable implementation lookup material
  projects/
    <project>/tasks.md      # Active long-running project execution file
    archive/                # Completed project folders
```

Additional `docs/` folders are allowed when useful (for example `docs/decisions`, `docs/setup`, `docs/quality`, `docs/build-logs`).

## What goes where

### `docs/architecture/`
- Purpose: design intent and system shape.
- Include: boundaries, dependency rules, layering, data flow, major tradeoffs.
- Question answered: "How is this system supposed to be built?"

### `docs/references/`
- Purpose: durable lookup facts for implementation.
- Include: contracts, schema snapshots, API notes, env var catalogs, integration constraints.
- Question answered: "What exact facts do I need to implement this safely?"

### `docs/projects/<project>/tasks.md`
- Purpose: active plan, progress, and resume point.
- Maintain with `$project-planner` and execute with `$project-executor`.
- Question answered: "What are we doing next?"

## Maintenance policy

1. Update `docs/architecture/` when boundaries, layering, or key flows change.
2. Update `docs/references/` when external contracts or operational facts change.
3. Update `docs/projects/*/tasks.md` continuously during active work.
4. Move completed projects to `docs/projects/archive/` after closeout.
5. If the same docs mismatch repeats, add a mechanical check in CI or scripts.

## Practical rule

Keep AGENTS short. Put durable detail in `docs/`. Keep project execution state in `docs/projects/*/tasks.md`.
