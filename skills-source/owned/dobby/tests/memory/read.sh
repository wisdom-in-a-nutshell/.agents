#!/usr/bin/env bash
# Tests for `dobby memory read`.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0
TEST_AREA="$(find "$REPO_ROOT/memory/areas" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | head -n 1)"
TEST_AREA_DIR="memory/areas/$TEST_AREA"
TEST_AREA_FILE="$TEST_AREA"
if [[ ! -f "$REPO_ROOT/$TEST_AREA_DIR/$TEST_AREA_FILE.md" ]]; then
    TEST_AREA_FILE="$(find "$REPO_ROOT/$TEST_AREA_DIR" -maxdepth 1 -type f -name '*.md' -exec basename {} .md \; | sort | head -n 1)"
fi

section "memory read --section now"
run_dobby memory read --section now --plain
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "contains weekly shape section" "## This week's shape" "$CAPTURED_STDOUT"

section "memory read --section area.<name> (directory concat)"
# area.<name> -> concat all *.md in memory/areas/<name>/
run_dobby memory read --section "area.$TEST_AREA" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read area.$TEST_AREA" "$CAPTURED_STDOUT"
assert_jq_eq "path=$TEST_AREA_DIR" '.data.path' "$TEST_AREA_DIR" "$CAPTURED_STDOUT"
assert_jq_truthy "content has at least one file section" \
    '(.data.content | startswith("## "))' "$CAPTURED_STDOUT"

section "memory read --section area.<name>.<file> (single file)"
run_dobby memory read --section "area.$TEST_AREA.$TEST_AREA_FILE" --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read area.$TEST_AREA.$TEST_AREA_FILE" "$CAPTURED_STDOUT"
assert_jq_eq "path=$TEST_AREA_DIR/$TEST_AREA_FILE.md" '.data.path' "$TEST_AREA_DIR/$TEST_AREA_FILE.md" "$CAPTURED_STDOUT"

section "memory read — invalid section root"
run_dobby memory read --section bogus
assert_exit "exit 2 (E_VALIDATION)" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.read bogus" "E_VALIDATION" "$CAPTURED_STDOUT"
assert_jq_truthy "hint is non-empty" '.error.hint | length > 0' "$CAPTURED_STDOUT"

section "memory read — nonexistent area"
run_dobby memory read --section area.nope
assert_exit "exit 1 (E_NOT_FOUND)" 1 "$CAPTURED_EXIT"
assert_envelope_error "memory.read area.nope" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "memory read — nonexistent area file"
run_dobby memory read --section "area.$TEST_AREA.nothing-here"
assert_exit "exit 1 (E_NOT_FOUND)" 1 "$CAPTURED_EXIT"
assert_envelope_error "memory.read area.$TEST_AREA.nothing-here" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "memory read — malformed area path"
run_dobby memory read --section "area.$TEST_AREA.$TEST_AREA_FILE.extra"
assert_exit "exit 2 (E_VALIDATION)" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.read malformed area" "E_VALIDATION" "$CAPTURED_STDOUT"

finish_test "memory/read.sh"
