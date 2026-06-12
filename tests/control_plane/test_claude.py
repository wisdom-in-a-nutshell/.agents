from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    make_skill_source,
    run_command,
    write_json,
    write_text,
)


class ClaudeSyncTests(TempDirTestCase):
    def _write_registry(self, root: Path, skills: list[dict[str, object]]) -> Path:
        for item in skills:
            make_skill_source(root / str(item["source_path"]), str(item["skill"]))
        return write_json(
            root / "skills/registry.json",
            {
                "managed_skills": skills,
                "managed_plugin_skills": [],
                "unmanaged_repo_local_skills": [],
                "paths": {"github_root": str(self.temp_path / "GitHub")},
            },
        )

    def _isolated_targets(self, root: Path) -> list[str]:
        source = write_text(root / "config/global.agents.md", "# Global\n")
        return [
            "--global-context-source",
            str(source),
            "--global-context-target",
            str(self.temp_path / "claude/CLAUDE.md"),
            "--launcher-target",
            str(self.temp_path / "bin/claude"),
            "--real-cli-path",
            str(self.temp_path / "homebrew/bin/claude"),
        ]

    def test_apply_renders_global_skills_instructions_settings_stop_hook_and_yolo_launcher(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(
            root,
            [
                {
                    "skill": "global-one",
                    "origin": "owned",
                    "scope": "global",
                    "repos": [],
                    "source_path": "skills-source/owned/global-one",
                    "upstream_ref": "-",
                },
                {
                    "skill": "repo-only",
                    "origin": "owned",
                    "scope": "repo",
                    "repos": ["repo-a"],
                    "source_path": "skills-source/owned/repo-only",
                    "upstream_ref": "-",
                },
            ],
        )
        claude_home = self.temp_path / "claude"
        write_json(claude_home / "settings.json", {"model": "test-model"})

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        skill_link = claude_home / "skills/global-one"
        self.assertTrue(skill_link.is_symlink())
        self.assertEqual(
            (root / "skills-source/owned/global-one").resolve(),
            (skill_link.parent / os.readlink(skill_link)).resolve(),
        )
        self.assertFalse((claude_home / "skills/repo-only").exists())

        instructions = self.temp_path / "claude/CLAUDE.md"
        self.assertTrue(instructions.is_symlink())
        self.assertEqual(
            (root / "config/global.agents.md").resolve(),
            (instructions.parent / os.readlink(instructions)).resolve(),
        )

        settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual("test-model", settings["model"])
        self.assertEqual("bypassPermissions", settings["permissions"]["defaultMode"])
        self.assertEqual(True, settings["permissions"]["skipDangerousModePermissionPrompt"])
        self.assertIn("Bash", settings["permissions"]["allow"])
        self.assertIn("Workflow", settings["permissions"]["allow"])
        # Max-YOLO acceptance flags: never blocked on a one-time usage/permission dialog.
        self.assertEqual(True, settings["skipDangerousModePermissionPrompt"])
        self.assertEqual(True, settings["skipAutoPermissionPrompt"])
        self.assertEqual(True, settings["skipWorkflowUsageWarning"])
        self.assertEqual(True, settings["enableAllProjectMcpServers"])
        # Built-in git/commit/PR instructions are always disabled on this machine.
        self.assertEqual(False, settings["includeGitInstructions"])
        self.assertIn("Stop", settings["hooks"])
        self.assertNotIn("PreToolUse", settings["hooks"])
        self.assertNotIn("PermissionRequest", settings["hooks"])
        self.assertEqual(
            'python3 "$HOME/GitHub/agents/hooks/scripts/claude_stop.py"',
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
        )

        launcher = self.temp_path / "bin/claude"
        self.assertTrue(launcher.is_file())
        self.assertTrue(os.access(launcher, os.X_OK))
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("--dangerously-skip-permissions", launcher_text)
        self.assertIn("$HOME/.secrets/anthropic/env", launcher_text)
        self.assertIn(str(self.temp_path / "homebrew/bin/claude"), launcher_text)

    def test_apply_prunes_managed_auto_allow_hooks_but_preserves_custom_hooks(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        legacy_pre_tool_command = (
            "printf '%s\\n' "
            "'{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\","
            "\"permissionDecisionReason\":\"YOLO mode\"}}'"
        )
        legacy_permission_command = (
            "printf '%s\\n' "
            "'{\"hookSpecificOutput\":{\"hookEventName\":\"PermissionRequest\",\"decision\":{\"behavior\":\"allow\"}}}'"
        )
        write_json(
            claude_home / "settings.json",
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 ~/.agents/hooks/scripts/claude_stop.py",
                                },
                                {"type": "command", "command": "custom-stop"},
                            ],
                        }
                    ],
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {"type": "command", "command": legacy_pre_tool_command},
                                {"type": "command", "command": "custom-pre-tool"},
                            ],
                        }
                    ],
                    "PermissionRequest": [
                        {"hooks": [{"type": "command", "command": legacy_permission_command}]}
                    ],
                }
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [{"matcher": "*", "hooks": [{"type": "command", "command": "custom-pre-tool"}]}],
            settings["hooks"]["PreToolUse"],
        )
        self.assertNotIn("PermissionRequest", settings["hooks"])
        self.assertEqual(
            "custom-stop",
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
        )
        self.assertEqual(
            'python3 "$HOME/GitHub/agents/hooks/scripts/claude_stop.py"',
            settings["hooks"]["Stop"][1]["hooks"][0]["command"],
        )

    def test_apply_renders_repo_scoped_skills_into_repo_claude_skills(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(
            root,
            [
                {
                    "skill": "repo-only",
                    "origin": "owned",
                    "scope": "repo",
                    "repos": ["repo-a"],
                    "source_path": "skills-source/owned/repo-only",
                    "upstream_ref": "-",
                },
                {
                    "skill": "repo-b-only",
                    "origin": "owned",
                    "scope": "repo",
                    "repos": ["repo-b"],
                    "source_path": "skills-source/owned/repo-b-only",
                    "upstream_ref": "-",
                },
            ],
        )
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "repo-b")
        claude_home = self.temp_path / "claude"

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--repo",
                "repo-a",
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        repo_skill_link = repo_a / ".claude/skills/repo-only"
        self.assertTrue(repo_skill_link.is_symlink())
        self.assertEqual(
            (root / "skills-source/owned/repo-only").resolve(),
            (repo_skill_link.parent / os.readlink(repo_skill_link)).resolve(),
        )
        self.assertFalse((claude_home / "skills/repo-only").exists())
        self.assertFalse((repo_b / ".claude/skills/repo-b-only").exists())

    def test_apply_renders_repo_claude_guidance_import_bridge(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        repo_registry = write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {},
                "repos": [{"path": str(self.temp_path / "GitHub/repo-a")}],
            },
        )
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        write_text(repo_a / "AGENTS.md", "# Repo Guidance\n")
        claude_home = self.temp_path / "claude"

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--repo-registry",
                str(repo_registry),
                "--repo",
                "repo-a",
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        guidance = repo_a / ".claude/CLAUDE.md"
        self.assertEqual("@../AGENTS.md\n", guidance.read_text(encoding="utf-8"))

    def test_apply_renders_repo_dev_server_launch_config(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        claude_home = self.temp_path / "claude"
        preview_runner = (root / "scripts/run-agent-preview-server.py").resolve()
        dev_servers = write_json(
            root / "dev-servers/registry.json",
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

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--repo",
                "repo-a",
                "--dev-servers-registry",
                str(dev_servers),
                "--preview-runner",
                str(preview_runner),
                "--skip-skills",
                "--skip-global-context",
                "--skip-settings",
                "--skip-launcher",
                str(registry),
            ]
        )

        launch = json.loads((repo_a / ".claude/launch.json").read_text(encoding="utf-8"))
        self.assertEqual("0.0.1", launch["version"])
        self.assertEqual(1, len(launch["configurations"]))
        config = launch["configurations"][0]
        self.assertEqual("Preview", config["name"])
        self.assertEqual("python3", config["runtimeExecutable"])
        self.assertEqual(
            [
                str(preview_runner),
                "--host",
                "127.0.0.1",
                "--port",
                "3000",
                "--",
                "pnpm",
                "dev",
                "--host",
                "127.0.0.1",
                "--port",
                "3000",
            ],
            config["runtimeArgs"],
        )
        self.assertEqual(3000, config["port"])
        self.assertFalse(config["autoPort"])

        codex_env = tomllib.loads(
            (repo_a / ".codex/environments/environment.toml").read_text(encoding="utf-8")
        )
        self.assertEqual("repo-a", codex_env["name"])
        self.assertEqual("Preview", codex_env["actions"][0]["name"])
        self.assertEqual("run", codex_env["actions"][0]["icon"])
        self.assertEqual(
            f"python3 {preview_runner} --host 127.0.0.1 --port 3000 -- pnpm dev --host 127.0.0.1 --port 3000",
            codex_env["actions"][0]["command"],
        )

    def test_dev_server_launch_config_is_opt_in_per_repo(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "repo-b")
        claude_home = self.temp_path / "claude"
        preview_runner = (root / "scripts/run-agent-preview-server.py").resolve()
        dev_servers = write_json(
            root / "dev-servers/registry.json",
            {
                "managed_dev_servers": [
                    {
                        "repo": "repo-a",
                        "servers": [
                            {
                                "name": "dev",
                                "runtimeExecutable": "pnpm",
                                "runtimeArgs": ["dev"],
                                "port": 3000,
                            }
                        ],
                    }
                ]
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--dev-servers-registry",
                str(dev_servers),
                "--preview-runner",
                str(preview_runner),
                "--skip-skills",
                "--skip-global-context",
                "--skip-settings",
                "--skip-launcher",
                str(registry),
            ]
        )

        # Listed repo gets a launch config; unlisted repo is never touched.
        self.assertTrue((repo_a / ".claude/launch.json").is_file())
        self.assertTrue((repo_a / ".codex/environments/environment.toml").is_file())
        self.assertFalse((repo_b / ".claude/launch.json").exists())
        self.assertFalse((repo_b / ".codex/environments/environment.toml").exists())

    def test_dev_server_rejects_multiple_or_auto_port_previews(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        init_git_repo(github_root / "repo-a")
        claude_home = self.temp_path / "claude"

        for servers in (
            [
                {
                    "name": "dev",
                    "runtimeExecutable": "pnpm",
                    "runtimeArgs": ["dev"],
                    "port": 3000,
                },
                {
                    "name": "prod",
                    "runtimeExecutable": "pnpm",
                    "runtimeArgs": ["start"],
                    "port": 3001,
                },
            ],
            [
                {
                    "name": "dev",
                    "runtimeExecutable": "pnpm",
                    "runtimeArgs": ["dev"],
                    "port": 3000,
                    "autoPort": True,
                },
            ],
        ):
            dev_servers = write_json(
                root / "dev-servers/registry.json",
                {"managed_dev_servers": [{"repo": "repo-a", "servers": servers}]},
            )

            result = run_command(
                [
                    str(REPO_ROOT / "scripts/sync-claude.py"),
                    "--apply",
                    "--claude-home",
                    str(claude_home),
                    "--github-root",
                    str(github_root),
                    "--dev-servers-registry",
                    str(dev_servers),
                    "--skip-skills",
                    "--skip-global-context",
                    "--skip-settings",
                    "--skip-launcher",
                    str(registry),
                ],
                check=False,
            )

            self.assertNotEqual(0, result.returncode)

    def test_dev_server_rejects_hardcoded_port_literal(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        init_git_repo(github_root / "repo-a")
        claude_home = self.temp_path / "claude"
        dev_servers = write_json(
            root / "dev-servers/registry.json",
            {
                "managed_dev_servers": [
                    {
                        "repo": "repo-a",
                        "servers": [
                            {
                                "name": "dev",
                                "runtimeExecutable": "pnpm",
                                "runtimeArgs": ["dev", "--port", "3000"],
                                "port": 3000,
                            }
                        ],
                    }
                ]
            },
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--dev-servers-registry",
                str(dev_servers),
                "--skip-skills",
                "--skip-global-context",
                "--skip-settings",
                "--skip-launcher",
                str(registry),
            ],
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("hardcodes port 3000", result.stderr)

    def test_apply_seeds_workspace_trust_for_managed_repos(self) -> None:
        root = init_git_repo(self.temp_path / "agents")
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        claude_home = self.temp_path / "claude"
        # ~/.claude.json is derived as <claude_home>/../.claude.json -> temp/.claude.json
        claude_json = self.temp_path / ".claude.json"
        write_json(
            claude_json,
            {
                "numStartups": 7,
                "projects": {"/already/trusted": {"hasTrustDialogAccepted": True, "lastCost": 1.5}},
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        data = json.loads(claude_json.read_text(encoding="utf-8"))
        # Unrelated top-level keys and existing project data are preserved.
        self.assertEqual(7, data["numStartups"])
        self.assertEqual(1.5, data["projects"]["/already/trusted"]["lastCost"])
        # Managed workspaces (control-plane repo + discovered GitHub repos) are now trusted.
        self.assertTrue(data["projects"][str(repo_a.resolve())]["hasTrustDialogAccepted"])
        self.assertTrue(data["projects"][str(repo_a.resolve())]["hasCompletedProjectOnboarding"])
        self.assertTrue(data["projects"][str(root.resolve())]["hasTrustDialogAccepted"])

    def test_workspace_trust_is_skipped_when_claude_json_missing(self) -> None:
        root = init_git_repo(self.temp_path / "agents")
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"

        # No temp/.claude.json exists -> trust seeding is a no-op (never creates the file).
        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                *self._isolated_targets(root),
                str(registry),
            ]
        )
        self.assertFalse((self.temp_path / ".claude.json").exists())

    def test_apply_merges_trusted_workspaces(self) -> None:
        root = init_git_repo(self.temp_path / "agents")
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "nested/repo-b")
        claude_home = self.temp_path / "claude"
        existing = self.temp_path / "existing"
        existing.mkdir()
        write_json(claude_home / "settings.json", {"permissions": {"additionalDirectories": [str(existing)]}})

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [
                str(existing.resolve()),
                str(repo_b.resolve()),
                str(repo_a.resolve()),
                str(root.resolve()),
            ],
            settings["permissions"]["additionalDirectories"],
        )

    def test_apply_renders_managed_claude_settings_overlay(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        # Pre-existing settings carry an unrelated key plus a manually enabled
        # plugin that the overlay does not mention; both must survive the merge.
        write_json(
            claude_home / "settings.json",
            {
                "model": "test-model",
                "enabledPlugins": {"keep-me@inline": True},
            },
        )
        overlay = write_json(
            root / "config/claude-settings.json",
            {
                "version": 1,
                "enabledPlugins": {"anthropic-skills@inline": False},
                "skillOverrides": {"loop": "name-only", "review": "off"},
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--claude-settings-overlay",
                str(overlay),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
        # Overlay disables the bundled plugin while preserving the manual entry.
        self.assertEqual(False, settings["enabledPlugins"]["anthropic-skills@inline"])
        self.assertEqual(True, settings["enabledPlugins"]["keep-me@inline"])
        # Per-skill visibility overrides for bundled skills land verbatim.
        self.assertEqual("name-only", settings["skillOverrides"]["loop"])
        self.assertEqual("off", settings["skillOverrides"]["review"])
        # Unrelated existing keys are untouched.
        self.assertEqual("test-model", settings["model"])

    def test_apply_renders_repo_settings_into_repo_claude_settings(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "repo-b")
        # repo-a already carries an unmanaged key that must survive the merge.
        write_json(
            repo_a / ".claude/settings.json",
            {"permissions": {"defaultMode": "acceptEdits"}},
        )
        hooks_registry = write_json(
            root / "hooks/registry.json",
            {
                "version": 1,
                "managed_hooks": [
                    {
                        "id": "repo-session-start",
                        "event": "SessionStart",
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["repo-a"],
                        "runtimes": ["claude"],
                        "matchers": {"claude": "startup"},
                        "timeout": 5,
                    }
                ],
            },
        )
        overlay = write_json(
            root / "config/claude-settings.json",
            {
                "version": 1,
                # repo-b has managed settings but no managed hooks: it must
                # still be visited and rendered.
                "repoSettings": {
                    "repo-a": {"autoMemoryEnabled": False},
                    "repo-b": {"autoMemoryEnabled": False},
                },
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--github-root",
                str(github_root),
                "--hooks-registry",
                str(hooks_registry),
                "--claude-settings-overlay",
                str(overlay),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        settings_a = json.loads(
            (repo_a / ".claude/settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, settings_a["autoMemoryEnabled"])
        # The managed hook block and the pre-existing unmanaged key coexist.
        self.assertIn("SessionStart", settings_a["hooks"])
        self.assertEqual({"defaultMode": "acceptEdits"}, settings_a["permissions"])
        settings_b = json.loads(
            (repo_b / ".claude/settings.json").read_text(encoding="utf-8")
        )
        self.assertEqual(False, settings_b["autoMemoryEnabled"])
        self.assertNotIn("hooks", settings_b)

    def test_unmanaged_repo_settings_key_fails(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        overlay = write_json(
            root / "config/claude-settings.json",
            {"version": 1, "repoSettings": {"repo-a": {"model": "haiku"}}},
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--claude-settings-overlay",
                str(overlay),
                *self._isolated_targets(root),
                str(registry),
            ],
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("repoSettings", result.stderr)

    def test_invalid_skill_override_value_fails(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        overlay = write_json(
            root / "config/claude-settings.json",
            {"version": 1, "skillOverrides": {"loop": "sometimes"}},
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--claude-home",
                str(claude_home),
                "--claude-settings-overlay",
                str(overlay),
                *self._isolated_targets(root),
                str(registry),
            ],
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("skillOverrides", result.stderr)

    def test_existing_global_context_symlink_target_is_not_resolved_for_write(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        source = write_text(root / "config/global.agents.md", "# Global Agent Context\n")
        target = self.temp_path / "claude/CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(os.path.relpath(source, target.parent))

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude.py"),
                "--apply",
                "--skip-yolo",
                "--skip-settings",
                "--skip-launcher",
                "--skip-skills",
                "--claude-home",
                str(claude_home),
                "--global-context-source",
                str(source),
                "--global-context-target",
                str(target),
                str(registry),
            ]
        )

        self.assertEqual("# Global Agent Context\n", source.read_text(encoding="utf-8"))
        self.assertTrue(target.is_symlink())
        self.assertEqual(source.resolve(), (target.parent / os.readlink(target)).resolve())
