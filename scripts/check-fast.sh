#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

scripts/check-repo-hygiene.sh
bash -n hooks/git/pre-commit scripts/sync-managed-git-hooks.sh scripts/check-agent-control-planes.sh scripts/enroll-managed-repos.sh scripts/serve-control-plane-dashboard.sh scripts/install-control-plane-dashboard-launchagent.sh scripts/switch-claude-provider.sh codex/scripts/switch-codex-subscription.sh
scripts/check-skills-registry.sh --staged-ok
scripts/check-plugins-registry.sh --staged-ok
scripts/sync-managed-git-hooks.sh --check --repo "$PWD"
codex/scripts/check-codex-control-plane.sh --repo "$PWD"

echo "[check-fast] passed"
