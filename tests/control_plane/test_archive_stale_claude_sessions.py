from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from tests.control_plane.support import REPO_ROOT, TempDirTestCase


def load_archiver_module():  # noqa: ANN202
    path = REPO_ROOT / "codex/scripts/archive-stale-claude-sessions.py"
    spec = importlib.util.spec_from_file_location("archive_stale_claude_sessions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


NOW_MS = int(time.time() * 1000)
HOUR_MS = 3600 * 1000


class ArchiveStaleClaudeSessionsTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.module = load_archiver_module()
        self.support_dir = self.temp_path / "Claude"
        self.handshake_dir = self.temp_path / "handshakes"
        self.handshake_dir.mkdir(parents=True, exist_ok=True)
        self.lock = self.temp_path / "state/archive.lock"
        self.backup_root = self.temp_path / "state/backups"

    # --- fixtures -----------------------------------------------------------

    def write_session(
        self,
        session_id: str,
        *,
        last_activity_ms: int,
        is_archived: bool = False,
        cli_session_id: str | None = None,
        group: str = "claude-code-sessions",
        title: str = "Fixture session",
        extra: dict[str, Any] | None = None,
        drop_key: str | None = None,
    ) -> Path:
        payload: dict[str, Any] = {
            "sessionId": session_id,
            "cliSessionId": cli_session_id or f"cli-{session_id}",
            "title": title,
            "isArchived": is_archived,
            "lastActivityAt": last_activity_ms,
            "cwd": "/Users/dobby/GitHub/example",
        }
        if extra:
            payload.update(extra)
        if drop_key:
            payload.pop(drop_key, None)
        path = self.support_dir / group / "workspace-1" / "account-1" / f"{session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        return path

    def write_handshake(self, name: str, *, pid: int, session_id: str) -> Path:
        path = self.handshake_dir / f"{name}.json"
        path.write_text(
            json.dumps({"pid": pid, "sessionId": session_id}), encoding="utf-8"
        )
        return path

    def make_args(self, *, apply: bool):  # noqa: ANN202
        argv = [
            "--support-dir",
            str(self.support_dir),
            "--handshake-glob",
            str(self.handshake_dir / "*.json"),
            "--lock",
            str(self.lock),
            "--backup-root",
            str(self.backup_root),
        ]
        argv.append("--apply" if apply else "--dry-run")
        return self.module.parse_args(argv)

    def is_archived_on_disk(self, path: Path) -> bool:
        return json.loads(path.read_text(encoding="utf-8"))["isArchived"]

    # --- tests --------------------------------------------------------------

    def test_dry_run_selects_stale_but_writes_nothing(self) -> None:
        stale = self.write_session("local_stale", last_activity_ms=NOW_MS - 48 * HOUR_MS)
        recent = self.write_session("local_recent", last_activity_ms=NOW_MS - 1 * HOUR_MS)

        data = self.module.run(self.make_args(apply=False))

        self.assertFalse(data["applied"])
        self.assertEqual(data["scanned"], 2)
        self.assertEqual(data["archived_count"], 1)
        decisions = {s["session_id"]: s for s in data["sessions"]}
        self.assertEqual(decisions["local_stale"]["decision"], "archive")
        self.assertEqual(decisions["local_recent"]["decision"], "keep")
        # Nothing written on disk in dry-run.
        self.assertFalse(self.is_archived_on_disk(stale))
        self.assertFalse(self.is_archived_on_disk(recent))
        self.assertIsNone(data["backup_dir"])

    def test_apply_archives_only_stale_and_backs_up(self) -> None:
        stale = self.write_session("local_stale", last_activity_ms=NOW_MS - 48 * HOUR_MS)
        recent = self.write_session("local_recent", last_activity_ms=NOW_MS - 1 * HOUR_MS)
        already = self.write_session(
            "local_already", last_activity_ms=NOW_MS - 72 * HOUR_MS, is_archived=True
        )
        agent_mode = self.write_session(
            "local_agentmode",
            last_activity_ms=NOW_MS - 48 * HOUR_MS,
            group="local-agent-mode-sessions",
        )

        data = self.module.run(self.make_args(apply=True))

        self.assertTrue(data["applied"])
        self.assertEqual(data["archived_count"], 2)  # stale + agent_mode
        self.assertTrue(self.is_archived_on_disk(stale))
        self.assertTrue(self.is_archived_on_disk(agent_mode))
        self.assertFalse(self.is_archived_on_disk(recent))
        self.assertTrue(self.is_archived_on_disk(already))  # untouched, stays archived
        # Backup of the changed files exists.
        backup_dir = Path(data["backup_dir"])
        self.assertTrue(backup_dir.is_dir())
        backups = list(backup_dir.rglob("*.json"))
        self.assertEqual(len(backups), 2)
        # The compact JSON shape is preserved (single line, no spaces after separators).
        self.assertNotIn(", ", stale.read_text(encoding="utf-8"))

    def test_running_session_is_skipped(self) -> None:
        # A stale session whose cliSessionId belongs to a live process must be kept.
        self.write_session(
            "local_running",
            last_activity_ms=NOW_MS - 48 * HOUR_MS,
            cli_session_id="cli-live-123",
        )
        self.write_handshake("proc", pid=os.getpid(), session_id="cli-live-123")

        data = self.module.run(self.make_args(apply=True))

        self.assertEqual(data["running_session_count"], 1)
        decision = data["sessions"][0]
        self.assertEqual(decision["decision"], "keep")
        self.assertEqual(decision["reason"], "running")
        self.assertEqual(data["archived_count"], 0)

    def test_dead_pid_handshake_does_not_protect_session(self) -> None:
        self.write_session(
            "local_stale",
            last_activity_ms=NOW_MS - 48 * HOUR_MS,
            cli_session_id="cli-dead",
        )
        # PID 2**31-1 is effectively never a live process.
        self.write_handshake("dead", pid=2_147_483_646, session_id="cli-dead")

        data = self.module.run(self.make_args(apply=True))

        self.assertEqual(data["running_session_count"], 0)
        self.assertEqual(data["archived_count"], 1)

    def test_keep_session_is_skipped(self) -> None:
        self.write_session("local_keep", last_activity_ms=NOW_MS - 48 * HOUR_MS)
        args = self.make_args(apply=True)
        args.keep_session = ["local_keep"]

        data = self.module.run(args)

        self.assertEqual(data["archived_count"], 0)
        self.assertEqual(data["sessions"][0]["reason"], "keep_session")

    def test_schema_drift_aborts_without_writing(self) -> None:
        # A session-shaped file missing lastActivityAt must abort the whole run.
        self.write_session("local_broken", last_activity_ms=NOW_MS, drop_key="lastActivityAt")
        stale = self.write_session("local_stale", last_activity_ms=NOW_MS - 48 * HOUR_MS)

        with self.assertRaises(self.module.SchemaError):
            self.module.run(self.make_args(apply=True))

        # No write happened to the otherwise-stale sibling.
        self.assertFalse(self.is_archived_on_disk(stale))

    def test_non_session_json_is_ignored(self) -> None:
        # A stray non-session JSON object must not trip the schema guard.
        stray = self.support_dir / "claude-code-sessions" / "workspace-1" / "account-1" / "index.json"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text(json.dumps({"unrelated": True}), encoding="utf-8")
        self.write_session("local_stale", last_activity_ms=NOW_MS - 48 * HOUR_MS)

        data = self.module.run(self.make_args(apply=False))

        self.assertEqual(data["scanned"], 1)
        self.assertEqual(data["archived_count"], 1)

    def test_nested_local_agent_handshake_is_ignored(self) -> None:
        # Local-agent-mode sessions can contain nested Claude working copies with
        # live process handshakes under `.claude/sessions`. Those files have a
        # sessionId but are not sidebar metadata and do not carry archive fields.
        handshake = (
            self.support_dir
            / "local-agent-mode-sessions"
            / "workspace-1"
            / "account-1"
            / "local_agent"
            / ".claude"
            / "sessions"
            / "123.json"
        )
        handshake.parent.mkdir(parents=True, exist_ok=True)
        handshake.write_text(
            json.dumps(
                {
                    "pid": 123,
                    "sessionId": "cli-session",
                    "cwd": "/tmp/claude-workspace",
                    "startedAt": NOW_MS,
                }
            ),
            encoding="utf-8",
        )
        self.write_session(
            "local_agent",
            last_activity_ms=NOW_MS - 48 * HOUR_MS,
            group="local-agent-mode-sessions",
        )

        data = self.module.run(self.make_args(apply=False))

        self.assertEqual(data["scanned"], 1)
        self.assertEqual(data["archived_count"], 1)
