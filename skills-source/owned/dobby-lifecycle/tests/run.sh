#!/usr/bin/env bash
# Fast checks for Dobby lifecycle hook scripts.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m py_compile \
  "$SKILL_DIR/scripts/session_memory_lib.py" \
  "$SKILL_DIR/scripts/remember_lib.py" \
  "$SKILL_DIR/scripts/claude_lib.py" \
  "$SKILL_DIR/scripts/transcript_lib.py" \
  "$SKILL_DIR/scripts/session-memory" \
  "$SKILL_DIR/scripts/session-transcript" \
  "$SKILL_DIR/scripts/dream-memory" \
  "$SKILL_DIR/scripts/validate" \
  "$SKILL_DIR/scripts/remember-session" \
  "$SKILL_DIR/scripts/remember-claude-session" \
  "$SKILL_DIR/scripts/hooks/session-start" \
  "$SKILL_DIR/scripts/hooks/user-prompt-submit" \
  "$SKILL_DIR/scripts/hooks/finalize-codex-thread" \
  "$SKILL_DIR/scripts/hooks/finalize-claude-session"

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
  --runtime codex \
  --title "Test memory" \
  --summary "Carry this forward." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
  --no-input)"
session_path="$(python3 - "$write_output" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["data"]["path"])
PY
)"
if [[ ! -d "$session_path" || ! -f "$session_path/meta.json" || ! -f "$session_path/summary.md" ]]; then
  echo "session-memory write should create a session folder with meta.json + summary.md" >&2
  exit 1
fi
"$session_cli" validate "$session_path" --no-input >/dev/null
"$SKILL_DIR/scripts/validate" --workspace-root "$repo" "$session_path/meta.json" "$session_path/summary.md" --no-input >/dev/null

bad_session_name="$repo/memory/sessions/2026/05/bad.json"
mkdir -p "$(dirname "$bad_session_name")"
cp "$session_path/meta.json" "$bad_session_name"
if "$SKILL_DIR/scripts/validate" --workspace-root "$repo" "$bad_session_name" --no-input >/dev/null 2>&1; then
  echo "lifecycle validate should reject session paths boot cannot discover" >&2
  exit 1
fi
rm -f "$bad_session_name"

if "$session_cli" write --workspace-root "$repo" --trigger test --thread-id t --title "No runtime" --summary "x" --workspace-changes "none recorded" --no-input >/dev/null 2>&1; then
  echo "session-memory write should require a runtime" >&2
  exit 1
fi

stdin_write_output="$(cat <<'JSON' | "$session_cli" write --workspace-root "$repo" --stdin-json --no-input
{
  "trigger": "test",
  "threadId": "thread-test",
  "runtime": "codex",
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

if "$session_cli" write --workspace-root "$repo" --trigger test --runtime codex --title "Missing summary" --workspace-changes "No durable workspace changes besides this session-memory record." --no-input >/dev/null; then
  echo "session-memory write should reject empty summary" >&2
  exit 1
fi

runtime_write_output="$("$session_cli" write \
  --workspace-root "$repo" \
  --trigger test \
  --thread-id session-claude-test \
  --runtime claude \
  --title "Claude session memory" \
  --summary "Runtime-tagged record." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
  --no-input)"
runtime_session_path="$(python3 - "$runtime_write_output" <<'PY'
import json, sys
data = json.loads(sys.argv[1])["data"]
assert data["record"]["runtime"] == "claude", data
print(data["path"])
PY
)"

bad_folder="$repo/memory/sessions/2026/05/25-040506"
mkdir -p "$bad_folder"
cp "$runtime_session_path/summary.md" "$bad_folder/summary.md"
python3 - "$runtime_session_path/meta.json" "$bad_folder/meta.json" <<'PY'
import json, sys
meta = json.loads(open(sys.argv[1]).read())
meta["runtime"] = "gemini"
open(sys.argv[2], "w").write(json.dumps(meta))
PY
if "$session_cli" validate "$bad_folder" --no-input >/dev/null; then
  echo "session-memory validate should reject unknown runtime values" >&2
  exit 1
fi
python3 - "$runtime_session_path/meta.json" "$bad_folder/meta.json" <<'PY'
import json, sys
meta = json.loads(open(sys.argv[1]).read())
meta["surfaceKey"] = "legacy"
open(sys.argv[2], "w").write(json.dumps(meta))
PY
if "$session_cli" validate "$bad_folder" --no-input >/dev/null; then
  echo "session-memory validate should reject unsupported schema keys" >&2
  exit 1
fi
cp "$runtime_session_path/meta.json" "$bad_folder/meta.json"
printf '# Ok\n\nbody without the required section\n' >"$bad_folder/summary.md"
if "$session_cli" validate "$bad_folder" --no-input >/dev/null; then
  echo "session-memory validate should reject summary.md without a workspace-changes section" >&2
  exit 1
fi
rm -rf "$bad_folder"

mkdir -p "$repo/memory/sessions/2026/05"
cat >"$repo/memory/sessions/2026/05/25-010203.md" <<'MD'
# Legacy

- Keep this migrated.
MD
"$session_cli" migrate-md --workspace-root "$repo" --apply --delete-source --no-input >/dev/null
if [[ ! -f "$repo/memory/sessions/2026/05/25-010203/meta.json" ]]; then
  echo "session-memory migrate-md should create a session folder" >&2
  exit 1
fi
if [[ -f "$repo/memory/sessions/2026/05/25-010203.md" ]]; then
  echo "session-memory migrate-md --delete-source should remove Markdown source" >&2
  exit 1
fi

flat_card="$repo/memory/sessions/2026/05/26-090000.json"
cat >"$flat_card" <<'JSON'
{"schemaVersion":2,"createdAt":"2026-05-26T09:00:00+02:00","threadId":"flat-thread","trigger":"test","title":"Flat card","summary":"Legacy v2 card.","workspaceChanges":"No durable workspace changes besides this session-memory record."}
JSON
"$session_cli" migrate-flat --workspace-root "$repo" --apply --no-input >/dev/null
if [[ -f "$flat_card" || ! -f "$repo/memory/sessions/2026/05/26-090000/meta.json" ]]; then
  echo "session-memory migrate-flat should convert flat cards into folders" >&2
  exit 1
fi
python3 - "$repo/memory/sessions/2026/05/26-090000/meta.json" <<'PY'
import json, sys
meta = json.loads(open(sys.argv[1]).read())
assert meta["schemaVersion"] == 3, meta
assert meta["runtime"] == "codex", meta
PY

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

transcript_log="$tmp_dir/transcript-argv.json"
fake_transcript="$tmp_dir/session-transcript"
cat >"$fake_transcript" <<PY
#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ["TRANSCRIPT_LOG"]).write_text(json.dumps(sys.argv[1:]))
print(json.dumps({"schema_version": "1.0", "command": "session-transcript capture", "status": "ok", "data": {}, "error": None, "meta": {}}))
PY
chmod +x "$fake_transcript"

hook_output="$(cd "$repo" && REMEMBER_LOG="$remember_log" TRANSCRIPT_LOG="$transcript_log" \
  DOBBY_REMEMBER_SESSION_BIN="$fake_remember" DOBBY_SESSION_TRANSCRIPT_BIN="$fake_transcript" \
  "$SKILL_DIR/scripts/hooks/finalize-codex-thread" <"$payload")"
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
transcript_argv="$(cat "$transcript_log")"
if ! grep -q "capture" <<<"$transcript_argv" || ! grep -q "thread-test" <<<"$transcript_argv"; then
  echo "finalize-codex-thread hook should run session-transcript capture for the source thread" >&2
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
claude_instruction_output="$("$SKILL_DIR/scripts/remember-claude-session" \
  --session-id claude-session-test \
  --workspace-root "$repo" \
  --trigger codexclaw-chat-end \
  --print-instruction \
  --plain \
  --no-input)"
if ! grep -q '"sourceRuntime": "claude"' <<<"$claude_instruction_output"; then
  echo "remember-claude-session prompt should carry the claude runtime tag" >&2
  exit 1
fi
if grep -q "{{" <<<"$claude_instruction_output"; then
  echo "remember-claude-session --print-instruction should not leave template placeholders" >&2
  exit 1
fi

fake_claude="$tmp_dir/fake-claude"
claude_argv_log="$tmp_dir/claude-argv.json"
cat >"$fake_claude" <<PY
#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ["CLAUDE_ARGV_LOG"]).write_text(json.dumps(sys.argv[1:]))
print("No memory changes needed")
PY
chmod +x "$fake_claude"
claude_payload="$tmp_dir/claude-finalize-payload.json"
cat >"$claude_payload" <<JSON
{
  "schema_version": "1.0",
  "hook_event_name": "FinalizeClaudeSession",
  "session_id": "claude-session-test",
  "reason": "stale-cleanup"
}
JSON
claude_transcript_log="$tmp_dir/claude-transcript-argv.json"
claude_hook_output="$(cd "$repo" && CLAUDE_ARGV_LOG="$claude_argv_log" DOBBY_CLAUDE_BIN="$fake_claude" \
  TRANSCRIPT_LOG="$claude_transcript_log" DOBBY_SESSION_TRANSCRIPT_BIN="$fake_transcript" \
  "$SKILL_DIR/scripts/hooks/finalize-claude-session" <"$claude_payload")"
if ! grep -q '"command": "remember-claude-session"' <<<"$claude_hook_output"; then
  echo "finalize-claude-session hook should run remember-claude-session" >&2
  exit 1
fi
claude_argv="$(cat "$claude_argv_log")"
if ! grep -q -- "--resume" <<<"$claude_argv" || ! grep -q "claude-session-test" <<<"$claude_argv"; then
  echo "remember-claude-session should resume the source session id" >&2
  exit 1
fi
if ! grep -q -- "-p" <<<"$claude_argv"; then
  echo "remember-claude-session should run claude headless with -p" >&2
  exit 1
fi
claude_transcript_argv="$(cat "$claude_transcript_log")"
if ! grep -q "capture" <<<"$claude_transcript_argv" || ! grep -q "claude-session-test" <<<"$claude_transcript_argv"; then
  echo "finalize-claude-session hook should run session-transcript capture for the session" >&2
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

# --- session-transcript: normalize raw transcripts and capture them into session folders ---
transcript_cli="$SKILL_DIR/scripts/session-transcript"

fake_claude_projects="$tmp_dir/claude-projects/-tmp-repo"
mkdir -p "$fake_claude_projects"
cat >"$fake_claude_projects/claude-raw-test.jsonl" <<'JSONL'
{"type":"user","sessionId":"claude-raw-test","cwd":"/tmp/repo","timestamp":"2026-06-10T10:00:00.000Z","message":{"role":"user","content":"Hello, can you check the tests?"}}
{"type":"assistant","sessionId":"claude-raw-test","cwd":"/tmp/repo","timestamp":"2026-06-10T10:00:05.000Z","message":{"id":"msg_1","model":"claude-test-1","role":"assistant","usage":{"input_tokens":100,"cache_read_input_tokens":900,"output_tokens":50},"content":[{"type":"text","text":"Sure, checking now."},{"type":"tool_use","id":"tu_1","name":"Bash","input":{}}]}}
{"type":"user","sessionId":"claude-raw-test","cwd":"/tmp/repo","timestamp":"2026-06-10T10:00:09.000Z","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_1","is_error":true,"content":"command not found: pytest"}]}}
{"type":"assistant","sessionId":"claude-raw-test","cwd":"/tmp/repo","timestamp":"2026-06-10T10:00:10.000Z","message":{"id":"msg_2","model":"claude-test-1","role":"assistant","usage":{"input_tokens":120,"cache_read_input_tokens":900,"output_tokens":30},"content":[{"type":"text","text":"Tests are green."}]}}
JSONL

claude_dialogue="$(CLAUDE_PROJECTS_DIR="$tmp_dir/claude-projects" "$transcript_cli" render \
  --raw "$fake_claude_projects/claude-raw-test.jsonl" --runtime claude --plain --no-input)"
for needle in "runtime: claude" "normalizer: v" "## User" "## Agent" "Hello, can you check the tests?" "Tests are green." "tools: Bash" "tool error: Bash"; do
  if ! grep -q "$needle" <<<"$claude_dialogue"; then
    echo "claude dialogue render missing: $needle" >&2
    exit 1
  fi
done

fake_codex_sessions="$tmp_dir/codex-sessions/2026/06/10"
mkdir -p "$fake_codex_sessions"
cat >"$fake_codex_sessions/rollout-2026-06-10T10-00-00-codex-raw-test.jsonl" <<'JSONL'
{"timestamp":"2026-06-10T10:00:00.000Z","type":"session_meta","payload":{"id":"codex-raw-test","cwd":"/tmp/repo"}}
{"timestamp":"2026-06-10T10:00:01.000Z","type":"turn_context","payload":{"cwd":"/tmp/repo","model":"gpt-test"}}
{"timestamp":"2026-06-10T10:00:02.000Z","type":"event_msg","payload":{"type":"user_message","message":"Please rename the helper."}}
{"timestamp":"2026-06-10T10:00:03.000Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{}","call_id":"c1"}}
{"timestamp":"2026-06-10T10:00:04.000Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Renamed and verified."}]}}
{"timestamp":"2026-06-10T10:00:05.000Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"total_tokens":12345,"output_tokens":678}}}}
JSONL

codex_dialogue="$(CODEX_SESSIONS_DIR="$tmp_dir/codex-sessions" "$transcript_cli" render \
  --raw "$fake_codex_sessions/rollout-2026-06-10T10-00-00-codex-raw-test.jsonl" --runtime codex --plain --no-input)"
for needle in "runtime: codex" "model: gpt-test" "Please rename the helper." "Renamed and verified." "tools: exec_command" "cumulative ~12,345"; do
  if ! grep -q "$needle" <<<"$codex_dialogue"; then
    echo "codex dialogue render missing: $needle" >&2
    exit 1
  fi
done

capture_write_output="$("$session_cli" write \
  --workspace-root "$repo" \
  --trigger test \
  --thread-id claude-raw-test \
  --runtime claude \
  --title "Capture test" \
  --summary "Session whose transcript we capture." \
  --workspace-changes "No durable workspace changes besides this session-memory record." \
  --no-input)"
capture_session_path="$(python3 - "$capture_write_output" <<'PY'
import json, sys
print(json.loads(sys.argv[1])["data"]["path"])
PY
)"
CLAUDE_PROJECTS_DIR="$tmp_dir/claude-projects" "$transcript_cli" capture \
  --workspace-root "$repo" --thread-id claude-raw-test --no-input >/dev/null
if [[ ! -f "$capture_session_path/raw.jsonl" || ! -f "$capture_session_path/dialogue.md" ]]; then
  echo "session-transcript capture should write raw.jsonl + dialogue.md into the session folder" >&2
  exit 1
fi
python3 - "$capture_session_path/meta.json" <<'PY'
import json, sys
meta = json.loads(open(sys.argv[1]).read())
assert meta.get("cwd") == "/tmp/repo", meta
PY

backfill_output="$(CLAUDE_PROJECTS_DIR="$tmp_dir/claude-projects" CODEX_SESSIONS_DIR="$tmp_dir/codex-sessions" \
  CODEX_ARCHIVED_SESSIONS_DIR="$tmp_dir/codex-archived" "$transcript_cli" backfill --workspace-root "$repo" --apply --no-input)"
python3 - "$backfill_output" <<'PY'
import json, sys
data = json.loads(sys.argv[1])["data"]
assert data["apply"] is True, data
# the capture-test folder is already complete; others have no matching raw
assert data["alreadyComplete"] >= 1, data
PY

# --- dream-memory: proposal-only dreaming runner ---
dream_cli="$SKILL_DIR/scripts/dream-memory"

dream_instruction="$("$dream_cli" --workspace-root "$repo" --print-instruction --plain --no-input)"
for needle in "proposal-only" "dialogue.md" "report.md" "run.json" "noop"; do
  if ! grep -q "$needle" <<<"$dream_instruction"; then
    echo "dream-memory instruction missing: $needle" >&2
    exit 1
  fi
done
if grep -q "{{" <<<"$dream_instruction"; then
  echo "dream-memory instruction should not leave template placeholders" >&2
  exit 1
fi

fake_dreamer="$tmp_dir/fake-dreamer"
cat >"$fake_dreamer" <<'PY'
#!/usr/bin/env python3
import json, pathlib, re, sys
instruction = sys.argv[-1]
match = re.search(r'"runDir": "([^"]+)"', instruction)
run_dir = pathlib.Path(match.group(1))
run_id = run_dir.name
(run_dir / "report.md").write_text("# Dream-memory run\n\n## Run\nok\n")
(run_dir / "run.json").write_text(json.dumps({
    "schemaVersion": 1,
    "runId": run_id,
    "window": {"from": "x", "to": "y", "days": 7},
    "status": "ok",
    "counts": {"candidates": 1, "noop": 1, "flags": 0, "byCategory": {"noop": 1}},
    "candidates": [{"id": "noop-1", "category": "noop", "why": "test"}],
}))
print("dream written")
PY
chmod +x "$fake_dreamer"

dream_output="$(DOBBY_CLAUDE_BIN="$fake_dreamer" "$dream_cli" --workspace-root "$repo" --json --no-input)"
python3 - "$dream_output" "$repo" <<'PY'
import json, pathlib, sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
data = payload["data"]
run_dir = pathlib.Path(data["runDir"])
assert (run_dir / "report.md").is_file()
assert (run_dir / "run.json").is_file()
assert (run_dir / "inputs.manifest.json").is_file()
assert (run_dir / "events.jsonl").is_file()
assert data["validation"]["valid"] is True, data["validation"]
assert data["validation"]["counts"]["candidates"] == 1
manifest = json.loads((run_dir / "inputs.manifest.json").read_text())
assert manifest["counts"]["sessions"] >= 1, manifest["counts"]
PY
