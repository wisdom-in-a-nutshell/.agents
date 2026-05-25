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

## Private MacBook Access

Use Tailscale Serve for private access from another tailnet device such as the
MacBook. The helper starts the local dashboard on `127.0.0.1`, publishes it only
inside the tailnet, and prints the full Tailscale DNS URL:

```bash
./scripts/serve-control-plane-dashboard.sh start
```

The first run can open a one-time Tailscale approval page for HTTPS
certificates. If the page also mentions Funnel, do not use `tailscale funnel`
for this dashboard; the helper configures `tailscale serve`, and `status`
should show `tailnet only`.

Default URLs on this machine:

```text
http://127.0.0.1:8765/dashboard/
https://dobbys-mac-mini.tail7857da.ts.net:8765/dashboard/
```

The URL uses the Mac Mini name because the dashboard runs on the Mac Mini. A
MacBook such as `adithyans-macbook-pro.tail7857da.ts.net` is the client device,
not the host for this dashboard.

Use the full `*.tail7857da.ts.net` name for HTTPS. The short MagicDNS name can
resolve on correctly configured clients, but Tailscale HTTPS certificates are
for the full tailnet DNS name, so browsers can reject short-name HTTPS URLs.

Check or stop the private exposure:

```bash
./scripts/serve-control-plane-dashboard.sh status
./scripts/serve-control-plane-dashboard.sh stop
```

## Persistent Local Server

For normal use on the Mac Mini, install the local dashboard server as a user
LaunchAgent and keep Tailscale Serve pointed at the same port:

```bash
./scripts/install-control-plane-dashboard-launchagent.sh --apply
./scripts/serve-control-plane-dashboard.sh status
```

The LaunchAgent keeps `http://127.0.0.1:8765/dashboard/` running at login and
restarts it if the process exits. Tailscale Serve owns the private tailnet URL:

```text
https://dobbys-mac-mini.tail7857da.ts.net:8765/dashboard/
```

Inspect the service:

```bash
./scripts/install-control-plane-dashboard-launchagent.sh --status
./scripts/install-control-plane-dashboard-launchagent.sh --logs
```

Remove only the persistent local server:

```bash
./scripts/install-control-plane-dashboard-launchagent.sh --uninstall
```

This does not remove the Tailscale Serve proxy. Use
`./scripts/serve-control-plane-dashboard.sh stop` only when you also want to
remove the private tailnet exposure.

For additional local apps, prefer another fixed port rather than path routing:

```text
8765  .agents dashboard
8766  next local dashboard
8767  local docs viewer
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
not scrape the browser UI.
