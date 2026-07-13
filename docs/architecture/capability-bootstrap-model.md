# Capability Bootstrap Model

This repo has three capability families: Codex plugins, standalone skills, and standalone MCPs.

Agent delegation is intentionally not modeled here. Codex can still spawn subagents through its native runtime behavior, but this control plane does not keep a registry of named agents or assign those agents to repos.

## Control-Plane Shape

```mermaid
flowchart TD
    P[plugins/registry.json]
    A[skills/registry.json]
    B[codex/config/repo-bootstrap.json]
    C[mcp/config/presets.json]
    PS[sync-plugins-registry.sh]
    E[sync-skills-registry.sh]
    F[sync-repo-codex-configs.sh]
    G[sync-config.sh]
    H[validate repo bootstrap registry]
    D[control-plane-dashboard.py]
    I[Global Codex runtime]
    J[Repo-local runtime]
    K[Dashboard]

    P --> PS
    P --> G
    P --> F
    P --> D
    A --> E
    A --> D
    B --> F
    B --> H
    B --> D
    C --> F
    C --> G
    C --> H
    C --> D
    C --> J
    E --> I
    F --> J
    G --> I
    D --> K
```

## Codex Plugins

Source of truth:

- `plugins/registry.json`

Plugins remain native Codex plugins. The registry supports `global`, `repo`, and `dormant` scope: global entries render into `~/.codex/config.toml`, repo entries render only into assigned repo `.codex/config.toml`, and dormant entries stay tracked without rendering. Bundled plugin discovery points at the marketplace inside `Codex.app`; the control plane only seeds the installed plugin cache for enabled bundled plugins. The control plane does not automatically split plugin packages into skill or MCP registries.

## Skills

Source of truth:

- `skills/registry.json`

Skills are standalone agent guidance. They can be global, repo-scoped, unmanaged repo-local, or explicitly linked from tracked plugin source through `managed_plugin_skills`. The dashboard shows effective skill availability per repo.

## MCPs

Source of truth:

- MCP definitions and repository/client targets in `mcp/config/presets.json`
- managed repo inventory in `codex/config/repo-bootstrap.json`

MCPs are standalone endpoints and transports. Every definition owns a two-axis target matrix: repositories down one axis and clients (`codex`, `claude`, `copilot`) across the other. A selector can target explicit values or `"all"`. If a plugin contains MCP internally, that remains plugin-owned unless it is manually promoted into this registry.

Codex cells render to repo `.codex/config.toml`. Claude and Copilot can share root `.mcp.json`. An exclusive Copilot target with `repos: "all"` renders once to `~/.copilot/mcp-config.json`; narrower Copilot-only targets render to `.github/mcp.json` only where no root `.mcp.json` exists. Because Copilot CLI 1.0.70 selects root `.mcp.json` instead of merging the two workspace files, the compiler rejects a repo matrix that would require both. It also rejects Claude-without-Copilot targets because Copilot discovers Claude's root project file.

## Working Rules

- Keep Codex plugin scope and state in `plugins/registry.json`.
- Keep skill content in `skills-source/`.
- Keep MCP definitions and all MCP target assignments in `mcp/config/presets.json`.
- Keep repo inventory and repo defaults in `codex/config/repo-bootstrap.json`.
- Do not automatically project plugin package contents into skills or MCPs.
- When a plugin capability must be reliable in one repo without enabling the native plugin globally, explicitly link its bundled skills through `skills/registry.json` `managed_plugin_skills` and promote any needed MCP server into `mcp/config/presets.json`.

## Related Docs

- [Codex Control Plane](/Users/dobby/GitHub/agents/docs/architecture/codex-control-plane.md)
- [Codex Config Layers](/Users/dobby/GitHub/agents/docs/architecture/codex-config-layers.md)
- [Control Plane Dashboard](/Users/dobby/GitHub/agents/docs/references/control-plane-dashboard.md)
