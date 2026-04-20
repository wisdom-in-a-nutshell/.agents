#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHECK_SKILLS_SCRIPT="${SCRIPT_DIR}/check-skills-registry.sh"
CHECK_PLUGINS_SCRIPT="${SCRIPT_DIR}/check-plugins-registry.sh"
CHECK_HYGIENE_SCRIPT="${SCRIPT_DIR}/check-repo-hygiene.sh"
CHECK_CODEX_SCRIPT="${ROOT_DIR}/codex/scripts/check-codex-control-plane.sh"
CHECK_CLAUDE_SCRIPT="${ROOT_DIR}/claude/scripts/check-claude-control-plane.sh"
TEST_CONTROL_PLANE_SCRIPT="${SCRIPT_DIR}/test-control-plane.sh"
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate repo hygiene, shared registries, Codex and Claude rendered state, and tests.

Options:
  --repo <path>    Limit Codex and Claude validation to an exact repo path (repeatable)
  -h, --help       Show this help

Examples:
  ~/.agents/scripts/check-agent-control-planes.sh
  ~/.agents/scripts/check-agent-control-planes.sh --repo ~/.agents
USAGE
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

log() {
  printf '%s\n' "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

[[ -x "$CHECK_SKILLS_SCRIPT" ]] || die "Missing executable: $CHECK_SKILLS_SCRIPT"
[[ -x "$CHECK_PLUGINS_SCRIPT" ]] || die "Missing executable: $CHECK_PLUGINS_SCRIPT"
[[ -x "$CHECK_HYGIENE_SCRIPT" ]] || die "Missing executable: $CHECK_HYGIENE_SCRIPT"
[[ -x "$CHECK_CODEX_SCRIPT" ]] || die "Missing executable: $CHECK_CODEX_SCRIPT"
[[ -x "$CHECK_CLAUDE_SCRIPT" ]] || die "Missing executable: $CHECK_CLAUDE_SCRIPT"
[[ -x "$TEST_CONTROL_PLANE_SCRIPT" ]] || die "Missing executable: $TEST_CONTROL_PLANE_SCRIPT"

REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

hygiene_cmd=("$CHECK_HYGIENE_SCRIPT")
log "+ ${hygiene_cmd[*]}"
"${hygiene_cmd[@]}"

skills_cmd=("$CHECK_SKILLS_SCRIPT")
log "+ ${skills_cmd[*]}"
"${skills_cmd[@]}"

plugins_cmd=("$CHECK_PLUGINS_SCRIPT")
log "+ ${plugins_cmd[*]}"
"${plugins_cmd[@]}"

codex_cmd=(
  "$CHECK_CODEX_SCRIPT"
  "${REPO_ARGS[@]}"
)
log "+ ${codex_cmd[*]}"
"${codex_cmd[@]}"

claude_cmd=(
  "$CHECK_CLAUDE_SCRIPT"
  "${REPO_ARGS[@]}"
)
log "+ ${claude_cmd[*]}"
"${claude_cmd[@]}"

test_cmd=("$TEST_CONTROL_PLANE_SCRIPT")
log "+ ${test_cmd[*]}"
"${test_cmd[@]}"
