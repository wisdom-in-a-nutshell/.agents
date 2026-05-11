# Codex Control Plane

This repo is the canonical personal control plane for Codex across both machines. The core idea is simple: keep the durable source of truth in `~/.agents`, keep the live runtime home in `~/.codex`, and keep `~/GitHub/scripts` limited to generic machine bootstrap plus shared shell glue that is not Codex-owned.

That split keeps Codex-specific policy, repo assignment, shared MCP presets, skills, docs, and managed scripts in one synced place without pretending that auth, sessions, logs, or runtime databases belong in git.

The control plane includes native Codex plugin state plus the repo bootstrap registry in `~/.agents/codex/config/repo-bootstrap.json`.

Codex plugin scope and state lives in `~/.agents/plugins/registry.json`. Plugins stay plugins; the control plane does not split plugin packages into skill or MCP registries.

The repo bootstrap registry in `~/.agents/codex/config/repo-bootstrap.json` then acts as the canonical source for:

- which repos are managed
- which extra repos live outside `~/GitHub`
- which repo-local MCP presets should be enabled
- which repo-local `.codex/config.toml` files should be generated

Shared MCP preset definitions themselves now live in `~/.agents/mcp/config/presets.json`.

OpenAI-bundled Codex runtime skills are handled separately by `~/.agents/codex/config/bundled-skills-policy.json`. That file classifies runtime-installed bundled skills as either allowed or disabled so new upstream bundled skills do not silently become part of the local control plane without review.

At the machine boundary, external repos such as `~/GitHub/scripts` should call the shared root wrappers in `~/.agents/scripts/` rather than reaching into Codex internals directly. The low-level Codex scripts still live in `codex/scripts/`, but machine-facing orchestration now happens one layer up.

## Figure 1: Ownership Layout

```mermaid
flowchart TD
    A[~/.agents<br/>canonical Codex control plane]
    B[~/GitHub/scripts<br/>generic bootstrap + shared shell glue]
    C[~/.codex<br/>runtime home]
    D[Repo-local .codex<br/>project overrides]

    A --> C
    B --> C
    C --> D
```

## Figure 2: Apply Flow

```mermaid
flowchart TD
    A[Edit ~/.agents] --> B[bootstrap-machine-codex.sh]
    A --> P[plugins/registry.json]
    A --> R[repo-bootstrap.json]
    P --> Q[sync-plugins-registry.sh]
    P --> C
    P --> E
    A --> V[bundled-skills-policy.json]
    B --> C[sync-config.sh]
    B --> D[sync-trusted-projects.sh]
    B --> E[sync-repo-codex-configs.sh]
    B --> F[configure-ghostty-cwd.sh]
    Q --> K[plugin registry views]
    Q --> R
    C --> G[~/.codex/config.toml]
    V --> C
    R --> D
    R --> E
    T --> E
    U --> C
    U --> E
    D --> G
    E --> I[Repo-local .codex/config.toml]
    F --> J[Ghostty config]
```

## Figure 3: Runtime Flow

```mermaid
flowchart TD
    A[Ghostty / shell startup] --> B[zshrc.shared]
    B --> C[codex-shell.zsh]
    H[Ghostty initial-command] --> I[ghostty-codex-then-shell.sh]
    I --> J[Codex CLI]
    D[~/.codex/config.toml] --> J
    E[Repo-local .codex/config.toml] --> J
    K[~/.codex/hooks.json<br/>global hooks] --> J
    L[Repo-local .codex/hooks.json] --> J
    J --> F[Stop hook]
    F --> G[git add / commit / pull --rebase / push]
```

## Main Parts

### `~/.agents`

Owns the durable, synced source of truth for Codex-specific setup:

- managed config fragments and presets
- bundled Codex skill allow/disable policy
- repo bootstrap registry
- hook registry and shared hook dispatch scripts
- native Codex plugin registry
- Codex-specific scripts and wrappers
- skills, references, and architecture docs
- ownership and operations documentation

This is the repo a future agent should edit first when changing personal Codex behavior across machines.

### `~/GitHub/scripts`

Owns only generic machine bootstrap and shared shell glue that is broader than Codex:

- machine-wide setup flows
- non-Codex launchd/install helpers
- shared shell files that source Codex fragments from `~/.agents`

This repo remains useful for bootstrapping a fresh machine, but Codex-specific wrappers, templates, and policy live in `~/.agents`.

### `~/.codex`

Owns applied runtime state and generated live configuration:

- live `config.toml`
- auth/session/history/log/cache/db state
- runtime-installed skills and generated artifacts
- any scripts that must exist at runtime because Codex points to them directly

`~/.codex` is where Codex runs, not where the long-term design should live.
It is now treated as runtime-only rather than as a git-tracked control-plane repo.

### Repo-local `.codex/`

Owns project-specific Codex overrides when a repo needs different behavior:

- generated or hand-owned repo-local config
- generated repo-local hook config
- repo MCP enablement
- repo-local tool or app toggles
- project-specific model or trust settings

These settings stay close to the repo because they describe how Codex should behave in that repo, not across the whole machine.

## Main Flow

1. Canonical Codex policy and assets are edited in `~/.agents`.
2. Shared machine-facing apply enters through `~/.agents/scripts/bootstrap-machine-agent-control-planes.sh` or `~/.agents/scripts/auto-apply-agent-control-planes.sh`.
3. The global template drives machine config in `~/.codex`.
4. Global-scope native Codex plugin state from `plugins/registry.json` is rendered into the global Codex config.
5. The repo bootstrap registry drives both trusted repo discovery and managed repo-local `.codex/config.toml` generation.
6. Repo-scope native Codex plugin state from `plugins/registry.json` is rendered into assigned repo-local `.codex/config.toml` files.
7. The hook registry drives global `~/.codex/hooks.json` generation plus managed repo-local `.codex/hooks.json` generation.
8. The Codex bootstrap installs the stale-session archive LaunchAgent, which uses Codex app-server APIs to archive managed-repo threads after their `updatedAt` timestamp is older than the configured threshold.
9. Codex starts from `~/.codex/config.toml` and any trusted repo-local `.codex/config.toml` and `.codex/hooks.json` in real project repos.
10. Repo-local overrides refine behavior for one project without changing the global control plane.

## Key Boundaries

- Canonical and sync-worthy belongs in `~/.agents`.
- Applied runtime and volatile state belongs in `~/.codex`.
- Generic machine bootstrap belongs in `~/GitHub/scripts`.
- Repo-specific Codex behavior belongs in repo-local `.codex/`.
- Codex plugin scope and state belongs in `plugins/registry.json`; standalone skills and MCPs belong in their own registries.
- The repo registry decides which repos get generated repo-local config and which MCP presets they receive.

## Notes

- `~/.codex` should be treated as an applied runtime home, not as a tracked repo.
- If a file must exist under `~/.codex` for Codex to call it directly, the preferred pattern is to keep the canonical source in `~/.agents` and sync or link it into place.
- Deeper keep / move / generate decisions live in the ownership reference.

See [Codex Control Plane Ownership](/Users/dobby/.agents/docs/references/codex-control-plane-ownership.md) for the exact split.
See [Codex Control Plane Operations](/Users/dobby/.agents/docs/references/codex-control-plane-operations.md) for exact commands, healthy-state checks, and common failure modes.
See [Capability Bootstrap Model](/Users/dobby/.agents/docs/architecture/capability-bootstrap-model.md) for the skills / MCPs / plugins structure.
See [Codex Config Layers](/Users/dobby/.agents/docs/architecture/codex-config-layers.md) for the config-specific layering model.
See [Codex Control Plane Script Flows](/Users/dobby/.agents/docs/architecture/codex-control-plane-script-flows.md) for smaller diagrams showing what each main script group does.
