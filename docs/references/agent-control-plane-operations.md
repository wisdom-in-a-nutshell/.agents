# Agent Control-Plane Operations

Use this page for the machine-facing apply and validation entrypoints that live
at the root of `~/.agents`.

This repo is Codex-only. The root wrappers exist so external machine bootstrap
repos such as `~/GitHub/scripts` can call one stable `.agents` surface instead
of reaching into Codex internals directly.

Sparse machines are normal. A repo listed in the shared registries but not
cloned on the current machine is skipped silently by sync/check commands.
Existing non-git folders at managed repo paths still warn because they may be
broken placeholders that should be deleted or replaced with a real checkout.

For repo authors adding `scripts/hooks/*.py`, start with
[`repo-lifecycle-hook-adapter.md`](/Users/dobby/.agents/docs/references/repo-lifecycle-hook-adapter.md).

## Canonical Entry Points

- `scripts/bootstrap-machine-agent-control-planes.sh`
  - machine-facing full bootstrap batch
  - syncs managed skill links from `skills/registry.json`
  - syncs managed repo local Git `core.hooksPath` to the shared Git hooks directory
  - applies the Codex runtime via `codex/scripts/bootstrap-machine-codex.sh`
- `scripts/auto-apply-agent-control-planes.sh`
  - machine-facing post-sync reconcile entrypoint
  - checks the current `~/.agents` commit against a machine-local stamp
  - runs the minimum apply steps needed for runtime-relevant changes
- `scripts/enroll-managed-repos.sh`
  - scans direct child Git repos under `~/GitHub`
  - appends missing repos to `codex/config/repo-bootstrap.json` as minimal entries
  - regenerates the repo bootstrap registry views
- `scripts/check-agent-control-planes.sh`
  - validates hygiene, skills, plugins, managed Git hooks, Codex rendered state, and tests
- `scripts/audit-agent-runtime-drift.py`
  - read-only machine-health audit entrypoint
  - checks local Codex runtime drift such as unclassified OpenAI plugins and required plugin availability
- `scripts/sync-managed-git-hooks.sh`
  - sets repo-local `core.hooksPath` to `~/.agents/hooks/git`
  - supports `--check`
- `scripts/test-control-plane.sh`
  - hermetic regression test entrypoint

## Runtime-Relevant Change Model

`scripts/auto-apply-agent-control-planes.sh` watches:

- `skills/`
- `skills-source/`
- `mcp/`
- `codex/`
- `hooks/`
- `scripts/`

Current apply rules:

- `skills/` or `skills-source/` changes:
  - run `scripts/sync-skills-registry.sh`
  - run `codex/scripts/bootstrap-machine-codex.sh`
- `plugins/` changes:
  - run `scripts/sync-plugins-registry.sh`
  - run `codex/scripts/bootstrap-machine-codex.sh`
- `mcp/`, `hooks/`, or `codex/` changes:
  - run `codex/scripts/bootstrap-machine-codex.sh`
- `hooks/git/`, `scripts/sync-managed-git-hooks.sh`, or `codex/config/repo-bootstrap.json` changes:
  - run `scripts/sync-managed-git-hooks.sh`
- first reconcile or missing prior stamp:
  - fall back to the full shared bootstrap batch

## Commands

```bash
cd ~/.agents
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
```

Scoped validation/bootstrap:

```bash
./scripts/bootstrap-machine-agent-control-planes.sh --apply --repo ~/.agents
./scripts/check-agent-control-planes.sh --repo ~/.agents
```

## Lifecycle Hook Contract

- Lifecycle hooks are defined in [`hooks/registry.json`](/Users/dobby/.agents/hooks/registry.json).
- Codex global hooks render into `~/.codex/hooks.json`.
- Codex repo-local hooks render into managed repo `.codex/hooks.json`.
- `Stop` is global so the git conveyor does not depend on repo-local hook loading.
- `SessionStart`, `UserPromptSubmit`, and `SessionEnd` are repo-scoped to `adi` and `angie`.
- Event entrypoints live in [`hooks/scripts/`](/Users/dobby/.agents/hooks/scripts).
- Repo-specific lifecycle behavior belongs in optional Python scripts under `scripts/hooks/`.
- Missing repo scripts are successful no-ops.

## Commit Gate Contract

- The `Stop` hook runs [`hooks/scripts/stop.py`](/Users/dobby/.agents/hooks/scripts/stop.py).
- It stages changes, runs `git commit`, and lets Git invoke the shared local hook from [`hooks/git/pre-commit`](/Users/dobby/.agents/hooks/git/pre-commit).
- The shared Git hook delegates to repo-owned `scripts/check-fast.sh` when present.
- For tracked branches, Stop optimistically pushes first and only runs `git pull --rebase` when the push shows the remote is ahead.
- Brand-new branches without upstream tracking use `git push -u <remote> HEAD`.
- Stop hook timing is logged to `~/.local/state/agents-control-plane/log/hooks-stop.log`.
