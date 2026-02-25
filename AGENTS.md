# .agents repo

Personal agent-skill control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Source of Truth

- `skills/registry.json` is the only canonical registry.
- Managed canonical skill content lives in:
  - `skills-source/external/<skill>/`
  - `skills-source/owned/<skill>/`
- Global runtime skills live in `skills/<skill>` as symlinks.
- Generated views for Obsidian live in:
  - `skills/registry.md`
  - `skills/registry.base`
  - `skills/registry-items/`

## Operations

- Dry-run sync: `./scripts/sync-skills-registry.sh`
- Apply sync: `./scripts/sync-skills-registry.sh --apply`
- Validate generated registry artifacts: `./scripts/check-skills-registry.sh`
- Dry-run external upstream refresh: `./scripts/refresh-external-skills.sh`
- Apply external upstream refresh: `./scripts/refresh-external-skills.sh --apply`

## Rules

- Distribution policy is link-only.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- If `skills/registry.json` changes, run sync/check in the same change.
