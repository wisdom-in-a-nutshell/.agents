#!/usr/bin/env bash
set -euo pipefail

AGENTS_REPO="${HOME}/.agents"
GITHUB_ROOT="${HOME}/GitHub"
STAMP_FILE="${HOME}/.local/state/agents-control-plane/last-reconciled-agents.sha"
MODE="--apply"

ROOT_BOOTSTRAP_SCRIPT=""
SYNC_SKILLS_SCRIPT=""
CODEX_BOOTSTRAP_SCRIPT=""
CLAUDE_BOOTSTRAP_SCRIPT=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Auto-apply shared agent control-plane state after ~/.agents sync when tracked
runtime-relevant files changed.

Default mode is apply. Use --dry-run to report what would run.

Options:
  --apply                Apply changes (default)
  --dry-run              Report only
  --agents-repo <path>   Override ~/.agents repo path
  --github-root <path>   Override ~/GitHub root for Codex bootstrap
  --stamp-file <path>    Override machine-local reconcile stamp file
  -h, --help             Show this help
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

stamp_current_sha() {
  local sha="$1"
  if [[ "$MODE" != "--apply" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$STAMP_FILE")"
  printf '%s\n' "$sha" >"$STAMP_FILE"
  log "Stamped reconcile state: $STAMP_FILE -> $sha"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      MODE="--apply"
      shift
      ;;
    --dry-run)
      MODE="--dry-run"
      shift
      ;;
    --agents-repo)
      AGENTS_REPO="${2:-}"
      shift 2
      ;;
    --github-root)
      GITHUB_ROOT="${2:-}"
      shift 2
      ;;
    --stamp-file)
      STAMP_FILE="${2:-}"
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

ROOT_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/scripts/bootstrap-machine-agent-control-planes.sh"
SYNC_SKILLS_SCRIPT="${AGENTS_REPO}/scripts/sync-skills-registry.sh"
CODEX_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/codex/scripts/bootstrap-machine-codex.sh"
CLAUDE_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/claude/scripts/bootstrap-machine-claude.sh"

[[ -d "$AGENTS_REPO/.git" ]] || die "Missing ~/.agents git repo: $AGENTS_REPO"
[[ -x "$ROOT_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $ROOT_BOOTSTRAP_SCRIPT"
[[ -x "$SYNC_SKILLS_SCRIPT" ]] || die "Missing executable: $SYNC_SKILLS_SCRIPT"
[[ -x "$CODEX_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CODEX_BOOTSTRAP_SCRIPT"
[[ -x "$CLAUDE_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CLAUDE_BOOTSTRAP_SCRIPT"

current_sha="$(git -C "$AGENTS_REPO" rev-parse HEAD)"
last_sha=""
if [[ -f "$STAMP_FILE" ]]; then
  last_sha="$(tr -d '[:space:]' <"$STAMP_FILE")"
fi

if [[ -z "$last_sha" ]]; then
  log "APPLY: no prior reconcile stamp"
  log "+ ${ROOT_BOOTSTRAP_SCRIPT} ${MODE} --github-root ${GITHUB_ROOT}"
  "$ROOT_BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT"
  stamp_current_sha "$current_sha"
  exit 0
fi

if [[ "$last_sha" == "$current_sha" ]]; then
  log "SKIP: already reconciled at ${current_sha}"
  stamp_current_sha "$current_sha"
  exit 0
fi

if ! git -C "$AGENTS_REPO" cat-file -e "${last_sha}^{commit}" 2>/dev/null; then
  log "APPLY: previous reconcile commit is no longer available"
  log "+ ${ROOT_BOOTSTRAP_SCRIPT} ${MODE} --github-root ${GITHUB_ROOT}"
  "$ROOT_BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT"
  stamp_current_sha "$current_sha"
  exit 0
fi

mapfile -t changed_paths < <(
  git -C "$AGENTS_REPO" diff --name-only "$last_sha" "$current_sha" -- \
    claude \
    codex \
    mcp \
    skills \
    skills-source
)

if (( ${#changed_paths[@]} == 0 )); then
  log "SKIP: no runtime-relevant agent control-plane changes since ${last_sha}"
  stamp_current_sha "$current_sha"
  exit 0
fi

skills_changed=0
codex_changed=0
claude_changed=0
shared_mcp_changed=0
repo_registry_changed=0

for path in "${changed_paths[@]}"; do
  case "$path" in
    skills/*|skills-source/*)
      skills_changed=1
      ;;
  esac
  case "$path" in
    codex/*)
      codex_changed=1
      ;;
  esac
  case "$path" in
    claude/*)
      claude_changed=1
      ;;
  esac
  case "$path" in
    mcp/*)
      shared_mcp_changed=1
      ;;
  esac
  if [[ "$path" == "codex/config/repo-bootstrap.json" ]]; then
    repo_registry_changed=1
  fi
done

actions=()
if (( skills_changed == 1 )); then
  actions+=("sync_skills_registry")
fi
if (( codex_changed == 1 || shared_mcp_changed == 1 )); then
  actions+=("bootstrap_codex")
fi
if (( claude_changed == 1 || shared_mcp_changed == 1 || skills_changed == 1 || repo_registry_changed == 1 )); then
  actions+=("bootstrap_claude")
fi

if (( ${#actions[@]} == 0 )); then
  log "SKIP: runtime-relevant diff did not require a control-plane apply"
  stamp_current_sha "$current_sha"
  exit 0
fi

log "APPLY: detected shared agent control-plane changes since ${last_sha}"
for action in "${actions[@]}"; do
  case "$action" in
    sync_skills_registry)
      cmd=("$SYNC_SKILLS_SCRIPT" "$MODE")
      ;;
    bootstrap_codex)
      cmd=("$CODEX_BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT")
      ;;
    bootstrap_claude)
      cmd=("$CLAUDE_BOOTSTRAP_SCRIPT" "$MODE")
      ;;
    *)
      die "Unknown reconcile action: $action"
      ;;
  esac
  log "+ ${cmd[*]}"
  "${cmd[@]}"
done

stamp_current_sha "$current_sha"
