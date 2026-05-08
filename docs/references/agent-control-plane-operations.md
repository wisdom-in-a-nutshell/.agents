# Agent Control-Plane Operations

Use this page for the shared machine-facing apply and validation entrypoints that live at the root of `~/.agents`.

These wrappers exist so external machine bootstrap repos such as `~/GitHub/scripts` can call one stable `.agents` surface instead of reaching into Codex- or Claude-specific internals directly.

For repo authors adding `scripts/hooks/*.py`, start with
[`repo-lifecycle-hook-adapter.md`](/Users/dobby/.agents/docs/references/repo-lifecycle-hook-adapter.md).

## Canonical Shared Entry Points

- `scripts/bootstrap-machine-agent-control-planes.sh`
  - machine-facing full bootstrap batch
  - syncs managed skill links from `skills/registry.json`
  - syncs managed repo local Git `core.hooksPath` to the shared Git hooks directory
  - renders repo-local hook files from the shared hook registry through the Codex, Claude, and GitHub Copilot control planes
  - applies the Codex runtime via `codex/scripts/bootstrap-machine-codex.sh`
  - applies the Claude runtime via `claude/scripts/bootstrap-machine-claude.sh`
- `scripts/auto-apply-agent-control-planes.sh`
  - machine-facing post-sync reconcile entrypoint
  - checks the current `~/.agents` commit against a machine-local stamp
  - runs the minimum shared apply steps needed for runtime-relevant changes
- `scripts/check-agent-control-planes.sh`
  - shared validation entrypoint
  - validates skills registry artifacts, managed repo local Git hook config, repo-local hook config, plus Codex and Claude rendered runtime state
  - runs the hermetic control-plane regression suite in `tests/control_plane/`
- `scripts/audit-agent-runtime-drift.py`
  - read-only machine-health audit entrypoint
  - calls the shared control-plane validation, then checks local runtime-only drift such as unclassified OpenAI Codex plugins and required Computer Use availability
  - defaults to a stable JSON result contract; use `--plain` for operator-readable health-check logs
  - is intended to be scheduled and notified by `~/GitHub/scripts`, not by launchd directly from this repo
- `scripts/sync-managed-git-hooks.sh`
  - machine-facing local-only sync for managed repo Git hooks
  - sets repo-local `core.hooksPath` to `~/.agents/hooks/git`
  - supports `--check` to fail when a managed repo is not pointed at the shared hook directory
- `scripts/sync-copilot-hooks.sh`
  - repo-facing sync for managed GitHub Copilot hook files
  - renders `.github/hooks/agent-control-plane.json` for each managed repo in `codex/config/repo-bootstrap.json`
  - supports `--check` to fail when repo-local Copilot hook files are stale
- `scripts/test-control-plane.sh`
  - hermetic regression test entrypoint for shared skills, hooks, MCPs, Codex config rendering, Claude config rendering, and shared registry views

## Runtime-Relevant Change Model

`scripts/auto-apply-agent-control-planes.sh` currently watches:

- `skills/`
- `skills-source/`
- `mcp/`
- `codex/`
- `claude/`
- `hooks/`
- `scripts/sync-copilot-hooks.sh`
- `scripts/sync-managed-git-hooks.sh`

Current apply rules:

- `skills/` or `skills-source/` changes:
  - run `scripts/sync-skills-registry.sh`
  - run `codex/scripts/bootstrap-machine-codex.sh`
  - run `claude/scripts/bootstrap-machine-claude.sh`
- `mcp/` changes:
  - run both Codex and Claude bootstrap batches
- `hooks/` changes:
  - sync repo-local GitHub Copilot hook files
  - run both Codex and Claude bootstrap batches
- `hooks/git/`, `scripts/sync-managed-git-hooks.sh`, or repo-bootstrap registry changes:
  - sync managed repo local Git hook config
- `scripts/sync-copilot-hooks.sh` or repo-bootstrap registry changes:
  - sync managed repo local GitHub Copilot hook files
- `codex/` changes:
  - run Codex bootstrap
  - if the change is `codex/config/repo-bootstrap.json`, also run Claude bootstrap
- `claude/` changes:
  - run Claude bootstrap
- first reconcile or missing prior stamp:
  - fall back to the full shared bootstrap batch

## Commands

```bash
cd ~/.agents
./scripts/bootstrap-machine-agent-control-planes.sh
./scripts/bootstrap-machine-agent-control-planes.sh --apply
./scripts/auto-apply-agent-control-planes.sh --dry-run
./scripts/auto-apply-agent-control-planes.sh --apply
./scripts/audit-agent-runtime-drift.py --plain
./scripts/check-agent-control-planes.sh
./scripts/test-control-plane.sh
./scripts/sync-managed-git-hooks.sh --apply
./scripts/sync-managed-git-hooks.sh --check
./scripts/sync-copilot-hooks.sh --apply
./scripts/sync-copilot-hooks.sh --check
```

Optional scoped Claude validation/bootstrap:

```bash
./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo ~/.agents
./scripts/check-agent-control-planes.sh --repo ~/.agents
```

Preferred rule for repo bootstrap or MCP changes:

- if a change touches `mcp/config/presets.json`, `codex/config/repo-bootstrap.json`, or repo MCP assignment, use the shared root bootstrap wrapper first:
  - `./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo <repo>`
- use component-only `codex/scripts/*` or `claude/scripts/*` entrypoints only when you intentionally want to troubleshoot or re-render one surface without touching the other

## Boundary Rule

- Machine repos such as `~/GitHub/scripts` should call these root wrappers.
- Codex- and Claude-specific scripts remain the low-level component entrypoints owned by `codex/` and `claude/`.
- Update this page and the component docs together when the shared machine-facing flow changes.

## Agent Lifecycle Hook Contract

- Lifecycle hooks are defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and rendered into repo-local Codex, Claude, and GitHub Copilot config surfaces for the repos assigned there.
- Current assignment policy:
  - `Stop` is global for Codex and Claude so the git conveyor does not depend on repo-local hook loading.
  - GitHub Copilot still receives `agentStop` through repo-local hook files for all managed repos.
  - `SessionStart`, `UserPromptSubmit`, `PreCompact`, `PostCompact`, and `SessionEnd` are repo-scoped to `adi` and `angie`.
- Rendered global hook surfaces are `~/.codex/hooks.json` and `~/.claude/settings.json`; rendered repo-local hook surfaces are `.codex/hooks.json`, `.claude/settings.json`, and `.github/hooks/agent-control-plane.json`.
- Event entrypoints live in [`hooks/scripts/session_start.py`](/Users/dobby/.agents/hooks/scripts/session_start.py), [`hooks/scripts/user_prompt_submit.py`](/Users/dobby/.agents/hooks/scripts/user_prompt_submit.py), [`hooks/scripts/pre_compact.py`](/Users/dobby/.agents/hooks/scripts/pre_compact.py), [`hooks/scripts/post_compact.py`](/Users/dobby/.agents/hooks/scripts/post_compact.py), and [`hooks/scripts/session_end.py`](/Users/dobby/.agents/hooks/scripts/session_end.py).
- Shared dispatch plumbing lives in [`hooks/scripts/hook_runtime.py`](/Users/dobby/.agents/hooks/scripts/hook_runtime.py); runtime-specific payload normalization lives in [`hooks/scripts/hook_adapter.py`](/Users/dobby/.agents/hooks/scripts/hook_adapter.py).
- The canonical repo hook authoring contract is [`repo-lifecycle-hook-adapter.md`](/Users/dobby/.agents/docs/references/repo-lifecycle-hook-adapter.md). Keep payload fields, environment variables, stdout semantics, smoke tests, and hand-off guidance there instead of duplicating them on this operations page.
- Repo-specific lifecycle behavior belongs in optional Python scripts under `scripts/hooks/`. Missing repo scripts are successful no-ops.
- Codex renders assigned `SessionStart`, `UserPromptSubmit`, `PreCompact`, `PostCompact`, and `Stop` events; it does not render a fake `SessionEnd`.

## Agent Commit Gate Contract

- The `Stop` hook is defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json). Codex and Claude render it globally; GitHub Copilot renders it repo-locally as `agentStop`.
- In Codex and Claude, `Stop` is the native runtime event for turn-stop behavior. In GitHub Copilot, the same logical hook renders as `agentStop`.
- The `Stop` hook runs [`hooks/scripts/stop.py`](/Users/dobby/.agents/hooks/scripts/stop.py), stages changes, and runs `git commit`.
- Git invokes the shared local hook from [`hooks/git/pre-commit`](/Users/dobby/.agents/hooks/git/pre-commit) because managed repos have local `core.hooksPath` set to `~/.agents/hooks/git`.
- The shared Git hook delegates to repo-owned `scripts/check-fast.sh` when present.
- For tracked branches, the Stop hook optimistically pushes first and only runs `git pull --rebase` when the push shows the remote is ahead.
- Stop hook timing is logged to `~/.local/state/agents-control-plane/log/hooks-stop.log` with phase durations such as status, add, commit/check, push, and pull/rebase fallback.
- Treat `scripts/check-fast.sh` as the repo's fast deterministic commit gate for agent-made changes, not as a general after-turn lifecycle hook.
- Prefer staged/affected checks in `scripts/check-fast.sh`; only keep broad checks there when they are cheap and protect a repo-level invariant.
- Put slow or broad repo-wide validation in `scripts/check-full.sh` or another explicit command.

## GitHub Copilot Hook Rendering

- GitHub Copilot loads hook files from `.github/hooks/*.json` in the repository.
- This control plane renders one managed file per assigned repo: `.github/hooks/agent-control-plane.json`.
- Local Copilot CLI can read the rendered file from the worktree. Copilot cloud agent needs the file committed on the repo's default branch.
- The rendered file includes only the events assigned to that repo and uses GitHub's native event names:
  - `sessionStart`
  - `userPromptSubmitted`
  - `agentStop`
  - `sessionEnd`
- The rendered commands guard on `~/.agents/hooks/scripts/<hook>.py` existing before running.
  - Local Copilot CLI sessions on this machine execute the shared hook dispatchers.
  - GitHub cloud agent sessions no-op if `~/.agents` is absent, instead of failing because this personal control plane is not installed in the cloud runner.
- Do not add repo-specific behavior directly to `.github/hooks/agent-control-plane.json`; add optional repo scripts under `scripts/hooks/` or update `hooks/registry.json`.
