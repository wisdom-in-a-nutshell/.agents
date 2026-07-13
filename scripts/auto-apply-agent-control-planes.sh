#!/usr/bin/env bash
set -euo pipefail

AGENTS_REPO="${AGENTS_CONTROL_PLANE_ROOT:-${HOME}/GitHub/agents}"
GITHUB_ROOT="${HOME}/GitHub"
STAMP_FILE="${HOME}/.local/state/agents-control-plane/last-reconciled-agents.sha"
MODE="--apply"

ROOT_BOOTSTRAP_SCRIPT=""
SYNC_SKILLS_SCRIPT=""
SYNC_PLUGINS_SCRIPT=""
SYNC_COPILOT_SCRIPT=""
SYNC_GIT_HOOKS_SCRIPT=""
CODEX_BOOTSTRAP_SCRIPT=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Auto-apply shared agent control-plane state after the agents repo sync when tracked
runtime-relevant files changed.

Default mode is apply. Use --dry-run to report what would run.

Options:
  --apply                Apply changes (default)
  --dry-run              Report only
  --agents-repo <path>   Override agents control-plane repo path
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
SYNC_PLUGINS_SCRIPT="${AGENTS_REPO}/scripts/sync-plugins-registry.sh"
SYNC_COPILOT_SCRIPT="${AGENTS_REPO}/scripts/sync-copilot.sh"
SYNC_GIT_HOOKS_SCRIPT="${AGENTS_REPO}/scripts/sync-managed-git-hooks.sh"
CODEX_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/codex/scripts/bootstrap-machine-codex.sh"

[[ -d "$AGENTS_REPO/.git" ]] || die "Missing agents control-plane git repo: $AGENTS_REPO"
[[ -x "$ROOT_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $ROOT_BOOTSTRAP_SCRIPT"
[[ -x "$SYNC_SKILLS_SCRIPT" ]] || die "Missing executable: $SYNC_SKILLS_SCRIPT"
[[ -x "$SYNC_PLUGINS_SCRIPT" ]] || die "Missing executable: $SYNC_PLUGINS_SCRIPT"
[[ -x "$SYNC_COPILOT_SCRIPT" ]] || die "Missing executable: $SYNC_COPILOT_SCRIPT"
[[ -x "$SYNC_GIT_HOOKS_SCRIPT" ]] || die "Missing executable: $SYNC_GIT_HOOKS_SCRIPT"
[[ -x "$CODEX_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CODEX_BOOTSTRAP_SCRIPT"

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

changed_paths=()
while IFS= read -r path; do
  if [[ -n "$path" ]]; then
    changed_paths+=("$path")
  fi
done < <(
  git -C "$AGENTS_REPO" diff --name-only "$last_sha" "$current_sha" -- \
    codex \
    config \
    hooks \
    mcp \
    plugins \
    dev-servers \
    scripts \
    skills \
    skills-source
)

if (( ${#changed_paths[@]} == 0 )); then
  log "SKIP: no runtime-relevant agent control-plane changes since ${last_sha}"
  stamp_current_sha "$current_sha"
  exit 0
fi

skills_changed=0
plugins_changed=0
codex_changed=0
hooks_changed=0
git_hooks_changed=0
root_bootstrap_changed=0
shared_mcp_changed=0
repo_registry_changed=0
dev_servers_changed=0

for path in "${changed_paths[@]}"; do
  case "$path" in
    scripts/bootstrap-machine-agent-control-planes.sh)
      root_bootstrap_changed=1
      ;;
    scripts/sync-copilot.py|scripts/sync-copilot.sh)
      root_bootstrap_changed=1
      ;;
  esac
  case "$path" in
    config/*)
      root_bootstrap_changed=1
      ;;
  esac
  case "$path" in
    hooks/*)
      hooks_changed=1
      ;;
  esac
  case "$path" in
    hooks/git/*|scripts/sync-managed-git-hooks.sh)
      git_hooks_changed=1
      ;;
  esac
  case "$path" in
    skills/*|skills-source/*)
      skills_changed=1
      ;;
  esac
  case "$path" in
    plugins/*)
      plugins_changed=1
      ;;
  esac
  case "$path" in
    codex/*)
      codex_changed=1
      ;;
  esac
  case "$path" in
    mcp/*)
      shared_mcp_changed=1
      ;;
  esac
  case "$path" in
    dev-servers/*)
      dev_servers_changed=1
      ;;
  esac
  if [[ "$path" == "codex/config/repo-bootstrap.json" ]]; then
    repo_registry_changed=1
  fi
done

need_sync_skills=0
need_sync_plugins=0
need_sync_git_hooks=0
need_root_bootstrap=0
need_bootstrap_codex=0

if (( root_bootstrap_changed == 1 || dev_servers_changed == 1 || shared_mcp_changed == 1 || repo_registry_changed == 1 )); then
  need_root_bootstrap=1
fi
if (( skills_changed == 1 )); then
  need_sync_skills=1
fi
if (( plugins_changed == 1 )); then
  need_sync_plugins=1
fi
if (( git_hooks_changed == 1 || repo_registry_changed == 1 )); then
  need_sync_git_hooks=1
fi
if (( skills_changed == 1 || plugins_changed == 1 || codex_changed == 1 || hooks_changed == 1 || shared_mcp_changed == 1 )); then
  need_bootstrap_codex=1
fi

actions=()
if (( need_root_bootstrap == 1 )); then
  actions+=("root_bootstrap")
else
  if (( need_sync_skills == 1 )); then
    actions+=("sync_skills_registry")
  fi
  if (( need_sync_plugins == 1 )); then
    actions+=("sync_plugins_registry")
  fi
  if (( need_sync_git_hooks == 1 )); then
    actions+=("sync_managed_git_hooks")
  fi
  if (( need_bootstrap_codex == 1 )); then
    actions+=("bootstrap_codex")
  fi
fi

if (( ${#actions[@]} == 0 )); then
  log "SKIP: runtime-relevant diff did not require a control-plane apply"
  stamp_current_sha "$current_sha"
  exit 0
fi

log "APPLY: detected shared agent control-plane changes since ${last_sha}"
for action in "${actions[@]}"; do
  case "$action" in
    root_bootstrap)
      cmd=("$ROOT_BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT")
      ;;
    sync_skills_registry)
      if [[ "$MODE" == "--apply" ]]; then
        cmd=("$SYNC_SKILLS_SCRIPT" --apply)
      else
        cmd=("$SYNC_SKILLS_SCRIPT")
      fi
      ;;
    sync_plugins_registry)
      if [[ "$MODE" == "--apply" ]]; then
        cmd=("$SYNC_PLUGINS_SCRIPT" --apply)
      else
        cmd=("$SYNC_PLUGINS_SCRIPT")
      fi
      ;;
    sync_managed_git_hooks)
      cmd=("$SYNC_GIT_HOOKS_SCRIPT" "$MODE")
      ;;
    bootstrap_codex)
      cmd=("$CODEX_BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT")
      ;;
    *)
      die "Unknown reconcile action: $action"
      ;;
  esac
  log "+ ${cmd[*]}"
  "${cmd[@]}"
done

stamp_current_sha "$current_sha"
