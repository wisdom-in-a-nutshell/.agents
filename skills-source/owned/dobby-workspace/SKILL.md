---
name: dobby-workspace
description: "Operate the shared Dobby workspace body map and shape lint across personal Dobby workspaces. Use when changing STRUCTURE.md/body routing, workspace folder contracts, repo shape linting, or when boot context should load the common Dobby workspace map."
---

# Dobby Workspace

This skill owns the shared Dobby workspace body contract.

Use it for:

- understanding the common Dobby workspace organs and routing model
- updating workspace shape rules shared across `adi`, `angie`, or future Dobby homes
- running or editing the workspace shape linter
- deciding whether a repo-local `STRUCTURE.md` should be thin or needs local exceptions

Do not use this skill for:

- lifecycle hook runtime behavior → use `dobby-lifecycle`
- Shelf operations → use `dobby-shelf`
- journal/check-in writes → use `journal-checkin`
- health data → use `health`

## Common map

Load `references/body-map.md` when you need the shared semantic map that should
be bootstrapped into Dobby sessions.

Repo-local `STRUCTURE.md` should stay thin: local identity/exception notes only,
with the shared body map coming from this skill.

## Linter

Use the script:

```bash
~/.agents/skills-source/owned/dobby-workspace/scripts/lint-workspace --workspace-root /path/to/workspace
```

The linter is a cheap mechanical reflex. It should stay deterministic and fast.
When it fails, treat the message as an instruction from the workspace:

1. If the new path/artifact was accidental, remove it.
2. If it was deliberate, ask Adi whether the workspace body should change.
3. If Adi agrees, update the shared body map and linter together, plus any thin
   repo-local `STRUCTURE.md` note if needed.

Keep exact enforced shape in the linter, not in long prompt prose.
