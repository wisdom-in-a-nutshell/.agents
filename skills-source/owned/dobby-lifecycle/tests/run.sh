#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/finalize-codex-thread" \
  "$SKILL_DIR/scripts/hooks/session-end"

if grep -R "consolidate-thread\|PreCompact\|SIDECAR" "$SKILL_DIR/scripts" "$SKILL_DIR/references" >/dev/null; then
  echo "sidecar/pre-compact/consolidate-thread references should not be part of the simple lifecycle design" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
repo="$tmp_dir/repo"
mkdir -p "$repo"

payload="$tmp_dir/finalize-payload.json"
cat >"$payload" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "FinalizeCodexThread",
  "cwd": "$repo",
  "repo_root": "$repo",
  "thread_id": "thread-test",
  "reason": "test"
}
JSON

hook_output="$($SKILL_DIR/scripts/hooks/finalize-codex-thread <"$payload")"
if [[ -z "$hook_output" ]]; then
  echo "finalize-codex-thread hook should emit a finalization instruction" >&2
  exit 1
fi
if ! grep -q "final turn" <<<"$hook_output"; then
  echo "finalization instruction should describe same-thread finalization" >&2
  exit 1
fi
if ! grep -q "thread-test" <<<"$hook_output"; then
  echo "finalization instruction should include source thread id" >&2
  exit 1
fi
