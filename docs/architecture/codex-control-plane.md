# Codex Control Plane

This repo is becoming the canonical personal control plane for Codex across both machines. The core idea is simple: keep the durable source of truth in `~/.agents`, keep the live runtime home in `~/.codex`, and keep `~/GitHub/scripts` limited to generic machine bootstrap plus shared shell glue that is not Codex-owned.

That split keeps Codex-specific policy, MCP presets, skills, docs, and managed scripts in one synced place without pretending that auth, sessions, logs, or runtime databases belong in git.

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
    B --> C[sync-config.sh]
    B --> D[sync-trusted-projects.sh]
    B --> E[configure-ghostty-cwd.sh]
    C --> F[~/.codex/config.toml]
    C --> G[Xcode Codex config]
    D --> F
    D --> G
    E --> H[Ghostty config]
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
    J --> F[notify.py]
    F --> G[git automation]
```

## Main Parts

### `~/.agents`

Owns the durable, synced source of truth for Codex-specific setup:

- managed config fragments and presets
- Codex-specific scripts and wrappers
- skills, references, and architecture docs
- migration and ownership documentation

This is the repo a future agent should edit first when changing personal Codex behavior across machines.

### `~/GitHub/scripts`

Owns only generic machine bootstrap and shared shell glue that is broader than Codex:

- machine-wide setup flows
- non-Codex launchd/install helpers
- shared shell files that source Codex fragments from `~/.agents`

This repo should remain useful for bootstrapping a fresh machine, but it should stop owning Codex-specific wrappers, templates, and policy.

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

- repo MCP enablement
- repo-local tool or app toggles
- project-specific model or trust settings

These settings stay close to the repo because they describe how Codex should behave in that repo, not across the whole machine.

## Main Flow

1. Canonical Codex policy and assets are edited in `~/.agents`.
2. Generic machine bootstrap can call into that control plane when needed.
3. Those commands apply managed outputs into `~/.codex`.
4. Codex starts from `~/.codex/config.toml` and any trusted repo-local `.codex/config.toml` in real project repos.
5. Repo-local overrides refine behavior for one project without changing the global control plane.

## Key Boundaries

- Canonical and sync-worthy belongs in `~/.agents`.
- Applied runtime and volatile state belongs in `~/.codex`.
- Generic machine bootstrap belongs in `~/GitHub/scripts`.
- Repo-specific Codex behavior belongs in repo-local `.codex/`.

## Notes

- `~/.codex` should be treated as an applied runtime home, not as a tracked repo.
- If a file must exist under `~/.codex` for Codex to call it directly, the preferred pattern is to keep the canonical source in `~/.agents` and sync or link it into place.
- Deeper keep / move / generate decisions live in the ownership reference.

See [Codex Control Plane Ownership](/Users/dobby/.agents/docs/references/codex-control-plane-ownership.md) for the exact split.
See [Codex Control Plane Operations](/Users/dobby/.agents/docs/references/codex-control-plane-operations.md) for exact commands, healthy-state checks, and common failure modes.
See [Codex Control Plane Script Flows](/Users/dobby/.agents/docs/architecture/codex-control-plane-script-flows.md) for smaller diagrams showing what each main script group does.
