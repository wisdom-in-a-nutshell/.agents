# .agents repo

Personal agent and Codex control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Keep canonical personal Codex control-plane assets reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Source of Truth

- `skills/registry.json` is the only canonical registry.
- `codex/` holds canonical personal Codex control-plane inputs.
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
  - Refresh preserves local `agents/openai.yaml` inside external skill folders.
- Dry-run Codex config apply: `./codex/scripts/sync-config.sh`
- Apply Codex config: `./codex/scripts/sync-config.sh --apply`
- Dry-run Codex trust sync: `./codex/scripts/sync-trusted-projects.sh`
- Apply Codex trust sync: `./codex/scripts/sync-trusted-projects.sh --apply`
- Dry-run Codex bootstrap batch: `./codex/scripts/bootstrap-machine-codex.sh`
- Apply Codex bootstrap batch: `./codex/scripts/bootstrap-machine-codex.sh --apply`

## Automation Cadence

- Scheduler entrypoint lives in `~/GitHub/scripts/sync/git-auto-sync.sh` (launchd every 15 minutes).
- External upstream refresh runs through that job with a once-per-day gate:
  - `~/.agents/scripts/refresh-external-skills.sh --apply`
- Managed link regeneration runs every auto-sync cycle:
  - `~/.agents/scripts/sync-skills-registry.sh --apply`
- Temporary Codex App Server snapshot refresh is managed outside the skill folder:
  - refresh: `~/.agents/scripts/refresh-codex-app-server-readme-reference.sh`
  - launcher: `~/.agents/scripts/install-codex-app-server-snapshot-launchd.sh`

## Rules

- Distribution policy is link-only.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- If `skills/registry.json` changes, run sync/check in the same change.
