#!/usr/bin/env bash
# Shared bash test helpers for the Dobby CLI contract tests.
#
# Source this at the top of every test script:
#     source "$(dirname "$0")/../lib/assert.sh"
#
# Conventions:
# - Each test function prints ONE line per assertion to stdout.
# - Passing assertions print "  ✓ <name>"
# - Failing assertions print "  ✗ <name>: <reason>" AND increment a global fail counter.
# - Test scripts return the number of failures as their exit code (capped at 255).
# - Tests must be idempotent: they set up their own state and clean up after themselves.

# Resolve the skill root, workspace root, and split Dobby entrypoints once.
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"

resolve_workspace() {
    if [[ -n "${DOBBY_WORKSPACE:-}" ]]; then
        printf '%s\n' "$DOBBY_WORKSPACE"
        return
    fi
    if [[ -f "$PWD/dobby/constitution.md" && -d "$PWD/memory" && -d "$PWD/journal" ]]; then
        printf '%s\n' "$PWD"
        return
    fi
    local git_root
    git_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)
    if [[ -n "$git_root" && -f "$git_root/dobby/constitution.md" && -d "$git_root/memory" && -d "$git_root/journal" ]]; then
        printf '%s\n' "$git_root"
        return
    fi
    printf '%s\n' "$HOME/GitHub/adi"
}

REPO_ROOT="$(resolve_workspace)"
export DOBBY_WORKSPACE="$REPO_ROOT"
DOBBY="$TESTS_DIR/support/dobby-shim"
DOBBY_CALENDAR="$SKILL_DIR/scripts/dobby-calendar"

# Failure counter — test scripts can read and return at the end.
export FAIL_COUNT=${FAIL_COUNT:-0}

_pass() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
_fail() { printf "  \033[31m✗\033[0m %s: %s\n" "$1" "$2"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# Eventual-consistency helper for live integration calls.
#
# Retries the command up to N times with a delay between attempts, returning
# 0 on the first success and the last exit code after exhaustion. Captures the
# final stdout into CAPTURED_STDOUT (same shape as run_dobby) so the caller
# can assert against it.
retry_cmd() {
    local attempts="$1"; shift
    local delay="$1"; shift
    local last=1
    for ((i=1; i<=attempts; i++)); do
        CAPTURED_STDOUT=$("$@" 2>/dev/null || true)
        last=$?
        if [[ $last -eq 0 ]] && [[ -n "$CAPTURED_STDOUT" ]]; then
            return 0
        fi
        sleep "$delay"
    done
    return "$last"
}

section() {
    printf "\n\033[1m%s\033[0m\n" "$1"
}

assert_eq() {
    local name="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        _pass "$name"
    else
        _fail "$name" "expected $(printf '%q' "$expected"), got $(printf '%q' "$actual")"
    fi
}

assert_ne() {
    local name="$1" unexpected="$2" actual="$3"
    if [[ "$unexpected" != "$actual" ]]; then
        _pass "$name"
    else
        _fail "$name" "got disallowed value $(printf '%q' "$actual")"
    fi
}

assert_contains() {
    local name="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        _pass "$name"
    else
        _fail "$name" "did not find $(printf '%q' "$needle")"
    fi
}

assert_not_contains() {
    local name="$1" needle="$2" haystack="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        _pass "$name"
    else
        _fail "$name" "unexpectedly found $(printf '%q' "$needle")"
    fi
}

assert_exit() {
    local name="$1" expected="$2" actual="$3"
    if [[ "$expected" -eq "$actual" ]]; then
        _pass "$name"
    else
        _fail "$name" "expected exit $expected, got $actual"
    fi
}

assert_jq_eq() {
    local name="$1" expr="$2" expected="$3" json="$4"
    local actual
    actual=$(printf '%s' "$json" | jq -r "$expr" 2>/dev/null || echo "<jq-error>")
    assert_eq "$name" "$expected" "$actual"
}

assert_jq_truthy() {
    local name="$1" expr="$2" json="$3"
    local actual
    actual=$(printf '%s' "$json" | jq "$expr" 2>/dev/null || echo "false")
    if [[ "$actual" == "true" ]] || [[ "$actual" != "null" && -n "$actual" && "$actual" != "false" ]]; then
        _pass "$name"
    else
        _fail "$name" "expected truthy for $expr, got $actual"
    fi
}

# Validate the full Dobby envelope shape.
assert_envelope_shape() {
    local name_prefix="$1" json="$2"
    assert_jq_eq "$name_prefix: schema_version=1.0" '.schema_version' "1.0" "$json"
    assert_jq_truthy "$name_prefix: has command field" '.command' "$json"
    assert_jq_truthy "$name_prefix: has status field" '.status' "$json"
    assert_jq_truthy "$name_prefix: has meta.request_id" '.meta.request_id' "$json"
    assert_jq_truthy "$name_prefix: has meta.duration_ms" '.meta | has("duration_ms")' "$json"
    assert_jq_truthy "$name_prefix: has meta.timestamp_utc" '.meta.timestamp_utc' "$json"
}

assert_envelope_ok() {
    local name_prefix="$1" json="$2"
    assert_envelope_shape "$name_prefix" "$json"
    assert_jq_eq "$name_prefix: status=ok" '.status' "ok" "$json"
    assert_jq_eq "$name_prefix: error is null" '.error' "null" "$json"
    assert_jq_truthy "$name_prefix: data is not null" '.data != null' "$json"
}

assert_envelope_error() {
    local name_prefix="$1" expected_code="$2" json="$3"
    assert_envelope_shape "$name_prefix" "$json"
    assert_jq_eq "$name_prefix: status=error" '.status' "error" "$json"
    assert_jq_eq "$name_prefix: data is null" '.data' "null" "$json"
    assert_jq_eq "$name_prefix: error.code=$expected_code" '.error.code' "$expected_code" "$json"
    assert_jq_truthy "$name_prefix: error.message non-empty" '.error.message' "$json"
}

# Run a dobby command and capture stdout, stderr, exit code separately.
# Usage: run_dobby <args...>
# Populates: CAPTURED_STDOUT, CAPTURED_STDERR, CAPTURED_EXIT
run_dobby() {
    local stdout_file stderr_file
    stdout_file=$(mktemp)
    stderr_file=$(mktemp)
    set +e
    "$DOBBY" "$@" > "$stdout_file" 2> "$stderr_file"
    CAPTURED_EXIT=$?
    set -e
    CAPTURED_STDOUT=$(cat "$stdout_file")
    CAPTURED_STDERR=$(cat "$stderr_file")
    rm -f "$stdout_file" "$stderr_file"
}

# Same, but pipes the given string to stdin.
run_dobby_stdin() {
    local input="$1"; shift
    local stdout_file stderr_file
    stdout_file=$(mktemp)
    stderr_file=$(mktemp)
    set +e
    printf '%s' "$input" | "$DOBBY" "$@" > "$stdout_file" 2> "$stderr_file"
    CAPTURED_EXIT=$?
    set -e
    CAPTURED_STDOUT=$(cat "$stdout_file")
    CAPTURED_STDERR=$(cat "$stderr_file")
    rm -f "$stdout_file" "$stderr_file"
}

# Print a test-script-level summary footer and return the fail count
# (capped at 255 for exit codes).
finish_test() {
    local script_name="${1:-test}"
    if [[ $FAIL_COUNT -eq 0 ]]; then
        printf "\n\033[32m%s: PASS\033[0m\n" "$script_name"
    else
        printf "\n\033[31m%s: FAIL (%d failures)\033[0m\n" "$script_name" "$FAIL_COUNT"
    fi
    if [[ $FAIL_COUNT -gt 255 ]]; then
        return 255
    fi
    return "$FAIL_COUNT"
}
