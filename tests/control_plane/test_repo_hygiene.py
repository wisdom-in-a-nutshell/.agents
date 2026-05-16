from __future__ import annotations

import sys

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_text


class RepoHygieneTests(TempDirTestCase):
    def test_repo_hygiene_script_passes_current_repo(self) -> None:
        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/check-repo-hygiene.py"),
                "--root",
                str(REPO_ROOT),
            ]
        )

        self.assertIn("OK: repo hygiene checks passed.", result.stdout)

    def test_runtime_backup_files_are_not_present_in_repo_tree(self) -> None:
        backups = [
            path
            for path in REPO_ROOT.rglob("*.bak.*")
            if ".git" not in path.parts and ".cache" not in path.parts
        ]

        self.assertEqual([], [str(path.relative_to(REPO_ROOT)) for path in backups])

    def test_runtime_backup_patterns_are_ignored(self) -> None:
        result = run_command(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "check-ignore",
                ".codex/config.toml.bak.20990101-000000",
            ]
        )

        ignored = set(result.stdout.splitlines())
        self.assertEqual(
            {
                ".codex/config.toml.bak.20990101-000000",
            },
            ignored,
        )

    def test_repo_hygiene_script_rejects_backup_artifact(self) -> None:
        root = self.temp_path / "repo"
        write_text(root / "note.md", "# Note\n")
        write_text(root / "config.toml.bak.20990101-000000", "stale\n")

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/check-repo-hygiene.py"),
                "--root",
                str(root),
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("backup/scratch artifact", result.stderr)

    def test_repo_hygiene_script_rejects_broken_symlink(self) -> None:
        root = self.temp_path / "repo"
        root.mkdir(parents=True)
        (root / "missing-link").symlink_to("missing-target")

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/check-repo-hygiene.py"),
                "--root",
                str(root),
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("broken symlink", result.stderr)

    def test_repo_hygiene_script_rejects_broken_local_markdown_link(self) -> None:
        root = self.temp_path / "repo"
        write_text(root / "docs" / "index.md", "[Missing](missing.md)\n")

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/check-repo-hygiene.py"),
                "--root",
                str(root),
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("broken local markdown link", result.stderr)
