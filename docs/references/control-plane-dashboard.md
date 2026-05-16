# Control Plane Dashboard

The dashboard is a read-only browser view over the canonical `.agents` registries.

Canonical inputs stay split by ownership:

- `skills/registry.json`
- `plugins/registry.json`
- `mcp/config/presets.json`
- `hooks/registry.json`
- `codex/config/repo-bootstrap.json`

The dashboard server reads those files on each request and exposes one normalized payload at:

```text
/api/control-plane
```

## Start The Dashboard

```bash
./scripts/control-plane-dashboard.py serve --no-input
```

Then open:

```text
http://127.0.0.1:8765/dashboard/
```

Use another port if needed:

```bash
./scripts/control-plane-dashboard.py serve --port 8766 --no-input
```

## Inspect The Data Contract

```bash
./scripts/control-plane-dashboard.py data --no-input
./scripts/control-plane-dashboard.py data --plain --no-input
```

The JSON command follows the repo's agent-facing client shape:

- `schema_version`
- `command`
- `status`
- `data`
- `error`
- `meta`

The normalized `data` object contains:

- `sources`: canonical source files used by the dashboard
- `counts`: total counts by registry family and status
- `warnings`: lightweight registry issues visible to the dashboard
- `items`: one flat searchable list
- `groups`: grouped lists for skills, plugins, MCP presets, repos, and hooks

## Contract Boundary

The dashboard is an operator inspection surface. Automation should consume
`scripts/control-plane-dashboard.py data --no-input` or `/api/control-plane`,
not scrape the HTML table.
