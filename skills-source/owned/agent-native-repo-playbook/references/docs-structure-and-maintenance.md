# Docs Structure and Maintenance (Solo Agent-Native)

Use one lightweight minimum docs contract across repositories unless there is a strong reason to deviate.

## Default docs layout

```text
docs/
  architecture/
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
- Default shape: short plain-English overview, one simple Mermaid `flowchart TD`, main parts, main flow, key tradeoffs or constraints, and links to deeper references.
- Keep architecture docs visual-first and high-level. If one diagram gets crowded, split it into Level 1 / Level 2 / Level 3 views instead of forcing every detail into one figure.

### `docs/references/`
- Purpose: durable lookup facts for implementation.
- Include: contracts, schema snapshots, API notes, env var catalogs, integration constraints.
- Question answered: "What exact facts do I need to implement this safely?"

## Fast decision rule

Use this quick test when deciding between the two:

- `docs/architecture/` = how the system is supposed to work
- `docs/references/` = exact facts needed to change or operate it safely

In practice:

- If the doc is mainly about understanding the shape of the system, put it in `docs/architecture/`.
- If the doc is mainly about looking up exact behavior, contracts, limits, fields, or commands, put it in `docs/references/`.

## Examples

Put these in `docs/architecture/`:

- request/data flow through the main parts of the system
- service or module boundaries and dependency direction
- background job, queue, or worker architecture
- why the repo uses a specific cache, event, or storage boundary

Put these in `docs/references/`:

- field precedence rules for stored or generated data
- environment variable catalog for an app or service
- API field contract or DTO shape summary
- cache invalidation rules and dependency signatures
- third-party integration constraints, limits, or command snippets

## Architecture doc authoring

Use this default structure unless the repo already has a strong local pattern:

1. Title
2. Short overview
3. Mermaid diagram
4. Main parts
5. Main flow
6. Tradeoffs or important constraints
7. Links to deeper references

For Mermaid diagrams:

- Prefer `flowchart TD` for quick scanning.
- Keep node count modest.
- Show the main path first.
- Group related nodes only when grouping improves understanding.
- Keep container labels passive; arrows should connect real components, not block titles.
- Use consistent zone color only when it improves scanability, and never rely on color alone.
- Verify the rendered diagram when the target renderer is available.

If a person cannot understand the diagram in a few seconds, it is too detailed. Split overview, ownership zones, and key runtime paths into separate small diagrams when needed.

### `docs/projects/<project>/tasks.md`
- Purpose: active plan, progress, and resume point.
- Maintain and execute with `$project`.
- Question answered: "What are we doing next?"
- Default bias: once the scoped work is confidently complete, close out and archive it instead of keeping a completed tracker active.

## Maintenance policy

1. Update `docs/architecture/` when boundaries, layering, or key flows change.
2. Update `docs/references/` when external contracts or operational facts change.
3. Update `docs/projects/*/tasks.md` continuously during active work.
4. Move completed projects to `docs/projects/archive/` immediately after confident closeout. Ask only when completion is materially uncertain.
5. If the same docs mismatch repeats, add a mechanical check in CI or scripts.

## Practical rule

Keep AGENTS short. Put durable detail in `docs/`. Keep project execution state in `docs/projects/*/tasks.md`.
