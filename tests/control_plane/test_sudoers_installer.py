from __future__ import annotations

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command


class SudoersInstallerTests(TempDirTestCase):
    def test_default_mode_is_dry_run(self) -> None:
        target = self.temp_path / "codex-ops"

        result = run_command(
            [
                str(REPO_ROOT / "codex/scripts/install-sudoers-codex-ops.sh"),
                "--user",
                "test-user",
                "--file",
                str(target),
            ]
        )

        self.assertIn("test-user ALL=(root) NOPASSWD:", result.stdout)
        self.assertFalse(target.exists())

    def test_apply_no_input_fails_without_root_instead_of_prompting(self) -> None:
        target = self.temp_path / "codex-ops"

        result = run_command(
            [
                str(REPO_ROOT / "codex/scripts/install-sudoers-codex-ops.sh"),
                "--apply",
                "--no-input",
                "--user",
                "test-user",
                "--file",
                str(target),
            ],
            check=False,
        )

        if result.returncode == 0:
            self.skipTest("test process is running as root")

        self.assertEqual(result.returncode, 3)
        self.assertIn("--no-input forbids prompting", result.stderr)
        self.assertFalse(target.exists())
