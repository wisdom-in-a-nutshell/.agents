#!/usr/bin/env bash
set -euo pipefail

MODE="--dry-run"
GROUP_NAME="Codex Ghostty"
MACRO_NAME="Open Ghostty Codex Picker Tab"
HOTKEY_KEY_CODE=17
HOTKEY_MODIFIERS=6400
HELPER_PATH="${HOME}/.agents/codex/scripts/open-ghostty-codex-picker-tab.sh"
KM_APP="/Applications/Keyboard Maestro.app"
MACROS_PLIST="${HOME}/Library/Application Support/Keyboard Maestro/Keyboard Maestro Macros.plist"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Install a thin Keyboard Maestro trigger for Ghostty:
  - Group active only in Ghostty
  - Cmd+Shift+T runs the shared Codex picker-tab helper

Default mode is dry-run. Use --apply to import/update the macro.

Options:
  --apply                Apply changes
  --dry-run              Show planned macro XML only (default)
  --group-name <name>    Keyboard Maestro macro group name
  --macro-name <name>    Keyboard Maestro macro name
  --helper <path>        Helper script path
  -h, --help             Show this help
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply|--dry-run)
      MODE="$1"
      shift
      ;;
    --group-name)
      GROUP_NAME="${2:-}"
      shift 2
      ;;
    --macro-name)
      MACRO_NAME="${2:-}"
      shift 2
      ;;
    --helper)
      HELPER_PATH="${2:-}"
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

[[ -d "$KM_APP" ]] || die "Keyboard Maestro.app not found at $KM_APP"
[[ -x "$HELPER_PATH" ]] || die "Helper is missing or not executable: $HELPER_PATH"

[[ -f "$MACROS_PLIST" ]] || die "Keyboard Maestro macros store not found: $MACROS_PLIST"

if [[ "$MODE" == "--dry-run" ]]; then
  printf 'Would install Keyboard Maestro macro "%s" in group "%s" using helper:\n%s\n' \
    "$MACRO_NAME" "$GROUP_NAME" "$HELPER_PATH"
  exit 0
fi

BACKUP_PATH="${MACROS_PLIST}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$MACROS_PLIST" "$BACKUP_PATH"

python3 - "$MACROS_PLIST" "$GROUP_NAME" "$MACRO_NAME" "$HELPER_PATH" "$HOTKEY_KEY_CODE" "$HOTKEY_MODIFIERS" <<'PY'
import plistlib
import sys
import time
import uuid
from pathlib import Path

plist_path = Path(sys.argv[1])
group_name = sys.argv[2]
macro_name = sys.argv[3]
helper_path = sys.argv[4]
hotkey_key_code = int(sys.argv[5])
hotkey_modifiers = int(sys.argv[6])

APPLE_EPOCH_OFFSET = 978307200
now = time.time() - APPLE_EPOCH_OFFSET

def km_uuid() -> str:
    return str(uuid.uuid4()).upper()

with plist_path.open("rb") as fh:
    data = plistlib.load(fh)

groups = data.setdefault("MacroGroups", [])
groups[:] = [g for g in groups if g.get("Name") != group_name]

group_uid = km_uuid()
toggle_uid = km_uuid()
macro_uid = km_uuid()

group = {
    "Activate": "Normal",
    "AddToMacroPalette": False,
    "AddToStatusMenu": False,
    "CreationDate": now,
    "DisplayToggle": False,
    "IsActive": True,
    "KeyCode": 32767,
    "Macros": [
        {
            "Actions": [
                {
                    "IncludeStdErr": True,
                    "IsActive": True,
                    "IsDisclosed": True,
                    "MacroActionType": "ExecuteShellScript",
                    "Path": "",
                    "Text": f"#!/bin/zsh\n\"{helper_path}\"",
                    "TimeOutAbortsMacro": True,
                    "TrimResults": True,
                    "TrimResultsNew": True,
                    "UseText": True,
                }
            ],
            "CreationDate": now,
            "IsActive": True,
            "ModificationDate": now,
            "Name": macro_name,
            "Triggers": [
                {
                    "FireType": "Pressed",
                    "KeyCode": hotkey_key_code,
                    "MacroTriggerType": "HotKey",
                    "Modifiers": hotkey_modifiers,
                }
            ],
            "UID": macro_uid,
        }
    ],
    "Modifiers": 0,
    "Name": group_name,
    "PaletteUnderMouse": False,
    "Targeting": {
        "Targeting": "These",
        "TargetingApps": [
            {
                "BundleIdentifier": "com.mitchellh.ghostty",
                "Name": "Ghostty",
                "NewFile": "/Applications/Ghostty.app",
            }
        ],
    },
    "ToggleMacroUID": toggle_uid,
    "UID": group_uid,
}

groups.append(group)

with plist_path.open("wb") as fh:
    plistlib.dump(data, fh, fmt=plistlib.FMT_BINARY, sort_keys=False)
PY

osascript -e 'tell application "Keyboard Maestro" to reload' >/dev/null 2>&1 || true

printf 'Installed Keyboard Maestro macro "%s" in group "%s".\n' "$MACRO_NAME" "$GROUP_NAME"
printf 'Backup: %s\n' "$BACKUP_PATH"
