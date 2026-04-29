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

    def test_apply_syncs_claude_skill_links_for_repo_targets(self) -> None:
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
        write_text(
            root / "claude/scripts/sync-skills.sh",
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    f"printf '%s\\n' \"$0 $*\" >> {str(log)!r}",
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
            str(repo.resolve() / ".claude" / "skills" / "example-skill"),
            payload["data"]["expected_claude_links"],
        )
        command_log = log.read_text(encoding="utf-8")
        self.assertIn("claude/scripts/sync-skills.sh", command_log)
        self.assertIn("--apply --registry", command_log)
        self.assertIn(f"--repo {repo.resolve()}", command_log)


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
        self.assertEqual(payload["command"], "bootstrap-plugin")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["error"], None)
        self.assertFalse(payload["data"]["apply"])
        self.assertEqual(payload["data"]["plugin"], "example-plugin")
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
                "example-plugin",
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
