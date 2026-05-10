#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/pre-compact" \
  "$SKILL_DIR/scripts/hooks/post-compact" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/hooks/codex-finalize-session" \
  "$SKILL_DIR/scripts/hooks/write-session-note"

tmp_root="$(mktemp -d)"
active_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root" "$active_root"' EXIT

cat >"$tmp_root/precompact-payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PreCompact",
  "runtime": "codex",
  "repo_root": "$tmp_root",
  "cwd": "$tmp_root",
  "session_id": "test-source-thread",
  "turn_id": "test-turn",
  "model": "test-model"
}
JSON

python3 "$SKILL_DIR/scripts/hooks/pre-compact" <"$tmp_root/precompact-payload.json"
if [[ -e "$tmp_root/tmp" ]]; then
  echo "PreCompact must be fully inert and create no artifacts" >&2
  find "$tmp_root/tmp" -maxdepth 4 -type f >&2 || true
  exit 1
fi

cat >"$tmp_root/postcompact-payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PostCompact",
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

DOBBY_CODEX_FINALIZER_DISABLED=1 python3 "$SKILL_DIR/scripts/hooks/post-compact" <"$tmp_root/postcompact-payload.json"
post_record_count="$(find "$tmp_root/tmp/hooks/post-compact" -type f -name '*.json' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$post_record_count" != "1" ]]; then
  echo "expected PostCompact to write exactly one finalizer job record, got $post_record_count" >&2
  exit 1
fi
if [[ -e "$tmp_root/tmp/hooks/session-finalizer/worker.log" ]]; then
  echo "PostCompact should respect DOBBY_CODEX_FINALIZER_DISABLED and not launch worker" >&2
  exit 1
fi

cat >"$active_root/postcompact-payload.json" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "PostCompact",
  "runtime": "codex",
  "repo_root": "$active_root",
  "session_id": "finalizer-owned-thread"
}
JSON
DOBBY_INTERNAL_SIDECAR=1 python3 "$SKILL_DIR/scripts/hooks/post-compact" <"$active_root/postcompact-payload.json"
if [[ -e "$active_root/tmp" ]]; then
  echo "Internal sidecar PostCompact context should be inert and write no lifecycle artifacts" >&2
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
DOBBY_INTERNAL_SIDECAR=1 python3 "$SKILL_DIR/scripts/hooks/session-end" <"$active_root/session-end-payload.json"
if [[ -e "$active_root/tmp" ]]; then
  echo "Internal sidecar SessionEnd context should be inert and write no lifecycle artifacts" >&2
  exit 1
fi

if ! grep -q 'env\["DOBBY_INTERNAL_SIDECAR"\] = "1"' "$SKILL_DIR/scripts/hooks/codex-finalize-session"; then
  echo "codex-finalize-session must mark its app-server as DOBBY_INTERNAL_SIDECAR" >&2
  exit 1
fi
