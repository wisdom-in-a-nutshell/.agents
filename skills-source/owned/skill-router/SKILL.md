---
name: skill-router
description: Route skill placement for the `~/.agents` control-plane repo. Use when deciding whether a skill should be `owned`, `external`, or `repo-local`; when creating a new skill with `skill-creator`; or when promoting/moving skills between repo-local and managed registry. Apply this repo's AGENTS.md policy, update `skills/registry.json`, and run sync/check.
---

# Skill Router

Use this skill to decide where a skill should live in the `.agents` system and execute the correct flow.

## Scope

- This skill is specific to the `~/.agents` repository.
- Always apply policy from `~/.agents/AGENTS.md` first.
- If current repo is not `~/.agents`, only decide placement and list exact changes; do not assume write access to `.agents` files.

## Decision Rules

1. Use `external` when the source is upstream and should be refreshable.
2. Use `owned` when the skill is authored locally and should be reusable globally or across repos.
3. Use `repo-local` when the skill is specific to one repo and should remain local.
4. If intent is ambiguous, ask one question: "Should this be external, owned, or repo-local?"
5. Default to the narrowest useful scope. Only use `scope: global` when the skill belongs in the small default kit for unrelated repos; otherwise prefer managed `scope: repo` or unmanaged repo-local placement.
6. When a skill depends on a repo-level MCP preset, keep the repo-scoped skill targets aligned with the repos that declare that preset in `codex/config/repo-bootstrap.json`.

## Paths in This Environment

- Control plane repo: `~/.agents`
- Managed owned skills: `~/.agents/skills-source/owned/<skill>`
- Managed external skills: `~/.agents/skills-source/external/<skill>`
- Global runtime links: `~/.agents/skills/<skill>`
- Registry: `~/.agents/skills/registry.json`
- Repo-local skill location: `<repo>/.agents/skills/<skill>`
- Repo targets in managed `repos` can be repo names under `~/GitHub` or explicit repo roots such as `~/.agents` when the target repo lives outside `~/GitHub`.

## Standard Flow (When User Says "Create Skill")

1. Clarify destination type: `owned`, `external`, or `repo-local`.
2. If creating new managed skill, scaffold with `skill-creator` `init_skill.py`.
3. Apply placement workflow below.
4. If `skills/registry.json` changed, run sync/check in same change.

## Bootstrap Shortcut (When User Gives a `skills.sh` URL)

Use the canonical bootstrap script instead of hand-editing the registry when the request is:

- "install this upstream skill"
- "bootstrap this skill into repo X"
- "take this `skills.sh` URL and wire it into a repo"

Command:

```bash
cd ~/.agents
./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo> --apply
```

Examples:

```bash
./scripts/bootstrap-skill.sh https://skills.sh/microsoft/skills/copilot-sdk --repo codexclaw --apply
./scripts/bootstrap-skill.sh openai/skills:skills/.curated/openai-docs@main --repo win --apply
```

Behavior:

1. Parses the upstream skill reference.
2. Adds or updates the managed external entry in `skills/registry.json`.
3. Runs `refresh-external-skills` for that skill.
4. Runs `sync-skills-registry --apply`.
5. Regenerates repo bootstrap registry artifacts.

Defaults:

- Prefer `scope: repo` when the user names a target repo.
- Prefer `scope: global` only when the skill clearly belongs in the small cross-repo default kit.
- If the skill already exists as `global`, do not create a redundant repo-scoped duplicate just to target one repo.

## Placement Workflows

### A) Create New Owned Global Skill

1. Scaffold skill:
```bash
python3 ~/.agents/skills-source/external/skill-creator/scripts/init_skill.py <skill-name> --path ~/.agents/skills-source/owned
```
2. Ensure `SKILL.md` + `agents/openai.yaml` are correct.
3. Add entry to `~/.agents/skills/registry.json`:
   - `skill`: `<skill-name>`
   - `origin`: `owned`
   - `scope`: `global`
   - `repos`: `[]`
   - `source_path`: `skills-source/owned/<skill-name>`
   - `upstream_ref`: `-`
4. Run:
```bash
cd ~/.agents
./scripts/sync-skills-registry.sh --apply
./scripts/check-skills-registry.sh
```

### B) Add External Skill

1. Add the managed entry in `~/.agents/skills/registry.json`:
   - `skill: <skill>`
   - `origin: external`
   - `scope: global` or `scope: repo` as needed
   - `source_path: skills-source/external/<skill>`
   - valid `upstream_ref`
2. Import the canonical source from upstream:
```bash
cd ~/.agents
./scripts/refresh-external-skills.sh --apply --skill <skill>
```
3. Confirm the imported source now exists under `~/.agents/skills-source/external/<skill>`.
4. Run sync/check:
```bash
cd ~/.agents
./scripts/sync-skills-registry.sh --apply
./scripts/check-skills-registry.sh
```
5. Treat direct installer-based global installs as non-canonical in this repo. Prefer registry + refresh so external skills remain reproducible and refreshable.
6. If the input is a `skills.sh` URL or upstream ref and no special handling is needed, prefer the bootstrap shortcut above instead of doing these steps manually.

### C) Keep Skill Repo-Local

1. Store in `<repo>/.agents/skills/<skill>`.
2. Add `{ repo, skill }` to `unmanaged_repo_local_skills` in `~/.agents/skills/registry.json` for visibility.
3. Do not add a managed entry unless promoting.

### D) Promote Repo-Local -> Managed Owned

1. Copy skill folder from `<repo>/.agents/skills/<skill>` to `~/.agents/skills-source/owned/<skill>`.
2. Add managed entry in registry (usually `scope: repo` first, then `global` if needed).
3. If needed, remove old unmanaged repo-local entry.
4. Run sync/check.

## Safety Rules

- Edit canonical skill sources, not symlink destinations.
- If `skills/registry.json` changes, run sync/check in the same change.
- Keep distribution link-only.
- Do not create additional mapping manifests; use `skills/registry.json` only.
