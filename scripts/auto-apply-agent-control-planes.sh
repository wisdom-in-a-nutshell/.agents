#!/usr/bin/env bash
set -euo pipefail

AGENTS_REPO="${HOME}/.agents"
GITHUB_ROOT="${HOME}/GitHub"
STAMP_FILE="${HOME}/.local/state/agents-control-plane/last-reconciled-agents.sha"
PLUGIN_REFRESH_STAMP_FILE="${HOME}/.local/state/agents-control-plane/last-external-plugin-refresh.date"
MODE="--apply"

ROOT_BOOTSTRAP_SCRIPT=""
SYNC_SKILLS_SCRIPT=""
SYNC_PLUGINS_SCRIPT=""
SYNC_GIT_HOOKS_SCRIPT=""
SYNC_COPILOT_HOOKS_SCRIPT=""
REFRESH_EXTERNAL_PLUGINS_SCRIPT=""
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

refresh_external_plugins_if_due() {
  local today=""
  local last=""
  local cmd=()
  today="$(date -u +%F)"
  if [[ -f "$PLUGIN_REFRESH_STAMP_FILE" ]]; then
    last="$(tr -d '[:space:]' <"$PLUGIN_REFRESH_STAMP_FILE")"
  fi
  if [[ "$last" == "$today" ]]; then
    log "SKIP: external plugin refresh already ran for ${today}"
    return 0
  fi

  cmd=("$REFRESH_EXTERNAL_PLUGINS_SCRIPT")
  if [[ "$MODE" == "--apply" ]]; then
    cmd+=(--apply)
    log "APPLY: external plugin refresh is due for ${today}"
  else
    log "DRY-RUN: external plugin refresh is due for ${today}"
  fi
  log "+ ${cmd[*]}"
  "${cmd[@]}"

  if [[ "$MODE" != "--apply" ]]; then
    return 0
  fi

  log "+ ${SYNC_PLUGINS_SCRIPT} --apply"
  "$SYNC_PLUGINS_SCRIPT" --apply
  mkdir -p "$(dirname "$PLUGIN_REFRESH_STAMP_FILE")"
  printf '%s\n' "$today" >"$PLUGIN_REFRESH_STAMP_FILE"
  log "Stamped external plugin refresh: $PLUGIN_REFRESH_STAMP_FILE -> $today"
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
SYNC_GIT_HOOKS_SCRIPT="${AGENTS_REPO}/scripts/sync-managed-git-hooks.sh"
SYNC_COPILOT_HOOKS_SCRIPT="${AGENTS_REPO}/scripts/sync-copilot-hooks.sh"
REFRESH_EXTERNAL_PLUGINS_SCRIPT="${AGENTS_REPO}/scripts/refresh-external-plugins.sh"
CODEX_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/codex/scripts/bootstrap-machine-codex.sh"
CLAUDE_BOOTSTRAP_SCRIPT="${AGENTS_REPO}/claude/scripts/bootstrap-machine-claude.sh"

[[ -d "$AGENTS_REPO/.git" ]] || die "Missing ~/.agents git repo: $AGENTS_REPO"
[[ -x "$ROOT_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $ROOT_BOOTSTRAP_SCRIPT"
[[ -x "$SYNC_SKILLS_SCRIPT" ]] || die "Missing executable: $SYNC_SKILLS_SCRIPT"
[[ -x "$SYNC_PLUGINS_SCRIPT" ]] || die "Missing executable: $SYNC_PLUGINS_SCRIPT"
[[ -x "$SYNC_GIT_HOOKS_SCRIPT" ]] || die "Missing executable: $SYNC_GIT_HOOKS_SCRIPT"
[[ -x "$SYNC_COPILOT_HOOKS_SCRIPT" ]] || die "Missing executable: $SYNC_COPILOT_HOOKS_SCRIPT"
[[ -x "$REFRESH_EXTERNAL_PLUGINS_SCRIPT" ]] || die "Missing executable: $REFRESH_EXTERNAL_PLUGINS_SCRIPT"
[[ -x "$CODEX_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CODEX_BOOTSTRAP_SCRIPT"
[[ -x "$CLAUDE_BOOTSTRAP_SCRIPT" ]] || die "Missing executable: $CLAUDE_BOOTSTRAP_SCRIPT"

refresh_external_plugins_if_due

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
    claude \
    codex \
    hooks \
    mcp \
    plugins \
    plugins-source \
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
claude_changed=0
hooks_changed=0
git_hooks_changed=0
copilot_hooks_changed=0
root_bootstrap_changed=0
shared_mcp_changed=0
repo_registry_changed=0

for path in "${changed_paths[@]}"; do
  case "$path" in
    scripts/bootstrap-machine-agent-control-planes.sh)
      root_bootstrap_changed=1
      ;;
  esac
  case "$path" in
    hooks/*)
      hooks_changed=1
      ;;
  esac
  case "$path" in
    hooks/*|scripts/sync-copilot-hooks.sh)
      copilot_hooks_changed=1
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
    plugins/*|plugins-source/*)
      plugins_changed=1
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

need_sync_skills=0
need_sync_plugins=0
need_sync_git_hooks=0
need_sync_copilot_hooks=0
need_root_bootstrap=0
need_bootstrap_codex=0
need_bootstrap_claude=0

if (( root_bootstrap_changed == 1 )); then
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
if (( copilot_hooks_changed == 1 || repo_registry_changed == 1 )); then
  need_sync_copilot_hooks=1
fi
if (( skills_changed == 1 || plugins_changed == 1 || codex_changed == 1 || hooks_changed == 1 || shared_mcp_changed == 1 )); then
  need_bootstrap_codex=1
fi
if (( claude_changed == 1 || hooks_changed == 1 || shared_mcp_changed == 1 || skills_changed == 1 || plugins_changed == 1 || repo_registry_changed == 1 )); then
  need_bootstrap_claude=1
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
  if (( need_sync_copilot_hooks == 1 )); then
    actions+=("sync_copilot_hooks")
  fi
  if (( need_bootstrap_codex == 1 )); then
    actions+=("bootstrap_codex")
  fi
  if (( need_bootstrap_claude == 1 )); then
    actions+=("bootstrap_claude")
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
    sync_copilot_hooks)
      cmd=("$SYNC_COPILOT_HOOKS_SCRIPT" "$MODE")
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
