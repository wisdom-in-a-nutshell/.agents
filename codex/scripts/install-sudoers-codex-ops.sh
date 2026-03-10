#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${USER}"
SUDOERS_FILE="/etc/sudoers.d/codex-ops"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: install-sudoers-codex-ops.sh [options]

Install a scoped passwordless sudo policy for Codex machine-ops commands.

Options:
  --user <name>      Username to grant policy to (default: current user)
  --file <path>      Sudoers file path (default: /etc/sudoers.d/codex-ops)
  --dry-run          Print the generated sudoers line and exit
  -h, --help         Show this help

Allowed command groups:
  - /opt/homebrew/bin/brew services *
  - /opt/homebrew/bin/tailscale *
  - /bin/launchctl *
  - /usr/sbin/softwareupdate *
  - /usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate *
  - /usr/bin/defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      TARGET_USER="${2:-}"
      shift 2
      ;;
    --file)
      SUDOERS_FILE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$TARGET_USER" ]]; then
  echo "--user cannot be empty" >&2
  exit 2
fi

RULE="${TARGET_USER} ALL=(root) NOPASSWD: /opt/homebrew/bin/brew services *, /opt/homebrew/bin/tailscale *, /bin/launchctl *, /usr/sbin/softwareupdate *, /usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate *, /usr/bin/defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "$RULE"
  exit 0
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT
printf '%s\n' "$RULE" > "$TMP_FILE"

if [[ "${EUID}" -ne 0 ]]; then
  sudo -v
fi

sudo /usr/bin/install -o root -g wheel -m 440 "$TMP_FILE" "$SUDOERS_FILE"
sudo /usr/sbin/visudo -cf "$SUDOERS_FILE"

echo "Installed: $SUDOERS_FILE"
echo "Validation: OK"
