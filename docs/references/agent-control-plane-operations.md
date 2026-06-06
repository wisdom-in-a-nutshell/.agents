# Agent Control-Plane Operations

Use this page for the machine-facing apply and validation entrypoints that live at the root of `~/GitHub/agents`.

This repo manages shared agent surfaces for Codex, Claude Code, skills, plugins, MCP presets, lifecycle hooks, and the local dashboard. The temporary Antigravity spike script is tracked for manual experiments but is disabled in the shared machine bootstrap. `~/.agents` is no longer the source checkout; it is reserved for runtime surfaces such as Codex user-scope skills at `~/.agents/skills`.

Sparse machines are normal. A repo listed in the shared registries but not cloned on the current machine is skipped silently by sync/check commands. Existing non-git folders at managed repo paths still warn because they may be broken placeholders that should be deleted or replaced with a real checkout.

For repo authors adding `scripts/hooks/*.py`, start with [`repo-lifecycle-hook-adapter.md`](/Users/dobby/GitHub/agents/docs/references/repo-lifecycle-hook-adapter.md).

## Canonical Entry Points

- `scripts/bootstrap-machine-agent-control-planes.sh`
  - machine-facing full bootstrap batch
  - syncs managed skill links from `skills/registry.json`
  - syncs managed repo local Git `core.hooksPath` to `~/GitHub/agents/hooks/git`
  - skips the temporary Antigravity spike surface by default
  - applies the Claude Code control-plane surface
  - applies the Codex runtime via `codex/scripts/bootstrap-machine-codex.sh`
- `scripts/auto-apply-agent-control-planes.sh`
  - machine-facing post-sync reconcile entrypoint
  - checks the current `~/GitHub/agents` commit against a machine-local stamp
  - runs the minimum apply steps needed for runtime-relevant changes
- `scripts/enroll-managed-repos.sh`
  - scans direct child Git repos under `~/GitHub`
  - appends missing repos to `codex/config/repo-bootstrap.json` as minimal entries
  - leaves visualization to the local control-plane dashboard
- `scripts/check-agent-control-planes.sh`
  - validates hygiene, skills, plugins, managed Git hooks, Codex rendered state, and tests
- `scripts/audit-agent-runtime-drift.py`
  - read-only machine-health audit entrypoint
  - checks local Codex runtime drift such as unclassified OpenAI plugins and required plugin availability
- `scripts/sync-managed-git-hooks.sh`
  - sets repo-local `core.hooksPath` to `~/GitHub/agents/hooks/git`
  - supports `--check`
- `scripts/sync-claude.sh`
  - renders `~/.claude/CLAUDE.md` from `config/global.agents.md`
  - renders managed global skill links under `~/.claude/skills`
  - renders managed repo-scoped skill links under each target repo's `.claude/skills`
  - renders repo `.claude/CLAUDE.md` bridge files containing `@../AGENTS.md` when the repo has `AGENTS.md`
  - renders user settings and the managed `Stop` hook under `~/.claude/settings.json`
  - enables YOLO through Claude Code's native bypass mode
  - renders a `~/bin/claude` wrapper that starts sessions with `--dangerously-skip-permissions`
  - renders per-repo dev-server launch configs (`.claude/launch.json`) from `dev-servers/registry.json`, opt-in per repo
- `scripts/sync-skills-registry.sh`
  - renders global Codex skill symlinks into `~/.agents/skills`
  - renders repo-scoped Codex skill symlinks into repo `.agents/skills`
- `scripts/switch-claude-provider.sh`
  - switches the machine-local Claude Code credential profile used by the wrapper
- `scripts/test-control-plane.sh`
  - hermetic regression test entrypoint

## Runtime-Relevant Change Model

`scripts/auto-apply-agent-control-planes.sh` watches:

- `config/`
- `skills/`
- `skills-source/`
- `plugins/`
- `mcp/`
- `codex/`
- `hooks/`
- `scripts/`
- `dev-servers/`

Current apply rules:

- `skills/` or `skills-source/` changes:
  - run `scripts/sync-skills-registry.sh`
  - run `codex/scripts/bootstrap-machine-codex.sh`
- `plugins/` changes:
  - run `scripts/sync-plugins-registry.sh`
  - run `codex/scripts/bootstrap-machine-codex.sh`
- `config/`, `mcp/`, `hooks/`, `codex/`, or `dev-servers/` changes:
  - run the relevant client sync or fall back to the full shared bootstrap batch
- `hooks/git/`, `scripts/sync-managed-git-hooks.sh`, or `codex/config/repo-bootstrap.json` changes:
  - run `scripts/sync-managed-git-hooks.sh`
- first reconcile or missing prior stamp:
  - fall back to the full shared bootstrap batch

## Commands

```bash
cd ~/GitHub/agents
./scripts/bootstrap-machine-agent-control-planes.sh
./scripts/bootstrap-machine-agent-control-planes.sh --apply
./scripts/enroll-managed-repos.sh --dry-run
./scripts/enroll-managed-repos.sh --apply
./scripts/auto-apply-agent-control-planes.sh --dry-run
./scripts/auto-apply-agent-control-planes.sh --apply
./scripts/audit-agent-runtime-drift.py --plain
./scripts/check-agent-control-planes.sh
./scripts/test-control-plane.sh
./scripts/sync-managed-git-hooks.sh --apply
./scripts/sync-managed-git-hooks.sh --check
./scripts/sync-claude.sh --apply
./scripts/switch-claude-provider.sh status
./scripts/switch-claude-provider.sh subscription --apply
./scripts/switch-claude-provider.sh aws --apply
```

Scoped validation/bootstrap:

```bash
./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo ~/GitHub/agents
./scripts/check-agent-control-planes.sh --repo ~/GitHub/agents
```

## Lifecycle Hook Contract

- Lifecycle hooks are defined in [`hooks/registry.json`](/Users/dobby/GitHub/agents/hooks/registry.json).
- Codex global hooks render into `~/.codex/hooks.json`.
- Codex repo-local hooks render into managed repo `.codex/hooks.json`.
- Claude Code global hooks render into `~/.claude/settings.json`.
- `Stop` is global so the git conveyor does not depend on repo-local hook loading.
- `SessionStart` and `UserPromptSubmit` are repo-scoped to selected repos in `hooks/registry.json`.
- Explicit Codex thread finalization is not a native hook. The global `codex/scripts/finalize-codex-thread.py` command derives repo policy from `thread/read` and runs optional repo-local `scripts/hooks/finalize_codex_thread.py` before archive.
- Event entrypoints live in [`hooks/scripts/`](/Users/dobby/GitHub/agents/hooks/scripts).
- Repo-specific lifecycle behavior belongs in optional Python scripts under `scripts/hooks/`.
- Missing repo scripts are successful no-ops.

## Commit Gate Contract

- The `Stop` hook runs [`hooks/scripts/stop.py`](/Users/dobby/GitHub/agents/hooks/scripts/stop.py).
- It stages changes, runs `git commit`, and lets Git invoke the shared local hook from [`hooks/git/pre-commit`](/Users/dobby/GitHub/agents/hooks/git/pre-commit).
- The shared Git hook delegates to repo-owned `scripts/check-fast.sh` when present.
- For tracked branches, Stop optimistically pushes first and only runs `git pull --rebase` when the push shows the remote is ahead.
- Brand-new branches without upstream tracking use `git push -u <remote> HEAD`.
- Stop hook timing is logged to `~/.local/state/agents-control-plane/log/hooks-stop.log`.
