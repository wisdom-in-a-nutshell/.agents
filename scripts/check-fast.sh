#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

scripts/check-repo-hygiene.sh
bash -n hooks/git/pre-commit scripts/sync-managed-git-hooks.sh scripts/sync-copilot-hooks.sh scripts/check-agent-control-planes.sh
scripts/sync-managed-git-hooks.sh --check --repo "$PWD"
scripts/sync-copilot-hooks.sh --check --repo "$PWD"

echo "[check-fast] passed"
