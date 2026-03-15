#!/usr/bin/env bash
set -euo pipefail

direction="right"

usage() {
  cat <<'EOF'
Usage: open-ghostty-codex-picker-split.sh [--direction right|down]

Open a Ghostty split pane and immediately run codex_jump in the new split.
The split inherits the current Ghostty working directory.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --direction)
      [[ $# -ge 2 ]] || { usage >&2; exit 1; }
      direction="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
done

case "$direction" in
  right|down) ;;
  *)
    echo "Unsupported direction: $direction" >&2
    exit 1
    ;;
esac

/usr/bin/osascript <<APPLESCRIPT
tell application "Ghostty"
  activate

  if (count windows) = 0 then
    error "Ghostty has no open windows."
  end if

  set launchConfig to new surface configuration
  set environment variables of launchConfig to {"CODEX_DISABLE_AUTOSTART=1"}
  set command of launchConfig to "/bin/zsh -l"
  set initial input of launchConfig to "codex_jump\n"

  set currentTerm to focused terminal of selected tab of front window
  split currentTerm direction ${direction} with configuration launchConfig
end tell
APPLESCRIPT
