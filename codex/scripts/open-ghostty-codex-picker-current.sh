#!/usr/bin/env bash
set -euo pipefail

/usr/bin/osascript <<'APPLESCRIPT'
tell application "Ghostty"
  activate

  if (count windows) = 0 then
    set launchConfig to new surface configuration
    set environment variables of launchConfig to {"CODEX_DISABLE_AUTOSTART=1"}
    set command of launchConfig to "/bin/zsh -l"
    set initial input of launchConfig to "codex_jump\n"
    new window with configuration launchConfig
  else
    set currentTerm to focused terminal of selected tab of front window
    input text "codex_jump\n" to currentTerm
  end if
end tell
APPLESCRIPT
