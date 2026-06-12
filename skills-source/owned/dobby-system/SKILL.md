---
name: dobby-system
description: Shared orientation for the Dobby multi-repo system. Use when Codex is working in or across `/Users/dobby/GitHub/adi`, `/Users/dobby/GitHub/angie`, `/Users/dobby/GitHub/dobby-engine`, `/Users/dobby/GitHub/codexclaw`, or `/Users/dobby/GitHub/agents` and needs to understand repo ownership, identity/workspace boundaries, the shared engine model, dashboard/gateway flow, hooks/control-plane responsibilities, or where a Dobby-related change belongs.
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
