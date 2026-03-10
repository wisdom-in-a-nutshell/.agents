#!/usr/bin/env bash
set -euo pipefail

APPLY=0
GITHUB_ROOT="${HOME}/GitHub"
GLOBAL_CONFIG="${HOME}/.codex/config.toml"
XCODE_CONFIG="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/config.toml"
XCODE_RULES="${HOME}/Library/Developer/Xcode/CodingAssistant/codex/rules/xcode.rules"
GHOSTTY_CONFIG="${HOME}/Library/Application Support/com.mitchellh.ghostty/config"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Apply the Codex-specific portion of machine bootstrap from the canonical
personal control plane in ~/.agents.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show actions only (default)
  --github-root <path>   Root used for workspace-write + repo trust scan
  --global-config <p>    Override ~/.codex/config.toml target
  --xcode-config <p>     Override Xcode Codex config target
  --xcode-rules <p>      Override Xcode rules target
  --ghostty-config <p>   Override Ghostty config target
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/bootstrap-machine-codex.sh
  ~/.agents/codex/scripts/bootstrap-machine-codex.sh --apply
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
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
    --github-root)
      GITHUB_ROOT="${2:-}"
      shift 2
      ;;
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --xcode-config)
      XCODE_CONFIG="${2:-}"
      shift 2
      ;;
    --xcode-rules)
      XCODE_RULES="${2:-}"
      shift 2
      ;;
    --ghostty-config)
      GHOSTTY_CONFIG="${2:-}"
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

MODE_FLAG="--dry-run"
if (( APPLY == 1 )); then
  MODE_FLAG="--apply"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_CONFIG_SCRIPT="${SCRIPT_DIR}/sync-config.sh"
SYNC_TRUSTED_SCRIPT="${SCRIPT_DIR}/sync-trusted-projects.sh"
GHOSTTY_SCRIPT="${SCRIPT_DIR}/configure-ghostty-cwd.sh"

[[ -x "$SYNC_CONFIG_SCRIPT" ]] || die "Missing executable: $SYNC_CONFIG_SCRIPT"
[[ -x "$SYNC_TRUSTED_SCRIPT" ]] || die "Missing executable: $SYNC_TRUSTED_SCRIPT"
[[ -x "$GHOSTTY_SCRIPT" ]] || die "Missing executable: $GHOSTTY_SCRIPT"

sync_config_cmd=(
  "$SYNC_CONFIG_SCRIPT"
  "$MODE_FLAG"
  --github-root "$GITHUB_ROOT"
  --global-config "$GLOBAL_CONFIG"
  --xcode-config "$XCODE_CONFIG"
  --xcode-rules "$XCODE_RULES"
)
log "+ ${sync_config_cmd[*]}"
"${sync_config_cmd[@]}"

sync_trusted_cmd=(
  "$SYNC_TRUSTED_SCRIPT"
  "$MODE_FLAG"
  --root "$GITHUB_ROOT"
  --global-config "$GLOBAL_CONFIG"
  --xcode-config "$XCODE_CONFIG"
)
log "+ ${sync_trusted_cmd[*]}"
"${sync_trusted_cmd[@]}"

ghostty_cmd=(
  "$GHOSTTY_SCRIPT"
  "$MODE_FLAG"
  --config "$GHOSTTY_CONFIG"
)
log "+ ${ghostty_cmd[*]}"
"${ghostty_cmd[@]}"
