# Codex Control Plane Script Flows

This page breaks the Codex control-plane scripts into smaller figures.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the top-level system shape.
Use [Codex Control Plane Operations](/Users/dobby/.agents/docs/references/codex-control-plane-operations.md) for exact commands and checks.

## Overview

The scripts are easier to understand if you split them into three groups:

- plugin-source refresh/sync scripts that feed skills and MCP
- apply scripts that write config and trust state
- post-sync reconcile scripts that auto-apply new control-plane revisions
- startup scripts that shape the terminal and Ghostty experience
- post-turn scripts that run after Codex finishes a turn

## Figure 1: Plugin Source And Apply Scripts

```mermaid
flowchart TD
    P[refresh-external-plugins.sh] --> Q[sync-plugins-registry.sh]
    Q --> S[skills/registry.json managed_plugin_skills]
    Q --> T[mcp/config/presets.json plugin_presets]
    Q --> R[repo-bootstrap.json plugin_mcp_presets]
    A[bootstrap-machine-codex.sh] --> B[sync-config.sh]
    A --> C[sync-trusted-projects.sh]
    A --> D[sync-repo-codex-configs.sh]
    A --> E[configure-ghostty-cwd.sh]
    R[repo-bootstrap.json] --> C
    R --> D
    M[mcp/config/presets.json] --> B
    M --> D
    B --> F[~/.codex/config.toml]
    B --> G[Xcode Codex config]
    C --> F
    C --> G
    D --> H[Repo-local .codex/config.toml]
    E --> I[Ghostty config]
```

### What This Group Does

- [`refresh-external-plugins.sh`](/Users/dobby/.agents/scripts/refresh-external-plugins.sh)
  - refreshes mirrored plugin source under `plugins-source/external/`
- [`sync-plugins-registry.sh`](/Users/dobby/.agents/scripts/sync-plugins-registry.sh)
  - validates `plugins/registry.json`
  - writes plugin registry views
  - derives plugin-provided skills into `skills/registry.json`
  - derives plugin-provided MCP presets into `mcp/config/presets.json`
  - derives repo MCP assignments into `codex/config/repo-bootstrap.json`
- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - orchestrates the main Codex-specific bootstrap batch
- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - writes the managed terminal and Xcode Codex config
  - injects machine-wide global MCP servers from [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)
- [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - writes exact trust entries for discovered Git repos
- [`sync-repo-codex-configs.sh`](/Users/dobby/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - renders managed repo-local `.codex/config.toml` files for all registered repos
  - also materializes repo-local `.codex/agents/*.toml` files for assigned repo-scoped custom agents
  - resolves repo MCP presets through [`mcp/config/presets.json`](/Users/dobby/.agents/mcp/config/presets.json)
- [`repo-bootstrap.json`](/Users/dobby/.agents/codex/config/repo-bootstrap.json)
  - defines the managed repo set, repo MCP assignment, repo-scoped custom agents, and per-repo model/service-tier/reasoning overrides
- [`configure-ghostty-cwd.sh`](/Users/dobby/.agents/codex/scripts/configure-ghostty-cwd.sh)
  - rewrites Ghostty config so Codex startup and cwd handling stay consistent

## Figure 2: Post-Sync Reconcile

```mermaid
flowchart TD
    A[git-auto-sync.sh] --> B[auto-apply-agent-control-planes.sh]
    B --> C{What changed in ~/.agents?}
    C -->|skills| D[sync-skills-registry.sh]
    C -->|plugins| P[refresh-external-plugins.sh + sync-plugins-registry.sh]
    C -->|skills, plugins, codex, or mcp| E[bootstrap-machine-codex.sh --apply]
    C -->|skills, plugins, claude, or shared inputs| F[bootstrap-machine-claude.sh --apply]
    D --> G[Update shared runtime links]
    P --> G2[Update plugin-derived skills/MCP state]
    E --> H[Codex runtime updated]
    F --> I[Claude runtime updated]
    G --> J[Update machine-local reconcile stamp]
    G2 --> J
    H --> J
    I --> J
```

### What This Group Does

- [`git-auto-sync.sh`](/Users/dobby/GitHub/scripts/sync/git-auto-sync.sh)
  - remains the launchd-driven machine sync loop in the generic `scripts` repo
- [`auto-apply-agent-control-planes.sh`](/Users/dobby/.agents/scripts/auto-apply-agent-control-planes.sh)
  - checks whether the current `~/.agents` revision contains new runtime-relevant shared control-plane changes since the last successful reconcile on that machine
  - runs the minimum shared apply steps needed for skills, Codex, and Claude
  - keeps a machine-local stamp under `~/.local/state/agents-control-plane/`
  - the surrounding `~/GitHub/scripts/sync/git-auto-sync.sh` loop also reapplies the shared `~/.zshrc` and `~/.zprofile` links after the shared agent reconcile step
- [`auto-apply-codex-control-plane.sh`](/Users/dobby/.agents/codex/scripts/auto-apply-codex-control-plane.sh)
  - remains the lower-level Codex-only reconcile helper for targeted Codex-only troubleshooting or component-scoped automation

## Figure 3: Shell And Startup Scripts

```mermaid
flowchart TD
    A[zshrc.shared] --> B[codex-shell.zsh]
    A2[zprofile.shared] --> G[Codex CLI]
    C[Ghostty initial-command] --> D[ghostty-codex-then-shell.sh]
    B --> E[codex_jump]
    H[Optional Ghostty helpers] --> I[open-ghostty-codex-picker-current.sh / open-ghostty-codex-tab.sh / open-ghostty-codex-picker-tab.sh]
    D --> G[Codex CLI]
    I --> G
```

### What This Group Does

- [`zshrc.shared`](/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared)
  - generic shared shell file that sources the Codex shell fragment
- [`zprofile.shared`](/Users/dobby/GitHub/scripts/setup/codex/zprofile.shared)
  - shared login-shell bootstrap that hydrates machine-local shared env and trusted repo-local env for `zsh -lc` shells
- [`codex-shell.zsh`](/Users/dobby/.agents/codex/shell/codex-shell.zsh)
  - defines Codex shell behavior such as the jump picker and Ghostty auto-start logic
- [`ghostty-codex-then-shell.sh`](/Users/dobby/.agents/codex/scripts/ghostty-codex-then-shell.sh)
  - runs Codex first, then falls back to a normal login shell
- [`link-shared-zshrc.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zshrc.sh)
  - links `~/.zshrc` to the tracked shared shell file
- [`link-shared-zprofile.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zprofile.sh)
  - links `~/.zprofile` to the tracked shared login-shell file

## Figure 4: Post-Turn Automation

```mermaid
flowchart TD
    A[Agent turn reaches Stop] --> B[hooks/scripts/stop.py]
    B --> C[git add -A]
    C --> D[git commit runs repo-owned pre-commit]
    D --> E{commit succeeded?}
    E -->|no| F[return hook block with failure details]
    E -->|yes, tracked branch| G[git pull --rebase]
    G --> H[git push remote HEAD]
    E -->|yes, no upstream| I[git push -u remote HEAD]
```

### What This Group Does

- [`stop.py`](/Users/dobby/.agents/hooks/scripts/stop.py)
  - runs as the shared Codex and Claude `Stop` hook
  - stages all repo changes and lets `git commit` run that repo's own pre-commit checks
  - if commit checks fail, returns hook continuation JSON with the failure output so the current agent can fix it
  - for tracked branches, commits then runs `git pull --rebase` followed by push
  - for brand-new local branches without upstream tracking, uses `git push -u <remote> HEAD` to establish upstream automatically
- [`session_start.py`](/Users/dobby/.agents/hooks/scripts/session_start.py)
  - shared no-op `SessionStart` hook; kept silent unless a future milestone intentionally adds startup context

## Figure 5: Optional Machine Policy Script

```mermaid
flowchart TD
    A[install-sudoers-codex-ops.sh] --> B["/etc/sudoers.d/codex-ops"]
    B --> C[Codex machine ops without password prompts]
```

### What This Script Does

- [`install-sudoers-codex-ops.sh`](/Users/dobby/.agents/codex/scripts/install-sudoers-codex-ops.sh)
  - installs the narrow sudo policy used by Codex machine-ops workflows

## Reading Order

If you want the fastest mental model, read in this order:

1. [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md)
2. [Codex Control Plane Script Flows](/Users/dobby/.agents/docs/architecture/codex-control-plane-script-flows.md)
3. [Codex Control Plane Operations](/Users/dobby/.agents/docs/references/codex-control-plane-operations.md)
