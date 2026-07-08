from __future__ import annotations

import sys

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_text


class GrokSyncTests(TempDirTestCase):
    def test_apply_renders_managed_config(self) -> None:
        source = write_text(
            self.temp_path / "grok-managed-config.toml",
            "[compat.claude]\nhooks = false\n",
        )
        target = self.temp_path / "home/.grok/managed_config.toml"
        write_text(target, "[compat.claude]\nhooks = true\n")

        run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-grok.py"),
                "--apply",
                "--no-skip-if-uninstalled",
                "--source",
                str(source),
                "--target",
                str(target),
            ]
        )

        self.assertEqual(source.read_text(encoding="utf-8"), target.read_text(encoding="utf-8"))

    def test_check_detects_drift(self) -> None:
        source = write_text(
            self.temp_path / "grok-managed-config.toml",
            "[compat.claude]\nhooks = false\n",
        )
        target = write_text(
            self.temp_path / "home/.grok/managed_config.toml",
            "[compat.claude]\nhooks = true\n",
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-grok.py"),
                "--check",
                "--no-skip-if-uninstalled",
                "--source",
                str(source),
                "--target",
                str(target),
            ],
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("OUT-OF-SYNC", result.stderr)

    def test_skips_when_runtime_home_is_absent_and_grok_is_not_installed(self) -> None:
        source = write_text(
            self.temp_path / "grok-managed-config.toml",
            "[compat.claude]\nhooks = false\n",
        )
        target = self.temp_path / "home/.grok/managed_config.toml"

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-grok.py"),
                "--check",
                "--source",
                str(source),
                "--target",
                str(target),
            ],
            env={"PATH": ""},
        )

        self.assertEqual(0, result.returncode)
        self.assertIn("SKIP", result.stdout)
        self.assertFalse(target.exists())
