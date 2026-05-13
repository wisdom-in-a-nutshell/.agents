#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${USER}"
SUDOERS_FILE="/etc/sudoers.d/codex-ops"
APPLY=0
NO_INPUT=0

usage() {
  cat <<'USAGE'
Usage: install-sudoers-codex-ops.sh [options]

Install a scoped passwordless sudo policy for Codex machine-ops commands.
Default mode is dry-run. Use --apply to write the sudoers file.

Options:
  --user <name>      Username to grant policy to (default: current user)
  --file <path>      Sudoers file path (default: /etc/sudoers.d/codex-ops)
  --apply            Install the generated sudoers file
  --dry-run          Print the generated sudoers line and exit (default)
  --no-input         Fail instead of prompting for sudo authentication
  -h, --help         Show this help

Allowed command groups:
  - /opt/homebrew/bin/brew services *
  - /opt/homebrew/bin/tailscale *
  - /bin/launchctl *
  - /usr/sbin/softwareupdate *
  - /usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate *
  - /usr/bin/defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true
  - /usr/bin/install -d -m 0755 /Library/Application Support/ClaudeCode
  - /usr/bin/install -m 0644 * /Library/Application Support/ClaudeCode/managed-settings.json
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
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --no-input)
      NO_INPUT=1
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

RULE="${TARGET_USER} ALL=(root) NOPASSWD: /opt/homebrew/bin/brew services *, /opt/homebrew/bin/tailscale *, /bin/launchctl *, /usr/sbin/softwareupdate *, /usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate *, /usr/bin/defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true, /usr/bin/install -d -m 0755 /Library/Application\\ Support/ClaudeCode, /usr/bin/install -m 0644 * /Library/Application\\ Support/ClaudeCode/managed-settings.json"

if [[ "$APPLY" -ne 1 ]]; then
  echo "$RULE"
  exit 0
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT
printf '%s\n' "$RULE" > "$TMP_FILE"

if [[ "${EUID}" -ne 0 ]]; then
  if [[ "$NO_INPUT" -eq 1 ]]; then
    echo "ERROR: --apply requires root or sudo authentication; --no-input forbids prompting." >&2
    exit 3
  fi
  sudo -v
fi

sudo /usr/bin/install -o root -g wheel -m 440 "$TMP_FILE" "$SUDOERS_FILE"
sudo /usr/sbin/visudo -cf "$SUDOERS_FILE"

echo "Installed: $SUDOERS_FILE"
echo "Validation: OK"
