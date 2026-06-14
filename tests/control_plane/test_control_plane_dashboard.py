from __future__ import annotations

import json
import plistlib
import sys

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, write_executable, write_json, write_text, run_command


class ControlPlaneDashboardDataTests(TempDirTestCase):
    def write_minimal_control_plane(self) -> None:
        root = self.temp_path
        github_root = root / "GitHub"
        adi = github_root / "adi"
        codexclaw = github_root / "codexclaw"
        adi.mkdir(parents=True)
        codexclaw.mkdir(parents=True)
        write_text(root / "skills-source/owned/global-helper/SKILL.md", "# global-helper\n")
        write_text(root / "skills-source/owned/repo-helper/SKILL.md", "# repo-helper\n")
        write_text(
            root / "plugins-source/external/build-ios-apps/skills/ios-debugger-agent/SKILL.md",
            "# ios-debugger-agent\n",
        )
        write_json(
            root / "skills/registry.json",
            {
                "managed_skills": [
                    {
                        "skill": "global-helper",
                        "origin": "owned",
                        "scope": "global",
                        "repos": [],
                        "source_path": "skills-source/owned/global-helper",
                        "upstream_ref": "-",
                    },
                    {
                        "skill": "repo-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/repo-helper",
                        "upstream_ref": "-",
                    },
                ],
                "managed_plugin_skills": [
                    {
                        "skill": "ios-debugger-agent",
                        "origin": "external",
                        "scope": "repo",
                        "repos": ["codexclaw"],
                        "source_path": "plugins-source/external/build-ios-apps/skills/ios-debugger-agent",
                        "upstream_ref": "openai-curated/build-ios-apps@0.1.2",
                        "source_plugin": "build-ios-apps",
                    }
                ],
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "local-review",
                    }
                ],
            },
        )
        write_json(
            root / "plugins/registry.json",
            {
                "version": 1,
                "managed_plugins": [
                    {
                        "plugin": "browser",
                        "marketplace": "openai-bundled",
                        "enabled": True,
                        "scope": "global",
                        "repos": [],
                        "category": "Engineering",
                    },
                    {
                        "plugin": "build-ios-apps",
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["codexclaw"],
                        "category": "Coding",
                    },
                ],
                "unmanaged_repo_local_plugins": [],
            },
        )
        write_json(
            root / "mcp/config/presets.json",
            {
                "presets": {
                    "openaiDeveloperDocs": {
                        "transport": "http",
                        "url": "https://developers.openai.com/mcp",
                    },
                    "cloudflare-docs": {
                        "transport": "http",
                        "url": "https://docs.mcp.cloudflare.com/mcp",
                    },
                },
                "global_presets": ["openaiDeveloperDocs"],
                "plugin_presets": {},
                "plugin_global_presets": [],
            },
        )
        write_json(
            root / "hooks/registry.json",
            {
                "version": 1,
                "managed_hooks": [
                    {
                        "id": "global-stop",
                        "event": "Stop",
                        "enabled": True,
                        "scope": "global",
                        "runtimes": ["codex"],
                        "timeout": 900,
                        "command": 'python3 "$HOME/GitHub/agents/hooks/scripts/stop.py"',
                    }
                ],
            },
        )
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_reasoning_effort": "high",
                    "plan_mode_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "path": str(adi),
                        "mcp_presets": ["cloudflare-docs"],
                    },
                    {
                        "path": str(codexclaw),
                    },
                ],
            },
        )
        write_json(root / "dev-servers/registry.json", {"repos": []})

    def test_data_command_emits_agent_contract_and_normalized_groups(self) -> None:
        self.write_minimal_control_plane()

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control-plane-dashboard.py"),
                "data",
                "--root",
                str(self.temp_path),
                "--no-input",
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["command"], "control-plane-dashboard data")
        self.assertEqual(payload["status"], "ok")
        self.assertIsNone(payload["error"])
        self.assertIn("request_id", payload["meta"])

        data = payload["data"]
        self.assertEqual(data["counts"]["skills"], 4)
        self.assertEqual(data["counts"]["plugins"], 2)
        self.assertEqual(data["counts"]["mcp"], 2)
        self.assertEqual(data["counts"]["repos"], 2)
        self.assertEqual(data["counts"]["hooks"], 1)
        self.assertEqual(data["counts"]["warnings"], 0)
        self.assertEqual(data["groups"]["repos"][0]["details"]["skill_count"], 3)
        self.assertEqual(data["groups"]["repos"][1]["details"]["skill_count"], 2)
        self.assertEqual(data["groups"]["repos"][0]["details"]["mcp_count"], 2)
        self.assertEqual(data["groups"]["repos"][1]["details"]["plugin_count"], 2)
        self.assertTrue(data["groups"]["repos"][0]["details"]["exists"])
        self.assertTrue(any(item["name"] == "openaiDeveloperDocs" for item in data["groups"]["mcp"]))
        plugin_skill = [
            item for item in data["groups"]["skills"] if item["name"] == "ios-debugger-agent"
        ][0]
        self.assertEqual(plugin_skill["repos"], ["codexclaw"])
        self.assertEqual(plugin_skill["title"], "build-ios-apps:ios-debugger-agent")
        self.assertEqual(plugin_skill["details"]["source_plugin"], "build-ios-apps")

    def test_data_warns_for_missing_managed_repo_path(self) -> None:
        self.write_minimal_control_plane()
        write_json(
            self.temp_path / "codex/config/repo-bootstrap.json",
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_reasoning_effort": "high",
                    "plan_mode_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "path": str(self.temp_path / "GitHub/adi"),
                    },
                    {
                        "path": str(self.temp_path / "GitHub/deleted-repo"),
                    },
                ],
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control-plane-dashboard.py"),
                "data",
                "--root",
                str(self.temp_path),
                "--no-input",
            ]
        )

        data = json.loads(result.stdout)["data"]
        warnings = data["warnings"]
        self.assertEqual(data["counts"]["warnings"], 1)
        self.assertEqual(warnings[0]["code"], "managed_repo_missing")
        self.assertIn("deleted-repo", warnings[0]["message"])
        deleted = [repo for repo in data["groups"]["repos"] if repo["name"] == "deleted-repo"][0]
        self.assertFalse(deleted["details"]["exists"])

    def test_plain_data_command_is_stable_summary(self) -> None:
        self.write_minimal_control_plane()

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control-plane-dashboard.py"),
                "data",
                "--root",
                str(self.temp_path),
                "--plain",
                "--no-input",
            ]
        )

        self.assertTrue(result.stdout.startswith("ok items="))
        self.assertIn("skills=4", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_missing_root_uses_json_error_contract(self) -> None:
        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control-plane-dashboard.py"),
                "data",
                "--root",
                str(self.temp_path / "missing"),
                "--no-input",
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "E_ROOT_NOT_FOUND")


class ControlPlaneDashboardLaunchAgentTests(TempDirTestCase):
    def test_launchagent_installer_defaults_to_shared_python_shim(self) -> None:
        home = self.temp_path / "home"
        python_shim = home / ".local/bin/python3.13-shim"
        resolver = home / "GitHub/scripts/setup/codex/resolve-preferred-homebrew-python.sh"
        write_executable(python_shim, "#!/usr/bin/env bash\nexit 0\n")
        write_executable(
            resolver,
            f"#!/usr/bin/env bash\nprintf '%s\\n' {str(python_shim)!r}\n",
        )

        result = run_command(
            [
                "bash",
                str(REPO_ROOT / "scripts/install-control-plane-dashboard-launchagent.sh"),
                "--dry-run",
                "--label",
                "com.test.agents-dashboard",
                "--root",
                str(REPO_ROOT),
            ],
            env={"HOME": str(home)},
        )

        payload = plistlib.loads(result.stdout.encode("utf-8"))
        self.assertEqual(payload["ProgramArguments"][0], str(python_shim))

    def test_launchagent_installer_dry_run_renders_dashboard_service_plist(self) -> None:
        result = run_command(
            [
                "bash",
                str(REPO_ROOT / "scripts/install-control-plane-dashboard-launchagent.sh"),
                "--dry-run",
                "--label",
                "com.test.agents-dashboard",
                "--root",
                str(REPO_ROOT),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
                "--python",
                sys.executable,
            ]
        )

        payload = plistlib.loads(result.stdout.encode("utf-8"))
        self.assertEqual(payload["Label"], "com.test.agents-dashboard")
        self.assertTrue(payload["RunAtLoad"])
        self.assertTrue(payload["KeepAlive"])
        self.assertEqual(payload["ThrottleInterval"], 60)
        self.assertEqual(payload["WorkingDirectory"], str(REPO_ROOT))
        self.assertEqual(
            payload["ProgramArguments"],
            [
                sys.executable,
                str(REPO_ROOT / "scripts/control-plane-dashboard.py"),
                "serve",
                "--root",
                str(REPO_ROOT),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
                "--no-input",
            ],
        )
