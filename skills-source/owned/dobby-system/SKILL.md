---
name: dobby-system
description: Shared orientation for the Dobby multi-repo system and person-workspace anatomy. Use when Codex is working in or across `/Users/dobby/GitHub/adi`, `/Users/dobby/GitHub/angie`, `/Users/dobby/GitHub/dobby-engine`, `/Users/dobby/GitHub/codexclaw`, or `/Users/dobby/GitHub/agents` and needs to understand repo ownership, Adi/Angie workspace folders, memory/body-map routing, source-material placement, identity/workspace boundaries, the shared engine model, dashboard/gateway flow, hooks/control-plane responsibilities, or where a Dobby-related change belongs.
---

# Dobby System

## Purpose

Use this skill to orient before changing the Dobby system across repos. Keep the mental model centralized: each repo owns one layer, and cross-repo work should change the owning layer directly instead of scattering duplicate rules.

## Repo Ownership Map

| Repo | Owns | Does not own |
|---|---|---|
| `/Users/dobby/GitHub/adi` | Adi's identity/data workspace: constitution, memory, journal, Shelf state, person prompts, workspace hooks, `./bin/dobby` shim | Shared engine implementation, Angie's private data |
| `/Users/dobby/GitHub/angie` | Angie's identity/data workspace: constitution, memory, journal, Shelf state, person prompts, workspace hooks, `./bin/dobby` shim | Shared engine implementation, Adi's private data |
| `/Users/dobby/GitHub/dobby-engine` | Shared Dobby CLI, Python engine, dashboard source, engine contracts, default prompts/docs, tests | Person-specific identity, memory, journals, private state |
| `/Users/dobby/GitHub/codexclaw` | Product shell: iOS app, mobile gateway, assistant runtime integration, user-facing app contracts | Dobby identity data, core Dobby engine logic unless through documented CLI/API boundary |
| `/Users/dobby/GitHub/agents` | Agent control plane: shared skills, Codex/Claude config, hooks, MCP/plugin registries, skill distribution | Dobby product behavior, Dobby personal data, engine runtime behavior |

## Core Model

- Folder identity matters. An agent opened in `adi` is operating as Adi's Dobby workspace; an agent opened in `angie` is operating as Angie's Dobby workspace.
- Workspace repos are thin. They hold identity/data and call the shared engine through workspace-local `./bin/dobby`.
- The shared engine must remain workspace-agnostic. Runtime person data comes from `DOBBY_WORKSPACE` or workspace marker discovery, not from hardcoded Adi/Angie paths.
- `codexclaw` should treat Dobby as a workspace-backed service boundary. It should call the workspace/engine contract, not read private memory files ad hoc.
- `agents` distributes capabilities and lifecycle hooks. Put shared Dobby orientation here as this skill; do not turn `agents` into the Dobby architecture doc home.

## Workspace Anatomy

Use this skill as the entry point, then read the current workspace's
`docs/body-map.md` for exact routing before changing workspace shape or deciding
where person data belongs. Do not duplicate body-map detail here.

Adi and Angie workspaces share the same organ layout:

```text
bin/ dobby/ docs/ journal/ memory/ projects/ scripts/ state/ tmp/
```

Inside a person workspace:

- `bin/dobby` is the only Dobby CLI entry point; it pins the workspace and calls
  the shared engine.
- `dobby/constitution.md` is Dobby behavior and boundaries.
- `memory/profile.md` is durable person context; `memory/now.md` is current
  orientation.
- `memory/areas/<area>/canon.md` is the one durable area layer.
- `memory/areas/<area>/area.json` indexes area metadata, data dirs, and assets.
- `memory/sessions/` and `memory/dreams/` are continuity records.
- `journal/` holds raw reflections/check-ins; `state/` holds live state such as
  Shelf; `projects/` holds active work trackers; `tmp/` is disposable scratch.

Before writing Dobby memory, check the shared write contract at
`/Users/dobby/GitHub/dobby-engine/docs/agent-write-recipes.md`. Use
`./bin/dobby` for CLI-owned writes such as journal, Shelf, sessions, dreams,
calendar, and mail. Direct file writes are for documented shapes such as area
canon, `area.json`, and source-material JSON.

For social archives, corpora, imported documents, and other source material:

- Keep raw exports as inputs/backups or repo-local temp/source assets, not as
  canon.
- Store normalized supporting captures under the relevant person's workspace,
  usually `memory/areas/<area>/<dataDir>/...` as source-material JSON when the
  area declares that data dir.
- Put durable conclusions in `canon.md`; put personal open loops in Shelf; put
  raw reflection in `journal/`.
- Keep person-private data out of `dobby-engine`, `agents`, `codexclaw`, and
  public/content repos such as `blog-personal`. Those repos may be sources, not
  homes for private corpus data.
- Area `log.jsonl` files are retired; do not create them.

## Choosing Where a Change Belongs

1. If it changes Dobby commands, hooks, validation, memory processing, dashboard code, or shared behavior for both people, change `dobby-engine`.
2. If it changes Adi's or Angie's constitution, memory, journal, Shelf state, or person-specific prompt behavior, change only that person's workspace repo.
3. If it changes the phone app, mobile gateway, assistant runtime selection, or product-facing behavior, change `codexclaw`.
4. If it changes which skills/tools/hooks/configs agents receive, change `agents`.
5. If more than one repo is touched, keep each repo's change scoped to its ownership layer and validate each repo separately.

## Operational Rules

- Prefer workspace-local `./bin/dobby` for Dobby operations from `adi` or `angie`; do not call engine internals from a workspace unless debugging the engine boundary.
- Do not copy personal data into `dobby-engine`, `codexclaw`, or `agents`.
- Do not merge Adi and Angie workspaces into one repo or one branch history. Separate repos are the privacy and writer-boundary.
- Do not recreate duplicate engine code in workspaces. Shared code belongs in `dobby-engine`.
- Do not add README surfaces for this system. Use `AGENTS.md` for repo-local routing, this skill for cross-repo orientation, and repo docs for durable contracts.
- When a boundary changes, update the owning repo's `AGENTS.md` or docs in the same change. Update this skill only if the cross-repo ownership map or operating model changes.

## Validation Expectations

Run the owner repo's fast check before finishing:

```bash
cd /Users/dobby/GitHub/adi && scripts/check-fast.sh
cd /Users/dobby/GitHub/angie && scripts/check-fast.sh
cd /Users/dobby/GitHub/dobby-engine && scripts/check-fast.sh
cd /Users/dobby/GitHub/codexclaw && scripts/check-fast.sh
cd /Users/dobby/GitHub/agents && scripts/check-fast.sh
```

For cross-repo work, run checks for every touched repo. If changing shared engine behavior, also smoke at least one real workspace path when relevant.
