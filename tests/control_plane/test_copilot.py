from __future__ import annotations

import json
import sys

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    run_command,
    write_json,
    write_text,
)


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
                "--hooks-file",
                str(home / ".copilot/hooks/agents-control-plane.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
                "--skip-global-instructions",
            ],
            env={"HOME": str(home)},
        )

        settings = json.loads((home / ".copilot/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["askUser"], False)
        self.assertEqual(settings["effortLevel"], "high")
        self.assertEqual(settings["banner"], "never")
        self.assertEqual(
            settings["disabledSkills"],
            [
                "af",
                "agent-merge",
                "agentfinder",
                "create-canvas",
                "customize-cloud-agent",
                "find-skills",
                "imagegen",
                "media-toolkit",
                "openai-docs",
                "orchestrate",
                "pdf",
                "project",
                "social-media-publishing",
            ],
        )
        self.assertNotIn("trustedFolders", settings)

        config_text = (home / ".copilot/config.json").read_text(encoding="utf-8")
        config = json.loads("\n".join(line for line in config_text.splitlines() if not line.startswith("//")))
        self.assertIn(str(github_root.resolve()), config["trustedFolders"])
        self.assertIn(str(agents_repo.resolve()), config["trustedFolders"])
        self.assertIn(str((home / ".agents").resolve()), config["trustedFolders"])
        self.assertIn(str((home / "existing").resolve()), config["trustedFolders"])

        hooks = json.loads((home / ".copilot/hooks/agents-control-plane.json").read_text(encoding="utf-8"))
        self.assertEqual(set(hooks["hooks"]), {"SessionStart", "UserPromptSubmit", "Stop"})
        self.assertIn("--runtime copilot", hooks["hooks"]["Stop"][0]["bash"])

        launcher = home / "bin/copilot"
        self.assertTrue(launcher.is_file())
        self.assertTrue(launcher.stat().st_mode & 0o111)
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn(".secrets/copilot-cli/env", launcher_text)
        self.assertIn("source \"$secret_env\"", launcher_text)
        self.assertIn("--yolo", launcher_text)
        self.assertIn("--no-ask-user", launcher_text)
        self.assertIn("--mode", launcher_text)
        self.assertIn("autopilot", launcher_text)
        self.assertIn("--max-autopilot-continues", launcher_text)
        self.assertIn("--disable-builtin-mcps", launcher_text)
        self.assertIn("--disable-mcp-server", launcher_text)
        self.assertIn("openaiDeveloperDocs", launcher_text)
        self.assertIn(str(real_cli), launcher_text)

    def test_apply_renders_github_app_preview_config(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        app_support = home / "Library/Application Support/com.github.githubapp"
        real_cli = self.temp_path / "real-copilot"
        preview_runner = home / "GitHub/agents/scripts/run-agent-preview-server.py"
        dev_servers = write_json(
            home / "GitHub/agents/dev-servers/registry.json",
            {
                "managed_dev_servers": [
                    {
                        "repo": "repo-a",
                        "servers": [
                            {
                                "name": "Preview",
                                "host": "127.0.0.1",
                                "runtimeExecutable": "pnpm",
                                "runtimeArgs": ["dev", "--host", "{host}", "--port", "{port}"],
                                "port": 3000,
                                "autoPort": False,
                            }
                        ],
                    }
                ]
            },
        )
        write_text(preview_runner, "#!/usr/bin/env python3\n")
        write_text(real_cli, "#!/usr/bin/env bash\nprintf '{}\\n'\n")
        real_cli.chmod(0o755)

        base_args = [
            sys.executable,
            str(REPO_ROOT / "scripts/sync-copilot.py"),
            "--settings-file",
            str(home / ".copilot/settings.json"),
            "--user-config-file",
            str(home / ".copilot/config.json"),
            "--hooks-file",
            str(home / ".copilot/hooks/agents-control-plane.json"),
            "--launcher-target",
            str(home / "bin/copilot"),
            "--real-cli-path",
            str(real_cli),
            "--github-root",
            str(github_root),
            "--app-support-dir",
            str(app_support),
            "--dev-servers-registry",
            str(dev_servers),
            "--preview-runner",
            str(preview_runner),
            "--skip-global-instructions",
        ]

        run_command([*base_args, "--apply"], env={"HOME": str(home)})

        config = (repo_a / ".github/github-app.yml").read_text(encoding="utf-8")
        self.assertTrue(config.startswith("# THIS IS AUTOGENERATED. DO NOT EDIT MANUALLY.\n"))
        self.assertIn("scripts:\n  run:", config)
        self.assertIn("pnpm dev --host 127.0.0.1 --port 3000", config)
        self.assertIn('${HOME}/GitHub/agents/scripts/run-agent-preview-server.py', config)
        self.assertIn("server_ready_pattern: '(?i)(https?://\\S+)'", config)
        self.assertIn("auto_open_in_browser: true", config)

        run_command([*base_args, "--check", "--skip-cli-probe"], env={"HOME": str(home)})

        write_text(repo_a / ".github/github-app.yml", "scripts: {}\n")
        result = run_command(
            [*base_args, "--check", "--skip-cli-probe"],
            env={"HOME": str(home)},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub Copilot app preview config is out of sync", result.stderr)

    def test_github_app_preview_config_uses_workspace_path_for_repo_root(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        app_support = home / "Library/Application Support/com.github.githubapp"
        real_cli = self.temp_path / "real-copilot"
        preview_runner = home / "GitHub/agents/scripts/run-agent-preview-server.py"
        dev_servers = write_json(
            home / "GitHub/agents/dev-servers/registry.json",
            {
                "managed_dev_servers": [
                    {
                        "repo": "repo-a",
                        "servers": [
                            {
                                "name": "Preview",
                                "host": "127.0.0.1",
                                "runtimeExecutable": "/bin/bash",
                                "runtimeArgs": [
                                    "-lc",
                                    "cd {repo_root} && pnpm dev --host {host} --port {port}",
                                ],
                                "port": 3001,
                                "autoPort": False,
                            }
                        ],
                    }
                ]
            },
        )
        write_text(preview_runner, "#!/usr/bin/env python3\n")
        write_text(real_cli, "#!/usr/bin/env bash\nprintf '{}\\n'\n")
        real_cli.chmod(0o755)

        run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-copilot.py"),
                "--apply",
                "--settings-file",
                str(home / ".copilot/settings.json"),
                "--user-config-file",
                str(home / ".copilot/config.json"),
                "--hooks-file",
                str(home / ".copilot/hooks/agents-control-plane.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
                "--dev-servers-registry",
                str(dev_servers),
                "--preview-runner",
                str(preview_runner),
                "--skip-global-instructions",
            ],
            env={"HOME": str(home)},
        )

        config = (repo_a / ".github/github-app.yml").read_text(encoding="utf-8")
        self.assertIn("cd ${COPILOT_WORKSPACE_PATH:-$HOME/GitHub/repo-a}", config)
        self.assertIn("pnpm dev --host 127.0.0.1 --port 3001", config)

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
            "--hooks-file",
            str(home / ".copilot/hooks/agents-control-plane.json"),
            "--launcher-target",
            str(home / "bin/copilot"),
            "--real-cli-path",
            str(real_cli),
            "--github-root",
            str(github_root),
            "--app-support-dir",
            str(app_support),
            "--skip-global-instructions",
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
                "--hooks-file",
                str(home / ".copilot/hooks/agents-control-plane.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
                "--skip-cli-probe",
                "--skip-global-instructions",
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected direct Copilot skill copies", result.stderr)

    def test_check_rejects_unexpected_app_bundled_skills(self) -> None:
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
            "--hooks-file",
            str(home / ".copilot/hooks/agents-control-plane.json"),
            "--launcher-target",
            str(home / "bin/copilot"),
            "--real-cli-path",
            str(real_cli),
            "--github-root",
            str(github_root),
            "--app-support-dir",
            str(app_support),
            "--skip-global-instructions",
        ]
        run_command(apply_args, env={"HOME": str(home)})
        write_text(app_support / "app-skills/noise/SKILL.md", "---\nname: noise\ndescription: no\n---\n")

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/sync-copilot.py"),
                "--check",
                "--settings-file",
                str(home / ".copilot/settings.json"),
                "--user-config-file",
                str(home / ".copilot/config.json"),
                "--hooks-file",
                str(home / ".copilot/hooks/agents-control-plane.json"),
                "--launcher-target",
                str(home / "bin/copilot"),
                "--real-cli-path",
                str(real_cli),
                "--github-root",
                str(github_root),
                "--app-support-dir",
                str(app_support),
                "--skip-cli-probe",
                "--skip-global-instructions",
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected Copilot app bundled skills: noise", result.stderr)

    def test_apply_renders_global_instructions_symlink(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        app_support = home / "Library/Application Support/com.github.githubapp"
        real_cli = self.temp_path / "real-copilot"
        (github_root / "agents").mkdir(parents=True)
        (home / ".agents").mkdir(parents=True)
        write_text(real_cli, "#!/usr/bin/env bash\nprintf '{}\\n'\n")
        real_cli.chmod(0o755)

        canonical_source = self.temp_path / "canonical/global.agents.md"
        write_text(canonical_source, "# Global Agent Guidance\n\nBe helpful.\n")
        instructions_target = home / ".copilot/copilot-instructions.md"

        base_args = [
            sys.executable,
            str(REPO_ROOT / "scripts/sync-copilot.py"),
            "--settings-file",
            str(home / ".copilot/settings.json"),
            "--user-config-file",
            str(home / ".copilot/config.json"),
            "--hooks-file",
            str(home / ".copilot/hooks/agents-control-plane.json"),
            "--launcher-target",
            str(home / "bin/copilot"),
            "--real-cli-path",
            str(real_cli),
            "--github-root",
            str(github_root),
            "--app-support-dir",
            str(app_support),
            "--global-instructions-source",
            str(canonical_source),
            "--global-instructions-target",
            str(instructions_target),
        ]

        run_command([*base_args, "--apply"], env={"HOME": str(home)})

        self.assertTrue(instructions_target.is_symlink())
        self.assertEqual(instructions_target.resolve(), canonical_source.resolve())
        self.assertEqual(instructions_target.read_text(encoding="utf-8"), "# Global Agent Guidance\n\nBe helpful.\n")

        run_command([*base_args, "--check", "--skip-cli-probe"], env={"HOME": str(home)})

        instructions_target.unlink()
        write_text(instructions_target, "not a symlink\n")
        result = run_command(
            [*base_args, "--check", "--skip-cli-probe"],
            env={"HOME": str(home)},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing managed Copilot global instructions symlink", result.stderr)
