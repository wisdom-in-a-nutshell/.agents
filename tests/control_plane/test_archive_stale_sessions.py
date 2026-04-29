from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command


def load_archiver_module():  # noqa: ANN202
    path = REPO_ROOT / "codex/scripts/archive-stale-sessions.py"
    spec = importlib.util.spec_from_file_location("archive_stale_sessions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeAppServerClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, params or {}))
        if not self.responses:
            raise AssertionError(f"unexpected request: {method}")
        return self.responses.pop(0)


class ArchiveStaleSessionsTests(TempDirTestCase):
    def test_candidate_selection_uses_updated_at_cutoff(self) -> None:
        module = load_archiver_module()
        client = FakeAppServerClient(
            [
                {
                    "data": [
                        {
                            "id": "old-thread",
                            "name": "Old enough",
                            "cwd": str(self.temp_path),
                            "updatedAt": 100,
                            "source": "vscode",
                            "status": {"type": "notLoaded"},
                            "path": "/tmp/old.jsonl",
                        },
                        {
                            "id": "fresh-thread",
                            "name": "Too fresh",
                            "cwd": str(self.temp_path),
                            "updatedAt": 200,
                            "source": "vscode",
                            "status": {"type": "notLoaded"},
                            "path": "/tmp/fresh.jsonl",
                        },
                    ],
                    "nextCursor": "ignored-after-cutoff",
                }
            ]
        )

        candidates = module.list_candidates(
            client,
            repos=[str(self.temp_path)],
            cutoff_epoch=150,
            page_limit=100,
            source_kinds=None,
            use_state_db_only=False,
        )

        self.assertEqual([candidate.thread_id for candidate in candidates], ["old-thread"])
        self.assertEqual(client.calls[0][0], "thread/list")
        self.assertEqual(client.calls[0][1]["sortKey"], "updated_at")
        self.assertEqual(client.calls[0][1]["sortDirection"], "asc")

    def test_help_does_not_claim_loaded_thread_detection(self) -> None:
        result = run_command(
            [
                str(REPO_ROOT / "codex/scripts/archive-stale-sessions.py"),
                "--help",
            ]
        )

        self.assertNotIn("skip-loaded", result.stdout)
        self.assertNotIn("thread/loaded", result.stdout)
