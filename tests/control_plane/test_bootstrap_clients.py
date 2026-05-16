from __future__ import annotations

import json
import sys

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_json, write_text


class BootstrapSkillClientContractTests(TempDirTestCase):
    def test_dry_run_success_defaults_to_json_contract(self) -> None:
        registry = self.temp_path / "skills" / "registry.json"
        write_json(
            registry,
            {
                "managed_skills": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_skills": [],
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-skill.py"),
                "owner/repo:skills/example-skill@main",
                "--scope",
                "global",
                "--registry-file",
                str(registry),
                "--no-input",
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["command"], "bootstrap-skill")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["error"], None)
        self.assertFalse(payload["data"]["apply"])
        self.assertEqual(payload["data"]["skill"], "example-skill")
        self.assertIn("request_id", payload["meta"])
        self.assertIn("duration_ms", payload["meta"])
        self.assertIn("timestamp_utc", payload["meta"])

    def test_validation_failure_uses_json_error_contract_and_usage_exit(self) -> None:
        registry = self.temp_path / "skills" / "registry.json"
        write_json(
            registry,
            {
                "managed_skills": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_skills": [],
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-skill.py"),
                "owner/repo:skills/example-skill@main",
                "--registry-file",
                str(registry),
                "--no-input",
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["error"]["code"], "E_REPO_REQUIRED")
        self.assertFalse(payload["error"]["retryable"])
        self.assertIn("--repo", payload["error"]["hint"])

    def test_plain_mode_is_operator_inspection_output(self) -> None:
        registry = self.temp_path / "skills" / "registry.json"
        write_json(
            registry,
            {
                "managed_skills": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_skills": [],
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-skill.py"),
                "owner/repo:skills/example-skill@main",
                "--scope",
                "global",
                "--registry-file",
                str(registry),
                "--plain",
                "--no-input",
            ]
        )

        self.assertTrue(result.stdout.startswith("ok skill=example-skill scope=global"))
        self.assertEqual(result.stderr, "")

    def test_apply_syncs_codex_skill_links_for_repo_targets(self) -> None:
        root = self.temp_path
        github_root = root / "GitHub"
        repo = github_root / "target-repo"
        repo.mkdir(parents=True)
        registry = root / "skills" / "registry.json"
        log = root / "commands.log"
        write_json(
            registry,
            {
                "managed_skills": [],
                "paths": {"github_root": str(github_root)},
                "unmanaged_repo_local_skills": [],
            },
        )
        for script in (
            "scripts/refresh-external-skills.py",
            "scripts/sync-skills-registry.py",
            "codex/scripts/sync-repo-bootstrap-registry.py",
        ):
            write_text(
                root / script,
                "\n".join(
                    [
                        "from pathlib import Path",
                        "import sys",
                        f"Path({str(log)!r}).open('a').write(' '.join(sys.argv) + '\\n')",
                    ]
                ),
            )
        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-skill.py"),
                "owner/repo:skills/example-skill@main",
                "--repo",
                "target-repo",
                "--registry-file",
                str(registry),
                "--apply",
                "--no-input",
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertIn(
            str(repo.resolve() / ".agents" / "skills" / "example-skill"),
            payload["data"]["expected_links"],
        )
        command_log = log.read_text(encoding="utf-8")
        self.assertIn("scripts/refresh-external-skills.py --apply --skill example-skill", command_log)
        self.assertIn("scripts/sync-skills-registry.py --apply", command_log)
        self.assertIn("codex/scripts/sync-repo-bootstrap-registry.py", command_log)


class BootstrapPluginClientContractTests(TempDirTestCase):
    def test_dry_run_success_defaults_to_json_contract(self) -> None:
        registry = self.temp_path / "plugins" / "registry.json"
        write_json(
            registry,
            {
                "managed_plugins": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_plugins": [],
                "version": 1,
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-plugin.py"),
                "example-plugin",
                "--registry-file",
                str(registry),
                "--no-input",
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["command"], "bootstrap-plugin")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["error"], None)
        self.assertFalse(payload["data"]["apply"])
        self.assertEqual(payload["data"]["plugin"], "example-plugin")
        self.assertEqual(payload["data"]["marketplace"], "openai-curated")
        self.assertEqual(payload["data"]["scope"], "global")
        self.assertEqual(payload["data"]["repos"], [])
        self.assertNotIn("targets", payload["data"])
        self.assertIn("request_id", payload["meta"])
        self.assertIn("duration_ms", payload["meta"])
        self.assertIn("timestamp_utc", payload["meta"])

    def test_validation_failure_uses_json_error_contract_and_usage_exit(self) -> None:
        registry = self.temp_path / "plugins" / "registry.json"
        write_json(
            registry,
            {
                "managed_plugins": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_plugins": [],
                "version": 1,
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-plugin.py"),
                "https://example.com/openai/plugins/tree/main/plugins/example-plugin",
                "--registry-file",
                str(registry),
                "--no-input",
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["data"], {})
        self.assertEqual(payload["error"]["code"], "E_INVALID_PLUGIN_REF")
        self.assertFalse(payload["error"]["retryable"])
        self.assertIn("plugin name", payload["error"]["hint"])

    def test_repo_scope_requires_repo_and_records_repo_targets(self) -> None:
        github_root = self.temp_path / "GitHub"
        repo = github_root / "target-repo"
        repo.mkdir(parents=True)
        registry = self.temp_path / "plugins" / "registry.json"
        write_json(
            registry,
            {
                "managed_plugins": [],
                "paths": {"github_root": str(github_root)},
                "unmanaged_repo_local_plugins": [],
                "version": 1,
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-plugin.py"),
                "example-plugin",
                "--scope",
                "repo",
                "--repo",
                "target-repo",
                "--registry-file",
                str(registry),
                "--no-input",
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["scope"], "repo")
        self.assertEqual(payload["data"]["repos"], ["target-repo"])
        self.assertEqual(
            payload["data"]["resolved_repo_roots"],
            {"target-repo": str(repo.resolve())},
        )

    def test_repo_scope_without_repo_is_usage_error(self) -> None:
        registry = self.temp_path / "plugins" / "registry.json"
        write_json(
            registry,
            {
                "managed_plugins": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
                "unmanaged_repo_local_plugins": [],
                "version": 1,
            },
        )

        result = run_command(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/bootstrap-plugin.py"),
                "example-plugin",
                "--scope",
                "repo",
                "--registry-file",
                str(registry),
                "--no-input",
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "E_REPO_REQUIRED")
