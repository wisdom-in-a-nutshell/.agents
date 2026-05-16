# Docs Router

Use this file as the docs contract for the `.agents` control-plane repo.

## Docs Contract

- `docs/architecture/`: system shape, boundaries, and control-plane flow when architecture docs are needed.
- `docs/references/`: durable implementation facts, command snippets, and operational lookup material for humans and agents.
- `docs/projects/<project>/tasks.md`: active long-running docs or repo work.
- `docs/projects/archive/<project>/tasks.md`: completed project history; do not treat archived trackers as active context.

## Rule Of Thumb

- `architecture` = how this system is supposed to work
- `references` = exact facts needed to change or operate it safely

## Rule

- Keep docs short and durable.
- Keep root `AGENTS.md` as the repo router.
- Use nested `AGENTS.md` only where local rules materially differ from the parent scope.
- Do not use nested `AGENTS.md` as navigation aids; move durable detail into `docs/architecture/` or `docs/references/`.
- Keep one canonical doc per topic and link to it instead of duplicating guidance.
- Keep reference docs only when they are exact lookup material, operational contracts, or source-of-truth maps. Delete or archive prose-only summaries that merely restate code, tests, or another doc.
