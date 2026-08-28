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
http://127.0.0.1:8765/
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
http://127.0.0.1:8765/
https://dobbys-mac-mini.tail7857da.ts.net:8765/
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

The LaunchAgent keeps `http://127.0.0.1:8765/` running at login and restarts it if the process
exits. Production runs the exact released server code and dashboard assets through
`~/.local/share/agents-control-plane-dashboard/current`. The installer renders the shared
Homebrew Python shim from `~/GitHub/scripts/setup/codex/resolve-preferred-homebrew-python.sh` and
starts it through `env -i`, so the secretless dashboard receives only its explicit HOME, PATH, and
Python settings instead of the GUI launchd domain's unrelated inherited credentials. Tailscale
Serve owns the private tailnet URL:

```text
https://dobbys-mac-mini.tail7857da.ts.net:8765/
```

Inspect the service:

```bash
./scripts/install-control-plane-dashboard-launchagent.sh --status
./scripts/install-control-plane-dashboard-launchagent.sh --logs
```

Deploy the built dashboard assets and refresh the LaunchAgent through the
repo-owned deploy wrapper:

```bash
./scripts/deploy-control-plane-dashboard.sh --apply --plain --no-input
```

The central Mac Mini production reconciler in `~/GitHub/scripts` runs this wrapper after a
successful registered `main` publication. The wrapper runs the full control-plane gate in a
detached exact-SHA worktree, builds a versioned release, verifies that live `main` did not move,
atomically switches `current`/`previous`, and restores the old release if activation or API health
fails. The production API reports the exact release SHA, and activation succeeds only after the
restarted process reports that captured revision. Code, registry, and test validation stays inside
the frozen worktree; machine-rendered
Copilot/Codex state, Git-hook enrollment, and runtime drift are checked through the canonical
`~/GitHub/agents` checkout because ephemeral worktree paths are neither managed repos nor valid
runtime symlink targets. Control-plane tests receive a disposable `HOME` under `tmp/`, and renderer
tests skip default per-repo dev-server and Codex-environment targets unless a test supplies an
isolated registry and temporary workspace. Even if a future test forgets a target override, an
exact-source full gate cannot rewrite a live managed repo. The five-minute reconcile remains
missed-event and health recovery.

`--status` allowlists launchd lifecycle fields; it does not print the inherited environment.

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

## Cloudflare Access URL

The Mac Mini also exposes this dashboard through Cloudflare Tunnel and
Cloudflare Access:

```text
https://agents.adithyan.io/
```

The shared tunnel inventory, launchd owner, and cross-service validation
commands live in:

```text
~/GitHub/scripts/docs/references/mac-mini-cloudflare-tunnel.md
```

Cloudflare Access protects the entire hostname. The current policy allows only:

```text
adithyan@wisdominanutshell.academy
```

The local tunnel target is:

```text
agents.adithyan.io -> http://127.0.0.1:8765
```

The legacy `/dashboard/` path redirects to `/`. The `/api/control-plane`
endpoint remains available behind Access because the browser UI needs it.
`/source/...` is disabled by default for remote safety; set
`AGENTS_DASHBOARD_ENABLE_SOURCE=1` only when deliberately enabling source-file
browsing.

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

The MCP section is a dedicated distribution matrix: managed repositories are
rows, Codex/Claude/Copilot are columns, and each active cell lists the MCPs
delivered to that exact combination. Server filters isolate one definition and
show its endpoint, repo coverage, client coverage, and registry source. This is
the operator view of `mcp/config/presets.json`; assignments are not duplicated
in the repo bootstrap registry. A global client target remains visible in every
managed repo row and is labeled with the client whose user surface carries it.

Repo entries come from `codex/config/repo-bootstrap.json`. If a managed repo
path no longer exists on the current machine, the dashboard keeps the row but
adds a `managed_repo_missing` warning so the stale registry entry appears in the
Attention view instead of silently looking healthy.

## Contract Boundary

The dashboard is an operator inspection surface. Automation should consume
`scripts/control-plane-dashboard.py data --no-input` or `/api/control-plane`,
not scrape the browser UI.
