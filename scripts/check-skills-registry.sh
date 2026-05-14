#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STAGED_OK=0

case "${1:-}" in
  --staged-ok)
    STAGED_OK=1
    ;;
  "")
    ;;
  *)
    echo "Usage: $(basename "$0") [--staged-ok]" >&2
    exit 2
    ;;
esac

cd "$REPO_ROOT"

# Regenerate derived registry views, then verify no tracked artifacts changed.
# If they did, the repo was out of sync.
python3 scripts/sync-skills-registry.py >/dev/null
python3 codex/scripts/sync-repo-bootstrap-registry.py >/dev/null

paths=(
  docs/references/registry/skills.base
  docs/references/registry/skills-items
  docs/references/registry/repo-bootstrap.base
  docs/references/registry/repo-bootstrap-items
  docs/references/registry/mcp-registry.base
  docs/references/registry/mcp-registry-items
)

if (( STAGED_OK == 1 )); then
  changes="$(
    {
      git diff --name-status -- "${paths[@]}"
      git ls-files --others --exclude-standard -- "${paths[@]}"
    } | sed '/^$/d'
  )"
else
  changes="$(git status --porcelain -- "${paths[@]}")"
fi
if [[ -n "$changes" ]]; then
  echo "FAIL: registry artifacts were out of sync."
  if (( STAGED_OK == 1 )); then
    echo "Regenerated files are present but not staged. Review and include them in your change:"
  else
    echo "Regenerated files are present. Review and include them in your change:"
  fi
  echo "$changes"
  exit 1
fi

echo "OK: registry artifacts are in sync."
