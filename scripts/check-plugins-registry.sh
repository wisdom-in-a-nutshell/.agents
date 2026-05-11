#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

# Regenerate derived registry views, then verify no tracked artifacts changed.
# If they did, the repo was out of sync.
python3 scripts/sync-plugins-registry.py >/dev/null

changes="$(git status --porcelain -- \
  docs/references/registry/plugins.base \
  docs/references/registry/plugins-items)"
if [[ -n "$changes" ]]; then
  echo "FAIL: plugin registry artifacts were out of sync."
  echo "Regenerated files are present. Review and include them in your change:"
  echo "$changes"
  exit 1
fi

echo "OK: plugin registry artifacts are in sync."
