#!/usr/bin/env bash
set -euo pipefail

APPLY=0
LABEL="com.${USER}.codex-sidebar-project-pruner"
HOUR=1
MINUTE=0
OLDER_THAN_DAYS=2
SCRIPT_PATH="${HOME}/.agents/codex/scripts/prune-sidebar-projects.py"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.local/state/codex-control-plane/log"
OUT_LOG="${LOG_DIR}/sidebar-project-prune.out.log"
ERR_LOG="${LOG_DIR}/sidebar-project-prune.err.log"
REMOTE_HOSTS=()
AUTO_REMOTE_HOSTS=1
NO_UNSAVED_THREAD_PROJECTS=0
RUN_AT_LOAD=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Install/update a LaunchAgent that prunes stale Codex Desktop sidebar projects.
Default mode is dry-run. Use --apply to write and load.

Options:
  --apply                    Write and load the LaunchAgent
  --dry-run                  Print the plist only (default)
  --label <label>            LaunchAgent label
  --hour <0-23>              Hour to run (default: 1)
  --minute <0-59>            Minute to run (default: 0)
  --older-than-days <n>      Forwarded prune threshold (default: 2)
  --remote-host <host>       Forwarded remote host, e.g. macmini (repeatable)
  --auto-remote-hosts        Include hosts from ~/.codex remote-projects (default)
  --no-auto-remote-hosts     Do not inspect ~/.codex remote-projects
  --no-unsaved-thread-projects
                             Forward only saved/remote sidebar entries
  --script <path>            Pruner script path
  --run-at-load              Run once immediately when loaded
  --no-run-at-load           Do not run immediately when loaded (default)
  -h, --help                 Show this help

Examples:
  ~/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh
  ~/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh --apply
  ~/.agents/codex/scripts/install-sidebar-project-prune-launchagent.sh --apply --remote-host macmini --no-unsaved-thread-projects
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

is_number() {
  [[ "${1:-}" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

xml_escape() {
  local value="$1"
  value="${value//&/&amp;}"
  value="${value//</&lt;}"
  value="${value//>/&gt;}"
  printf '%s' "$value"
}

render_program_arguments() {
  local args=(
    "$SCRIPT_PATH"
    "--apply"
    "--older-than-days" "$OLDER_THAN_DAYS"
    "--quit-codex-app"
    "--reopen-codex-app"
    "--plain"
  )
  for host in "${REMOTE_HOSTS[@]}"; do
    args+=("--remote-host" "$host")
  done
  if (( NO_UNSAVED_THREAD_PROJECTS == 1 )); then
    args+=("--no-unsaved-thread-projects")
  fi
  for arg in "${args[@]}"; do
    printf '      <string>%s</string>\n' "$(xml_escape "$arg")"
  done
}

load_auto_remote_hosts() {
  (( AUTO_REMOTE_HOSTS == 1 )) || return 0
  local state_file="${HOME}/.codex/.codex-global-state.json"
  [[ -f "$state_file" ]] || return 0
  while IFS= read -r host; do
    [[ -n "$host" ]] || continue
    REMOTE_HOSTS+=("$host")
  done < <(python3 - "$state_file" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
seen = set()
for item in data.get("remote-projects", []):
    if not isinstance(item, dict):
        continue
    host_id = item.get("hostId")
    if not isinstance(host_id, str) or not host_id.startswith("remote-ssh-discovered:"):
        continue
    host = host_id.split(":", 1)[1]
    if host and host not in seen:
        seen.add(host)
        print(host)
PY
  )
}

render_plist() {
  local run_at_load_value="<false/>"
  if (( RUN_AT_LOAD == 1 )); then
    run_at_load_value="<true/>"
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
$(render_program_arguments)
    </array>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>${HOUR}</integer>
      <key>Minute</key>
      <integer>${MINUTE}</integer>
    </dict>

    <key>RunAtLoad</key>
    ${run_at_load_value}

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
    --older-than-days)
      OLDER_THAN_DAYS="${2:-}"
      shift 2
      ;;
    --remote-host)
      REMOTE_HOSTS+=("${2:-}")
      shift 2
      ;;
    --auto-remote-hosts)
      AUTO_REMOTE_HOSTS=1
      shift
      ;;
    --no-auto-remote-hosts)
      AUTO_REMOTE_HOSTS=0
      shift
      ;;
    --no-unsaved-thread-projects)
      NO_UNSAVED_THREAD_PROJECTS=1
      shift
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
[[ -x "$SCRIPT_PATH" ]] || die "pruner script is not executable: $SCRIPT_PATH"
is_int "$HOUR" || die "invalid --hour: $HOUR"
is_int "$MINUTE" || die "invalid --minute: $MINUTE"
(( HOUR >= 0 && HOUR <= 23 )) || die "--hour must be 0..23"
(( MINUTE >= 0 && MINUTE <= 59 )) || die "--minute must be 0..59"
is_number "$OLDER_THAN_DAYS" || die "invalid --older-than-days: $OLDER_THAN_DAYS"
load_auto_remote_hosts
if ((${#REMOTE_HOSTS[@]} > 0)); then
  mapfile -t REMOTE_HOSTS < <(printf '%s\n' "${REMOTE_HOSTS[@]}" | awk 'NF && !seen[$0]++')
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

DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST_PATH"
if (( RUN_AT_LOAD == 1 )); then
  launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
fi

printf 'Loaded %s from %s\n' "$LABEL" "$PLIST_PATH"
printf 'Schedule: %02d:%02d daily\n' "$HOUR" "$MINUTE"
printf 'Threshold: older than %s days\n' "$OLDER_THAN_DAYS"
printf 'Logs:\n  %s\n  %s\n' "$OUT_LOG" "$ERR_LOG"
