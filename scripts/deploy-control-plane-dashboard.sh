#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0
OUTPUT="json"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Deploy the local agents control-plane dashboard.

Options:
  --apply              Build dashboard assets, reload launchd, and smoke the API
  --dry-run            Report what would run (default)
  --json               Emit one JSON object (default)
  --plain              Emit compact plain text
  --no-input           Accepted for agent-safe non-interactive callers
  -h, --help           Show help
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

emit() {
  local status="$1"
  local message="$2"
  local exit_code="${3:-0}"
  if [[ "$OUTPUT" == "plain" ]]; then
    printf '%s message=%s\n' "$status" "$message"
  else
    local escaped_message
    escaped_message="$(printf '%s' "$message" | json_escape)"
    printf '{"schema_version":"1.0","command":"deploy-control-plane-dashboard","status":"%s","data":{"message":%s},"error":null,"meta":{}}\n' \
      "$status" "$escaped_message"
  fi
  exit "$exit_code"
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
    --json)
      OUTPUT="json"
      shift
      ;;
    --plain)
      OUTPUT="plain"
      shift
      ;;
    --no-input)
      shift
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

if [[ "$APPLY" -eq 0 ]]; then
  emit "ok" "dry run; would build dashboard, reload launchd, and smoke /api/control-plane"
fi

cd "$ROOT_DIR/dashboard-app"
npm run deploy

cd "$ROOT_DIR"
scripts/install-control-plane-dashboard-launchagent.sh --apply
curl -fsS "http://127.0.0.1:8765/api/control-plane" >/dev/null

emit "ok" "deployed and smoked agents control-plane dashboard"
