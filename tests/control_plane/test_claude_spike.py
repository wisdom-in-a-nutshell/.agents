from __future__ import annotations

import json
import os
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


class ClaudeSpikeSyncTests(TempDirTestCase):
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
        source = write_text(root / "codex/config/global.agents.md", "# Global\n")
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

    def test_apply_renders_global_skills_instructions_settings_hooks_and_yolo_launcher(self) -> None:
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
                str(REPO_ROOT / "scripts/sync-claude-spike.py"),
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
            (root / "codex/config/global.agents.md").resolve(),
            (instructions.parent / os.readlink(instructions)).resolve(),
        )

        settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual("test-model", settings["model"])
        self.assertEqual("bypassPermissions", settings["permissions"]["defaultMode"])
        self.assertEqual(True, settings["permissions"]["skipDangerousModePermissionPrompt"])
        self.assertIn("Bash", settings["permissions"]["allow"])
        self.assertIn("Stop", settings["hooks"])
        self.assertIn("PreToolUse", settings["hooks"])
        self.assertIn("PermissionRequest", settings["hooks"])
        self.assertEqual(
            "python3 ~/.agents/hooks/scripts/claude_stop.py",
            settings["hooks"]["Stop"][0]["hooks"][0]["command"],
        )

        launcher = self.temp_path / "bin/claude"
        self.assertTrue(launcher.is_file())
        self.assertTrue(os.access(launcher, os.X_OK))
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("--dangerously-skip-permissions", launcher_text)
        self.assertIn("$HOME/.secrets/anthropic/env", launcher_text)
        self.assertIn(str(self.temp_path / "homebrew/bin/claude"), launcher_text)

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
                str(REPO_ROOT / "scripts/sync-claude-spike.py"),
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
                str(existing),
                str(repo_b.resolve()),
                str(repo_a.resolve()),
                str(root.resolve()),
            ],
            settings["permissions"]["additionalDirectories"],
        )

    def test_existing_global_context_symlink_target_is_not_resolved_for_write(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        claude_home = self.temp_path / "claude"
        source = write_text(root / "codex/config/global.agents.md", "# Global Agent Context\n")
        target = self.temp_path / "claude/CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(os.path.relpath(source, target.parent))

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-claude-spike.py"),
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

