from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from tests.control_plane.support import REPO_ROOT, TempDirTestCase


def load_audit_module():  # noqa: ANN202
    path = REPO_ROOT / "scripts/audit-agent-runtime-drift.py"
    spec = importlib.util.spec_from_file_location("audit_agent_runtime_drift", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


NOW_MS = int(time.time() * 1000)
HOUR_MS = 3600 * 1000


class ClaudeSessionArchiverAuditTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.module = load_audit_module()
        self.support_dir = self.temp_path / "Claude"
        self.empty_handshakes = str(self.temp_path / "handshakes" / "*.json")

    def write_session(self, session_id: str, *, last_activity_ms: int, drop_key: str | None = None) -> Path:
        payload = {
            "sessionId": session_id,
            "cliSessionId": f"cli-{session_id}",
            "title": "Fixture",
            "isArchived": False,
            "lastActivityAt": last_activity_ms,
            "cwd": "/Users/dobby/GitHub/example",
        }
        if drop_key:
            payload.pop(drop_key, None)
        path = self.support_dir / "claude-code-sessions" / "ws" / "acct" / f"{session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        return path

    def call(self):  # noqa: ANN202
        return self.module.audit_claude_session_archiver(
            REPO_ROOT,
            self.temp_path,
            timeout_sec=30,
            support_dir=self.support_dir,
            handshake_glob=self.empty_handshakes,
        )

    def test_skipped_when_no_session_store(self) -> None:
        result = self.call()
        self.assertEqual(result["name"], "claude_session_archiver")
        self.assertEqual(result["status"], "skipped")

    def test_ok_when_sessions_parse(self) -> None:
        self.write_session("local_stale", last_activity_ms=NOW_MS - 48 * HOUR_MS)
        result = self.call()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["details"]["scanned"], 1)

    def test_error_on_schema_drift(self) -> None:
        # A session-shaped file missing lastActivityAt is schema drift.
        self.write_session("local_broken", last_activity_ms=NOW_MS, drop_key="lastActivityAt")
        result = self.call()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "E_CLAUDE_SESSION_SCHEMA_DRIFT")
        self.assertIn("schema", result["summary"].lower())
