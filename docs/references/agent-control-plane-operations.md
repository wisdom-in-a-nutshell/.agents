# Agent Control-Plane Operations

Use this page for the shared machine-facing apply and validation entrypoints that live at the root of `~/.agents`.

These wrappers exist so external machine bootstrap repos such as `~/GitHub/scripts` can call one stable `.agents` surface instead of reaching into Codex- or Claude-specific internals directly.

## Canonical Shared Entry Points

- `scripts/bootstrap-machine-agent-control-planes.sh`
  - machine-facing full bootstrap batch
  - syncs managed skill links from `skills/registry.json`
  - syncs managed repo local Git `core.hooksPath` to the shared Git hooks directory
  - renders repo-local GitHub Copilot hook files from the shared hook registry
  - applies the Codex runtime via `codex/scripts/bootstrap-machine-codex.sh`
  - applies the Claude runtime via `claude/scripts/bootstrap-machine-claude.sh`
- `scripts/auto-apply-agent-control-planes.sh`
  - machine-facing post-sync reconcile entrypoint
  - checks the current `~/.agents` commit against a machine-local stamp
  - runs the minimum shared apply steps needed for runtime-relevant changes
- `scripts/check-agent-control-planes.sh`
  - shared validation entrypoint
  - validates skills registry artifacts, managed repo local Git hook config, managed repo Copilot hook config, plus Codex and Claude rendered runtime state
  - runs the hermetic control-plane regression suite in `tests/control_plane/`
- `scripts/sync-managed-git-hooks.sh`
  - machine-facing local-only sync for managed repo Git hooks
  - sets repo-local `core.hooksPath` to `~/.agents/hooks/git`
  - supports `--check` to fail when a managed repo is not pointed at the shared hook directory
- `scripts/sync-copilot-hooks.sh`
  - repo-facing sync for managed GitHub Copilot hook files
  - renders `.github/hooks/agent-control-plane.json` for each managed repo in `codex/config/repo-bootstrap.json`
  - supports `--check` to fail when repo-local Copilot hook files are stale
- `scripts/test-control-plane.sh`
  - hermetic regression test entrypoint for shared skills, hooks, MCPs, Codex config rendering, Claude subagent rendering, and shared registry views

## Runtime-Relevant Change Model

`scripts/auto-apply-agent-control-planes.sh` currently watches:

- `agents/`
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
  - sync repo-local Copilot hook files
  - run both Codex and Claude bootstrap batches
- `hooks/git/`, `scripts/sync-managed-git-hooks.sh`, or repo-bootstrap registry changes:
  - sync managed repo local Git hook config
- `scripts/sync-copilot-hooks.sh` or repo-bootstrap registry changes:
  - sync managed repo local GitHub Copilot hook files
- `agents/` changes:
  - run both Codex and Claude bootstrap batches
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

## Agent Session Start Contract

- The global lifecycle `SessionStart` hook is defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and rendered into Codex, Claude, and managed repo-local GitHub Copilot hook config.
- The `SessionStart` hook runs [`hooks/scripts/session_start.py`](/Users/dobby/.agents/hooks/scripts/session_start.py).
- `session_start.py` resolves the current git root from the hook payload `cwd`.
- If the repo contains `scripts/hooks/session-start.sh`, the dispatcher runs that script from the repo root.
- The repo script receives the original hook JSON on stdin and these environment variables:
  - `AGENT_HOOK_EVENT=SessionStart`
  - `AGENT_HOOK_RUNTIME=codex`, `claude`, or `copilot`
  - `AGENT_REPO_ROOT=<repo root>`
- For Codex and Claude, the repo script's stdout is forwarded as startup context for the agent. GitHub Copilot currently ignores `sessionStart` output, so use this hook there only for local setup or logging.
- Keep repo script output concise, deterministic, and non-interactive.
- If the repo has no `scripts/hooks/session-start.sh`, the hook exits silently and successfully.

## Agent Prompt Submit Contract

- The global lifecycle `UserPromptSubmit` hook is defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and rendered into Codex, Claude, and managed repo-local GitHub Copilot hook config.
- The `UserPromptSubmit` hook runs [`hooks/scripts/user_prompt_submit.py`](/Users/dobby/.agents/hooks/scripts/user_prompt_submit.py).
- `user_prompt_submit.py` resolves the current git root from the hook payload `cwd`.
- If the repo contains `scripts/hooks/user-prompt-submit.sh`, the dispatcher runs that script from the repo root.
- The repo script receives the original hook JSON on stdin and these environment variables:
  - `AGENT_HOOK_EVENT=UserPromptSubmit`
  - `AGENT_HOOK_RUNTIME=codex`, `claude`, or `copilot`
  - `AGENT_REPO_ROOT=<repo root>`
- For Codex and Claude, the repo script's stdout is forwarded as additional prompt context. GitHub Copilot currently ignores `userPromptSubmitted` output.
- Keep repo script output concise, deterministic, and non-interactive.
- If the repo has no `scripts/hooks/user-prompt-submit.sh`, the hook exits silently and successfully.

## Agent Commit Gate Contract

- The global lifecycle `Stop` hook is defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and rendered into Codex, Claude, and managed repo-local GitHub Copilot hook config.
- In Codex and Claude, `Stop` is the native runtime event for turn-stop behavior. In GitHub Copilot, the same logical hook renders as `agentStop`.
- The `Stop` hook runs [`hooks/scripts/stop.py`](/Users/dobby/.agents/hooks/scripts/stop.py), stages changes, and runs `git commit`.
- Git invokes the shared local hook from [`hooks/git/pre-commit`](/Users/dobby/.agents/hooks/git/pre-commit) because managed repos have local `core.hooksPath` set to `~/.agents/hooks/git`.
- The shared Git hook delegates to repo-owned `scripts/check-fast.sh` when present.
- Treat `scripts/check-fast.sh` as the repo's fast deterministic commit gate for agent-made changes, not as a general after-turn lifecycle hook.
- Put slow or broad validation in `scripts/check-full.sh` or another explicit command.

## Agent Session End Contract

- The global lifecycle `SessionEnd` hook is defined once in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json) and currently renders into Claude runtime config and managed repo-local GitHub Copilot hook config.
- Codex does not currently expose a separate documented `SessionEnd` hook; do not render a fake Codex equivalent.
- The `SessionEnd` hook runs [`hooks/scripts/session_end.py`](/Users/dobby/.agents/hooks/scripts/session_end.py).
- If the repo contains `scripts/hooks/session-end.sh`, the dispatcher runs that script from the repo root.
- The repo script receives the original hook JSON on stdin and these environment variables:
  - `AGENT_HOOK_EVENT=SessionEnd`
  - `AGENT_HOOK_RUNTIME=claude` or `copilot`
  - `AGENT_REPO_ROOT=<repo root>`
- The repo script's stdout is logged under machine-local agent state instead of injected into context because the session is ending.
- If the repo has no `scripts/hooks/session-end.sh`, the hook exits silently and successfully.

## GitHub Copilot Hook Rendering

- GitHub Copilot loads hook files from `.github/hooks/*.json` in the repository.
- This control plane renders one managed file per repo: `.github/hooks/agent-control-plane.json`.
- Local Copilot CLI can read the rendered file from the worktree. Copilot cloud agent needs the file committed on the repo's default branch.
- The rendered file uses GitHub's native event names:
  - `sessionStart`
  - `userPromptSubmitted`
  - `agentStop`
  - `sessionEnd`
- The rendered commands guard on `~/.agents/hooks/scripts/<hook>.py` existing before running.
  - Local Copilot CLI sessions on this machine execute the shared hook dispatchers.
  - GitHub cloud agent sessions no-op if `~/.agents` is absent, instead of failing because this personal control plane is not installed in the cloud runner.
- Do not add repo-specific behavior directly to `.github/hooks/agent-control-plane.json`; add optional repo scripts under `scripts/hooks/` or update `hooks/registry.json`.
