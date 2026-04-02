#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLY=0
GLOBAL_CLAUDE_MD="${HOME}/.claude/CLAUDE.md"
CANONICAL_CLAUDE_MD="${CONTROL_PLANE_DIR}/config/global.claude.md"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Ensure ~/.claude/CLAUDE.md points at the canonical machine-wide guidance
file managed in ~/.agents.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show actions only (default)
  --global-claude-md <p> Override ~/.claude/CLAUDE.md target
  --canonical-claude <p> Override canonical global Claude source
  -h, --help             Show this help

Examples:
  ~/.agents/claude/scripts/sync-global-claude-md.sh
  ~/.agents/claude/scripts/sync-global-claude-md.sh --apply
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

ensure_parent_dir() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
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
    --global-claude-md)
      GLOBAL_CLAUDE_MD="${2:-}"
      shift 2
      ;;
    --canonical-claude)
      CANONICAL_CLAUDE_MD="${2:-}"
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

[[ "$GLOBAL_CLAUDE_MD" = /* ]] || die "--global-claude-md must be an absolute path"
[[ "$CANONICAL_CLAUDE_MD" = /* ]] || die "--canonical-claude must be an absolute path"
[[ -f "$CANONICAL_CLAUDE_MD" ]] || die "Missing canonical Claude file: $CANONICAL_CLAUDE_MD"
[[ -r "$CANONICAL_CLAUDE_MD" ]] || die "Canonical Claude file is not readable: $CANONICAL_CLAUDE_MD"

ensure_parent_dir "$GLOBAL_CLAUDE_MD"

if [[ -L "$GLOBAL_CLAUDE_MD" ]] && [[ "$(readlink "$GLOBAL_CLAUDE_MD")" == "$CANONICAL_CLAUDE_MD" ]]; then
  log "Global Claude symlink is already correct: $GLOBAL_CLAUDE_MD -> $CANONICAL_CLAUDE_MD"
  exit 0
fi

if (( APPLY == 0 )); then
  if [[ -L "$GLOBAL_CLAUDE_MD" ]]; then
    log "Would replace symlink: $GLOBAL_CLAUDE_MD -> $(readlink "$GLOBAL_CLAUDE_MD")"
  elif [[ -e "$GLOBAL_CLAUDE_MD" ]]; then
    log "Would replace file: $GLOBAL_CLAUDE_MD"
  else
    log "Would create symlink: $GLOBAL_CLAUDE_MD"
  fi
  log "Would point to canonical source: $CANONICAL_CLAUDE_MD"
  exit 0
fi

if [[ -e "$GLOBAL_CLAUDE_MD" || -L "$GLOBAL_CLAUDE_MD" ]]; then
  rm -f "$GLOBAL_CLAUDE_MD"
fi
ln -s "$CANONICAL_CLAUDE_MD" "$GLOBAL_CLAUDE_MD"
log "Linked $GLOBAL_CLAUDE_MD -> $CANONICAL_CLAUDE_MD"
