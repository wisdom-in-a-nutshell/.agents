# Docs Router

Use this file as the docs contract for the `.agents` control-plane repo.

## Docs Contract

- `docs/architecture/`: system shape, boundaries, and control-plane flow when architecture docs are needed.
- `docs/references/`: durable implementation facts, command snippets, and operational lookup material for humans and agents.
- `docs/projects/<project>/tasks.md`: active long-running docs or repo work.

## Rule Of Thumb

- `architecture` = how this system is supposed to work
- `references` = exact facts needed to change or operate it safely

## Rule

- Keep docs short and durable.
- Keep root `AGENTS.md` as the repo router.
- Keep one canonical doc per topic and link to it instead of duplicating guidance.
