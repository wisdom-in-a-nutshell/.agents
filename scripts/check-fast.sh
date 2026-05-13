#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

scripts/check-repo-hygiene.sh
bash -n hooks/git/pre-commit scripts/sync-managed-git-hooks.sh scripts/sync-copilot-hooks.sh scripts/check-agent-control-planes.sh scripts/enroll-managed-repos.sh
scripts/sync-managed-git-hooks.sh --check --repo "$PWD"
scripts/sync-copilot-hooks.sh --check --repo "$PWD"
codex/scripts/check-codex-control-plane.sh --repo "$PWD"
python3 -m claude.control_plane.check_repo_git_state --registry codex/config/repo-bootstrap.json --repo "$PWD"

echo "[check-fast] passed"
