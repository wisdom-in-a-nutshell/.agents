#!/usr/bin/env bash
set -euo pipefail

/usr/bin/osascript <<'APPLESCRIPT'
tell application "Ghostty"
  activate
  set launchConfig to new surface configuration
  set environment variables of launchConfig to {"CODEX_DISABLE_AUTOSTART=1"}
  set command of launchConfig to "/bin/zsh -l"
  set initial input of launchConfig to "codex_jump\n"

  if (count windows) = 0 then
    new window with configuration launchConfig
  else
    new tab in front window with configuration launchConfig
  end if
end tell
APPLESCRIPT
