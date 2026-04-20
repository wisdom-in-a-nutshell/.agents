#!/usr/bin/env bash
# Tests for `dobby memory read`.
set -euo pipefail
source "$(dirname "$0")/../lib/assert.sh"

FAIL_COUNT=0

section "memory read --section profile (JSON default)"
run_dobby memory read --section profile
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read profile default" "$CAPTURED_STDOUT"
assert_jq_eq "path=memory/profile.md" '.data.path' "memory/profile.md" "$CAPTURED_STDOUT"
assert_jq_truthy "content contains # Profile heading" '.data.content | contains("# Profile")' "$CAPTURED_STDOUT"

section "memory read --section profile --plain"
run_dobby memory read --section profile --plain
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "contains # Profile heading" "# Profile" "$CAPTURED_STDOUT"
assert_not_contains "no JSON envelope" '"schema_version"' "$CAPTURED_STDOUT"

section "memory read --section profile --json"
run_dobby memory read --section profile --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read profile" "$CAPTURED_STDOUT"
assert_jq_eq "path=memory/profile.md" '.data.path' "memory/profile.md" "$CAPTURED_STDOUT"
assert_jq_eq "section=profile" '.data.section' "profile" "$CAPTURED_STDOUT"
assert_jq_truthy "content non-empty" '.data.content | length > 0' "$CAPTURED_STDOUT"

section "memory read --section now"
run_dobby memory read --section now --plain
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_contains "contains # Now heading" "# Now" "$CAPTURED_STDOUT"

section "memory read --section area.<name> (directory concat)"
# area.builder -> concat all *.md in memory/areas/builder/
run_dobby memory read --section area.builder --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read area.builder" "$CAPTURED_STDOUT"
assert_jq_eq "path=memory/areas/builder" '.data.path' "memory/areas/builder" "$CAPTURED_STDOUT"
assert_jq_truthy "content has multiple file sections" \
    '(.data.content | contains("## builder")) and (.data.content | contains("## company"))' "$CAPTURED_STDOUT"

section "memory read --section area.<name>.<file> (single file)"
run_dobby memory read --section area.builder.builder --json
assert_exit "exit 0" 0 "$CAPTURED_EXIT"
assert_envelope_ok "memory.read area.builder.builder" "$CAPTURED_STDOUT"
assert_jq_eq "path=memory/areas/builder/builder.md" '.data.path' "memory/areas/builder/builder.md" "$CAPTURED_STDOUT"

section "memory read — invalid section root"
run_dobby memory read --section bogus
assert_exit "exit 2 (E_VALIDATION)" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.read bogus" "E_VALIDATION" "$CAPTURED_STDOUT"
assert_jq_truthy "hint is non-empty" '.error.hint | length > 0' "$CAPTURED_STDOUT"

section "memory read — profile with subsection (rejected)"
run_dobby memory read --section profile.identity
assert_exit "exit 2 (E_VALIDATION)" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.read profile.subsection" "E_VALIDATION" "$CAPTURED_STDOUT"

section "memory read — nonexistent area"
run_dobby memory read --section area.nope
assert_exit "exit 1 (E_NOT_FOUND)" 1 "$CAPTURED_EXIT"
assert_envelope_error "memory.read area.nope" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "memory read — nonexistent area file"
run_dobby memory read --section area.health.nothing-here
assert_exit "exit 1 (E_NOT_FOUND)" 1 "$CAPTURED_EXIT"
assert_envelope_error "memory.read area.health.nothing-here" "E_NOT_FOUND" "$CAPTURED_STDOUT"

section "memory read — malformed area path"
run_dobby memory read --section area.health.health.extra
assert_exit "exit 2 (E_VALIDATION)" 2 "$CAPTURED_EXIT"
assert_envelope_error "memory.read malformed area" "E_VALIDATION" "$CAPTURED_STDOUT"

finish_test "memory/read.sh"
