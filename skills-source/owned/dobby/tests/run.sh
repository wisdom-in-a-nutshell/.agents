#!/usr/bin/env bash
# Test runner for the Dobby memory skill scripts.
#
# By default, runs only cheap/non-mutating suites. Live suites (`*/live.sh`) are opt-in. Shelf tests live with the Shelf backend; calendar tests live in `dobby-calendar`.
#
# Usage:
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh                 # cheap suites only
#     RUN_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh      # include all live suites
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh memory          # only memory suites
#     bash ~/.agents/skills-source/owned/dobby/tests/run.sh live            # all live suites
#     SKIP_LIVE=1 bash ~/.agents/skills-source/owned/dobby/tests/run.sh     # force-skip live suites
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"
DOBBY_BIN="$TESTS_DIR/support/dobby-shim"

resolve_workspace() {
    if [[ -n "${DOBBY_WORKSPACE:-}" ]]; then
        printf '%s\n' "$DOBBY_WORKSPACE"
        return
    fi
    if [[ -f "$PWD/soul.md" && -d "$PWD/memory" && -d "$PWD/journal" ]]; then
        printf '%s\n' "$PWD"
        return
    fi
    local git_root
    git_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)
    if [[ -n "$git_root" && -f "$git_root/soul.md" && -d "$git_root/memory" && -d "$git_root/journal" ]]; then
        printf '%s\n' "$git_root"
        return
    fi
    printf '%s\n' "$HOME/GitHub/adi"
}

REPO_ROOT="$(resolve_workspace)"
export DOBBY_WORKSPACE="$REPO_ROOT"

has_filter() {
    local needle="$1"
    shift || true
    local pattern
    for pattern in "$@"; do
        [[ "$pattern" == *"$needle"* ]] && return 0
    done
    return 1
}

matches_filters() {
    local file="$1"
    shift || true
    local pattern
    for pattern in "$@"; do
        [[ "$file" == *"$pattern"* ]] || return 1
    done
    return 0
}

# Collect test scripts. If args are given, each arg is an ANDed substring filter
# on the script path. Example: `calendar live` selects `calendar/live.sh`.
SCRIPTS=()
SKIPPED_LIVE=0
LIVE_FILTER_REQUESTED=0
if has_filter "live" "$@"; then
    LIVE_FILTER_REQUESTED=1
fi
while IFS= read -r -d '' file; do
    # Skip library shims
    [[ "$file" == */lib/* ]] && continue
    [[ "$(basename "$file")" == "run.sh" ]] && continue
    if [[ $# -gt 0 ]]; then
        matches_filters "$file" "$@" || continue
    fi
    # Honor SKIP_LIVE. Otherwise, live suites are opt-in via RUN_LIVE=1 or an
    # explicit `live` filter.
    if [[ "${SKIP_LIVE:-0}" == "1" ]] && [[ "$file" == *"/live.sh" ]]; then
        continue
    fi
    if [[ "$file" == *"/live.sh" ]] \
        && [[ "${RUN_LIVE:-0}" != "1" ]] \
        && [[ "$LIVE_FILTER_REQUESTED" != "1" ]]; then
        SKIPPED_LIVE=$((SKIPPED_LIVE + 1))
        continue
    fi
    SCRIPTS+=("$file")
done < <(find "$TESTS_DIR" -type f -name '*.sh' -print0 | sort -z)

if [[ "$SKIPPED_LIVE" -gt 0 ]]; then
    printf "\033[33m[tests] skipped %d live suite(s); set RUN_LIVE=1 or filter on 'live' to run them\033[0m\n" "$SKIPPED_LIVE"
fi

TOTAL_SUITES=0
FAILED_SUITES=0
FAILED_NAMES=()

print_header() {
    printf "\n\033[1m════════════════════════════════════════\033[0m\n"
    printf "\033[1m%s\033[0m\n" "$1"
    printf "\033[1m════════════════════════════════════════\033[0m\n"
}

for script in "${SCRIPTS[@]}"; do
    rel="${script#$SKILL_DIR/}"
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    print_header "$rel"
    if bash "$script"; then
        :
    else
        rc=$?
        FAILED_SUITES=$((FAILED_SUITES + 1))
        FAILED_NAMES+=("$rel ($rc failures)")
    fi
done

printf "\n\033[1m════════════════════════════════════════\033[0m\n"
if [[ $FAILED_SUITES -eq 0 ]]; then
    printf "\033[32m✓ %d/%d suite(s) passed\033[0m\n" "$TOTAL_SUITES" "$TOTAL_SUITES"
    exit 0
else
    printf "\033[31m✗ %d/%d suite(s) failed\033[0m\n" "$FAILED_SUITES" "$TOTAL_SUITES"
    for name in "${FAILED_NAMES[@]}"; do
        printf "  - %s\n" "$name"
    done
    exit 1
fi
