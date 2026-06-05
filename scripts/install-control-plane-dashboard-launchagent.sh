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
PYTHON_BIN="${PYTHON_BIN:-python3}"
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
  --python <path>      Python executable (default: python3)
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
      <string>$(xml_escape "$PYTHON_BIN")</string>
      <string>$(xml_escape "${ROOT_DIR}/scripts/control-plane-dashboard.py")</string>
      <string>serve</string>
      <string>--root</string>
      <string>$(xml_escape "$ROOT_DIR")</string>
      <string>--host</string>
      <string>$(xml_escape "$HOST")</string>
      <string>--port</string>
      <string>$(xml_escape "$PORT")</string>
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
  if ! launchctl print "${domain}/${LABEL}" 2>/dev/null; then
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

[[ -n "$LABEL" ]] || die "missing --label"
[[ -d "$ROOT_DIR" ]] || die "missing dashboard repo root: $ROOT_DIR"
[[ -x "${ROOT_DIR}/scripts/control-plane-dashboard.py" ]] || die "dashboard script is not executable: ${ROOT_DIR}/scripts/control-plane-dashboard.py"
[[ -n "$HOST" ]] || die "missing --host"
is_int "$PORT" || die "invalid --port: $PORT"
is_int "$LOG_LINES" || die "invalid --logs value: $LOG_LINES"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || [[ -x "$PYTHON_BIN" ]] || die "missing python executable: $PYTHON_BIN"

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
launchctl bootstrap "$DOMAIN" "$PLIST_PATH"

printf 'Loaded %s from %s\n' "$LABEL" "$PLIST_PATH"
printf 'Local URL: %s\n' "$(local_url)"
printf 'Logs:\n  %s\n  %s\n' "$OUT_LOG" "$ERR_LOG"
