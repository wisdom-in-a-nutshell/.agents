from __future__ import annotations

import json
import sys

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_text


class CopilotSyncTests(TempDirTestCase):
    def test_apply_renders_settings_trust_and_launcher(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        agents_repo = github_root / "agents"
        app_support = home / "Library/Application Support/com.github.githubapp"
        real_cli = self.temp_path / "real-copilot"

        agents_repo.mkdir(parents=True)
        (home / ".agents").mkdir(parents=True)
        write_text(real_cli, "#!/usr/bin/env bash\nprintf 'copilot stub\\n'\n")
        real_cli.chmod(0o755)
        write_text(
            home / ".copilot/config.json",
            "// User settings belong in settings.json.\n// This file is managed automatically.\n"
            + json.dumps({"trustedFolders": [str(home / "existing")]}, indent=2)
            + "\n",
        )

        run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-copilot.py"),
                "--apply",
                "--settings-file",
                str(home / ".copilot/settings.json"),
                "--user-config-file",
                str(home / ".copilot/config.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
            ],
            env={"HOME": str(home)},
        )

        settings = json.loads((home / ".copilot/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["askUser"], False)
        self.assertEqual(settings["effortLevel"], "high")
        self.assertEqual(settings["banner"], "never")

        config_text = (home / ".copilot/config.json").read_text(encoding="utf-8")
        config = json.loads("\n".join(line for line in config_text.splitlines() if not line.startswith("//")))
        self.assertIn(str(github_root.resolve()), config["trustedFolders"])
        self.assertIn(str(agents_repo.resolve()), config["trustedFolders"])
        self.assertIn(str((home / ".agents").resolve()), config["trustedFolders"])

        launcher = home / "bin/copilot"
        self.assertTrue(launcher.is_file())
        self.assertTrue(launcher.stat().st_mode & 0o111)
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("--yolo", launcher_text)
        self.assertIn("--no-ask-user", launcher_text)
        self.assertIn(str(real_cli), launcher_text)

    def test_check_rejects_direct_copilot_skill_copies(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        app_support = home / "Library/Application Support/com.github.githubapp"
        real_cli = self.temp_path / "real-copilot"
        (github_root / "agents").mkdir(parents=True)
        (home / ".agents").mkdir(parents=True)
        write_text(real_cli, "#!/usr/bin/env bash\nprintf '{}\\n'\n")
        real_cli.chmod(0o755)

        apply_args = [
            sys.executable,
            str(REPO_ROOT / "scripts/sync-copilot.py"),
            "--apply",
            "--settings-file",
            str(home / ".copilot/settings.json"),
            "--user-config-file",
            str(home / ".copilot/config.json"),
            "--launcher-target",
            str(home / "bin/copilot"),
            "--real-cli-path",
            str(real_cli),
            "--github-root",
            str(github_root),
            "--app-support-dir",
            str(app_support),
        ]
        run_command(apply_args, env={"HOME": str(home)})
        write_text(home / ".copilot/skills/noise/SKILL.md", "---\nname: noise\ndescription: no\n---\n")

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-copilot.py"),
                "--check",
                "--settings-file",
                str(home / ".copilot/settings.json"),
                "--user-config-file",
                str(home / ".copilot/config.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
                "--skip-cli-probe",
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected direct Copilot skill copies", result.stderr)
