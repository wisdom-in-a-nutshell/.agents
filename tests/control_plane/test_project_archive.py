from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills-source" / "owned" / "project" / "scripts" / "archive_project.py"


class ProjectArchiveTests(unittest.TestCase):
    def _project(self, root: Path, name: str = "alpha") -> tuple[Path, Path]:
        source = root / "docs" / "projects" / name
        destination = root / "docs" / "projects" / "archive" / name
        (source / "resources").mkdir(parents=True)
        (source / "tasks.md").write_text("# Tracker\n", encoding="utf-8")
        (source / "learnings.md").write_text("# Learnings\n", encoding="utf-8")
        (source / "resources" / "evidence.md").write_text("# Evidence\n", encoding="utf-8")
        return source, destination

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_default_moves_complete_tree_and_removes_active_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = self._project(Path(tmp))
            result = self._run(
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--no-input",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertEqual(payload["command"], "project archive")
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["data"]["applied"])
            self.assertTrue(payload["data"]["source_removed"])
            self.assertTrue(payload["data"]["destination_created"])
            self.assertEqual(payload["data"]["file_count"], 3)
            self.assertFalse(source.exists())
            self.assertTrue((destination / "tasks.md").is_file())
            self.assertTrue((destination / "resources" / "evidence.md").is_file())

    def test_dry_run_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = self._project(Path(tmp))
            result = self._run(
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--dry-run",
                "--no-input",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["data"]["applied"])
            self.assertFalse(payload["data"]["source_removed"])
            self.assertEqual(payload["data"]["file_count"], 3)
            self.assertTrue(source.is_dir())
            self.assertFalse(destination.exists())

    def test_existing_archive_root_moves_complete_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = self._project(Path(tmp))
            destination.parent.mkdir(parents=True)
            (destination.parent / "older-project").mkdir()

            result = self._run(
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--no-input",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["data"]["source_removed"])
            self.assertTrue(payload["data"]["destination_created"])
            self.assertFalse(source.exists())
            self.assertTrue((destination / "tasks.md").is_file())
            self.assertTrue((destination.parent / "older-project").is_dir())

    def test_existing_destination_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = self._project(Path(tmp))
            destination.mkdir(parents=True)
            (destination / "tasks.md").write_text("# Existing\n", encoding="utf-8")
            result = self._run(
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--no-input",
            )

            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"]["code"], "E_DESTINATION_EXISTS")
            self.assertTrue(source.is_dir())
            self.assertEqual((destination / "tasks.md").read_text(encoding="utf-8"), "# Existing\n")

    def test_invalid_archive_layout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, _ = self._project(Path(tmp))
            invalid_destination = source.parent / "completed" / source.name
            result = self._run(
                "--source",
                str(source),
                "--destination",
                str(invalid_destination),
                "--no-input",
            )

            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error"]["code"], "E_INVALID_ARCHIVE_LAYOUT")
            self.assertTrue(source.is_dir())
            self.assertFalse(invalid_destination.exists())


if __name__ == "__main__":
    unittest.main()
