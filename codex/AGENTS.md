# Codex Control Plane

Canonical personal Codex control-plane assets live here.

## Purpose

- Keep synced, durable Codex configuration under `~/.agents`.
- Keep `~/GitHub/scripts` as the machine bootstrap/apply shell, not the long-term owner of Codex policy.
- Keep `~/.codex` as the applied runtime home.
- Keep Codex-adjacent terminal workflow behavior here when it exists to drive Codex, even if the trigger surface is Ghostty or Keyboard Maestro.

## Layout

- `config/`: canonical Codex config fragments and templates.
  - `config/global.agents.md`: canonical machine-wide guidance source for `~/.codex/AGENTS.md`.
  - `config/bundled-skills-policy.json`: allow/disable policy for OpenAI-bundled Codex runtime skills.
- `scripts/`: canonical Codex-specific automation scripts.
  - includes Ghostty/Codex helper scripts and any thin helper invoked by Keyboard Maestro for Codex workflows.
- `shell/`: Codex-specific shell and Ghostty integration fragments.

## Rules

- Do not store auth, session history, caches, logs, runtime databases, or secrets here.
- If a script must run from `~/.codex` or another runtime path, keep the canonical source here and sync or point to it from the runtime config.
- Prefer repo-local `.codex/config.toml` for project-specific MCP/tool behavior instead of putting repo policy here.
- Keep mixed shell-dotfile concerns out of this folder until they are cleanly split from Codex-only behavior.
- Treat `~/.codex/vendor_imports/` as Codex-managed runtime state.
- Keep managed backup artifacts under `~/.local/state/codex-control-plane/`, not alongside live files in `~/.codex`.
- Do not delete, flatten, or "clean up" `~/.codex/vendor_imports/skills`; Codex App expects it to remain a nested Git checkout of `openai/skills`.

## Key Boundaries

- `config/repo-bootstrap.json` decides managed repo inventory plus per-repo Codex defaults and overrides.
- `config/bundled-skills-policy.json` decides which OpenAI-bundled Codex skills are allowed to remain available and which are disabled in managed runtime config.
- MCP preset definitions belong in `../mcp/config/presets.json`, not in `repo-bootstrap.json`.
- Browser dashboard data is served from canonical registries by `../scripts/control-plane-dashboard.py`.

## References

- `../docs/architecture/codex-control-plane.md`: high-level system shape.
- `../docs/architecture/codex-config-layers.md`: config layering model.
- `../docs/references/codex-control-plane-operations.md`: exact commands and checks.
- `../docs/references/codex-control-plane-ownership.md`: keep / move / generate ownership.
