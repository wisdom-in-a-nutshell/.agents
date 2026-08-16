#!/usr/bin/env bash
set -euo pipefail

ACTIVE_ENV="${CLAUDE_SECRET_ENV:-$HOME/.secrets/anthropic/env}"
SUBSCRIPTION_ENV="${CLAUDE_SUBSCRIPTION_SECRET_ENV:-$HOME/.secrets/anthropic/env.subscription}"
BEDROCK_ENV="${CLAUDE_BEDROCK_SECRET_ENV:-$HOME/.secrets/anthropic/env.bedrock}"
REAL_CLI="${CLAUDE_REAL_BIN:-/opt/homebrew/bin/claude}"

APPLY=0
RUN_AUTH_STATUS=1
RUN_LOGIN=0
MODE="status"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [status|subscription|bedrock] [options]

Switch Claude Code between direct Claude subscription OAuth and Amazon Bedrock.
The Bedrock profile uses the default AWS credential chain and never routes through
an AWS Marketplace-backed Anthropic service.

Default mode is status/dry-run. Use --apply to write changes.

Options:
  --apply                  Apply the provider switch
  --dry-run                Print planned changes only
  --login                  After switching to subscription, run Claude OAuth login
  --no-auth-status         Do not call "claude auth status"
  --active-env <path>      Override active env link/file path
  --subscription-env <p>   Override subscription profile env path
  --bedrock-env <path>     Override Bedrock profile env path
  --real-cli <path>        Override real Claude Code executable
  -h, --help               Show this help

Examples:
  ~/GitHub/agents/scripts/switch-claude-provider.sh status
  ~/GitHub/agents/scripts/switch-claude-provider.sh subscription --apply
  ~/GitHub/agents/scripts/switch-claude-provider.sh subscription --apply --login
  ~/GitHub/agents/scripts/switch-claude-provider.sh bedrock --apply
USAGE
}

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    status|subscription|claude|claudeai|claude-ai|bedrock)
      [[ -z "${MODE_SET:-}" ]] || die "Mode already set to $MODE"
      MODE_SET=1
      MODE="$1"
      shift
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --login)
      RUN_LOGIN=1
      shift
      ;;
    --no-auth-status)
      RUN_AUTH_STATUS=0
      shift
      ;;
    --active-env)
      ACTIVE_ENV="${2:-}"
      shift 2
      ;;
    --subscription-env)
      SUBSCRIPTION_ENV="${2:-}"
      shift 2
      ;;
    --bedrock-env)
      BEDROCK_ENV="${2:-}"
      shift 2
      ;;
    --real-cli)
      REAL_CLI="${2:-}"
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

case "$MODE" in
  claude|claudeai|claude-ai)
    MODE="subscription"
    ;;
esac

[[ -n "$ACTIVE_ENV" ]] || die "--active-env cannot be empty"
[[ -n "$SUBSCRIPTION_ENV" ]] || die "--subscription-env cannot be empty"
[[ -n "$BEDROCK_ENV" ]] || die "--bedrock-env cannot be empty"

subscription_env_text() {
  cat <<'EOF'
# Claude Code direct Claude subscription mode.
# Auth is stored by Claude Code in macOS Keychain after `claude auth login --claudeai`.

unset CLAUDE_CODE_USE_BEDROCK
unset CLAUDE_CODE_USE_MANTLE
unset AWS_BEARER_TOKEN_BEDROCK
unset ANTHROPIC_BEDROCK_BASE_URL
unset ANTHROPIC_BEDROCK_MANTLE_BASE_URL
unset ANTHROPIC_BEDROCK_REGION_PREFIX
unset ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL
unset ANTHROPIC_DEFAULT_HAIKU_MODEL
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_WORKSPACE_ID
unset ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN
EOF
}

bedrock_env_text() {
  cat <<'EOF'
# Claude Code Amazon Bedrock mode.
# Authentication comes from the default AWS credential chain.

export CLAUDE_CODE_USE_BEDROCK=1
export CLAUDE_CODE_USE_MANTLE=1
export AWS_REGION=us-east-1
export AWS_PROFILE=default
export ANTHROPIC_BEDROCK_REGION_PREFIX=global
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_WORKSPACE_ID
unset ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN
EOF
}

write_profile() {
  local path="$1"
  local label="$2"
  local renderer="$3"
  log "WRITE ${path} (${label})"
  if [[ "$APPLY" -ne 1 ]]; then
    return
  fi
  mkdir -p "$(dirname "$path")"
  local tmp="${path}.tmp.$$"
  "$renderer" >"$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$path"
}

write_profiles() {
  write_profile "$SUBSCRIPTION_ENV" "direct Claude subscription profile" subscription_env_text
  write_profile "$BEDROCK_ENV" "Amazon Bedrock profile" bedrock_env_text
}

activate_env() {
  local target="$1"
  [[ -e "$target" ]] || die "Missing profile env: $target"
  log "LINK ${ACTIVE_ENV} -> ${target}"
  if [[ "$APPLY" -ne 1 ]]; then
    return
  fi
  mkdir -p "$(dirname "$ACTIVE_ENV")"
  local tmp="${ACTIVE_ENV}.tmp.$$"
  rm -f "$tmp"
  ln -s "$target" "$tmp"
  mv -f "$tmp" "$ACTIVE_ENV"
}

profile_for_active_env() {
  if [[ ! -e "$ACTIVE_ENV" && ! -L "$ACTIVE_ENV" ]]; then
    printf 'missing'
    return
  fi
  if [[ -L "$ACTIVE_ENV" ]]; then
    local resolved
    resolved="$(readlink "$ACTIVE_ENV")"
    case "$resolved" in
      "$SUBSCRIPTION_ENV"|*"/$(basename "$SUBSCRIPTION_ENV")")
        printf 'subscription'
        return
        ;;
      "$BEDROCK_ENV"|*"/$(basename "$BEDROCK_ENV")")
        printf 'bedrock'
        return
        ;;
    esac
  fi
  if [[ -f "$ACTIVE_ENV" ]] && grep -Eq 'CLAUDE_CODE_USE_BEDROCK|CLAUDE_CODE_USE_MANTLE' "$ACTIVE_ENV"; then
    printf 'bedrock-file'
  elif [[ -f "$ACTIVE_ENV" ]] && grep -q 'unset ANTHROPIC_API_KEY' "$ACTIVE_ENV"; then
    printf 'subscription-file'
  else
    printf 'custom'
  fi
}

print_status() {
  local profile
  profile="$(profile_for_active_env)"
  log "active_env:       ${ACTIVE_ENV}"
  if [[ -L "$ACTIVE_ENV" ]]; then
    log "active_target:    $(readlink "$ACTIVE_ENV")"
  elif [[ -e "$ACTIVE_ENV" ]]; then
    log "active_target:    regular file"
  else
    log "active_target:    missing"
  fi
  log "active_profile:   ${profile}"
  log "subscription_env: $([[ -e "$SUBSCRIPTION_ENV" ]] && printf present || printf missing)"
  log "bedrock_env:      $([[ -e "$BEDROCK_ENV" ]] && printf present || printf missing)"
  if [[ "$RUN_AUTH_STATUS" -eq 1 ]]; then
    if [[ ! -x "$REAL_CLI" ]]; then
      log "claude_auth:      skipped, missing executable: ${REAL_CLI}"
      return
    fi
    log "claude_auth:"
    set +e
    (
      set -a
      if [[ -f "$ACTIVE_ENV" ]]; then
        # shellcheck disable=SC1090
        source "$ACTIVE_ENV"
      fi
      set +a
      "$REAL_CLI" auth status
    ) | sed 's/^/  /'
    local auth_status="${PIPESTATUS[0]}"
    set -e
    if [[ "$auth_status" -ne 0 ]]; then
      log "claude_auth_exit: ${auth_status}"
    fi
  fi
}

case "$MODE" in
  status)
    print_status
    ;;
  subscription)
    write_profiles
    activate_env "$SUBSCRIPTION_ENV"
    if [[ "$RUN_LOGIN" -eq 1 ]]; then
      [[ "$APPLY" -eq 1 ]] || die "--login requires --apply"
      [[ -x "$REAL_CLI" ]] || die "Missing executable: $REAL_CLI"
      (
        set -a
        # shellcheck disable=SC1090
        source "$ACTIVE_ENV"
        set +a
        "$REAL_CLI" auth login --claudeai
      )
    fi
    print_status
    ;;
  bedrock)
    write_profiles
    activate_env "$BEDROCK_ENV"
    print_status
    ;;
  *)
    die "Unknown mode: $MODE"
    ;;
esac
