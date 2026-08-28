#!/usr/bin/env bash
set -euo pipefail

APPLY=0
UNINSTALL=0
STATUS_ONLY=0
LOG_LINES=0
LABEL="com.${USER}.agents-control-plane-dashboard"
ROOT_DIR="${AGENTS_CONTROL_PLANE_ROOT:-${HOME}/GitHub/agents}"
HOST="127.0.0.1"
PORT="8765"
DASHBOARD_ROOT="${AGENTS_CONTROL_PLANE_DASHBOARD_ROOT:-${HOME}/.local/share/agents-control-plane-dashboard/current}"
SERVER_SCRIPT="${AGENTS_CONTROL_PLANE_SERVER_SCRIPT:-}"
RELEASE_SHA="${AGENTS_CONTROL_PLANE_RELEASE_SHA:-development}"
PYTHON_BIN="${PYTHON_BIN:-}"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.local/state/agents-control-plane/log"
OUT_LOG="${LOG_DIR}/control-plane-dashboard.out.log"
ERR_LOG="${LOG_DIR}/control-plane-dashboard.err.log"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Install/update a macOS LaunchAgent for the local agents control-plane dashboard.
Default mode is dry-run. Use --apply to write and load.

Options:
  --apply              Write and load the LaunchAgent
  --dry-run            Print the plist only (default)
  --uninstall          Unload and remove the LaunchAgent plist
  --status             Print launchctl status and local readiness
  --logs [n]           Tail launchd logs (default lines: 80)
  --label <label>      LaunchAgent label
  --root <path>        agents control-plane repo root (default: ~/GitHub/agents)
  --host <host>        Local bind host (default: 127.0.0.1)
  --port <port>        Local dashboard port (default: 8765)
  --dashboard-root <path>
                       Built dashboard release link (default: ~/.local/share/agents-control-plane-dashboard/current)
  --server-script <path>
                       Exact dashboard server script (default: <root>/scripts/control-plane-dashboard.py)
  --release-sha <sha>  Exact source revision exposed by the production API
  --python <path>      Python executable (default: shared Homebrew Python)
  -h, --help           Show this help

Examples:
  ~/GitHub/agents/scripts/install-control-plane-dashboard-launchagent.sh
  ~/GitHub/agents/scripts/install-control-plane-dashboard-launchagent.sh --apply
  ~/GitHub/agents/scripts/install-control-plane-dashboard-launchagent.sh --status
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

resolve_default_python_bin() {
  local resolver="${HOME}/GitHub/scripts/setup/codex/resolve-preferred-homebrew-python.sh"
  local resolved

  if [[ -x "$resolver" ]]; then
    resolved="$("$resolver" --output python-shim 2>/dev/null || true)"
    if [[ -n "$resolved" && -x "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi

  resolved="$(command -v python3 || true)"
  if [[ -n "$resolved" ]]; then
    printf '%s\n' "$resolved"
    return 0
  fi

  return 1
}

xml_escape() {
  local value="$1"
  value="${value//&/&amp;}"
  value="${value//</&lt;}"
  value="${value//>/&gt;}"
  printf '%s' "$value"
}

local_url() {
  printf 'http://%s:%s/dashboard/' "$HOST" "$PORT"
}

local_api_url() {
  printf 'http://%s:%s/api/control-plane' "$HOST" "$PORT"
}

render_plist() {
  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$(xml_escape "$LABEL")</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>-i</string>
      <string>HOME=$(xml_escape "$HOME")</string>
      <string>PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
      <string>PYTHONUNBUFFERED=1</string>
      <string>$(xml_escape "$PYTHON_BIN")</string>
      <string>$(xml_escape "$SERVER_SCRIPT")</string>
      <string>serve</string>
      <string>--root</string>
      <string>$(xml_escape "$ROOT_DIR")</string>
      <string>--dashboard-root</string>
      <string>$(xml_escape "$DASHBOARD_ROOT")</string>
      <string>--host</string>
      <string>$(xml_escape "$HOST")</string>
      <string>--port</string>
      <string>$(xml_escape "$PORT")</string>
      <string>--release-sha</string>
      <string>$(xml_escape "$RELEASE_SHA")</string>
      <string>--no-input</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$(xml_escape "$ROOT_DIR")</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>60</integer>

    <key>StandardOutPath</key>
    <string>$(xml_escape "$OUT_LOG")</string>

    <key>StandardErrorPath</key>
    <string>$(xml_escape "$ERR_LOG")</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
      <key>HOME</key>
      <string>$(xml_escape "$HOME")</string>
    </dict>
  </dict>
</plist>
PLIST
}

print_status() {
  local domain="gui/$(id -u)"
  if launchctl print "${domain}/${LABEL}" >/dev/null 2>&1; then
    printf 'LaunchAgent loaded: %s\n' "$LABEL"
    launchctl print "${domain}/${LABEL}" 2>/dev/null | awk '
      /^\t(state|runs|pid|last exit code|run interval) = / {
        line = $0
        sub(/^\t/, "", line)
        print line
      }
    '
  else
    printf 'LaunchAgent not loaded: %s\n' "$LABEL"
  fi

  if curl -fsS "$(local_api_url)" >/dev/null 2>&1; then
    printf 'Local dashboard: available\n'
  else
    printf 'Local dashboard: unavailable\n'
  fi
  printf 'Local URL: %s\n' "$(local_url)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    --status)
      STATUS_ONLY=1
      shift
      ;;
    --logs)
      if [[ -n "${2:-}" && "${2:-}" != --* ]]; then
        LOG_LINES="$2"
        shift 2
      else
        LOG_LINES=80
        shift
      fi
      ;;
    --label)
      LABEL="${2:-}"
      PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
      shift 2
      ;;
    --root)
      ROOT_DIR="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --dashboard-root)
      DASHBOARD_ROOT="${2:-}"
      shift 2
      ;;
    --server-script)
      SERVER_SCRIPT="${2:-}"
      shift 2
      ;;
    --release-sha)
      RELEASE_SHA="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

SERVER_SCRIPT="${SERVER_SCRIPT:-${ROOT_DIR}/scripts/control-plane-dashboard.py}"
[[ -n "$LABEL" ]] || die "missing --label"
[[ -d "$ROOT_DIR" ]] || die "missing dashboard repo root: $ROOT_DIR"
[[ -x "$SERVER_SCRIPT" ]] || die "dashboard script is not executable: $SERVER_SCRIPT"
[[ -n "$HOST" ]] || die "missing --host"
[[ -n "$DASHBOARD_ROOT" ]] || die "missing --dashboard-root"
[[ -n "$RELEASE_SHA" ]] || die "missing --release-sha"
is_int "$PORT" || die "invalid --port: $PORT"
is_int "$LOG_LINES" || die "invalid --logs value: $LOG_LINES"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(resolve_default_python_bin)" || die "missing python executable: python3"
elif [[ "$PYTHON_BIN" != /* ]]; then
  PYTHON_BIN="$(command -v "$PYTHON_BIN" || true)"
fi
[[ -x "$PYTHON_BIN" ]] || die "missing python executable: $PYTHON_BIN"

DOMAIN="gui/$(id -u)"

if (( STATUS_ONLY == 1 )); then
  print_status
  exit 0
fi

if (( LOG_LINES > 0 )); then
  printf '[logs] stdout: %s\n' "$OUT_LOG"
  tail -n "$LOG_LINES" "$OUT_LOG" 2>/dev/null || true
  printf '[logs] stderr: %s\n' "$ERR_LOG"
  tail -n "$LOG_LINES" "$ERR_LOG" 2>/dev/null || true
  exit 0
fi

if (( UNINSTALL == 1 )); then
  launchctl bootout "$DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  printf 'Uninstalled %s\n' "$LABEL"
  printf 'Plist removed: %s\n' "$PLIST_PATH"
  exit 0
fi

if (( APPLY == 0 )); then
  render_plist
  exit 0
fi

[[ -f "$DASHBOARD_ROOT/index.html" ]] || die "dashboard release is unavailable: $DASHBOARD_ROOT"

mkdir -p "$(dirname "$PLIST_PATH")" "$LOG_DIR"
TMP_PLIST="$(mktemp)"
trap 'rm -f "$TMP_PLIST"' EXIT
render_plist >"$TMP_PLIST"
plutil -lint "$TMP_PLIST" >/dev/null

if [[ ! -f "$PLIST_PATH" ]] || ! cmp -s "$TMP_PLIST" "$PLIST_PATH"; then
  cp "$TMP_PLIST" "$PLIST_PATH"
  chmod 0644 "$PLIST_PATH"
fi

launchctl bootout "$DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
BOOTSTRAP_OUTPUT=""
for ATTEMPT in 1 2 3 4 5; do
  if BOOTSTRAP_OUTPUT="$(launchctl bootstrap "$DOMAIN" "$PLIST_PATH" 2>&1)"; then
    BOOTSTRAP_OUTPUT=""
    break
  fi
  [[ "$ATTEMPT" -eq 5 ]] || sleep 0.5
done
if [[ -n "$BOOTSTRAP_OUTPUT" ]]; then
  die "launchctl bootstrap failed after bounded retry: $(printf '%s' "$BOOTSTRAP_OUTPUT" | tail -n 1)"
fi

printf 'Loaded %s from %s\n' "$LABEL" "$PLIST_PATH"
printf 'Local URL: %s\n' "$(local_url)"
printf 'Logs:\n  %s\n  %s\n' "$OUT_LOG" "$ERR_LOG"
