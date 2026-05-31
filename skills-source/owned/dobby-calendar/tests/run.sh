#!/usr/bin/env bash
# Test runner for the Dobby Calendar skill. Live suites are opt-in.
set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"

resolve_workspace() {
    if [[ -n "${DOBBY_WORKSPACE:-}" ]]; then printf '%s\n' "$DOBBY_WORKSPACE"; return; fi
    if [[ -f "$PWD/dobby/constitution.json" && -d "$PWD/memory" && -d "$PWD/journal" ]]; then printf '%s\n' "$PWD"; return; fi
    local git_root
    git_root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)
    if [[ -n "$git_root" && -f "$git_root/dobby/constitution.json" && -d "$git_root/memory" && -d "$git_root/journal" ]]; then printf '%s\n' "$git_root"; return; fi
    printf '%s\n' "$HOME/GitHub/adi"
}

REPO_ROOT="$(resolve_workspace)"
export DOBBY_WORKSPACE="$REPO_ROOT"

has_filter() { local needle="$1"; shift || true; local p; for p in "$@"; do [[ "$p" == *"$needle"* ]] && return 0; done; return 1; }
matches_filters() { local file="$1"; shift || true; local p; for p in "$@"; do [[ "$file" == *"$p"* ]] || return 1; done; return 0; }

SCRIPTS=(); SKIPPED_LIVE=0; LIVE_FILTER_REQUESTED=0
if has_filter "live" "$@"; then LIVE_FILTER_REQUESTED=1; fi
while IFS= read -r -d '' file; do
    [[ "$file" == */lib/* ]] && continue
    [[ "$(basename "$file")" == "run.sh" ]] && continue
    if [[ $# -gt 0 ]]; then matches_filters "$file" "$@" || continue; fi
    if [[ "${SKIP_LIVE:-0}" == "1" && "$file" == *"/live.sh" ]]; then continue; fi
    if [[ "$file" == *"/live.sh" && "${RUN_LIVE:-0}" != "1" && "$LIVE_FILTER_REQUESTED" != "1" ]]; then SKIPPED_LIVE=$((SKIPPED_LIVE + 1)); continue; fi
    SCRIPTS+=("$file")
done < <(find "$TESTS_DIR" -type f -name '*.sh' -print0 | sort -z)

if [[ "$SKIPPED_LIVE" -gt 0 ]]; then printf "\033[33m[tests] skipped %d live suite(s); set RUN_LIVE=1 or filter on 'live' to run them\033[0m\n" "$SKIPPED_LIVE"; fi
TOTAL=0; FAILED=0; FAILED_NAMES=()
for script in "${SCRIPTS[@]}"; do
    rel="${script#$SKILL_DIR/}"
    TOTAL=$((TOTAL + 1))
    printf "\n\033[1m════════════════════════════════════════\033[0m\n\033[1m%s\033[0m\n\033[1m════════════════════════════════════════\033[0m\n" "$rel"
    if bash "$script"; then :; else rc=$?; FAILED=$((FAILED + 1)); FAILED_NAMES+=("$rel ($rc failures)"); fi
done
printf "\n\033[1m════════════════════════════════════════\033[0m\n"
if [[ $FAILED -eq 0 ]]; then printf "\033[32m✓ %d/%d suite(s) passed\033[0m\n" "$TOTAL" "$TOTAL"; exit 0; fi
printf "\033[31m✗ %d/%d suite(s) failed\033[0m\n" "$FAILED" "$TOTAL"
printf '  - %s\n' "${FAILED_NAMES[@]}"
exit 1
