---
name: skill-router
description: Route skill work to the right destination and workflow: create new skills, classify as owned/external/repo-local, promote repo-local skills to global managed skills, and keep skills/registry.json + symlinks in sync. Use when user asks where a skill should live, asks to move/promote a skill, or asks to combine skill-creator with repository placement rules.
---

# Skill Router

Use this skill to decide where a skill should live and execute the correct flow.

## Decision Rules

1. Use `external` when the source is upstream and should be refreshable.
2. Use `owned` when the skill is authored locally and should be reusable globally or across repos.
3. Use `repo-local` when the skill is specific to one repo and should remain local.
4. If intent is ambiguous, ask one question: "Should this be external, owned, or repo-local?"

## Paths in This Environment

- Control plane repo: `~/.agents`
- Managed owned skills: `~/.agents/skills-source/owned/<skill>`
- Managed external skills: `~/.agents/skills-source/external/<skill>`
- Global runtime links: `~/.agents/skills/<skill>`
- Registry: `~/.agents/skills/registry.json`
- Repo-local skill location: `<repo>/.agents/skills/<skill>`

## Workflows

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

1. Place under `~/.agents/skills-source/external/<skill>`.
2. Add managed entry in `~/.agents/skills/registry.json` with:
   - `origin: external`
   - `source_path: skills-source/external/<skill>`
   - valid `upstream_ref`
3. Run sync/check.
4. Optional refresh:
```bash
cd ~/.agents
./scripts/refresh-external-skills.sh --apply
```

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
