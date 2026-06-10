#!/usr/bin/env bash
set -euo pipefail

APPLY=0
LABEL="com.${USER}.dream-memory"
HOUR=5
MINUTE=30
DAYS=7
WORKSPACE_ROOT="${HOME}/GitHub/adi"
SCRIPT_PATH="${HOME}/GitHub/agents/skills-source/owned/dobby-lifecycle/scripts/dream-memory"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.local/state/claude-control-plane/log"
OUT_LOG="${LOG_DIR}/dream-memory.out.log"
ERR_LOG="${LOG_DIR}/dream-memory.err.log"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Install/update a LaunchAgent that runs Dobby's nightly proposal-only dreaming
pass (dream-memory) over the workspace. Default mode is dry-run. Use --apply
to write and load.

Options:
  --apply                    Write and load the LaunchAgent
  --dry-run                  Print the plist only (default)
  --label <label>            LaunchAgent label (default: com.<user>.dream-memory)
  --hour <0-23>              Daily run hour, local time (default: 5)
  --minute <0-59>            Daily run minute (default: 30)
  --days <n>                 Review window in days (default: 7)
  --workspace-root <path>    Dobby workspace (default: ~/GitHub/adi)
  --script <path>            dream-memory script path
  -h, --help                 Show this help

Examples:
  ~/GitHub/agents/codex/scripts/install-dream-memory-launchagent.sh
  ~/GitHub/agents/codex/scripts/install-dream-memory-launchagent.sh --apply
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
      <string>$(xml_escape "$SCRIPT_PATH")</string>
      <string>--workspace-root</string>
      <string>$(xml_escape "$WORKSPACE_ROOT")</string>
      <string>--days</string>
      <string>$(xml_escape "$DAYS")</string>
      <string>--json</string>
      <string>--no-input</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>${HOUR}</integer>
      <key>Minute</key>
      <integer>${MINUTE}</integer>
    </dict>

    <key>RunAtLoad</key>
    <false/>

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
    --hour)
      HOUR="${2:-}"
      shift 2
      ;;
    --minute)
      MINUTE="${2:-}"
      shift 2
      ;;
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --workspace-root)
      WORKSPACE_ROOT="${2:-}"
      shift 2
      ;;
    --script)
      SCRIPT_PATH="${2:-}"
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
[[ -x "$SCRIPT_PATH" ]] || die "dream-memory script is not executable: $SCRIPT_PATH"
[[ -d "$WORKSPACE_ROOT" ]] || die "workspace root is not a directory: $WORKSPACE_ROOT"
is_int "$HOUR" && (( HOUR <= 23 )) || die "invalid --hour: $HOUR"
is_int "$MINUTE" && (( MINUTE <= 59 )) || die "invalid --minute: $MINUTE"
is_int "$DAYS" && (( DAYS >= 1 )) || die "invalid --days: $DAYS"

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

printf 'Loaded %s from %s\n' "$LABEL" "$PLIST_PATH"
printf 'Schedule: daily at %02d:%02d local\n' "$HOUR" "$MINUTE"
printf 'Workspace: %s (window: %s days)\n' "$WORKSPACE_ROOT" "$DAYS"
printf 'Logs:\n  %s\n  %s\n' "$OUT_LOG" "$ERR_LOG"
