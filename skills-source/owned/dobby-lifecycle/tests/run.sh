#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/session_memory_lib.py" \
  "$SKILL_DIR/scripts/session-memory" \
  "$SKILL_DIR/scripts/validate" \
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
if ! grep -q '"workspaceChanges"' <<<"$schema_output"; then
  echo "session-memory schema should describe the workspace-changes visibility field" >&2
  exit 1
fi

write_output="$("$session_cli" write \
  --workspace-root "$repo" \
  --trigger test \
  --thread-id thread-test \
  --title "Test memory" \
  --summary "Carry this forward." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
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
"$SKILL_DIR/scripts/validate" --workspace-root "$repo" "$session_path" --no-input >/dev/null

bad_session_name="$repo/memory/sessions/2026/05/bad.json"
mkdir -p "$(dirname "$bad_session_name")"
cp "$session_path" "$bad_session_name"
if "$SKILL_DIR/scripts/validate" --workspace-root "$repo" "$bad_session_name" --no-input >/dev/null 2>&1; then
  echo "lifecycle validate should reject session-memory JSON filenames that boot cannot discover" >&2
  exit 1
fi
rm -f "$bad_session_name"

stdin_write_output="$(cat <<'JSON' | "$session_cli" write --workspace-root "$repo" --stdin-json --no-input
{
  "trigger": "test",
  "threadId": "thread-test",
  "title": "File audit",
  "summary": "Carry this file audit forward.",
  "workspaceChanges": "Updated `memory/areas/builder/log.jsonl` because future context needs the concrete fact."
}
JSON
)"
stdin_session_path="$(python3 - "$stdin_write_output" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["data"]["path"])
PY
)"
python3 - "$session_cli" "$stdin_session_path" <<'PY'
import json
import subprocess
import sys

payload = subprocess.check_output([sys.argv[1], "read", sys.argv[2], "--no-input"], text=True)
record = json.loads(payload)["data"]["record"]
assert record["workspaceChanges"] == "Updated `memory/areas/builder/log.jsonl` because future context needs the concrete fact."
PY

boot_output="$("$session_cli" render-boot --workspace-root "$repo" --plain --no-input)"
if ! grep -q "Carry this forward" <<<"$boot_output"; then
  echo "session-memory render-boot should include written summary" >&2
  exit 1
fi

if "$session_cli" write --workspace-root "$repo" --trigger test --title "Missing summary" --workspace-changes "No durable workspace changes besides this session-memory record." --no-input >/dev/null; then
  echo "session-memory write should reject empty summary" >&2
  exit 1
fi

bad_record="$tmp_dir/bad-session-record.json"
cat >"$bad_record" <<'JSON'
{"schemaVersion":2,"createdAt":"2026-05-25T01:02:03+02:00","threadId":"thread-test","trigger":"test","title":"Ok","summary":"ok","workspaceChanges":"none","surfaceKey":"legacy"}
JSON
if "$session_cli" validate "$bad_record" --no-input >/dev/null; then
  echo "session-memory validate should reject unsupported schema keys" >&2
  exit 1
fi

runtime_write_output="$("$session_cli" write \
  --workspace-root "$repo" \
  --trigger test \
  --thread-id session-claude-test \
  --runtime claude \
  --title "Claude session memory" \
  --summary "Runtime-tagged card." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
  --no-input)"
python3 - "$runtime_write_output" <<'PY'
import json, sys
data = json.loads(sys.argv[1])["data"]
assert data["record"]["runtime"] == "claude", data
PY

bad_runtime_record="$tmp_dir/bad-runtime-record.json"
cat >"$bad_runtime_record" <<'JSON'
{"schemaVersion":2,"createdAt":"2026-05-25T01:02:03+02:00","threadId":"thread-test","trigger":"test","title":"Ok","summary":"ok","workspaceChanges":"none","runtime":"gemini"}
JSON
if "$session_cli" validate "$bad_runtime_record" --no-input >/dev/null; then
  echo "session-memory validate should reject unknown runtime values" >&2
  exit 1
fi

bad_workspace_changes_record="$tmp_dir/bad-workspace-changes-record.json"
cat >"$bad_workspace_changes_record" <<'JSON'
{"schemaVersion":2,"createdAt":"2026-05-25T01:02:03+02:00","threadId":"thread-test","trigger":"test","title":"Ok","summary":"ok","workspaceChanges":""}
JSON
if "$session_cli" validate "$bad_workspace_changes_record" --no-input >/dev/null; then
  echo "session-memory validate should reject empty workspaceChanges" >&2
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
  "thread_id": "thread-test",
  "reason": "codexclaw-daily-rollover"
}
JSON

hook_output="$(cd "$repo" && REMEMBER_LOG="$remember_log" DOBBY_REMEMBER_SESSION_BIN="$fake_remember" "$SKILL_DIR/scripts/hooks/finalize-codex-thread" <"$payload")"
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
if ! grep -q -- "--trigger" <<<"$remember_argv" || ! grep -q "codexclaw-daily-rollover" <<<"$remember_argv"; then
  echo "remember-session should receive raw finalization trigger" >&2
  exit 1
fi
if grep -q -- "--source" <<<"$remember_argv" || grep -q -- "--reason" <<<"$remember_argv"; then
  echo "remember-session should not receive legacy source/reason args" >&2
  exit 1
fi
if grep -Eq -- "--workspace-root|--timeout-seconds|--remember-timeout-seconds" <<<"$remember_argv"; then
  echo "finalize-codex-thread hook should only forward thread id and trigger to remember-session" >&2
  exit 1
fi

fake_bin_dir="$tmp_dir/bin"
mkdir -p "$fake_bin_dir"
fake_codex="$fake_bin_dir/codex"
cat >"$fake_codex" <<'PY'
#!/usr/bin/env python3
import json
import os
import sys

resumed = set()

for line in sys.stdin:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    request_id = msg.get("id")
    if request_id is None:
        continue
    method = msg.get("method")
    if method == "initialize":
        response = {"id": request_id, "result": {}}
    elif method == "thread/read":
        thread_id = msg.get("params", {}).get("threadId")
        response = {
            "id": request_id,
            "result": {
                "thread": {
                    "id": thread_id,
                    "cwd": os.environ["FAKE_THREAD_CWD"],
                }
            },
        }
    elif method == "thread/resume":
        thread_id = msg.get("params", {}).get("threadId")
        resumed.add(thread_id)
        response = {"id": request_id, "result": {"thread": {"id": thread_id}}}
    elif method == "turn/start":
        thread_id = msg.get("params", {}).get("threadId")
        if thread_id not in resumed:
            response = {"id": request_id, "error": {"message": f"thread not resumed: {thread_id}"}}
            print(json.dumps(response), flush=True)
            continue
        response = {"id": request_id, "result": {"turn": {"id": "turn-test"}}}
        print(json.dumps(response), flush=True)
        print(
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": thread_id,
                        "turnId": "turn-test",
                        "status": "completed",
                    },
                }
            ),
            flush=True,
        )
        continue
    else:
        response = {"id": request_id, "result": {}}
    print(json.dumps(response), flush=True)
PY
chmod +x "$fake_codex"
instruction_output="$(PATH="$fake_bin_dir:$PATH" FAKE_THREAD_CWD="$repo" "$SKILL_DIR/scripts/remember-session" \
  --thread-id thread-test \
  --trigger codexclaw-daily-rollover \
  --print-instruction \
  --plain \
  --no-input)"
if ! grep -q "Remember this session" <<<"$instruction_output"; then
  echo "remember-session --print-instruction should render the Dobby memory prompt" >&2
  exit 1
fi
if grep -q "{{" <<<"$instruction_output"; then
  echo "remember-session --print-instruction should not leave template placeholders" >&2
  exit 1
fi
if ! grep -q '"sourceRuntime": "codex"' <<<"$instruction_output"; then
  echo "remember-session prompt should carry the source runtime tag" >&2
  exit 1
fi
if ! grep -q "Adi should not have to remember" <<<"$instruction_output"; then
  echo "remember-session prompt should include the forgot-to-remember audit" >&2
  exit 1
fi
if ! grep -q "schema source of truth" <<<"$instruction_output"; then
  echo "remember-session prompt should point agents to the session-memory client schema" >&2
  exit 1
fi
if ! grep -q "workspaceChanges" <<<"$instruction_output"; then
  echo "remember-session prompt should document the workspace-changes visibility field" >&2
  exit 1
fi
remember_output="$(PATH="$fake_bin_dir:$PATH" FAKE_THREAD_CWD="$repo" "$SKILL_DIR/scripts/remember-session" \
  --thread-id thread-test \
  --trigger codexclaw-daily-rollover \
  --json \
  --no-input)"
python3 - "$remember_output" "$repo" <<'PY'
import json
import pathlib
import sys

payload = json.loads(sys.argv[1])
repo = str(pathlib.Path(sys.argv[2]).resolve())
data = payload["data"]
assert data["threadId"] == "thread-test"
assert str(pathlib.Path(data["threadCwd"]).resolve()) == repo
assert str(pathlib.Path(data["workspaceRoot"]).resolve()) == repo
assert data["trigger"] == "codexclaw-daily-rollover"
assert data["turnStatus"] == "completed"
PY
