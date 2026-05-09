# Dobby Calendar Bridge

The Dobby Calendar Bridge is the skill-owned, machine-local EventKit permission holder for Dobby calendar operations.

## Why it exists

macOS Calendar privacy grants are tied to the process/app identity that touches EventKit. One caller app may work while another fails because macOS sees them as different apps. Shell changes inside the caller do not fix that attribution boundary.

The bridge gives Dobby one stable local identity:

```text
Dobby callers
        ↓
dobby-calendar CLI
        ↓
user-only Unix socket
        ↓
Dobby Calendar Bridge.app / LaunchAgent
        ↓
macOS EventKit / Calendar.app
```

## Ownership

The implementation lives in the Dobby skill so every Dobby workspace (`adi`, `angie`, future workspaces) uses the same calendar backend:

- source: `scripts/dobby_calendar/bridge/main.swift`
- app metadata: `scripts/dobby_calendar/bridge/Info.plist`
- installer: `scripts/dobby_calendar/bridge/install`
- client adapter: `scripts/dobby_calendar/cli.py`

The `~/GitHub/scripts` machine-ops repo may call the installer during bootstrap/health checks, but it does not own the bridge implementation.

## Installed runtime state

Per machine, the installer creates runtime artifacts outside the repo:

- app: `~/Applications/Dobby Calendar Bridge.app`
- LaunchAgent plist: `~/Library/LaunchAgents/com.<user>.dobby-calendar-bridge.plist`
- socket: `~/Library/Application Support/DobbyCalendarBridge/bridge.sock`
- logs: `~/Library/Logs/dobby-calendar-bridge.log` and `.err.log`

## Setup

Run once per Mac after the Dobby skill is available:

```bash
~/.agents/skills-source/owned/dobby-calendar/scripts/dobby_calendar/bridge/install --request-access
```

A human must grant **Full Calendar Access** to **Dobby Calendar Bridge** in System Settings > Privacy & Security > Calendars. This is a macOS TCC requirement; scripts cannot bypass it.

The installer must sign the bridge with a stable code-signing identity. macOS
Calendar permission is tied to the app's code identity; ad-hoc signing (`-s -`)
can make every rebuild look like a new app and reset Calendar access. The
installer therefore refuses ad-hoc signing by default and prefers, in order:

1. `DOBBY_CALENDAR_CODESIGN_IDENTITY` / `--codesign-identity`
2. `Dobby Local Code Signing` if present
3. Adi's `Apple Development: Adithyan Ilangovan (...)` identity
4. any available `Apple Development: ...` identity

Use `--allow-adhoc-signing` only as a last-resort repair path, and expect to
grant Calendar permission again afterward.

## Backends

`dobby-calendar` backend order:

1. native bridge socket
2. Homebrew `ical` fallback

Diagnostics:

```bash
DOBBY_CALENDAR_BACKEND=bridge ~/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar doctor
DOBBY_CALENDAR_BACKEND=ical ~/.agents/skills-source/owned/dobby-calendar/scripts/dobby-calendar doctor
```
