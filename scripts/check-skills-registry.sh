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

python3 scripts/sync-skills-registry.py >/dev/null
python3 codex/scripts/sync-repo-bootstrap-registry.py >/dev/null
echo "OK: skill registry and repo bootstrap registries are valid."
