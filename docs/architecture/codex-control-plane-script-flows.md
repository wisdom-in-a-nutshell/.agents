# Codex Control Plane Script Flows

This page breaks the Codex control-plane scripts into smaller figures.

Use [Codex Control Plane](/Users/dobby/.agents/docs/architecture/codex-control-plane.md) for the top-level system shape.
Use [Codex Control Plane Operations](/Users/dobby/.agents/docs/references/codex-control-plane-operations.md) for exact commands and checks.

## Overview

The scripts are easier to understand if you split them into three groups:

- apply scripts that write config and trust state
- startup scripts that shape the terminal and Ghostty experience
- post-turn scripts that run after Codex finishes a turn

## Figure 1: Apply Scripts

```mermaid
flowchart TD
    A[bootstrap-machine-codex.sh] --> B[sync-config.sh]
    A --> C[sync-trusted-projects.sh]
    A --> D[sync-repo-codex-configs.sh]
    A --> E[configure-ghostty-cwd.sh]
    R[repo-bootstrap.toml] --> C
    R --> D
    B --> F[~/.codex/config.toml]
    B --> G[Xcode Codex config]
    C --> F
    C --> G
    D --> H[Repo-local .codex/config.toml]
    E --> I[Ghostty config]
```

### What This Group Does

- [`bootstrap-machine-codex.sh`](/Users/dobby/.agents/codex/scripts/bootstrap-machine-codex.sh)
  - orchestrates the main Codex-specific bootstrap batch
- [`sync-config.sh`](/Users/dobby/.agents/codex/scripts/sync-config.sh)
  - writes the managed terminal and Xcode Codex config
- [`sync-trusted-projects.sh`](/Users/dobby/.agents/codex/scripts/sync-trusted-projects.sh)
  - writes exact trust entries for discovered Git repos
- [`sync-repo-codex-configs.sh`](/Users/adi/.agents/codex/scripts/sync-repo-codex-configs.sh)
  - renders managed repo-local `.codex/config.toml` files for all registered repos
- [`repo-bootstrap.toml`](/Users/adi/.agents/codex/config/repo-bootstrap.toml)
  - defines the managed repo set, extra repos outside `~/GitHub`, and repo MCP presets
- [`configure-ghostty-cwd.sh`](/Users/dobby/.agents/codex/scripts/configure-ghostty-cwd.sh)
  - rewrites Ghostty config so Codex startup and cwd handling stay consistent

## Figure 2: Shell And Startup Scripts

```mermaid
flowchart TD
    A[zshrc.shared] --> B[codex-shell.zsh]
    C[Ghostty initial-command] --> D[ghostty-codex-then-shell.sh]
    B --> E[codex_jump]
    B --> F[Ghostty auto-start loop]
    D --> G[Codex CLI]
    F --> G
```

### What This Group Does

- [`zshrc.shared`](/Users/dobby/GitHub/scripts/setup/codex/zshrc.shared)
  - generic shared shell file that sources the Codex shell fragment
- [`codex-shell.zsh`](/Users/dobby/.agents/codex/shell/codex-shell.zsh)
  - defines Codex shell behavior such as the jump picker and Ghostty auto-start logic
- [`ghostty-codex-then-shell.sh`](/Users/dobby/.agents/codex/scripts/ghostty-codex-then-shell.sh)
  - runs Codex first, then falls back to a normal login shell
- [`link-shared-zshrc.sh`](/Users/dobby/GitHub/scripts/setup/codex/link-shared-zshrc.sh)
  - links `~/.zshrc` to the tracked shared shell file

## Figure 3: Post-Turn Automation

```mermaid
flowchart TD
    A[Codex turn completes] --> B[notify.py]
    B --> C[git add / commit / pull --rebase / push]
    B --> D[auto-fix guard]
    D --> E[codex exec -p autofix]
```

### What This Group Does

- [`notify.py`](/Users/dobby/.agents/codex/scripts/notify.py)
  - runs after a Codex turn and automates the git loop
- [`notify-wrapper.sh`](/Users/dobby/.agents/codex/scripts/notify-wrapper.sh)
  - thin shell entrypoint that logs and calls `notify.py`

## Figure 4: Optional Machine Policy Script

```mermaid
flowchart TD
    A[install-sudoers-codex-ops.sh] --> B[/etc/sudoers.d/codex-ops]
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
