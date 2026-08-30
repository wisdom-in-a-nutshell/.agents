# .agents control-plane dashboard (UI)

React + Vite + TypeScript UI for the `.agents` control plane, styled with the
shared **adi-design** token system. This is the same stack as dobby-dashboard.

## Architecture

- **Data engine: Python, not this app.** `~/GitHub/agents/scripts/control-plane-dashboard.py`
  reads the skills/plugins/mcp/hooks/repo registries and is the single source of
  truth for control-plane data. It exposes the data two ways: `/api/control-plane`
  (HTTP, for this dashboard) and a `data` CLI subcommand (for other automation +
  the test suite). Do **not** re-implement that logic here.
- **This app is the UI only.** It fetches `/api/control-plane` and renders it.
- **Source vs served:** source lives here (`~/GitHub/agents/dashboard-app`). Production builds an
  exact committed revision into `~/.local/share/agents-control-plane-dashboard/releases/` and
  serves the atomic `current/dashboard` link.

## Develop

```sh
npm install
npm run dev      # Vite on :5180, proxies /api + /source to the Python server (:8765)
```

The Python server must be running (it is, via the
`com.dobby.agents-control-plane-dashboard` LaunchAgent).

## Deploy

Use `../scripts/deploy-control-plane-dashboard.sh --apply --plain --no-input` from clean `main` for
production. It runs the full repo gate in an exact-SHA worktree, builds a versioned release,
atomically activates it, reloads launchd with an isolated environment, and restores the prior
release if health fails.
Asset URLs use `base: '/dashboard/'`; deep-links use `?section=<id>`.

## Design

Identity comes entirely from `src/tokens.css` (a copy of the canonical
`adi-design/assets/tokens.css`) plus `src/tokens.local.css` (the scope-global /
scope-local product tokens). To evolve the look, change it in the adi-design
skill first, then re-copy `tokens.css` here. Sage is the one accent; titles are
Newsreader; surfaces are flat hairline.
