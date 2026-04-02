#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APPLY=0
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Run the Claude control-plane bootstrap batch.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply          Apply changes
  --dry-run        Show actions only (default)
  --repo <path>    Limit repo-local sync to an exact repo path (repeatable)
  -h, --help       Show this help

Examples:
  ~/.agents/claude/scripts/bootstrap-machine-claude.sh
  ~/.agents/claude/scripts/bootstrap-machine-claude.sh --apply
  ~/.agents/claude/scripts/bootstrap-machine-claude.sh --apply --repo ~/.agents
USAGE
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
    --repo)
      REPO_FILTERS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

MODE_FLAG="--dry-run"
if (( APPLY == 1 )); then
  MODE_FLAG="--apply"
fi

REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

bash "${SCRIPT_DIR}/sync-global-claude-md.sh" "$MODE_FLAG"
bash "${SCRIPT_DIR}/sync-settings.sh" "$MODE_FLAG"
bash "${SCRIPT_DIR}/sync-global-mcp.sh" "$MODE_FLAG"
bash "${SCRIPT_DIR}/sync-skills.sh" "$MODE_FLAG" "${REPO_ARGS[@]}"
bash "${SCRIPT_DIR}/sync-repo-claude-configs.sh" "$MODE_FLAG" "${REPO_ARGS[@]}"
