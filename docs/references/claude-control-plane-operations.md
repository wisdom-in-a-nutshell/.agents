# Claude Control Plane Operations

Use this page for the exact operator-facing facts of the local Claude control plane.

Use [Claude Control Plane](/Users/dobby/.agents/docs/architecture/claude-control-plane.md) for the high-level shape.

## Canonical Inputs

- `claude/config/global.claude.md`
  - symlink alias to `codex/config/global.agents.md` for `~/.claude/CLAUDE.md`
- `codex/config/global.agents.md`
  - single canonical machine-wide guidance source shared by Codex and Claude
- `claude/config/settings.json`
  - canonical source for `~/.claude/settings.json`
- `hooks/registry.json`
  - shared lifecycle hook registry merged into global Claude settings
- `claude/control_plane/*.py`
  - importable Python implementation for the Claude sync/render/validation entrypoints
- `claude/config/bootstrap.json`
  - Claude-only bootstrap defaults and repo-specific overrides
- `codex/config/repo-bootstrap.json`
  - shared repo inventory plus per-repo settings/MCP assignment
- `agents/registry.json`
  - shared agent exposure registry for Codex and Claude
- `claude/config/agents/*.md`
  - canonical Claude prompt bodies for managed subagents
- `mcp/config/presets.json`
  - shared MCP preset definitions and machine-wide global MCP defaults
- `skills/registry.json`
  - shared skill registry used to materialize `~/.claude/skills/` and repo `.claude/skills/`
- `scripts/bootstrap-machine-agent-control-planes.sh`
  - shared machine-facing bootstrap batch used by external bootstrap repos
- `scripts/auto-apply-agent-control-planes.sh`
  - shared post-sync reconcile entrypoint used after `~/.agents` sync
- `scripts/check-agent-control-planes.sh`
  - shared validation entrypoint for skills plus Codex and Claude

## Runtime Targets

- `~/.claude/CLAUDE.md`
  - global guidance file
- `~/.claude/settings.json`
  - permissive user/global defaults plus managed lifecycle hooks
- `~/.claude.json`
  - user runtime state and global MCP store
- `~/.claude/agents/*.md`
  - global Claude subagents rendered from the shared agent registry
- repo `CLAUDE.md`
  - usually a tiny file containing only `@AGENTS.md`
- repo `.claude/settings.json`
  - project settings
- repo `.mcp.json`
  - project MCP
- repo `.claude/skills/`
  - project skills
- repo `.claude/agents/*.md`
  - repo-scoped Claude subagents rendered from the shared agent registry
- nested repo `CLAUDE.md`
  - tiny file containing only `@AGENTS.md` wherever nested `AGENTS.md` exists

## Command Surface

The Claude control plane follows the same sync/check pattern as Codex, with scripts living under `claude/scripts/`:

- `claude/scripts/*.sh` are thin shell entrypoints
  - they delegate to `python3 -m claude.control_plane.<module>`
  - keep renderer and validation logic in the Python module layer rather than reintroducing large embedded heredocs

- `~/.agents/scripts/bootstrap-machine-agent-control-planes.sh`
  - machine-facing shared bootstrap batch for skills plus Codex and Claude
- `~/.agents/scripts/auto-apply-agent-control-planes.sh`
  - machine-facing post-sync reconcile entrypoint
- `~/.agents/scripts/check-agent-control-planes.sh`
  - shared validation entrypoint
- `sync-global-claude-md.sh`
  - link `~/.claude/CLAUDE.md` to `claude/config/global.claude.md`, which resolves to `codex/config/global.agents.md`
- `sync-settings.sh`
  - install the permissive global `settings.json` into `~/.claude/settings.json` and merge managed lifecycle hooks from `hooks/registry.json`
- `sync-global-mcp.sh`
  - merge global MCP entries from `mcp/config/presets.json` into `~/.claude.json`
- `sync-subagents.sh`
  - materialize global and project Claude subagents from `agents/registry.json`
- `sync-skills.sh`
  - materialize global and project Claude skills from `skills/registry.json`
- `sync-repo-claude-configs.sh`
  - render root and nested `CLAUDE.md` compatibility files, `.claude/settings.json`, and `.mcp.json` from the shared repo registry plus Claude bootstrap overlay
- `bootstrap-machine-claude.sh`
  - run the full Claude apply batch and validate rendered outputs at the end
- `check-claude-control-plane.sh`
  - validate canonical inputs and rendered outputs

## Supported Manual Rules

- `CLAUDE.md` should contain only `@AGENTS.md` for the generic case.
- Nested `AGENTS.md` files should also get sibling `CLAUDE.md` files containing only `@AGENTS.md`.
- `AGENTS.md` remains the shared repo instruction source.
- `codex/config/global.agents.md` remains the shared global instruction source.
- `skipDangerousModePermissionPrompt` belongs in user/global Claude settings, not project settings.
- `enableAllProjectMcpServers` is part of the permissive global baseline.
- `sandbox.enabled = false` is the closest local no-sandbox default.

## Current Global Settings Baseline

- `claude/config/settings.json` is the source of truth for `~/.claude/settings.json`.
- `hooks/registry.json` is the source of truth for managed global `SessionStart` and `Stop` hook entries inside `~/.claude/settings.json`.
- The canonical global baseline is provider-neutral by default.
- Provider-specific opt-ins such as AWS Bedrock should live in explicit shell wrappers, not in the machine-wide Claude settings baseline.

## Scope Rules

- Global Claude guidance lives in `~/.claude/CLAUDE.md`, linked through `claude/config/global.claude.md` to the shared global AGENTS source.
- Project Claude guidance lives in repo `CLAUDE.md`.
- Global MCP lives in `~/.claude.json`.
- Project MCP lives in `.mcp.json`.
- Global skills live under `~/.claude/skills/`.
- Project skills live under repo `.claude/skills/`.
- Global Claude subagents live under `~/.claude/agents/`.
- Project Claude subagents live under repo `.claude/agents/`.

## Expected Repo Diffs

- A Claude bootstrap on a machine may create or update repo-local compatibility files in managed repos.
- Common examples are:
  - repo `CLAUDE.md`
  - repo `.claude/settings.json`
  - repo `.mcp.json`
  - repo `.claude/skills/*`
  - repo `.claude/agents/*`
- Those are normal generated outputs from `sync-repo-claude-configs.sh` and `sync-skills.sh`, not evidence that the bootstrap misfired.
- Repo `.claude/agents/.managed-subagents.json` is also a normal generated manifest used to prune stale managed subagent files without touching hand-written ones.
- If a managed repo tracks those paths in git, they will appear as ordinary worktree changes until committed.
- `check-claude-control-plane.sh` now also flags untracked files under tracked repo-local Claude generated surfaces such as `.claude/skills/` and `.claude/agents/`.
  - This catches the "new generated Claude symlink was created but never added to the repo" case.
  - It does not auto-commit or auto-push target repos.

## Generic Baseline Exclusions

- Do not treat `soul.md` as part of the generic baseline.
- Do not require host-level `systemPrompt` parity for the generic baseline.
- Do not assume VS Code cloud/remote exposes the same operator surface as the local Claude CLI or SDK.
