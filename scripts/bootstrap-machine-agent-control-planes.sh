#!/usr/bin/env bash
set -euo pipefail

APPLY=0
GITHUB_ROOT="${HOME}/GitHub"
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYNC_SKILLS_SCRIPT="${SCRIPT_DIR}/sync-skills-registry.sh"
SYNC_PLUGINS_SCRIPT="${SCRIPT_DIR}/sync-plugins-registry.sh"
SYNC_ANTIGRAVITY_SPIKE_SCRIPT="${SCRIPT_DIR}/sync-antigravity-spike.sh"
SYNC_GIT_HOOKS_SCRIPT="${SCRIPT_DIR}/sync-managed-git-hooks.sh"
CODEX_BOOTSTRAP_SCRIPT="${ROOT_DIR}/codex/scripts/bootstrap-machine-codex.sh"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Run the machine-facing Codex control-plane bootstrap batch from ~/.agents.

Default mode is dry-run. Use --apply to write changes.

Options:
  --apply          Apply changes
  --dry-run        Show actions only (default)
  --github-root <path>
                    Override ~/GitHub root for Codex bootstrap
  --repo <path>    Limit repo-local sync/check to an exact repo path
                   (repeatable)
  -h, --help       Show this help

Examples:
  ~/.agents/scripts/bootstrap-machine-agent-control-planes.sh
  ~/.agents/scripts/bootstrap-machine-agent-control-planes.sh --apply
  ~/.agents/scripts/bootstrap-machine-agent-control-planes.sh --apply --repo ~/.agents
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
    --repo)
      REPO_FILTERS+=("${2:-}")
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

SYNC_ARGS=()
if (( APPLY == 1 )); then
  SYNC_ARGS+=(--apply)
fi

[[ -x "$SYNC_SKILLS_SCRIPT" ]] || die "Missing executable: $SYNC_SKILLS_SCRIPT"
[[ -x "$SYNC_PLUGINS_SCRIPT" ]] || die "Missing executable: $SYNC_PLUGINS_SCRIPT"
[[ -x "$SYNC_ANTIGRAVITY_SPIKE_SCRIPT" ]] || die "Missing executable: $SYNC_ANTIGRAVITY_SPIKE_SCRIPT"
[[ -x "$SYNC_GIT_HOOKS_SCRIPT" ]] || die "Missing executable: $SYNC_GIT_HOOKS_SCRIPT"
[[ -x "$CODEX_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CODEX_BOOTSTRAP_SCRIPT"
REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

sync_skills_cmd=(
  "$SYNC_SKILLS_SCRIPT"
  "${SYNC_ARGS[@]}"
  "${REPO_ARGS[@]}"
)
log "+ ${sync_skills_cmd[*]}"
"${sync_skills_cmd[@]}"

sync_plugins_cmd=(
  "$SYNC_PLUGINS_SCRIPT"
  "${SYNC_ARGS[@]}"
)
log "+ ${sync_plugins_cmd[*]}"
"${sync_plugins_cmd[@]}"

# Temporary Antigravity experiment: this may be ripped out once the durable
# cross-runtime bootstrap model is clear.
sync_antigravity_spike_cmd=(
  "$SYNC_ANTIGRAVITY_SPIKE_SCRIPT"
  "${SYNC_ARGS[@]}"
  --github-root "$GITHUB_ROOT"
)
log "+ ${sync_antigravity_spike_cmd[*]}"
"${sync_antigravity_spike_cmd[@]}"

sync_git_hooks_cmd=(
  "$SYNC_GIT_HOOKS_SCRIPT"
  "$MODE_FLAG"
  "${REPO_ARGS[@]}"
)
log "+ ${sync_git_hooks_cmd[*]}"
"${sync_git_hooks_cmd[@]}"

codex_cmd=(
  "$CODEX_BOOTSTRAP_SCRIPT"
  "$MODE_FLAG"
  --github-root "$GITHUB_ROOT"
  "${REPO_ARGS[@]}"
)
log "+ ${codex_cmd[*]}"
"${codex_cmd[@]}"
