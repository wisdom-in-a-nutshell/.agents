#!/usr/bin/env bash
set -euo pipefail

MODE="--dry-run"
CONFIG_PATH="${HOME}/Library/Application Support/com.mitchellh.ghostty/config"
WRAPPER_PATH="${HOME}/.agents/codex/scripts/ghostty-codex-then-shell.sh"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Configure Ghostty for CWD-safe Codex startup:
  - initial-command = direct:<wrapper>
  - shell-integration = zsh
  - remove command=direct:...ghostty-codex-then-shell.sh override
  - remove legacy Ghostty-owned picker keybinds

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show diff only (default)
  --config <path>        Ghostty config path
  --wrapper <path>       Wrapper script path
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/configure-ghostty-cwd.sh
  ~/.agents/codex/scripts/configure-ghostty-cwd.sh --apply
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '%s\n' "$*"
}

upsert_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp_file="${file}.tmp"

  awk -v key="$key" -v value="$value" '
    BEGIN {
      found = 0
      regex = "^[[:space:]]*" key "[[:space:]]*="
    }
    {
      if ($0 ~ regex) {
        if (!found) {
          print key " = " value
          found = 1
        }
        next
      }
      print
    }
    END {
      if (!found) {
        print ""
        print key " = " value
      }
    }
  ' "$file" > "$tmp_file"
  mv "$tmp_file" "$file"
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
    --wrapper)
      WRAPPER_PATH="${2:-}"
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

mkdir -p "$(dirname "$CONFIG_PATH")"
if [[ ! -f "$CONFIG_PATH" ]]; then
  : > "$CONFIG_PATH"
fi

[[ -x "$WRAPPER_PATH" ]] || die "Wrapper is missing or not executable: $WRAPPER_PATH"

RENDERED="${TMP_DIR}/ghostty.config"
cp "$CONFIG_PATH" "$RENDERED"

# Remove legacy wrapper command override that breaks split/tab cwd inheritance.
awk '
  !($0 ~ /^[[:space:]]*command[[:space:]]*=/ && $0 ~ /ghostty-codex-then-shell\.sh/)
' "$RENDERED" > "${RENDERED}.filtered"
mv "${RENDERED}.filtered" "$RENDERED"

# Remove legacy Ghostty-owned picker keybind variants. Keyboard Maestro owns
# the optional shortcuts now, so Ghostty config should not carry them.
awk '
  !($0 ~ /^[[:space:]]*keybind[[:space:]]*=[[:space:]]*super\+shift\+g=/)
' "$RENDERED" > "${RENDERED}.filtered"
mv "${RENDERED}.filtered" "$RENDERED"

# Remove any previously managed picker helper variants that used to live in
# Ghostty config instead of Keyboard Maestro.
awk '
  !($0 ~ /^[[:space:]]*keybind[[:space:]]*=[[:space:]]*super\+shift\+t=/) &&
  !($0 ~ /^[[:space:]]*keybind[[:space:]]*=[[:space:]]*chain=text:codex_jump\\n[[:space:]]*$/)
' "$RENDERED" > "${RENDERED}.filtered"
mv "${RENDERED}.filtered" "$RENDERED"

upsert_key "$RENDERED" "initial-command" "direct:${WRAPPER_PATH}"
upsert_key "$RENDERED" "shell-integration" "zsh"

if diff -u "$CONFIG_PATH" "$RENDERED" >/dev/null 2>&1; then
  log "No change: $CONFIG_PATH already matches desired Ghostty CWD-safe config."
  exit 0
fi

log "=== Ghostty Config Diff (${CONFIG_PATH}) ==="
diff -u "$CONFIG_PATH" "$RENDERED" || true

if [[ "$MODE" == "--dry-run" ]]; then
  log "Dry-run complete. Re-run with --apply to write changes."
  exit 0
fi

install -m 600 "$RENDERED" "$CONFIG_PATH"

log "Updated: $CONFIG_PATH"
