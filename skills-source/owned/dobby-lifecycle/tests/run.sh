#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/pre-compact" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/hooks/codex-finalize-session" \
  "$SKILL_DIR/scripts/hooks/write-session-note"

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root" "${active_root:-}"' EXIT

cat >"$tmp_root/precompact-payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PreCompact",
  "runtime": "codex",
  "repo_root": "$tmp_root",
  "cwd": "$tmp_root",
  "session_id": "test-source-thread",
  "turn_id": "test-turn",
  "model": "test-model",
  "raw_payload": {
    "session_id": "test-source-thread",
    "turn_id": "test-turn",
    "transcript_path": "$tmp_root/transcript.jsonl"
  }
}
JSON

python3 "$SKILL_DIR/scripts/hooks/pre-compact" <"$tmp_root/precompact-payload.json"

record_count="$(find "$tmp_root/tmp/hooks/pre-compact" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$record_count" != "1" ]]; then
  echo "expected PreCompact to write exactly one capture record, got $record_count" >&2
  exit 1
fi

if [[ -e "$tmp_root/tmp/hooks/session-finalizer/worker.log" ]]; then
  echo "PreCompact must be passive: it unexpectedly created a session-finalizer worker log" >&2
  exit 1
fi

if find "$tmp_root/tmp/hooks" -path '*session-finalizer*' -print -quit 2>/dev/null | grep -q .; then
  echo "PreCompact must not create session-finalizer artifacts" >&2
  exit 1
fi

active_root="$(mktemp -d)"
cat >"$active_root/payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PreCompact",
  "runtime": "codex",
  "repo_root": "$active_root",
  "session_id": "finalizer-owned-thread"
}
JSON
DOBBY_CODEX_FINALIZER_ACTIVE=1 python3 "$SKILL_DIR/scripts/hooks/pre-compact" <"$active_root/payload.json"
if [[ -e "$active_root/tmp/hooks/pre-compact" ]]; then
  echo "Finalizer-owned PreCompact context should be inert and write no records" >&2
  exit 1
fi

cat >"$active_root/session-end-payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "SessionEnd",
  "runtime": "codex",
  "repo_root": "$active_root",
  "session_id": "finalizer-owned-thread"
}
JSON
DOBBY_CODEX_FINALIZER_ACTIVE=1 python3 "$SKILL_DIR/scripts/hooks/session-end" <"$active_root/session-end-payload.json"
if [[ -e "$active_root/tmp/hooks/session-end" || -e "$active_root/tmp/hooks/session-memory" || -e "$active_root/tmp/hooks/session-finalizer" ]]; then
  echo "Finalizer-owned SessionEnd context should be inert and write no lifecycle artifacts" >&2
  exit 1
fi
