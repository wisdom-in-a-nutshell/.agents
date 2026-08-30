#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_HELPER="$ROOT_DIR/scripts/local-production-source.sh"
ACTION="dry-run"
OUTPUT="json"
RELEASE_ROOT="${AGENTS_CONTROL_PLANE_RELEASE_ROOT:-${HOME}/.local/share/agents-control-plane-dashboard}"
RELEASES_DIR="$RELEASE_ROOT/releases"
CURRENT_LINK="$RELEASE_ROOT/current"
PREVIOUS_LINK="$RELEASE_ROOT/previous"
HEALTH_URL="http://127.0.0.1:8765/api/control-plane"
LABEL="com.${USER}.agents-control-plane-dashboard"
LOG_DIR="${HOME}/.local/state/agents-control-plane/log"
OUT_LOG="${LOG_DIR}/control-plane-dashboard.out.log"
ERR_LOG="${LOG_DIR}/control-plane-dashboard.err.log"
LOG_LINES=80
BUILD_WORKTREE=""
TEMPORARY_RELEASE=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Build and activate the local agents control-plane dashboard from exact clean main.

Options:
  --apply              Run the full gate, build a release, activate, and smoke
  --dry-run            Validate the command surface without changing state (default)
  --status             Report the active release, launchd state, and health
  --health             Require local health and the active release revision
  --logs [n]           Return bounded, redacted service logs (default: 80 lines)
  --json               Emit one JSON object (default)
  --plain              Emit compact plain text
  --no-input           Assert non-interactive operation; prompts are never used
  -h, --help           Show help
USAGE
}

set_action() {
  local next="$1"
  if [[ "$ACTION" != "dry-run" && "$ACTION" != "$next" ]]; then
    emit_error "E_INVALID_USAGE" "choose exactly one action" "Run with --help." 2 false
  fi
  ACTION="$next"
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

release_name() {
  local link="$1" target
  target="$(readlink "$link" 2>/dev/null || true)"
  [[ -n "$target" ]] && basename "$target" || printf 'none\n'
}

emit_status() {
  local require_health="${1:-0}" launchd="unavailable" health="unavailable"
  local current previous release_sha state="unknown" pid="" last_exit=""
  current="$(release_name "$CURRENT_LINK")"
  previous="$(release_name "$PREVIOUS_LINK")"
  release_sha=""
  if [[ -f "$CURRENT_LINK/SOURCE_SHA" ]]; then
    release_sha="$(tr -d '\r\n' <"$CURRENT_LINK/SOURCE_SHA")"
  fi
  local launch_payload=""
  if launch_payload="$(launchctl print "gui/$(id -u)/${LABEL}" 2>/dev/null)"; then
    launchd="loaded"
    state="$(printf '%s\n' "$launch_payload" | awk -F' = ' '/^\tstate = / {print $2; exit}')"
    pid="$(printf '%s\n' "$launch_payload" | awk -F' = ' '/^\tpid = / {print $2; exit}')"
    last_exit="$(printf '%s\n' "$launch_payload" | awk -F' = ' '/^\tlast exit code = / {print $2; exit}')"
  fi
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then health="ok"; fi
  if (( require_health == 1 )) && { [[ "$health" != "ok" ]] || [[ -z "$release_sha" ]]; }; then
    emit_error "E_HEALTH_UNAVAILABLE" "dashboard health or active revision is unavailable" "Inspect --logs and retry after repair." 4 true
  fi
  if [[ "$OUTPUT" == "plain" ]]; then
    printf 'service=agents-control-plane-dashboard current=%s previous=%s release_sha=%s launchd=%s state=%s pid=%s last_exit=%s health=%s\n' \
      "$current" "$previous" "${release_sha:-none}" "$launchd" "${state:-unknown}" "${pid:-none}" "${last_exit:-none}" "$health"
  else
    python3 - "$ACTION" "$current" "$previous" "$release_sha" "$launchd" "$state" "$pid" "$last_exit" "$health" "$HEALTH_URL" <<'PY'
import datetime, json, sys
action,current,previous,sha,launchd,state,pid,last_exit,health,url=sys.argv[1:]
def optional(value): return None if value in {"", "none"} else value
print(json.dumps({"schema_version":"1.0","command":"deploy-control-plane-dashboard","status":"ok","data":{"action":action,"service":"agents-control-plane-dashboard","current_release":optional(current),"previous_release":optional(previous),"release_sha":optional(sha),"launchd":{"status":launchd,"state":state or "unknown","pid":optional(pid),"last_exit_code":optional(last_exit)},"health":{"status":health,"url":url}},"error":None,"meta":{"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}},sort_keys=True))
PY
  fi
  exit 0
}

emit_logs() {
  python3 - "$OUTPUT" "$LOG_LINES" "$OUT_LOG" "$ERR_LOG" <<'PY'
import datetime, json, re, sys
from pathlib import Path
output,count_raw,*raw_paths=sys.argv[1:]
count=int(count_raw)
def redact(line):
    line=re.sub(r"(?i)(authorization:\s*bearer\s+)[^\s]+",r"\1<redacted>",line)
    line=re.sub(r"(?i)([?&](?:token|key|secret|signature|sig)=[^&\s]+)","<redacted-query>",line)
    return re.sub(r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD)[A-Z0-9_]*)=\S+",r"\1=<redacted>",line)
streams=[]; plain=[]
for raw in raw_paths:
    path=Path(raw)
    lines=path.read_text(encoding="utf-8",errors="replace").splitlines()[-count:] if path.is_file() else ["<missing>"]
    lines=[redact(line) for line in lines]
    streams.append({"path":str(path),"lines":lines}); plain.extend([f"[{path}]",*lines])
if output=="plain": print("\n".join(plain))
else: print(json.dumps({"schema_version":"1.0","command":"deploy-control-plane-dashboard","status":"ok","data":{"action":"logs","line_count":count,"streams":streams},"error":None,"meta":{"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}},sort_keys=True))
PY
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

prune_releases() {
  local current previous release canonical removed=0 failures=0
  current="$(readlink "$CURRENT_LINK" 2>/dev/null || true)"
  previous="$(readlink "$PREVIOUS_LINK" 2>/dev/null || true)"
  [[ -n "$current" && -d "$current" ]] || emit_error \
    "E_RELEASE_STATE" "current release is unavailable; pruning refused" \
    "Repair current before the next deployment." 4 false
  current="$(cd "$current" && pwd -P)"
  if [[ -n "$previous" && -d "$previous" ]]; then previous="$(cd "$previous" && pwd -P)"; fi
  for release in "$RELEASES_DIR"/*; do
    [[ -d "$release" && ! -L "$release" ]] || continue
    canonical="$(cd "$release" && pwd -P)"
    [[ "$canonical" == "$current" || "$canonical" == "$previous" ]] && continue
    if rm -rf -- "$release"; then removed=$((removed + 1)); else failures=$((failures + 1)); fi
  done
  printf '[deploy-control-plane-dashboard] release retention removed=%s failures=%s\n' "$removed" "$failures" >&2
  (( failures == 0 ))
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
    --apply) set_action apply; shift ;;
    --dry-run) ACTION="dry-run"; shift ;;
    --status) set_action status; shift ;;
    --health) set_action health; shift ;;
    --logs)
      set_action logs
      if [[ -n "${2:-}" && "${2:-}" != --* ]]; then LOG_LINES="$2"; shift 2; else shift; fi
      ;;
    --json) OUTPUT="json"; shift ;;
    --plain) OUTPUT="plain"; shift ;;
    --no-input) shift ;;
    -h|--help) usage; exit 0 ;;
    *) emit_error "E_INVALID_USAGE" "unknown option: $1" "Run with --help." 2 false ;;
  esac
done

[[ "$LOG_LINES" =~ ^[0-9]+$ ]] || emit_error "E_INVALID_USAGE" "invalid log line count: $LOG_LINES" "Use a non-negative integer." 2 false
if [[ "$ACTION" == "status" ]]; then emit_status 0; fi
if [[ "$ACTION" == "health" ]]; then emit_status 1; fi
if [[ "$ACTION" == "logs" ]]; then emit_logs; fi

[[ -f "$SOURCE_HELPER" ]] || emit_error \
  "E_DEPENDENCY_MISSING" "source guard is unavailable" "Restore scripts/local-production-source.sh." 4 false
# shellcheck disable=SC1090
. "$SOURCE_HELPER"

if [[ "$ACTION" == "dry-run" ]]; then
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

prune_releases || printf '[deploy-control-plane-dashboard] warning: release retention incomplete\n' >&2

emit_ok "deployed and smoked agents control-plane dashboard" "$EXPECTED_SHA"
