#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ACTION="start"
HOST="127.0.0.1"
PORT="8765"
HTTPS_PORT="8765"
HTTPS_PORT_SET=0
STATE_DIR="${ROOT_DIR}/tmp/control-plane-dashboard"
PID_FILE="${STATE_DIR}/server.pid"
LOG_FILE="${STATE_DIR}/server.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TAILSCALE_BIN="${TAILSCALE_BIN:-tailscale}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [start|status|stop] [options]

Start the local .agents dashboard and publish it privately through Tailscale Serve.

Options:
  --host <host>              Local bind host (default: 127.0.0.1)
  --port <port>              Local dashboard port (default: 8765)
  --https-port <port>        Tailscale HTTPS port (default: same as --port)
  -h, --help                 Show this help

Examples:
  ~/.agents/scripts/serve-control-plane-dashboard.sh start
  ~/.agents/scripts/serve-control-plane-dashboard.sh status
  ~/.agents/scripts/serve-control-plane-dashboard.sh stop
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

require_arg() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" ]] || die "missing value for ${option}"
}

local_url() {
  printf 'http://%s:%s/dashboard/' "$HOST" "$PORT"
}

local_api_url() {
  printf 'http://%s:%s/api/control-plane' "$HOST" "$PORT"
}

dashboard_is_ready() {
  curl -fsS "$(local_api_url)" >/dev/null 2>&1
}

pid_is_running() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

dashboard_listener_pid() {
  local pid command_line
  pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
  [[ -n "$pid" ]] || return 1
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *control-plane-dashboard.py*" serve "*)
      printf '%s\n' "$pid"
      ;;
    *)
      return 1
      ;;
  esac
}

start_dashboard() {
  mkdir -p "$STATE_DIR"
  if dashboard_is_ready; then
    local existing_pid
    if ! pid_is_running && existing_pid="$(dashboard_listener_pid)"; then
      printf '%s\n' "$existing_pid" >"$PID_FILE"
    fi
    printf 'Local dashboard is already available at %s\n' "$(local_url)"
    return
  fi

  printf 'Starting local dashboard at %s\n' "$(local_url)"
  nohup "$PYTHON_BIN" "${ROOT_DIR}/scripts/control-plane-dashboard.py" serve \
    --root "$ROOT_DIR" \
    --host "$HOST" \
    --port "$PORT" \
    --no-input \
    >"$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" >"$PID_FILE"

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if dashboard_is_ready; then
      return
    fi
    sleep 0.5
  done

  die "dashboard did not become ready; see ${LOG_FILE}"
}

tailscale_self_dns() {
  "$TAILSCALE_BIN" status --json | "$PYTHON_BIN" -c '
import json
import sys

data = json.load(sys.stdin)
name = data.get("Self", {}).get("DNSName", "").rstrip(".")
if name:
    print(name)
'
}

publish_tailscale() {
  require_command "$TAILSCALE_BIN"
  local target="http://${HOST}:${PORT}"
  "$TAILSCALE_BIN" serve --bg --https="$HTTPS_PORT" "$target"
}

print_urls() {
  local dns short_name
  dns="$(tailscale_self_dns)"
  if [[ -z "$dns" ]]; then
    printf 'Local URL: %s\n' "$(local_url)"
    printf 'Tailscale URL: unavailable; Tailscale did not report a device DNS name.\n'
    return
  fi

  short_name="${dns%%.*}"
  printf 'Local URL: %s\n' "$(local_url)"
  printf 'Tailscale URL: https://%s:%s/dashboard/\n' "$dns" "$HTTPS_PORT"
  printf 'Short MagicDNS URL: https://%s:%s/dashboard/\n' "$short_name" "$HTTPS_PORT"
}

stop_dashboard() {
  if pid_is_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$pid" >/dev/null 2>&1 || break
      sleep 0.2
    done
  else
    local existing_pid
    if existing_pid="$(dashboard_listener_pid)"; then
      kill "$existing_pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$PID_FILE"
}

show_status() {
  if dashboard_is_ready; then
    printf 'Local dashboard: available\n'
  else
    printf 'Local dashboard: unavailable\n'
  fi
  print_urls
  printf '\nTailscale Serve status:\n'
  "$TAILSCALE_BIN" serve status || true
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    start|status|stop)
      ACTION="$1"
      shift
      ;;
    --host)
      require_arg "$1" "${2:-}"
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      require_arg "$1" "${2:-}"
      PORT="${2:-}"
      if (( HTTPS_PORT_SET == 0 )); then
        HTTPS_PORT="$PORT"
      fi
      shift 2
      ;;
    --https-port)
      require_arg "$1" "${2:-}"
      HTTPS_PORT="${2:-}"
      HTTPS_PORT_SET=1
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ -n "$HOST" ]] || die "missing --host"
is_int "$PORT" || die "invalid --port: $PORT"
is_int "$HTTPS_PORT" || die "invalid --https-port: $HTTPS_PORT"
require_command curl
require_command "$PYTHON_BIN"

case "$ACTION" in
  start)
    start_dashboard
    publish_tailscale
    print_urls
    ;;
  status)
    show_status
    ;;
  stop)
    "$TAILSCALE_BIN" serve --https="$HTTPS_PORT" off >/dev/null 2>&1 || true
    stop_dashboard
    printf 'Stopped private dashboard exposure on HTTPS port %s.\n' "$HTTPS_PORT"
    ;;
  *)
    die "unknown action: $ACTION"
    ;;
esac
