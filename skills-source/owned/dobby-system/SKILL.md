---
name: dobby-system
description: Shared orientation for the Dobby multi-repo system and person-workspace anatomy. Use when Codex is working in or across `~/GitHub/adi`, `~/GitHub/angie`, `~/GitHub/dobby-engine`, `~/GitHub/documents`, `~/GitHub/dobby-gateway`, `~/GitHub/dobby-ios`, `~/GitHub/agents`, or `~/GitHub/scripts` and needs to understand repo ownership, Adi/Angie workspace folders, memory/body-map routing, source-material placement, identity/workspace boundaries, the shared engine model, dashboard/gateway flow, hooks/control-plane responsibilities, machine scheduler boundaries, document-corpus boundaries, or where a Dobby-related change belongs.
---

# Dobby System

## Purpose

Use this skill to orient before changing the Dobby system across repos. Keep the mental model centralized: each repo owns one layer, and cross-repo work should change the owning layer directly instead of scattering duplicate rules.

This skill is the canonical cross-repo orientation layer for Dobby. Future agents touching any Dobby-system repo should check it first, and should consider whether their change updates the shared mental model here before finishing.

## Repo Ownership Map

| Repo | Owns | Does not own |
|---|---|---|
| `~/GitHub/adi` | Adi's identity/data workspace: constitution, memory, journal, legacy Shelf import/audit material, person prompts, workspace hooks, `./bin/dobby` shim | Shared engine implementation, Angie's private data |
| `~/GitHub/angie` | Angie's identity/data workspace: constitution, memory, journal, legacy Shelf import/audit material, person prompts, workspace hooks, `./bin/dobby` shim | Shared engine implementation, Adi's private data |
| `~/GitHub/dobby-engine` | Shared Dobby CLI, Python engine, dashboard source, engine contracts, default prompts/docs, tests | Person-specific identity, memory, journals, private state |
| `~/GitHub/documents` | Canonical local document tooling: inventory, copy-only ingest/import, extraction, review, cleanup scripts, catalog/search CLI, and JSON/SQLite metadata contracts for `/Volumes/DobbyData/Documents` | Shared Dobby engine behavior, person memory/canon, workspace identity, raw document files in git |
| `~/GitHub/dobby-gateway` | Dobby's HTTP gateway/front door: mobile/web-facing gateway contracts, assistant runtime routing, bearer auth, launchd runtime, Cloudflare-facing service behavior, CLI/shared client contracts | iOS app implementation, Dobby identity data, core Dobby engine logic unless through documented CLI/API boundary |
| `~/GitHub/dobby-ios` | Dobby iOS app, SwiftUI surfaces, iOS build/deploy/TestFlight scripts, iOS-only docs, and the app's local config examples | Gateway runtime implementation, shared Dobby engine logic, person-private workspace data |
| `~/GitHub/agents` | Agent control plane: shared skills, Codex/Claude config, hooks, MCP/plugin registries, skill distribution | Dobby product behavior, Dobby personal data, engine runtime behavior |
| `~/GitHub/scripts` | Machine ops: bootstrap, launchd wiring, scheduler profiles, recurring machine wrappers, machine-local materializers | Dobby domain behavior, person memory/data, dashboard/API implementation, agent control-plane policy |

## Core Model

- Folder identity matters. An agent opened in `adi` is operating as Adi's Dobby workspace; an agent opened in `angie` is operating as Angie's Dobby workspace.
- Workspace repos are thin. They hold identity/data and call the shared engine through workspace-local `./bin/dobby`.
- The shared engine must remain workspace-agnostic. Runtime person data comes from `DOBBY_WORKSPACE` or workspace marker discovery, not from hardcoded Adi/Angie paths.
- Document access is a domain bridge, not engine-owned data. `dobby-engine`
  exposes `dobby documents status/search` plus the explicit copy-only
  `dobby documents ingest` front door; the separate `documents` repo owns
  catalog, import, and search-index implementation. Each personal workspace must
  opt into a document root such as `DOBBY_DOCUMENTS_DATA_ROOT`; the shared engine
  should not guess a person's corpus from a machine-wide default.
- `dobby-gateway` and client repos should treat Dobby as a workspace-backed service boundary. They should call the workspace/engine contract, not read private memory files ad hoc.
- Health storage is engine-owned but local and person-bound. The combined SQLite
  DB lives on the internal SSD at
  `~/Library/Application Support/Dobby/health/health.sqlite`; `dobby-engine`
  owns schema, migrations, sync/import, and queries. `person_id` separates Adi
  and Angie rows. `dobby-gateway`, `dobby-ios`, and other products must consume health through
  workspace-bound Dobby commands or gateway responses, never by reading health
  JSON files or SQLite directly. JSON health files in workspaces are import,
  audit, or backup material only.
- Shelf storage is engine-owned but local and person-bound. The SQLite DB lives
  on the internal SSD at
  `~/Library/Application Support/Dobby/shelf/shelf.sqlite`; `dobby-engine` owns
  schema, migrations, query/projection, and mutation logic. `person_id` separates
  Adi and Angie rows. Products and dashboards must consume Shelf through
  workspace-bound `dobby shelf` commands or gateway responses, never by reading
  workspace JSON or SQLite directly. This database is per-machine and is not
  replicated by Git sync: a hosted dashboard reads its serving host's Shelf, so
  dashboard-visible writes must target that host or an explicit remote-authoritative
  API. Workspace `state/shelf.json` is legacy import, audit, or backup material only.
- `agents` distributes capabilities and lifecycle hooks. Put shared Dobby orientation here as this skill; do not turn `agents` into the Dobby architecture doc home.
- `scripts` may schedule Dobby work on a specific machine, but only as a thin machine wrapper around the owning repo entrypoint. Live launchd plists under `~/Library/LaunchAgents/` are machine-local runtime state; tracked installers/runners live in `scripts`.

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
- `journal/` holds raw reflections/check-ins; `state/` holds legacy/import or
  backup machine-readable material; `projects/` holds active work trackers;
  `tmp/` is disposable scratch.

Before writing Dobby memory, check the shared write contract at
`~/GitHub/dobby-engine/docs/agent-write-recipes.md`. Use
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
- Keep person-private data out of `dobby-engine`, `agents`, `dobby-gateway`, `dobby-ios`, and
  public/content repos such as `blog-personal`. Those repos may be sources, not
  homes for private corpus data.
- Area `log.jsonl` files are retired; do not create them.

## Choosing Where a Change Belongs

1. If it changes Dobby commands, hooks, validation, memory processing, dashboard code, or shared behavior for both people, change `dobby-engine`.
2. If it changes document inventory, copy-only ingest/import, extraction, canonical cleanup, document search-index construction, or the `documents` CLI contract consumed by Dobby, change `documents`.
3. If it changes Adi's or Angie's constitution, memory, journal, legacy Shelf import/audit material, person-specific prompt behavior, or workspace-specific document-root opt-in, change only that person's workspace repo.
4. If it changes the mobile/web gateway, assistant runtime selection, gateway HTTP contracts, Cloudflare-facing local service behavior, or product routing in front of Dobby, change `dobby-gateway`.
5. If it changes the iOS app, SwiftUI surfaces, iOS build/deploy/TestFlight scripts, or iOS-only docs, change `dobby-ios`.
6. If it changes which skills/tools/hooks/configs agents receive, change `agents`.
7. If it changes machine bootstrap, launchd scheduling, scheduler profiles, or a thin machine-local wrapper around a Dobby command, change `scripts`; keep the real Dobby behavior in `dobby-engine` or the person workspace.
8. If more than one repo is touched, keep each repo's change scoped to its ownership layer and validate each repo separately.

## Documentation Boundary

Because Dobby is intentionally multi-repo and agent-native, documentation has two layers:

- This skill owns cross-repo orientation: repo ownership, privacy boundaries, shared engine/workspace model, routing rules, and rules that future agents must know before deciding where a change belongs.
- The owning repo owns implementation detail: command contracts, schemas, env vars, tests, local workflows, and feature-specific architecture docs. Put those in that repo's `AGENTS.md`, `docs/architecture/`, or `docs/references/` according to the repo's guidance.

Do not duplicate repo-specific contracts into this skill. Do not bury cross-repo Dobby rules only inside one repo. When a Dobby change affects more than one repo, or changes how agents should reason about ownership/routing, update this skill in the same change or explicitly record why it did not need an update.

## Operational Rules

- Prefer workspace-local `./bin/dobby` for Dobby operations from `adi` or `angie`; do not call engine internals from a workspace unless debugging the engine boundary.
- Do not copy personal data into `dobby-engine`, `dobby-gateway`, `dobby-ios`, or `agents`.
- Do not merge Adi and Angie workspaces into one repo or one branch history. Separate repos are the privacy and writer-boundary.
- Do not recreate duplicate engine code in workspaces. Shared code belongs in `dobby-engine`.
- Visible workspace artifacts are a built-in system capability, not a skill. Each artifact lives at `memory/areas/<area>/artifacts/<slug>/` (`artifact.json` + `index.html` dashboard); the workspace body map routes them. The dashboard (`index.html`) and the book (`book.json`) are **independent** expressions — never render one from the other. To read an artifact on the Kindle Scribe, the agent authors a `book.json` on demand (fresh prose, its own chapters) and runs `bin/dobby artifact export --dir <dir> [--kindle]` for a native book PDF. Person-private artifact content belongs in the person workspace; the minimal book toolkit, rendering, and the export command belong in `dobby-engine` (contract: `docs/artifacts.md`).
- Do not add README surfaces for this system. Use `AGENTS.md` for repo-local routing, this skill for cross-repo orientation, and repo docs for durable contracts.
- When a boundary changes, update the owning repo's `AGENTS.md` or docs in the same change, and check whether this skill's cross-repo orientation also changed. Update this skill for ownership, routing, privacy, or operating-model changes; leave feature-level contracts in the owning repo.

## Validation Expectations

Run the owner repo's fast check before finishing:

```bash
cd ~/GitHub/adi && scripts/check-fast.sh
cd ~/GitHub/angie && scripts/check-fast.sh
cd ~/GitHub/dobby-engine && scripts/check-fast.sh
cd ~/GitHub/dobby-gateway && scripts/check-fast.sh
cd ~/GitHub/dobby-ios && scripts/check-ios-fast.sh
cd ~/GitHub/agents && scripts/check-fast.sh
cd ~/GitHub/scripts && ops/check-fast.sh
```

For cross-repo work, run checks for every touched repo. If changing shared engine behavior, also smoke at least one real workspace path when relevant.
