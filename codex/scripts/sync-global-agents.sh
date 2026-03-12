#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLY=0
GLOBAL_AGENTS="${HOME}/.codex/AGENTS.md"
CANONICAL_AGENTS="${CONTROL_PLANE_DIR}/config/global.agents.md"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Ensure ~/.codex/AGENTS.md points at the canonical machine-wide guidance
file managed in ~/.agents.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply                Apply changes
  --dry-run              Show actions only (default)
  --global-agents <p>    Override ~/.codex/AGENTS.md target
  --canonical-agents <p> Override canonical global AGENTS source
  -h, --help             Show this help

Examples:
  ~/.agents/codex/scripts/sync-global-agents.sh
  ~/.agents/codex/scripts/sync-global-agents.sh --apply
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

backup_runtime_file_if_needed() {
  local file="$1"
  local backup_path="$file.bak.$TIMESTAMP"

  if [[ ! -e "$file" && ! -L "$file" ]]; then
    return 0
  fi

  if [[ -L "$file" ]]; then
    rm -f "$file"
    return 0
  fi

  if [[ ! -s "$file" ]]; then
    rm -f "$file"
    return 0
  fi

  if cmp -s "$file" "$CANONICAL_AGENTS"; then
    rm -f "$file"
    return 0
  fi

  mv "$file" "$backup_path"
  log "Backed up existing runtime AGENTS file to $backup_path"
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
    --global-agents)
      GLOBAL_AGENTS="${2:-}"
      shift 2
      ;;
    --canonical-agents)
      CANONICAL_AGENTS="${2:-}"
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

[[ "$GLOBAL_AGENTS" = /* ]] || die "--global-agents must be an absolute path"
[[ "$CANONICAL_AGENTS" = /* ]] || die "--canonical-agents must be an absolute path"
[[ -f "$CANONICAL_AGENTS" ]] || die "Missing canonical AGENTS file: $CANONICAL_AGENTS"
[[ -r "$CANONICAL_AGENTS" ]] || die "Canonical AGENTS file is not readable: $CANONICAL_AGENTS"

ensure_parent_dir "$GLOBAL_AGENTS"

if [[ -L "$GLOBAL_AGENTS" ]] && [[ "$(readlink "$GLOBAL_AGENTS")" == "$CANONICAL_AGENTS" ]]; then
  log "Global AGENTS symlink is already correct: $GLOBAL_AGENTS -> $CANONICAL_AGENTS"
  exit 0
fi

if (( APPLY == 0 )); then
  if [[ -L "$GLOBAL_AGENTS" ]]; then
    log "Would replace symlink: $GLOBAL_AGENTS -> $(readlink "$GLOBAL_AGENTS")"
  elif [[ -e "$GLOBAL_AGENTS" ]]; then
    log "Would replace file: $GLOBAL_AGENTS"
  else
    log "Would create symlink: $GLOBAL_AGENTS"
  fi
  log "Would point to canonical source: $CANONICAL_AGENTS"
  exit 0
fi

backup_runtime_file_if_needed "$GLOBAL_AGENTS"
ln -s "$CANONICAL_AGENTS" "$GLOBAL_AGENTS"
log "Linked $GLOBAL_AGENTS -> $CANONICAL_AGENTS"
