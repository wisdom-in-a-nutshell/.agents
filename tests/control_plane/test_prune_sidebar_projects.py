from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command


def load_pruner_module():  # noqa: ANN202
    path = REPO_ROOT / "codex/scripts/prune-sidebar-projects.py"
    spec = importlib.util.spec_from_file_location("prune_sidebar_projects", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DummyLock:
    def close(self) -> None:
        return None


class FailingArchiveClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, params or {}))
        if method == "thread/archive":
            raise AssertionError("sidebar pruner must not archive threads")
        return {}

    def close(self) -> None:
        self.closed = True


class PruneSidebarProjectsTests(TempDirTestCase):
    def test_default_threshold_is_two_days(self) -> None:
        module = load_pruner_module()

        self.assertEqual(module.DEFAULT_DAYS, 2.0)

    def test_help_does_not_expose_thread_archive_controls(self) -> None:
        result = run_command(
            [
                str(REPO_ROOT / "codex/scripts/prune-sidebar-projects.py"),
                "--help",
            ]
        )

        self.assertNotIn("--no-archive-stale-threads", result.stdout)
        self.assertNotIn("--max-archive", result.stdout)
        self.assertNotIn("--exclude-archived-activity", result.stdout)
        self.assertNotIn("archive eligible threads", result.stdout)

    def test_apply_prunes_sidebar_state_without_archiving_threads(self) -> None:
        module = load_pruner_module()
        root = str(self.temp_path / "stale-repo")
        state = {
            "active-workspace-roots": [],
            "electron-persisted-atom-state": {},
            "electron-saved-workspace-roots": [root],
            "project-order": [root],
            "remote-projects": [],
        }
        written_states: list[dict[str, Any]] = []
        client = FailingArchiveClient()

        originals = {
            "acquire_lock": module.acquire_lock,
            "backup_state": module.backup_state,
            "load_threads_for_targets": module.load_threads_for_targets,
            "read_global_state": module.read_global_state,
            "write_global_state": module.write_global_state,
        }
        try:
            module.acquire_lock = lambda _path: DummyLock()
            module.backup_state = lambda _codex_home, _backup_root: self.temp_path / "backup"
            module.read_global_state = lambda _path: json.loads(json.dumps(state))

            def write_global_state(_path: Path, value: dict[str, Any]) -> None:
                written_states.append(json.loads(json.dumps(value)))

            def load_threads_for_targets(
                *_args: Any,
                **_kwargs: Any,
            ) -> tuple[dict[tuple[str | None, str], Any], dict[str | None, Any]]:
                return {
                    (None, root): module.ProjectActivity(
                        root=root,
                        host_id=None,
                        last_updated=100,
                        thread_ids=("thread-1",),
                    )
                }, {None: client}

            module.write_global_state = write_global_state
            module.load_threads_for_targets = load_threads_for_targets

            result = module.run(
                argparse.Namespace(
                    activity_source="app-server",
                    activity_timestamp="created_or_unarchived_updated",
                    allow_active=False,
                    apply=True,
                    backup_root=self.temp_path / "backups",
                    codex_app_name="Codex",
                    codex_bin="codex",
                    codex_home=self.temp_path / "codex-home",
                    keep_root=[],
                    lock=self.temp_path / "lock",
                    no_unsaved_thread_projects=False,
                    older_than_days=2.0,
                    older_than_hours=None,
                    page_limit=100,
                    quit_codex_app=False,
                    quit_timeout_seconds=1.0,
                    remote_host=[],
                    reopen_codex_app=False,
                    ssh_bin="ssh",
                    state_db_only=False,
                    timeout_seconds=1.0,
                )
            )
        finally:
            for name, value in originals.items():
                setattr(module, name, value)

        self.assertEqual(client.calls, [])
        self.assertTrue(client.closed)
        self.assertNotIn("archived_thread_count", result)
        self.assertEqual(result["older_than_hours"], 48.0)
        self.assertEqual(result["pruned_saved_root_count"], 1)
        self.assertEqual(written_states[0]["electron-saved-workspace-roots"], [])
        self.assertEqual(written_states[0]["project-order"], [])
        self.assertEqual(result["projects"][0]["actions"], ["prune_saved_root", "prune_project_order_root"])
