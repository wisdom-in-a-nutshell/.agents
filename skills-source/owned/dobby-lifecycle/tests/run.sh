#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/session_memory_lib.py" \
  "$SKILL_DIR/scripts/session-memory" \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/finalize-codex-thread"

if grep -R "consolidate-thread\|PreCompact\|SIDECAR" "$SKILL_DIR/scripts" "$SKILL_DIR/references" >/dev/null; then
  echo "sidecar/pre-compact/consolidate-thread references should not be part of the simple lifecycle design" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
repo="$tmp_dir/repo"
mkdir -p "$repo"

session_cli="$SKILL_DIR/scripts/session-memory"

schema_output="$("$session_cli" schema --no-input)"
if ! grep -q '"schemaVersion"' <<<"$schema_output"; then
  echo "session-memory schema should describe the record contract" >&2
  exit 1
fi

write_output="$("$session_cli" write \
  --workspace-root "$repo" \
  --source codex-desktop \
  --reason test \
  --thread-id thread-test \
  --summary "Carry this forward." \
  --no-input)"
session_path="$(python3 - "$write_output" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["data"]["path"])
PY
)"
if [[ ! -f "$session_path" || "${session_path##*.}" != "json" ]]; then
  echo "session-memory write should create a JSON record" >&2
  exit 1
fi
"$session_cli" validate "$session_path" --no-input >/dev/null

boot_output="$("$session_cli" render-boot --workspace-root "$repo" --plain --no-input)"
if ! grep -q "Carry this forward" <<<"$boot_output"; then
  echo "session-memory render-boot should include written summary" >&2
  exit 1
fi

if "$session_cli" write --workspace-root "$repo" --source codex-desktop --reason test --no-input >/dev/null; then
  echo "session-memory write should reject empty summary" >&2
  exit 1
fi

bad_record="$tmp_dir/bad-session-record.json"
cat >"$bad_record" <<'JSON'
{"schemaVersion":1,"createdAt":"2026-05-25T01:02:03+02:00","source":"codex-desktop","reason":"test","threadId":"thread-test","summary":["ok"],"surfaceKey":"legacy"}
JSON
if "$session_cli" validate "$bad_record" --no-input >/dev/null; then
  echo "session-memory validate should reject unsupported schema keys" >&2
  exit 1
fi

mkdir -p "$repo/memory/sessions/2026/05"
cat >"$repo/memory/sessions/2026/05/25-010203.md" <<'MD'
# Legacy

- Keep this migrated.
MD
"$session_cli" migrate-md --workspace-root "$repo" --apply --delete-source --no-input >/dev/null
if [[ ! -f "$repo/memory/sessions/2026/05/25-010203.json" ]]; then
  echo "session-memory migrate-md should create a JSON record" >&2
  exit 1
fi
if [[ -f "$repo/memory/sessions/2026/05/25-010203.md" ]]; then
  echo "session-memory migrate-md --delete-source should remove Markdown source" >&2
  exit 1
fi

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
