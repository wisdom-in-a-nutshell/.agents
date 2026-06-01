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


class CopilotSpikeSyncTests(TempDirTestCase):
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
            str(self.temp_path / "copilot/copilot-instructions.md"),
            "--hooks-file",
            str(self.temp_path / "copilot/hooks/agents-control-plane.json"),
            "--launcher-target",
            str(self.temp_path / "bin/copilot"),
            "--real-cli-path",
            str(self.temp_path / "homebrew/bin/copilot"),
        ]

    def test_apply_renders_global_skills_instructions_hooks_and_yolo_launcher(self) -> None:
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
        copilot_home = self.temp_path / "copilot"
        write_json(copilot_home / "settings.json", {"model": "test-model"})

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-spike.py"),
                "--apply",
                "--copilot-home",
                str(copilot_home),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        skill_link = copilot_home / "skills/global-one"
        self.assertTrue(skill_link.is_symlink())
        self.assertEqual(
            (root / "skills-source/owned/global-one").resolve(),
            (skill_link.parent / os.readlink(skill_link)).resolve(),
        )
        self.assertFalse((copilot_home / "skills/repo-only").exists())

        settings = json.loads((copilot_home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual("test-model", settings["model"])
        self.assertEqual(False, settings["askUser"])
        self.assertEqual("never", settings["banner"])
        self.assertEqual(False, settings["beep"])

        instructions = self.temp_path / "copilot/copilot-instructions.md"
        self.assertTrue(instructions.is_symlink())
        self.assertEqual(
            (root / "codex/config/global.agents.md").resolve(),
            (instructions.parent / os.readlink(instructions)).resolve(),
        )

        hooks = json.loads(
            (self.temp_path / "copilot/hooks/agents-control-plane.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, hooks["version"])
        self.assertIn("agentStop", hooks["hooks"])
        self.assertIn("permissionRequest", hooks["hooks"])
        self.assertIn("preToolUse", hooks["hooks"])
        self.assertEqual(
            "python3 ~/.agents/hooks/scripts/copilot_stop.py",
            hooks["hooks"]["agentStop"][0]["bash"],
        )
        self.assertIn('"behavior":"allow"', hooks["hooks"]["permissionRequest"][0]["bash"])
        self.assertIn('"permissionDecision":"allow"', hooks["hooks"]["preToolUse"][0]["bash"])

        launcher = self.temp_path / "bin/copilot"
        self.assertTrue(launcher.is_file())
        self.assertTrue(os.access(launcher, os.X_OK))
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("--yolo --no-ask-user", launcher_text)
        self.assertIn(str(self.temp_path / "homebrew/bin/copilot"), launcher_text)

    def test_apply_merges_trusted_workspaces(self) -> None:
        root = init_git_repo(self.temp_path / "agents")
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "nested/repo-b")
        copilot_home = self.temp_path / "copilot"
        existing = self.temp_path / "existing"
        existing.mkdir()
        write_text(
            copilot_home / "config.json",
            "// User settings belong in settings.json.\n// This file is managed automatically.\n"
            + json.dumps({"trustedFolders": [str(existing)]}, indent=2)
            + "\n",
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-spike.py"),
                "--apply",
                "--copilot-home",
                str(copilot_home),
                "--github-root",
                str(github_root),
                *self._isolated_targets(root),
                str(registry),
            ]
        )

        raw_config = (copilot_home / "config.json").read_text(encoding="utf-8")
        config = json.loads("\n".join(line for line in raw_config.splitlines() if not line.startswith("//")))
        self.assertEqual(
            [
                str(existing.resolve()),
                str(repo_b.resolve()),
                str(repo_a.resolve()),
                str(root.resolve()),
            ],
            config["trustedFolders"],
        )

    def test_existing_global_context_symlink_target_is_not_resolved_for_write(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(root, [])
        copilot_home = self.temp_path / "copilot"
        source = write_text(root / "codex/config/global.agents.md", "# Global Agent Context\n")
        target = self.temp_path / "copilot/copilot-instructions.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(os.path.relpath(source, target.parent))

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-spike.py"),
                "--apply",
                "--skip-yolo",
                "--skip-hooks",
                "--skip-launcher",
                "--skip-skills",
                "--copilot-home",
                str(copilot_home),
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
