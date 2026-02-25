#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

# Regenerate derived views in dry mode for links, then verify no tracked
# registry artifacts changed. If they did, the repo was out of sync.
python3 scripts/sync-skills-registry.py >/dev/null

changes="$(git status --porcelain -- skills/registry.md skills/registry.base skills/registry-items)"
if [[ -n "$changes" ]]; then
  echo "FAIL: skills registry artifacts were out of sync."
  echo "Regenerated files are present. Review and include them in your change:"
  echo "$changes"
  exit 1
fi

echo "OK: skills registry artifacts are in sync."
