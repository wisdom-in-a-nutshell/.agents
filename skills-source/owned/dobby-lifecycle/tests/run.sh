#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/post-compact" \
  "$SKILL_DIR/scripts/hooks/session-end" \
  "$SKILL_DIR/scripts/hooks/codex-finalize-session" \
  "$SKILL_DIR/scripts/hooks/write-session-note"

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT

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

forbidden_var="DOBBY_INTERNAL_""SIDECAR"
if grep -R "$forbidden_var" "$SKILL_DIR/scripts/hooks" "$SKILL_DIR/references" >/dev/null; then
  echo "$forbidden_var should not be part of the current simple design" >&2
  exit 1
fi
