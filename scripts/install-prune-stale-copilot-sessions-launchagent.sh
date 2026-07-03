#!/usr/bin/env bash
set -euo pipefail

APPLY=0
LABEL="com.${USER}.copilot-session-pruner"
INTERVAL_SECONDS=3600
OLDER_THAN_HOURS=24
MAX_REPORT=25
RUN_AT_LOAD=1
CONTROL_PLANE_ROOT="${AGENTS_CONTROL_PLANE_ROOT:-${HOME}/GitHub/agents}"
SCRIPT_PATH="${CONTROL_PLANE_ROOT}/scripts/prune-stale-copilot-sessions.py"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.local/state/copilot-control-plane/log"
OUT_LOG="${LOG_DIR}/prune-stale-copilot-sessions.out.log"
ERR_LOG="${LOG_DIR}/prune-stale-copilot-sessions.err.log"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Install/update a LaunchAgent that prunes stale local GitHub Copilot session data
by age. Default mode is dry-run. Use --apply to write and load.

Options:
  --apply                    Write and load the LaunchAgent
  --dry-run                  Print the plist only (default)
  --label <label>            LaunchAgent label (default: com.<user>.copilot-session-pruner)
  --interval-seconds <n>     StartInterval seconds (default: 3600, one hour)
  --older-than-hours <n>     Forwarded stale-session threshold (default: 24)
  --max-report <n>           Candidate detail lines kept in launchd logs (default: 25)
  --script <path>            Stale-session pruner script path
  --run-at-load              Run once immediately when loaded (default)
  --no-run-at-load           Wait until the first interval fires
  -h, --help                 Show this help

Examples:
  ~/GitHub/agents/scripts/install-prune-stale-copilot-sessions-launchagent.sh
  ~/GitHub/agents/scripts/install-prune-stale-copilot-sessions-launchagent.sh --apply
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_number() {
  [[ "${1:-}" =~ ^[0-9]+([.][0-9]+)?$ ]]
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

render_plist() {
  local run_at_load_value="<true/>"
  if (( RUN_AT_LOAD == 0 )); then
    run_at_load_value="<false/>"
  fi

  cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$(xml_escape "$LABEL")</string>

    <key>ProgramArguments</key>
    <array>
      <string>$(xml_escape "$SCRIPT_PATH")</string>
      <string>--apply</string>
      <string>--older-than-hours</string>
      <string>$(xml_escape "$OLDER_THAN_HOURS")</string>
      <string>--max-report</string>
      <string>$(xml_escape "$MAX_REPORT")</string>
      <string>--plain</string>
    </array>

    <key>StartInterval</key>
    <integer>${INTERVAL_SECONDS}</integer>

    <key>RunAtLoad</key>
    ${run_at_load_value}

    <key>StandardOutPath</key>
    <string>$(xml_escape "$OUT_LOG")</string>

    <key>StandardErrorPath</key>
    <string>$(xml_escape "$ERR_LOG")</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>${HOME}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
      <key>HOME</key>
      <string>$(xml_escape "$HOME")</string>
    </dict>
  </dict>
</plist>
PLIST
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
    --label)
      LABEL="${2:-}"
      PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="${2:-}"
      shift 2
      ;;
    --older-than-hours)
      OLDER_THAN_HOURS="${2:-}"
      shift 2
      ;;
    --max-report)
      MAX_REPORT="${2:-}"
      shift 2
      ;;
    --script)
      SCRIPT_PATH="${2:-}"
      shift 2
      ;;
    --run-at-load)
      RUN_AT_LOAD=1
      shift
      ;;
    --no-run-at-load)
      RUN_AT_LOAD=0
      shift
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
[[ -x "$SCRIPT_PATH" ]] || die "stale-session pruner script is not executable: $SCRIPT_PATH"
is_int "$INTERVAL_SECONDS" || die "invalid --interval-seconds: $INTERVAL_SECONDS"
(( INTERVAL_SECONDS >= 300 )) || die "--interval-seconds must be >= 300"
is_number "$OLDER_THAN_HOURS" || die "invalid --older-than-hours: $OLDER_THAN_HOURS"
is_int "$MAX_REPORT" || die "invalid --max-report: $MAX_REPORT"

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

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
if (( RUN_AT_LOAD == 1 )); then
  launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
fi

printf 'Loaded %s from %s\n' "$LABEL" "$PLIST_PATH"
printf 'Interval: %ss\n' "$INTERVAL_SECONDS"
printf 'Prune threshold: session updated_at older than %sh\n' "$OLDER_THAN_HOURS"
printf 'Logs:\n  %s\n  %s\n' "$OUT_LOG" "$ERR_LOG"
