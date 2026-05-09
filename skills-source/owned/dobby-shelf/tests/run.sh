#!/usr/bin/env bash
set -uo pipefail
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$TESTS_DIR/.." && pwd)"
SCRIPTS=()
while IFS= read -r -d '' file; do
  [[ "$file" == */lib/* ]] && continue
  [[ "$(basename "$file")" == "run.sh" ]] && continue
  if [[ $# -gt 0 ]]; then
    ok=1
    for f in "$@"; do [[ "$file" == *"$f"* ]] || ok=0; done
    [[ "$ok" == 1 ]] || continue
  fi
  SCRIPTS+=("$file")
done < <(find "$TESTS_DIR" -type f -name '*.sh' -print0 | sort -z)
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
