#!/usr/bin/env bash
set -euo pipefail

ACTIVE_ENV="${CLAUDE_SECRET_ENV:-$HOME/.secrets/anthropic/env}"
SUBSCRIPTION_ENV="${CLAUDE_SUBSCRIPTION_SECRET_ENV:-$HOME/.secrets/anthropic/env.subscription}"
AWS_ENV="${CLAUDE_AWS_SECRET_ENV:-$HOME/.secrets/anthropic/env.aws}"
REAL_CLI="${CLAUDE_REAL_BIN:-/opt/homebrew/bin/claude}"

APPLY=0
RUN_AUTH_STATUS=1
RUN_LOGIN=0
MODE="status"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [status|subscription|aws] [options]

Switch Claude Code between direct Claude subscription OAuth and the AWS-backed
Anthropic endpoint while preserving both local credential profiles.

Default mode is status/dry-run. Use --apply to write changes.

Options:
  --apply                  Apply the provider switch
  --dry-run                Print planned changes only
  --login                  After switching to subscription, run Claude OAuth login
  --no-auth-status         Do not call "claude auth status"
  --active-env <path>      Override active env link/file path
  --subscription-env <p>   Override subscription profile env path
  --aws-env <path>         Override AWS profile env path
  --real-cli <path>        Override real Claude Code executable
  -h, --help               Show this help

Examples:
  ~/.agents/scripts/switch-claude-provider.sh status
  ~/.agents/scripts/switch-claude-provider.sh subscription --apply
  ~/.agents/scripts/switch-claude-provider.sh subscription --apply --login
  ~/.agents/scripts/switch-claude-provider.sh aws --apply
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
    status|subscription|claude|claudeai|claude-ai|aws)
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
    --aws-env)
      AWS_ENV="${2:-}"
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
[[ -n "$AWS_ENV" ]] || die "--aws-env cannot be empty"

subscription_env_text() {
  cat <<'EOF'
# Claude Code direct Claude subscription mode.
# Auth is stored by Claude Code in macOS Keychain after `claude auth login --claudeai`.

unset CLAUDE_CODE_USE_ANTHROPIC_AWS
unset ANTHROPIC_AWS_BASE_URL
unset ANTHROPIC_AWS_WORKSPACE_ID
unset ANTHROPIC_AWS_API_KEY
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_WORKSPACE_ID
unset ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN
unset CLAUDE_CODE_OAUTH_TOKEN
EOF
}

write_subscription_env() {
  log "WRITE ${SUBSCRIPTION_ENV} (direct Claude subscription profile)"
  if [[ "$APPLY" -ne 1 ]]; then
    return
  fi
  mkdir -p "$(dirname "$SUBSCRIPTION_ENV")"
  local tmp="${SUBSCRIPTION_ENV}.tmp.$$"
  subscription_env_text >"$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$SUBSCRIPTION_ENV"
}

preserve_existing_aws_env() {
  if [[ -e "$AWS_ENV" ]]; then
    return
  fi
  if [[ -L "$ACTIVE_ENV" ]]; then
    return
  fi
  if [[ ! -f "$ACTIVE_ENV" ]]; then
    return
  fi
  if ! grep -Eq 'CLAUDE_CODE_USE_ANTHROPIC_AWS|ANTHROPIC_AWS_' "$ACTIVE_ENV"; then
    return
  fi
  log "COPY ${ACTIVE_ENV} -> ${AWS_ENV} (preserve current AWS profile)"
  if [[ "$APPLY" -ne 1 ]]; then
    return
  fi
  mkdir -p "$(dirname "$AWS_ENV")"
  cp -p "$ACTIVE_ENV" "$AWS_ENV"
  chmod 600 "$AWS_ENV"
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
  local resolved=""
  if [[ -L "$ACTIVE_ENV" ]]; then
    resolved="$(readlink "$ACTIVE_ENV")"
    case "$resolved" in
      "$SUBSCRIPTION_ENV"|*"/$(basename "$SUBSCRIPTION_ENV")")
        printf 'subscription'
        return
        ;;
      "$AWS_ENV"|*"/$(basename "$AWS_ENV")")
        printf 'aws'
        return
        ;;
    esac
  fi
  if [[ -f "$ACTIVE_ENV" ]] && grep -Eq 'CLAUDE_CODE_USE_ANTHROPIC_AWS|ANTHROPIC_AWS_' "$ACTIVE_ENV"; then
    printf 'aws-file'
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
  log "aws_env:          $([[ -e "$AWS_ENV" ]] && printf present || printf missing)"
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
    preserve_existing_aws_env
    write_subscription_env
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
  aws)
    preserve_existing_aws_env
    [[ -e "$AWS_ENV" ]] || die "Missing AWS profile env: $AWS_ENV"
    write_subscription_env
    activate_env "$AWS_ENV"
    print_status
    ;;
  *)
    die "Unknown mode: $MODE"
    ;;
esac
