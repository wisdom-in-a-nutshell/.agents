#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/session_memory_lib.py" \
  "$SKILL_DIR/scripts/session-memory" \
  "$SKILL_DIR/scripts/remember-session" \
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
remember_log="$tmp_dir/remember-argv.json"
fake_remember="$tmp_dir/remember-session"
cat >"$fake_remember" <<PY
#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ["REMEMBER_LOG"]).write_text(json.dumps(sys.argv[1:]))
print(json.dumps({"schema_version": "1.0", "command": "remember-session", "status": "ok", "data": {"threadId": "thread-test"}, "error": None, "meta": {}}))
PY
chmod +x "$fake_remember"
cat >"$payload" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "FinalizeCodexThread",
  "cwd": "$repo",
  "repo_root": "$repo",
  "thread_id": "thread-test",
  "reason": "codexclaw-daily-rollover",
  "codex_bin": "fake-codex"
}
JSON

hook_output="$(REMEMBER_LOG="$remember_log" DOBBY_REMEMBER_SESSION_BIN="$fake_remember" $SKILL_DIR/scripts/hooks/finalize-codex-thread <"$payload")"
if [[ -z "$hook_output" ]]; then
  echo "finalize-codex-thread hook should emit remember-session output" >&2
  exit 1
fi
if ! grep -q '"command": "remember-session"' <<<"$hook_output"; then
  echo "finalize-codex-thread hook should run remember-session" >&2
  exit 1
fi
remember_argv="$(cat "$remember_log")"
if ! grep -q -- "--thread-id" <<<"$remember_argv" || ! grep -q "thread-test" <<<"$remember_argv"; then
  echo "remember-session should receive source thread id" >&2
  exit 1
fi
if ! grep -q -- "--source" <<<"$remember_argv" || ! grep -q "codexclaw" <<<"$remember_argv"; then
  echo "remember-session should receive normalized source" >&2
  exit 1
fi
if ! "$SKILL_DIR/scripts/remember-session" \
  --thread-id thread-test \
  --workspace-root "$repo" \
  --source codexclaw \
  --reason daily-rollover \
  --print-instruction \
  --plain \
  --no-input | grep -q "Remember this session"; then
  echo "remember-session --print-instruction should render the Dobby memory prompt" >&2
  exit 1
fi
