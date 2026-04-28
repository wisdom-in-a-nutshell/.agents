#!/usr/bin/env bash
# Opt-in live round-trip tests for things-client.
#
# These tests create real Things 3 tasks with a unique prefix, then cancel them.
# Run only when intentionally validating local Things write integration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THINGS="$ROOT/scripts/things-client"
PREFIX="THINGS-CLIENT-TEST-$(date +%s)"
CREATED_NAMES=()

cleanup() {
    for name in "${CREATED_NAMES[@]}"; do
        "$THINGS" cancel "$name" --no-input >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT

assert_json() {
    local name="$1"
    local json="$2"
    local script="$3"
    python3 - "$name" "$json" "$script" <<'PY'
import json
import sys

name, raw, script = sys.argv[1:4]
payload = json.loads(raw)
ns = {"payload": payload}
try:
    ok = bool(eval(script, {}, ns))
except Exception as exc:
    raise AssertionError(f"{name}: expression failed: {exc}\n{payload}") from exc
if not ok:
    raise AssertionError(f"{name}: assertion failed: {script}\n{payload}")
PY
    printf '  ok - %s\n' "$name"
}

command_json() {
    "$THINGS" "$@" --no-input
}

doctor="$(command_json doctor)"
assert_json "doctor ok" "$doctor" 'payload["status"] == "ok" and payload["data"]["ok"] is True'
assert_json "write token configured" "$doctor" 'any(c["name"] == "auth_token_configured" and c["ok"] for c in payload["data"]["checks"])'
assert_json "things running" "$doctor" 'any(c["name"] == "things3_running" and c["ok"] for c in payload["data"]["checks"])'

alpha="$PREFIX alpha"
beta="$PREFIX beta"
later="$PREFIX natural language"

printf '\nadd tasks\n'
out="$(command_json add "$alpha" --when today)"
assert_json "add alpha" "$out" 'payload["status"] == "ok" and payload["data"]["title"].endswith(" alpha")'
CREATED_NAMES+=("$alpha")
sleep 1

out="$(command_json add "$beta" --when today --notes "test notes")"
assert_json "add beta" "$out" 'payload["status"] == "ok" and payload["data"]["title"].endswith(" beta")'
CREATED_NAMES+=("$beta")
sleep 1

out="$(command_json add "$later" --when tomorrow)"
assert_json "add natural language" "$out" 'payload["status"] == "ok" and payload["data"]["title"].endswith(" natural language")'
CREATED_NAMES+=("$later")
sleep 1

printf '\nread back\n'
out="$(command_json search "$PREFIX")"
assert_json "search finds created tasks" "$out" 'payload["status"] == "ok" and payload["data"]["count"] >= 3'

out="$(command_json today)"
assert_json "today includes alpha" "$out" 'any(t["name"].endswith(" alpha") for t in payload["data"]["tasks"])'
assert_json "today includes beta" "$out" 'any(t["name"].endswith(" beta") for t in payload["data"]["tasks"])'

printf '\ncancel and cleanup\n'
out="$(command_json cancel "$beta")"
assert_json "cancel beta" "$out" 'payload["status"] == "ok" and payload["data"]["name"].endswith(" beta")'
CREATED_NAMES=("$alpha" "$later")

out="$("$THINGS" delete anything --no-input || true)"
assert_json "delete requires confirmation" "$out" 'payload["status"] == "error" and payload["error"]["code"] == "E_VALIDATION"'

out="$(command_json cancel "$alpha")"
assert_json "cancel alpha" "$out" 'payload["status"] == "ok"'

out="$(command_json cancel "$later")"
assert_json "cancel natural language" "$out" 'payload["status"] == "ok"'
CREATED_NAMES=()

sleep 1
out="$(command_json search "$PREFIX")"
assert_json "no open test tasks remain" "$out" 'payload["status"] == "ok" and payload["data"]["count"] == 0'

out="$(command_json search "$PREFIX" --include-completed)"
assert_json "canceled test tasks remain queryable" "$out" 'payload["status"] == "ok" and payload["data"]["count"] >= 3'

printf '\nthings-client live tests passed\n'
