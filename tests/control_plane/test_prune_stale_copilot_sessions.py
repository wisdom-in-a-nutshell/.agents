from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.control_plane.support import REPO_ROOT, TempDirTestCase


def load_pruner_module():  # noqa: ANN202
    path = REPO_ROOT / "scripts/prune-stale-copilot-sessions.py"
    spec = importlib.util.spec_from_file_location("prune_stale_copilot_sessions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def iso_hours_ago(hours: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class PruneStaleCopilotSessionsTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.module = load_pruner_module()
        self.copilot_home = self.temp_path / ".copilot"
        self.state_root = self.copilot_home / "session-state"
        self.store = self.copilot_home / "session-store.db"
        self.lock = self.temp_path / "state/prune.lock"
        self.backup_root = self.temp_path / "state/backups"
        self.copilot_home.mkdir(parents=True)
        self.state_root.mkdir(parents=True)
        self.create_store()

    def create_store(self) -> None:
        conn = sqlite3.connect(self.store)
        with conn:
            conn.executescript(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    cwd TEXT,
                    repository TEXT,
                    host_type TEXT,
                    branch TEXT,
                    summary TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    turn_index INTEGER NOT NULL,
                    user_message TEXT,
                    assistant_response TEXT
                );
                CREATE TABLE checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    checkpoint_number INTEGER NOT NULL
                );
                CREATE TABLE session_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    file_path TEXT NOT NULL
                );
                CREATE TABLE session_refs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    ref_type TEXT NOT NULL,
                    ref_value TEXT NOT NULL
                );
                CREATE TABLE forge_trajectory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    event_type TEXT NOT NULL
                );
                """
            )
        conn.close()

    def insert_session(self, session_id: str, *, updated_at: str) -> None:
        conn = sqlite3.connect(self.store)
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (id, cwd, repository, host_type, branch, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    "/Users/dobby/GitHub/example",
                    "wisdom-in-a-nutshell/example",
                    "github",
                    "main",
                    f"summary {session_id}",
                    updated_at,
                    updated_at,
                ),
            )
            conn.execute(
                "INSERT INTO turns (session_id, turn_index, user_message) VALUES (?, ?, ?)",
                (session_id, 1, "hello"),
            )
            conn.execute(
                "INSERT INTO checkpoints (session_id, checkpoint_number) VALUES (?, ?)",
                (session_id, 1),
            )
            conn.execute(
                "INSERT INTO session_files (session_id, file_path) VALUES (?, ?)",
                (session_id, "file.txt"),
            )
            conn.execute(
                "INSERT INTO session_refs (session_id, ref_type, ref_value) VALUES (?, ?, ?)",
                (session_id, "file", "file.txt"),
            )
            conn.execute(
                "INSERT INTO forge_trajectory_events (session_id, event_type) VALUES (?, ?)",
                (session_id, "tool"),
            )
        conn.close()
        self.write_workspace(session_id, updated_at=updated_at)

    def write_workspace(self, session_id: str, *, updated_at: str) -> Path:
        path = self.state_root / session_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "workspace.yaml").write_text(
            "\n".join(
                [
                    f"id: {session_id}",
                    "cwd: /Users/dobby/GitHub/example",
                    "repository: wisdom-in-a-nutshell/example",
                    "host_type: github",
                    "branch: main",
                    "created_at: 2026-01-01T00:00:00.000Z",
                    f"updated_at: {updated_at}",
                    "summary: fixture",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def make_args(self, *, apply: bool):  # noqa: ANN202
        argv = [
            "--copilot-home",
            str(self.copilot_home),
            "--lock",
            str(self.lock),
            "--backup-root",
            str(self.backup_root),
            "--older-than-hours",
            "24",
            "--max-report",
            "0",
        ]
        argv.append("--apply" if apply else "--dry-run")
        return self.module.parse_args(argv)

    def store_count(self, table: str, session_id: str) -> int:
        conn = sqlite3.connect(self.store)
        try:
            value = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE session_id = ?"
                if table != "sessions"
                else "SELECT COUNT(*) FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()[0]
            return int(value)
        finally:
            conn.close()

    def test_dry_run_selects_stale_but_writes_nothing(self) -> None:
        old_id = "11111111-1111-4111-8111-111111111111"
        recent_id = "22222222-2222-4222-8222-222222222222"
        self.insert_session(old_id, updated_at=iso_hours_ago(48))
        self.insert_session(recent_id, updated_at=iso_hours_ago(1))

        data = self.module.run(self.make_args(apply=False))

        self.assertFalse(data["applied"])
        self.assertEqual(data["pruned_count"], 1)
        decisions = {item["session_id"]: item for item in data["sessions"]}
        self.assertEqual(decisions[old_id]["decision"], "prune")
        self.assertEqual(decisions[recent_id]["decision"], "keep")
        self.assertEqual(self.store_count("sessions", old_id), 1)
        self.assertTrue((self.state_root / old_id).is_dir())
        self.assertIsNone(data["backup_dir"])

    def test_apply_prunes_store_rows_state_dir_and_writes_backup(self) -> None:
        old_id = "33333333-3333-4333-8333-333333333333"
        recent_id = "44444444-4444-4444-8444-444444444444"
        self.insert_session(old_id, updated_at=iso_hours_ago(48))
        self.insert_session(recent_id, updated_at=iso_hours_ago(1))

        data = self.module.run(self.make_args(apply=True))

        self.assertTrue(data["applied"])
        self.assertEqual(data["pruned_count"], 1)
        self.assertEqual(self.store_count("sessions", old_id), 0)
        for table in (
            "turns",
            "checkpoints",
            "session_files",
            "session_refs",
            "forge_trajectory_events",
        ):
            self.assertEqual(self.store_count(table, old_id), 0)
        self.assertEqual(self.store_count("sessions", recent_id), 1)
        self.assertFalse((self.state_root / old_id).exists())
        self.assertTrue((self.state_root / recent_id).is_dir())
        backup_dir = Path(data["backup_dir"])
        self.assertTrue((backup_dir / "session-store.db").is_file())
        self.assertTrue((backup_dir / "session-state" / old_id / "workspace.yaml").is_file())

    def test_running_session_lock_is_skipped(self) -> None:
        session_id = "55555555-5555-4555-8555-555555555555"
        self.insert_session(session_id, updated_at=iso_hours_ago(48))
        (self.state_root / session_id / f"inuse.{os.getpid()}.lock").write_text("", encoding="utf-8")

        data = self.module.run(self.make_args(apply=True))

        self.assertEqual(data["pruned_count"], 0)
        self.assertEqual(data["sessions"][0]["decision"], "keep")
        self.assertEqual(data["sessions"][0]["reason"], "running")
        self.assertEqual(self.store_count("sessions", session_id), 1)
        self.assertTrue((self.state_root / session_id).is_dir())

    def test_unindexed_stale_state_dir_is_pruned_by_default(self) -> None:
        session_id = "66666666-6666-4666-8666-666666666666"
        self.write_workspace(session_id, updated_at=iso_hours_ago(72))

        data = self.module.run(self.make_args(apply=True))

        self.assertEqual(data["unindexed_count"], 1)
        self.assertEqual(data["pruned_count"], 1)
        self.assertFalse((self.state_root / session_id).exists())

    def test_schema_drift_aborts_without_deleting_state(self) -> None:
        self.store.unlink()
        conn = sqlite3.connect(self.store)
        with conn:
            conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.close()
        session_id = "77777777-7777-4777-8777-777777777777"
        self.write_workspace(session_id, updated_at=iso_hours_ago(72))

        with self.assertRaises(self.module.SchemaError):
            self.module.run(self.make_args(apply=True))

        self.assertTrue((self.state_root / session_id).is_dir())
