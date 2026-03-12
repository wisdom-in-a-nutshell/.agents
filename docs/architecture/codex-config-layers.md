# Codex Config Layers

This page explains how Codex config is layered in this setup.

The short version is: canonical config lives in `~/.agents`, live machine config lives in `~/.codex`, and repo-specific behavior lives in repo-local `.codex/config.toml`. The important detail is that trusted repo-local config is additive, while the machine config sync is managed from templates.

## Figure 1: Config Layers

```mermaid
flowchart TD
    A[~/.agents/codex/config/global.config.toml]
    B[~/.agents/codex/config/xcode.config.toml]
    C[~/.agents/codex/config/repo-bootstrap.json]
    D[sync-config.sh]
    E[sync-trusted-projects.sh]
    F[sync-repo-codex-configs.sh]
    G[~/.codex/config.toml]
    H[Xcode Codex config]
    I[Repo-local .codex/config.toml]
    J[Codex runtime]

    A --> D
    B --> D
    C --> E
    C --> F
    D --> G
    D --> H
    E --> G
    E --> H
    F --> I
    G --> J
    I --> J
```

## Main Parts

### Canonical Templates

- `global.config.toml` defines the managed baseline for terminal Codex.
- `xcode.config.toml` defines the managed baseline for Xcode Codex.
- `repo-bootstrap.json` defines:
  - which repos are managed
  - which MCP presets each repo gets
  - optional per-repo model, reasoning, and service-tier overrides

These files are the source of truth.

### Live Machine Config

- `sync-config.sh` writes the managed baseline into `~/.codex/config.toml` and Xcode Codex config.
- It preserves machine-specific/runtime-specific state that should not live in git.
- It also prunes stale managed keys when the canonical template no longer wants them.

Example:
- `service_tier = "fast"` used to be in the canonical templates.
- After removing it from the templates, `sync-config.sh` now removes stale top-level copies from the live configs.

### Trusted Repo Config

- `sync-trusted-projects.sh` writes exact trusted repo roots into the live machine configs.
- That matters because repo-local `.codex/config.toml` is only loaded when the repo is trusted.

So trust sync is part of config layering, not a separate unrelated feature.

### Repo-Local Config

- `sync-repo-codex-configs.sh` generates repo-local `.codex/config.toml` files from `repo-bootstrap.json`.
- Most repos can have a minimal managed file with no repo-local overrides.
- Some repos get MCP presets or later model-specific overrides.
- `sync-repo-bootstrap-registry.sh` regenerates the Obsidian Base view for the same registry so the current assignments stay visible in Obsidian.

Current per-repo fields in `repo-bootstrap.json`:
- `mcp_presets`
- `model`
- `model_reasoning_effort`
- `service_tier`
- `notes`

## Main Flow

1. Edit canonical config in `~/.agents/codex/config/`.
2. Run `sync-config.sh` to update live machine config.
3. Run `sync-trusted-projects.sh` so Codex will load repo-local config for managed repos.
4. Run `sync-repo-codex-configs.sh` to render repo-local `.codex/config.toml` files.
5. Codex starts with `~/.codex/config.toml` and layers trusted repo-local config on top.

## Notes

- Use `docs/architecture/` to understand the shape of the system.
- Use [Codex Control Plane Operations](/Users/adi/.agents/docs/references/codex-control-plane-operations.md) for exact commands.
- Use [Codex Control Plane Ownership](/Users/adi/.agents/docs/references/codex-control-plane-ownership.md) for the keep/move/generate split.
