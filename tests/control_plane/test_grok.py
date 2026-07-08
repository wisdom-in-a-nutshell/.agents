from __future__ import annotations

import sys
import tomllib

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_text


class GrokSyncTests(TempDirTestCase):
    def test_apply_renders_managed_config(self) -> None:
        source = write_text(
            self.temp_path / "grok-config.toml",
            "[ui]\npermission_mode = \"always-approve\"\n\n"
            "[compat.claude]\nhooks = false\n",
        )
        target = self.temp_path / "home/.grok/config.toml"
        write_text(
            target,
            "[cli]\ninstaller = \"internal\"\n\n"
            "[[marketplace.sources]]\n"
            "name = \"xAI Official\"\n"
            "git = \"https://github.com/xai-org/plugin-marketplace.git\"\n\n"
            "[compat.claude]\n"
            "hooks = true\n",
        )

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

        data = tomllib.loads(target.read_text(encoding="utf-8"))
        self.assertEqual("internal", data["cli"]["installer"])
        self.assertEqual("xAI Official", data["marketplace"]["sources"][0]["name"])
        self.assertEqual("always-approve", data["ui"]["permission_mode"])
        self.assertEqual(False, data["compat"]["claude"]["hooks"])

    def test_check_detects_drift(self) -> None:
        source = write_text(
            self.temp_path / "grok-config.toml",
            "[ui]\npermission_mode = \"always-approve\"\n\n"
            "[compat.claude]\nhooks = false\n",
        )
        target = write_text(
            self.temp_path / "home/.grok/config.toml",
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
            self.temp_path / "grok-config.toml",
            "[ui]\npermission_mode = \"always-approve\"\n\n"
            "[compat.claude]\nhooks = false\n",
        )
        target = self.temp_path / "home/.grok/config.toml"

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
