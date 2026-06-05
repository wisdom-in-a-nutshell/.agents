#!/usr/bin/env bash
set -euo pipefail

APPLY=0
CHECK=0
REGISTRY_FILE=""
HOOKS_PATH=""
REPO_FILTERS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_REGISTRY_FILE="${ROOT_DIR}/codex/config/repo-bootstrap.json"
DEFAULT_HOOKS_PATH="${ROOT_DIR}/hooks/git"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Sync local Git hook configuration for managed repos.

Default mode is dry-run. Use --apply to set repo-local core.hooksPath.

Options:
  --apply                Apply local git config changes
  --dry-run              Show intended changes only (default)
  --check                Fail if managed repos do not point at the shared hook path
  --registry <path>      Override repo bootstrap registry
                         (default: codex/config/repo-bootstrap.json)
  --hooks-path <path>    Override shared Git hooks directory
                         (default: hooks/git)
  --repo <path>          Limit sync/check to an exact repo path (repeatable)
  -h, --help             Show this help

Examples:
  ~/GitHub/agents/scripts/sync-managed-git-hooks.sh
  ~/GitHub/agents/scripts/sync-managed-git-hooks.sh --apply
  ~/GitHub/agents/scripts/sync-managed-git-hooks.sh --check --repo ~/GitHub/win
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
      CHECK=0
      shift
      ;;
    --dry-run)
      APPLY=0
      CHECK=0
      shift
      ;;
    --check)
      APPLY=0
      CHECK=1
      shift
      ;;
    --registry)
      REGISTRY_FILE="${2:-}"
      shift 2
      ;;
    --hooks-path)
      HOOKS_PATH="${2:-}"
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

if [[ -z "$REGISTRY_FILE" ]]; then
  REGISTRY_FILE="$DEFAULT_REGISTRY_FILE"
fi
if [[ -z "$HOOKS_PATH" ]]; then
  HOOKS_PATH="$DEFAULT_HOOKS_PATH"
fi

REGISTRY_FILE="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$REGISTRY_FILE")"
HOOKS_PATH="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$HOOKS_PATH")"

[[ -f "$REGISTRY_FILE" ]] || die "Missing registry file: $REGISTRY_FILE"
[[ -r "$REGISTRY_FILE" ]] || die "Registry file is not readable: $REGISTRY_FILE"
[[ -d "$HOOKS_PATH" ]] || die "Missing shared hooks directory: $HOOKS_PATH"
[[ -x "$HOOKS_PATH/pre-commit" ]] || die "Missing executable shared pre-commit hook: $HOOKS_PATH/pre-commit"

REPOS=()
while IFS= read -r repo; do
  if [[ -n "$repo" ]]; then
    REPOS+=("$repo")
  fi
done < <(
  python3 - "$REGISTRY_FILE" ${REPO_FILTERS[@]+"${REPO_FILTERS[@]}"} <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

registry = Path(sys.argv[1]).expanduser().resolve()
filters = {str(Path(value).expanduser().resolve()) for value in sys.argv[2:]}
data = json.loads(registry.read_text(encoding="utf-8"))
repos = data.get("repos", [])
if not isinstance(repos, list):
    raise SystemExit(f"{registry}: repos must be an array")

for item in repos:
    if not isinstance(item, dict):
        continue
    raw_path = item.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        continue
    path = str(Path(raw_path).expanduser().resolve())
    if filters and path not in filters:
        continue
    print(path)
PY
)

if (( ${#REPO_FILTERS[@]} > 0 && ${#REPOS[@]} == 0 )); then
  die "No managed repos matched the requested --repo filters"
fi

drift_count=0
checked_count=0
updated_count=0
skipped_count=0

for repo in ${REPOS[@]+"${REPOS[@]}"}; do
  if [[ ! -d "$repo" ]]; then
    (( skipped_count += 1 ))
    continue
  fi
  if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
    log "SKIP not a git repo: $repo"
    (( skipped_count += 1 ))
    continue
  fi
  (( checked_count += 1 ))
  current="$(git -C "$repo" config --local --get core.hooksPath || true)"
  if [[ "$current" == "$HOOKS_PATH" ]]; then
    log "OK $repo core.hooksPath=$HOOKS_PATH"
    continue
  fi

  (( drift_count += 1 ))
  if (( CHECK == 1 )); then
    log "DRIFT $repo core.hooksPath=${current:-<unset>} expected=$HOOKS_PATH"
    continue
  fi
  if (( APPLY == 1 )); then
    git -C "$repo" config --local core.hooksPath "$HOOKS_PATH"
    log "Updated $repo core.hooksPath: ${current:-<unset>} -> $HOOKS_PATH"
    (( updated_count += 1 ))
  else
    log "Would update $repo core.hooksPath: ${current:-<unset>} -> $HOOKS_PATH"
  fi
done

if (( CHECK == 1 && drift_count > 0 )); then
  die "$drift_count managed repo(s) do not use the shared Git hooks path"
fi

if (( CHECK == 1 )); then
  log "Check complete. checked=$checked_count drift=$drift_count skipped=$skipped_count"
elif (( APPLY == 1 )); then
  log "Apply complete. checked=$checked_count updated=$updated_count skipped=$skipped_count"
else
  log "Dry run complete. checked=$checked_count drift=$drift_count skipped=$skipped_count"
fi
