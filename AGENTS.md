# .agents repo

Personal agent, Codex, and repo-local lifecycle hook control plane.

## Purpose

- Keep global skill sources and runtime links reproducible across MacBook + MacMini.
- Keep canonical personal Codex control-plane assets reproducible across MacBook + MacMini.
- Track one canonical skill registry in git.
- Keep repo-local skills in their repos unless explicitly promoted.

## Source of Truth

- `skills/registry.json` is the canonical skill registry.
- `plugins/registry.json` is the canonical plugin registry.
- `mcp/config/presets.json` is the canonical shared MCP registry.
- `hooks/registry.json` is the canonical Codex lifecycle hook registry.
- `codex/` holds canonical personal Codex control-plane inputs.
- `codex/config/global.agents.md` is the canonical machine-wide guidance source for `~/.codex/AGENTS.md`.
- `codex/config/bundled-skills-policy.json` is the canonical policy for classifying OpenAI-bundled Codex skills that appear under `~/.codex/skills/.system` or `~/.codex/skills/codex-primary-runtime`.
- `codex/config/repo-bootstrap.json` is the canonical shared repo registry for managed repo-local behavior.
  - Per repo it can define:
    - `mcp_presets`
    - `model`
    - `model_reasoning_effort`
    - `plan_mode_reasoning_effort`
    - `model_verbosity`
    - `personality`
    - `model_instructions_file`
    - `developer_instructions`
    - `project_root_markers`
    - `features`
    - `service_tier`
- Managed canonical skill content lives in:
  - `skills-source/external/<skill>/`
  - `skills-source/owned/<skill>/`
- Codex-native plugin scope and enablement lives in `plugins/registry.json`.
- Global runtime skills live in `skills/<skill>` as symlinks.
- Generated views for Obsidian live in:
  - `docs/references/registry/skills.base`
  - `docs/references/registry/skills-items/`
  - `docs/references/registry/repo-bootstrap.base`
  - `docs/references/registry/repo-bootstrap-items/`
  - `docs/references/registry/mcp-registry.base`
  - `docs/references/registry/mcp-registry-items/`
- Shared lifecycle hook scripts live in:
  - `hooks/scripts/`
- Shared local Git hook scripts live in:
  - `hooks/git/`

## Key Entry Points

- Apply all shared agent control planes: `./scripts/bootstrap-machine-agent-control-planes.sh --apply`
- Reconcile after git sync: `./scripts/auto-apply-agent-control-planes.sh --apply`
- Validate shared skills, plugins, Codex, and regression tests: `./scripts/check-agent-control-planes.sh`
- Audit applied local agent runtime drift for machine health checks: `./scripts/audit-agent-runtime-drift.py --plain`
- Run hermetic regression tests only: `./scripts/test-control-plane.sh`
- Bootstrap external skills/plugins through the agent-facing clients:
  - `./scripts/bootstrap-skill.sh <skills.sh-url-or-upstream-ref> --repo <repo>`
  - `./scripts/bootstrap-plugin.sh <plugin-name-or-id> [--scope global|repo|dormant] [--repo <repo>]`

Detailed operations live in:

- `docs/references/agent-control-plane-operations.md`
- `docs/references/repo-lifecycle-hook-adapter.md`
- `docs/references/codex-control-plane-operations.md`
- `docs/references/cli-interface-contract.md`

## Rendered Surfaces

- Treat paths listed in `docs/references/rendered-surfaces.md` as linked, rendered, or generated outputs.
- Do not hand-edit rendered outputs; update the canonical source and rerun the documented renderer/check.

## Rules

- Runtime distribution is link-first for standalone skills; Codex plugins stay native plugin entries in `plugins/registry.json`.
- Treat global skills and global plugins as a minimal default kit; prefer repo scope or repo-local unless a capability is broadly useful across unrelated repos.
- When a user provides a `skills.sh` URL or upstream skill reference and wants it installed into a repo, prefer `./scripts/bootstrap-skill.sh` over manual registry edits.
- Do not edit managed skills through repo symlink destinations; edit canonical source paths.
- Do not split Codex plugins into skill or MCP registries by default. If a plugin capability should become standalone, promote it manually into `skills/registry.json` or `mcp/config/presets.json`.
- Managed plugin entries render global plugin state into `~/.codex/config.toml` and repo-scoped plugin state into managed repo `.codex/config.toml`; standalone skills and MCPs remain separate registries.
- Keep repo-local skills listed in `skills/registry.json` under `unmanaged_repo_local_skills`.
- Keep `unmanaged_repo_local_skills` honest: if the target repo exists locally, the repo must contain `.agents/skills/<skill>/SKILL.md` or skill sync should fail until the stale registry entry is removed.
- Keep managed repo-scoped native plugins in `plugins/registry.json` under `managed_plugins` with `scope: "repo"` and `repos`.
- Keep unmanaged repo-local plugins listed in `plugins/registry.json` under `unmanaged_repo_local_plugins`.
- Do not add additional manifest files for skill mapping; update `skills/registry.json`.
- Do not add additional manifest files for plugin mapping; update `plugins/registry.json`.
- New or promoted agent-facing CLI clients must follow `docs/references/cli-interface-contract.md`.
- Do not hand-edit rendered runtime hook files. Update `hooks/registry.json` or `hooks/scripts/*`, then rerun the shared bootstrap/check.
- Repo lifecycle hook authoring contract lives in `docs/references/repo-lifecycle-hook-adapter.md`.
- Repo-specific lifecycle behavior belongs in optional Python scripts under `scripts/hooks/session_start.py`, `scripts/hooks/user_prompt_submit.py`, `scripts/hooks/pre_compact.py`, `scripts/hooks/post_compact.py`, and `scripts/hooks/session_end.py`.
- Managed repos get rendered repo-local hook config at `.codex/hooks.json` according to `hooks/registry.json`; do not hand-edit that surface. Update `hooks/registry.json`, `hooks/scripts/*`, or `codex/config/repo-bootstrap.json`, then rerun the shared bootstrap wrapper.
- Managed repos use local Git `core.hooksPath` pointing at `hooks/git/`; the shared commit-time hook delegates to repo-owned `scripts/check-fast.sh` when present.
- Use `scripts/check-fast.sh` as the fast, deterministic, repo-owned validation entrypoint. Prefer staged/affected checks there; keep slower repo-wide validation in `scripts/check-full.sh`.
- If `skills/registry.json` changes, run sync/check in the same change.
- If `plugins/registry.json` changes, run plugin sync/check in the same change.
- Do not hand-edit generated repo-local `.codex/config.toml` files in managed repos; update `codex/config/repo-bootstrap.json` and re-run the sync scripts.
- Do not hand-edit generated repo-local `.codex/hooks.json` files in managed repos; update `hooks/registry.json` and re-run the sync scripts.
- When a new OpenAI-bundled Codex skill appears locally, classify it in `codex/config/bundled-skills-policy.json` as either `allowed` or `disabled`; do not leave it as untracked local runtime drift.
- When changing shared bootstrap inputs such as `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`, or repo MCP assignment, prefer `./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo>` so Codex runtime and repo-local Codex hook state are re-rendered together. Use component-only scripts only for intentional single-surface troubleshooting.
- If `mcp/config/presets.json` changes, run Codex control-plane validation in the same change.
- If `hooks/registry.json`, `hooks/scripts/*`, `hooks/git/*`, or `scripts/sync-managed-git-hooks.sh` changes, run shared bootstrap/check plus `./scripts/test-control-plane.sh` in the same change.
- If `codex/config/global.config.toml` or `codex/config/repo-bootstrap.json` changes, run the Codex control-plane validation script in the same change.
