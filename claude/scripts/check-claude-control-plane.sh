#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$CONTROL_PLANE_DIR/.." && pwd)"

CANONICAL_DIR="${CONTROL_PLANE_DIR}/config"
GLOBAL_CLAUDE_MD="${HOME}/.claude/CLAUDE.md"
GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
GLOBAL_CONFIG="${HOME}/.claude.json"
GLOBAL_AGENTS_DIR="${HOME}/.claude/agents"
REPO_REGISTRY="${ROOT_DIR}/codex/config/repo-bootstrap.json"
BOOTSTRAP_FILE="${CANONICAL_DIR}/bootstrap.json"
MCP_REGISTRY="${ROOT_DIR}/mcp/config/presets.json"
SKILLS_REGISTRY="${ROOT_DIR}/skills/registry.json"
AGENT_REGISTRY="${ROOT_DIR}/agents/registry.json"
HOOKS_REGISTRY="${ROOT_DIR}/hooks/registry.json"
GLOBAL_AGENTS_MD=""
REPO_FILTERS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Validate canonical Claude control-plane inputs and the dry-run bootstrap path.

Options:
  --canonical-dir <path>    Override canonical claude/config directory
  --global-claude-md <path> Override runtime ~/.claude/CLAUDE.md path
  --global-settings <path>  Override runtime ~/.claude/settings.json path
  --global-config <path>    Override runtime ~/.claude.json path
  --global-agents-dir <p>   Override runtime ~/.claude/agents path
  --registry <path>         Override shared repo bootstrap registry path
  --bootstrap <path>        Override Claude bootstrap defaults/overrides path
  --mcp-registry <path>     Override shared MCP registry path
  --skills-registry <path>  Override shared skills registry path
  --agent-registry <path>   Override shared agent registry path
  --hooks-registry <path>   Override shared hooks registry path
  --global-agents <path>    Override shared global AGENTS guidance path
  --repo <path>             Limit repo-local validation to one repo path (repeatable)
  -h, --help                Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --canonical-dir)
      CANONICAL_DIR="${2:-}"
      BOOTSTRAP_FILE="${CANONICAL_DIR}/bootstrap.json"
      shift 2
      ;;
    --global-claude-md)
      GLOBAL_CLAUDE_MD="${2:-}"
      shift 2
      ;;
    --global-settings)
      GLOBAL_SETTINGS="${2:-}"
      shift 2
      ;;
    --global-config)
      GLOBAL_CONFIG="${2:-}"
      shift 2
      ;;
    --global-agents-dir)
      GLOBAL_AGENTS_DIR="${2:-}"
      shift 2
      ;;
    --registry)
      REPO_REGISTRY="${2:-}"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP_FILE="${2:-}"
      shift 2
      ;;
    --mcp-registry)
      MCP_REGISTRY="${2:-}"
      shift 2
      ;;
    --skills-registry)
      SKILLS_REGISTRY="${2:-}"
      shift 2
      ;;
    --agent-registry)
      AGENT_REGISTRY="${2:-}"
      shift 2
      ;;
    --hooks-registry)
      HOOKS_REGISTRY="${2:-}"
      shift 2
      ;;
    --global-agents)
      GLOBAL_AGENTS_MD="${2:-}"
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
      printf 'ERROR: Unknown option: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$GLOBAL_AGENTS_MD" ]]; then
  CANONICAL_ROOT="$(cd "${CANONICAL_DIR}/../.." && pwd)"
  GLOBAL_AGENTS_MD="${CANONICAL_ROOT}/codex/config/global.agents.md"
fi

cd "$ROOT_DIR"
python3 -m claude.control_plane.validate_inputs \
  --canonical-dir "$CANONICAL_DIR" \
  --registry "$REPO_REGISTRY" \
  --bootstrap "$BOOTSTRAP_FILE" \
  --mcp-registry "$MCP_REGISTRY" \
  --skills-registry "$SKILLS_REGISTRY" \
  --agent-registry "$AGENT_REGISTRY" \
  --hooks-registry "$HOOKS_REGISTRY" \
  --global-agents "$GLOBAL_AGENTS_MD"

REPO_ARGS=()
for repo in "${REPO_FILTERS[@]}"; do
  REPO_ARGS+=(--repo "$repo")
done

run_and_require_clean() {
  local label="$1"
  shift

  local output
  if ! output="$("$@" 2>&1)"; then
    printf '%s\n' "$output"
    exit 1
  fi

  printf '%s\n' "$output"

  if grep -Eq '^(SYNC |PRUNE |Would |Linked |Updated: |Removed file: |Removed managed symlink:|\+\+\+ |--- /dev/null|diff -u )' <<<"$output"; then
    printf 'ERROR: %s is out of sync. Re-run the corresponding apply step.\n' "$label" >&2
    exit 1
  fi
}

run_and_require_clean "global Claude guidance" \
  bash "${SCRIPT_DIR}/sync-global-claude-md.sh" --dry-run --global-claude-md "$GLOBAL_CLAUDE_MD" --canonical-claude "${CANONICAL_DIR}/global.claude.md"
run_and_require_clean "global Claude settings" \
  bash "${SCRIPT_DIR}/sync-settings.sh" --dry-run --global-settings "$GLOBAL_SETTINGS" --canonical-settings "${CANONICAL_DIR}/settings.json" --hooks-registry "$HOOKS_REGISTRY"
run_and_require_clean "global Claude MCP" \
  bash "${SCRIPT_DIR}/sync-global-mcp.sh" --dry-run --global-config "$GLOBAL_CONFIG" --mcp-registry "$MCP_REGISTRY"
run_and_require_clean "Claude subagent sync" \
  bash "${SCRIPT_DIR}/sync-subagents.sh" --dry-run --global-agents-dir "$GLOBAL_AGENTS_DIR" --registry "$REPO_REGISTRY" --agent-registry "$AGENT_REGISTRY" "${REPO_ARGS[@]}"
run_and_require_clean "Claude skills sync" \
  bash "${SCRIPT_DIR}/sync-skills.sh" --dry-run --registry "$SKILLS_REGISTRY" "${REPO_ARGS[@]}"
run_and_require_clean "repo Claude config sync" \
  bash "${SCRIPT_DIR}/sync-repo-claude-configs.sh" --dry-run --registry "$REPO_REGISTRY" --bootstrap "$BOOTSTRAP_FILE" --mcp-registry "$MCP_REGISTRY" "${REPO_ARGS[@]}"
python3 -m claude.control_plane.check_repo_git_state \
  --registry "$REPO_REGISTRY" \
  "${REPO_ARGS[@]}"

printf 'Claude control plane validation passed.\n'
