#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

# Regenerate derived registry views, then verify no tracked artifacts changed.
# If they did, the repo was out of sync.
python3 scripts/sync-skills-registry.py >/dev/null
python3 codex/scripts/sync-repo-bootstrap-registry.py >/dev/null

changes="$(git status --porcelain -- \
  docs/references/registry/skills.base \
  docs/references/registry/skills-items \
  docs/references/registry/repo-bootstrap.base \
  docs/references/registry/repo-bootstrap-items \
  docs/references/registry/mcp-registry.base \
  docs/references/registry/mcp-registry-items)"
if [[ -n "$changes" ]]; then
  echo "FAIL: registry artifacts were out of sync."
  echo "Regenerated files are present. Review and include them in your change:"
  echo "$changes"
  exit 1
fi

echo "OK: registry artifacts are in sync."
