#!/usr/bin/env bash
set -euo pipefail

MODE="--dry-run"
CONFIG_PATH="${HOME}/.config/karabiner/karabiner.json"
HELPER_PATH="${HOME}/.agents/codex/scripts/open-ghostty-codex-picker-tab.sh"
RULE_DESCRIPTION="Ghostty Codex picker shortcuts"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Configure Ghostty-specific Karabiner shortcuts:
  - Cmd+T opens a new Ghostty tab and immediately launches codex_jump
  - Cmd+Shift+T keeps a plain Ghostty new tab

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show diff only (default)
  --config <path>        Karabiner config path
  --helper <path>        Helper script path for picker-tab launch
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/configure-karabiner-ghostty-codex-shortcuts.sh
  ~/.agents/codex/scripts/configure-karabiner-ghostty-codex-shortcuts.sh --apply
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '%s\n' "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply|--dry-run)
      MODE="$1"
      shift
      ;;
    --config)
      CONFIG_PATH="${2:-}"
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

[[ -x "$HELPER_PATH" ]] || die "Helper is missing or not executable: $HELPER_PATH"

mkdir -p "$(dirname "$CONFIG_PATH")"
if [[ ! -f "$CONFIG_PATH" ]]; then
  printf '{\n  "profiles": [\n    {\n      "name": "Default profile",\n      "selected": true,\n      "virtual_hid_keyboard": {\n        "keyboard_type_v2": "ansi"\n      }\n    }\n  ]\n}\n' > "$CONFIG_PATH"
fi

RENDERED="${TMP_DIR}/karabiner.json"

jq \
  --arg description "$RULE_DESCRIPTION" \
  --arg helper "$HELPER_PATH" \
  '
  def ghostty_condition:
    {
      "type": "frontmost_application_if",
      "bundle_identifiers": ["^com\\.mitchellh\\.ghostty$"]
    };

  def picker_rule($description; $helper):
    {
      "description": $description,
      "manipulators": [
        {
          "type": "basic",
          "conditions": [ghostty_condition],
          "from": {
            "key_code": "t",
            "modifiers": {
              "mandatory": ["command"],
              "optional": []
            }
          },
          "to": [
            {
              "shell_command": $helper
            }
          ]
        },
        {
          "type": "basic",
          "conditions": [ghostty_condition],
          "from": {
            "key_code": "t",
            "modifiers": {
              "mandatory": ["command", "shift"],
              "optional": []
            }
          },
          "to": [
            {
              "key_code": "t",
              "modifiers": ["command"]
            }
          ]
        }
      ]
    };

  def ensure_profiles:
    if (.profiles | type) != "array" or (.profiles | length) == 0 then
      .profiles = [
        {
          "name": "Default profile",
          "selected": true,
          "virtual_hid_keyboard": {
            "keyboard_type_v2": "ansi"
          }
        }
      ]
    else
      .
    end;

  def ensure_selected_profile:
    if any(.profiles[]; (.selected // false) == true) then
      .
    else
      .profiles[0].selected = true
    end;

  def upsert_rule($description; $helper):
    .complex_modifications = (.complex_modifications // {})
    | .complex_modifications.rules =
        (
          (.complex_modifications.rules // [])
          | map(select(.description != $description))
          | . + [picker_rule($description; $helper)]
        );

  ensure_profiles
  | ensure_selected_profile
  | .profiles |= map(
      if (.selected // false) == true then
        upsert_rule($description; $helper)
      else
        .
      end
    )
  ' "$CONFIG_PATH" > "$RENDERED"

if diff -u "$CONFIG_PATH" "$RENDERED" >/dev/null 2>&1; then
  log "No change: $CONFIG_PATH already matches desired Ghostty/Codex Karabiner shortcuts."
  exit 0
fi

log "=== Karabiner Config Diff (${CONFIG_PATH}) ==="
diff -u "$CONFIG_PATH" "$RENDERED" || true

if [[ "$MODE" == "--dry-run" ]]; then
  log "Dry-run complete. Re-run with --apply to write changes."
  exit 0
fi

BACKUP_PATH="${CONFIG_PATH}.bak.${TIMESTAMP}"
cp "$CONFIG_PATH" "$BACKUP_PATH"
install -m 600 "$RENDERED" "$CONFIG_PATH"

log "Backup: $BACKUP_PATH"
log "Updated: $CONFIG_PATH"
