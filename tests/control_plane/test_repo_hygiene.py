from __future__ import annotations

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command


class RepoHygieneTests(TempDirTestCase):
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
                ".claude/settings.json.bak.20990101-000000",
            ]
        )

        ignored = set(result.stdout.splitlines())
        self.assertEqual(
            {
                ".codex/config.toml.bak.20990101-000000",
                ".claude/settings.json.bak.20990101-000000",
            },
            ignored,
        )
