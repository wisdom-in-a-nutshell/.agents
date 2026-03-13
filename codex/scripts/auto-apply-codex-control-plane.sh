#!/usr/bin/env bash
set -euo pipefail

AGENTS_REPO="${HOME}/.agents"
BOOTSTRAP_SCRIPT="${AGENTS_REPO}/codex/scripts/bootstrap-machine-codex.sh"
STAMP_FILE="${HOME}/.local/state/codex-control-plane/last-reconciled-agents.sha"
GITHUB_ROOT="${HOME}/GitHub"
MODE="--apply"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Auto-apply the Codex control plane after ~/.agents sync when tracked Codex files changed.

Default mode is apply. Use --dry-run to report whether a reconcile would run.

Options:
  --apply                Apply changes (default)
  --dry-run              Report only
  --agents-repo <path>   Override ~/.agents repo path
  --github-root <path>   Override ~/GitHub root
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

[[ -d "$AGENTS_REPO/.git" ]] || die "Missing ~/.agents git repo: $AGENTS_REPO"
[[ -x "$BOOTSTRAP_SCRIPT" ]] || die "Missing executable bootstrap script: $BOOTSTRAP_SCRIPT"

current_sha="$(git -C "$AGENTS_REPO" rev-parse HEAD)"
last_sha=""
if [[ -f "$STAMP_FILE" ]]; then
  last_sha="$(tr -d '[:space:]' <"$STAMP_FILE")"
fi

should_apply=0
reason=""

if [[ -z "$last_sha" ]]; then
  should_apply=1
  reason="no prior reconcile stamp"
elif [[ "$last_sha" == "$current_sha" ]]; then
  should_apply=0
  reason="already reconciled at ${current_sha}"
elif ! git -C "$AGENTS_REPO" cat-file -e "${last_sha}^{commit}" 2>/dev/null; then
  should_apply=1
  reason="previous reconcile commit is no longer available"
elif git -C "$AGENTS_REPO" diff --quiet "$last_sha" "$current_sha" -- codex; then
  should_apply=0
  reason="no Codex control-plane changes since ${last_sha}"
else
  should_apply=1
  reason="Codex control-plane files changed since ${last_sha}"
fi

if (( should_apply == 0 )); then
  log "SKIP: ${reason}"
  mkdir -p "$(dirname "$STAMP_FILE")"
  printf '%s\n' "$current_sha" >"$STAMP_FILE"
  exit 0
fi

log "APPLY: ${reason}"
log "+ ${BOOTSTRAP_SCRIPT} ${MODE} --github-root ${GITHUB_ROOT}"
"$BOOTSTRAP_SCRIPT" "$MODE" --github-root "$GITHUB_ROOT"

if [[ "$MODE" == "--apply" ]]; then
  mkdir -p "$(dirname "$STAMP_FILE")"
  printf '%s\n' "$current_sha" >"$STAMP_FILE"
  log "Stamped reconcile state: $STAMP_FILE -> $current_sha"
fi
