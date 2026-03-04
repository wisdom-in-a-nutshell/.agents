#!/usr/bin/env bash
set -euo pipefail

LABEL="com.dobby.codex-app-server-snapshot-refresh"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
REFRESH_SCRIPT="${HOME}/.agents/skills-source/owned/codex-app-server/scripts/refresh_snapshot.sh"

START_HOUR="${START_HOUR:-6}"
START_MINUTE="${START_MINUTE:-0}"

if [[ ! -x "${REFRESH_SCRIPT}" ]]; then
  echo "Refresh script missing or not executable: ${REFRESH_SCRIPT}" >&2
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
      <string>${REFRESH_SCRIPT}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>${START_HOUR}</integer>
      <key>Minute</key>
      <integer>${START_MINUTE}</integer>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/${LABEL}.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${LABEL}.err.log</string>
  </dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"
launchctl enable "gui/$(id -u)/${LABEL}"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "Installed launchd job: ${LABEL}"
echo "Plist: ${PLIST_PATH}"
echo "Schedule: daily at ${START_HOUR}:$(printf '%02d' "${START_MINUTE}") local time"
