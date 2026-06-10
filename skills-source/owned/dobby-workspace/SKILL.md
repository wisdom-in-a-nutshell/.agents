---
name: dobby-workspace
description: "Operate the shared Dobby workspace body map and shape lint across personal Dobby workspaces. Use when changing body routing, workspace folder contracts, repo shape linting, or when boot context should load the common Dobby workspace map."
---

# Dobby Workspace

This skill owns the shared Dobby workspace body contract.

Use it for:

- understanding the common Dobby workspace organs and routing model
- deciding where Dobby memory belongs
- updating workspace shape rules shared across `adi`, `angie`, or future Dobby homes
- running or editing the workspace shape linter

Do not use this skill for:

- lifecycle hook runtime behavior, boot loading, and finalization plumbing → use `dobby-lifecycle`
- Shelf operations → use `dobby-shelf`
- journal/check-in writes → use `journal-checkin`
- health data → use `health`

## Common map

Load `references/body-map.md` when you need the shared semantic map that should
be bootstrapped into Dobby sessions.

Do not create repo-local structure maps. The shared body map is the structure
source; repo-specific durable truth belongs in `dobby/constitution.json`, `memory/`, or the
relevant operational skill.

## Linter

Use the script:

```bash
~/GitHub/agents/skills-source/owned/dobby-workspace/scripts/lint-workspace --workspace-root /path/to/workspace
```

The linter is a cheap mechanical reflex. It should stay deterministic and fast.
When it fails, treat the message as an instruction from the workspace:

1. If the new path/artifact was accidental, remove it.
2. If it was deliberate, ask Adi whether the workspace body should change.
3. If Adi agrees, update the shared body map and linter together.

Keep exact enforced shape in the linter, not in long prompt prose.

## Validation orchestration

Use the shared workspace validator from repo `scripts/check-fast.sh`:

```bash
.agents/skills/dobby-workspace/scripts/validate --workspace-root "$PWD" --scope staged --no-input
```

Validation architecture:

- `dobby-workspace/scripts/validate` orchestrates fast checks and routes files.
- Domain schemas stay with the owning skill.
- Each domain skill exposes a public `scripts/validate` facade.
- The global Stop hook stays generic; it should not know Dobby schemas.

Current domain owners:

| Files | Owner |
|---|---|
| `memory/sessions/YYYY/MM/DD-HHMMSS[-N]/{meta.json,summary.md,dialogue.md,raw.jsonl}` | `dobby-lifecycle/scripts/validate` |
| `journal/daily/*/morning.json`, `journal/daily/*/night.json`, `journal/daily/*/general.json` | `journal-checkin/scripts/validate` |
| `state/shelf.json` | `dobby-shelf/scripts/validate` |
