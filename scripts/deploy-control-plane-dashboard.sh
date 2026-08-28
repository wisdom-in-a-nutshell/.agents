#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_HELPER="$ROOT_DIR/scripts/local-production-source.sh"
APPLY=0
OUTPUT="json"
RELEASE_ROOT="${AGENTS_CONTROL_PLANE_RELEASE_ROOT:-${HOME}/.local/share/agents-control-plane-dashboard}"
RELEASES_DIR="$RELEASE_ROOT/releases"
CURRENT_LINK="$RELEASE_ROOT/current"
PREVIOUS_LINK="$RELEASE_ROOT/previous"
HEALTH_URL="http://127.0.0.1:8765/api/control-plane"
BUILD_WORKTREE=""
TEMPORARY_RELEASE=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Build and activate the local agents control-plane dashboard from exact clean main.

Options:
  --apply              Run the full gate, build a release, activate, and smoke
  --dry-run            Validate the command surface without changing state (default)
  --json               Emit one JSON object (default)
  --plain              Emit compact plain text
  --no-input           Assert non-interactive operation; prompts are never used
  -h, --help           Show help
USAGE
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

emit_ok() {
  local message="$1"
  local revision="${2:-}"
  if [[ "$OUTPUT" == "plain" ]]; then
    printf 'ok revision=%s message=%s\n' "${revision:-none}" "$message"
  else
    printf '{"schema_version":"1.0","command":"deploy-control-plane-dashboard","status":"ok","data":{"message":%s,"revision":%s},"error":null,"meta":{}}\n' \
      "$(printf '%s' "$message" | json_escape)" \
      "$(printf '%s' "$revision" | json_escape)"
  fi
  exit 0
}

emit_error() {
  local code="$1"
  local message="$2"
  local hint="$3"
  local exit_code="$4"
  local retryable="${5:-false}"
  if [[ "$OUTPUT" == "plain" ]]; then
    printf 'error code=%s retryable=%s message=%s hint=%s\n' "$code" "$retryable" "$message" "$hint"
  else
    printf '{"schema_version":"1.0","command":"deploy-control-plane-dashboard","status":"error","data":{},"error":{"code":%s,"message":%s,"retryable":%s,"hint":%s},"meta":{}}\n' \
      "$(printf '%s' "$code" | json_escape)" \
      "$(printf '%s' "$message" | json_escape)" \
      "$retryable" \
      "$(printf '%s' "$hint" | json_escape)"
  fi
  exit "$exit_code"
}

replace_link() {
  local target="$1"
  local link="$2"
  local temporary="${link}.next.$$"
  rm -f "$temporary"
  ln -s "$target" "$temporary"
  mv -h -f "$temporary" "$link"
}

cleanup() {
  if [[ -n "${BUILD_WORKTREE:-}" && -d "$BUILD_WORKTREE" ]]; then
    git -C "$ROOT_DIR" worktree remove --force "$BUILD_WORKTREE" >/dev/null 2>&1 || true
  fi
  if [[ -n "${TEMPORARY_RELEASE:-}" && -d "$TEMPORARY_RELEASE" ]]; then
    rm -rf "$TEMPORARY_RELEASE"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --json) OUTPUT="json"; shift ;;
    --plain) OUTPUT="plain"; shift ;;
    --no-input) shift ;;
    -h|--help) usage; exit 0 ;;
    *) emit_error "E_INVALID_USAGE" "unknown option: $1" "Run with --help." 2 false ;;
  esac
done

[[ -f "$SOURCE_HELPER" ]] || emit_error \
  "E_DEPENDENCY_MISSING" "source guard is unavailable" "Restore scripts/local-production-source.sh." 4 false
# shellcheck disable=SC1090
. "$SOURCE_HELPER"

if (( APPLY == 0 )); then
  emit_ok "dry run; would gate exact clean main, build a versioned release, activate, and smoke"
fi

if ! capture_local_production_source "$ROOT_DIR" main; then
  emit_error \
    "E_PRODUCTION_SOURCE" \
    "production requires one exact clean main revision" \
    "Finish or move intermediate work, then retry from clean main." \
    2 \
    false
fi
EXPECTED_BRANCH="$LOCAL_PRODUCTION_SOURCE_BRANCH"
EXPECTED_SHA="$LOCAL_PRODUCTION_SOURCE_SHA"
SHORT_SHA="${EXPECTED_SHA:0:12}"
RELEASE_DIR="$RELEASES_DIR/$SHORT_SHA"

mkdir -p "$ROOT_DIR/tmp" "$RELEASES_DIR"
BUILD_WORKTREE="$(mktemp -d "$ROOT_DIR/tmp/agents-production-build.XXXXXX")"
rmdir "$BUILD_WORKTREE"
git -C "$ROOT_DIR" worktree add --quiet --detach "$BUILD_WORKTREE" "$EXPECTED_SHA"

printf '[deploy-control-plane-dashboard] full release gate revision=%s\n' "$EXPECTED_SHA" >&2
(
  cd "$BUILD_WORKTREE"
  AGENTS_MANAGED_REPO_CHECK_ROOT="$ROOT_DIR" bash scripts/check-full.sh
) >&2

printf '[deploy-control-plane-dashboard] building dashboard candidate\n' >&2
(
  cd "$BUILD_WORKTREE/dashboard-app"
  npm ci
  npm run build
) >&2

if ! verify_local_production_source "$ROOT_DIR" "$EXPECTED_BRANCH" "$EXPECTED_SHA"; then
  emit_error \
    "E_SOURCE_CHANGED" \
    "source changed during validation or build; activation was refused" \
    "Retry after the newest main revision is stable." \
    4 \
    true
fi

if [[ -e "$RELEASE_DIR" ]]; then
  RELEASE_DIR="${RELEASE_DIR}-$(date -u +%Y%m%dT%H%M%SZ)"
fi
TEMPORARY_RELEASE="$(mktemp -d "$RELEASES_DIR/.${SHORT_SHA}.XXXXXX")"
mkdir -p "$TEMPORARY_RELEASE/dashboard" "$TEMPORARY_RELEASE/runtime/scripts"
cp -R "$BUILD_WORKTREE/dashboard-app/dist/." "$TEMPORARY_RELEASE/dashboard/"
cp "$BUILD_WORKTREE/scripts/control-plane-dashboard.py" "$TEMPORARY_RELEASE/runtime/scripts/"
cp -R "$BUILD_WORKTREE/mcp" "$TEMPORARY_RELEASE/runtime/mcp"
printf '%s\n' "$EXPECTED_SHA" >"$TEMPORARY_RELEASE/SOURCE_SHA"

git -C "$ROOT_DIR" worktree remove --force "$BUILD_WORKTREE"
BUILD_WORKTREE=""
if ! verify_local_production_source "$ROOT_DIR" "$EXPECTED_BRANCH" "$EXPECTED_SHA"; then
  emit_error \
    "E_SOURCE_CHANGED" \
    "source changed before activation; candidate was discarded" \
    "Retry after the newest main revision is stable." \
    4 \
    true
fi

mv "$TEMPORARY_RELEASE" "$RELEASE_DIR"
TEMPORARY_RELEASE=""
OLD_CURRENT="$(readlink "$CURRENT_LINK" 2>/dev/null || true)"
OLD_PREVIOUS="$(readlink "$PREVIOUS_LINK" 2>/dev/null || true)"
if [[ -n "$OLD_CURRENT" && -d "$OLD_CURRENT" ]]; then
  replace_link "$OLD_CURRENT" "$PREVIOUS_LINK"
fi
replace_link "$RELEASE_DIR" "$CURRENT_LINK"

activate() {
  local release_sha="$1"
  "$ROOT_DIR/scripts/install-control-plane-dashboard-launchagent.sh" \
    --apply \
    --root "$ROOT_DIR" \
    --dashboard-root "$CURRENT_LINK/dashboard" \
    --server-script "$CURRENT_LINK/runtime/scripts/control-plane-dashboard.py" \
    --release-sha "$release_sha" >&2
}

wait_for_release_health() {
  local expected_sha="$1" payload
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    payload="$(curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null || true)"
    if python3 - "$expected_sha" "$payload" <<'PY' >/dev/null 2>&1
import json
import sys

expected, raw = sys.argv[1:]
payload = json.loads(raw)
raise SystemExit(0 if payload.get("release_sha") == expected else 1)
PY
    then
      return 0
    fi
    sleep 1
  done
  return 1
}

printf '[deploy-control-plane-dashboard] activating release=%s\n' "$RELEASE_DIR" >&2
if ! activate "$EXPECTED_SHA" || ! wait_for_release_health "$EXPECTED_SHA"; then
  if [[ -n "$OLD_CURRENT" && -d "$OLD_CURRENT" ]]; then
    replace_link "$OLD_CURRENT" "$CURRENT_LINK"
    if [[ -n "$OLD_PREVIOUS" && -d "$OLD_PREVIOUS" ]]; then
      replace_link "$OLD_PREVIOUS" "$PREVIOUS_LINK"
    fi
    activate "$(basename "$OLD_CURRENT" | cut -d- -f1)" || true
  else
    launchctl bootout "gui/$(id -u)/com.${USER}.agents-control-plane-dashboard" >/dev/null 2>&1 || true
  fi
  emit_error \
    "E_ACTIVATION_FAILED" \
    "candidate failed activation or health; previous release was restored when available" \
    "Inspect the dashboard LaunchAgent logs and retry after repair." \
    5 \
    true
fi

emit_ok "deployed and smoked agents control-plane dashboard" "$EXPECTED_SHA"
