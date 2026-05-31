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
)


class AntigravitySpikeSyncTests(TempDirTestCase):
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

    def test_apply_renders_global_skills_and_yolo_setting(self) -> None:
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
        app_data = self.temp_path / "antigravity-cli"
        write_json(app_data / "settings.json", {"model": "test-model"})

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-antigravity-spike.py"),
                "--apply",
                "--app-data-dir",
                str(app_data),
                str(registry),
            ]
        )

        skill_link = app_data / "skills/global-one"
        self.assertTrue(skill_link.is_symlink())
        self.assertEqual(
            (root / "skills-source/owned/global-one").resolve(),
            (skill_link.parent / os.readlink(skill_link)).resolve(),
        )
        self.assertFalse((app_data / "skills/repo-only").exists())

        settings = json.loads((app_data / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual("test-model", settings["model"])
        self.assertEqual("always-proceed", settings["toolPermission"])

    def test_apply_merges_trusted_workspaces(self) -> None:
        root = init_git_repo(self.temp_path / "agents")
        registry = self._write_registry(root, [])
        github_root = self.temp_path / "GitHub"
        repo_a = init_git_repo(github_root / "repo-a")
        repo_b = init_git_repo(github_root / "nested/repo-b")
        app_data = self.temp_path / "antigravity-cli"
        existing = self.temp_path / "existing"
        existing.mkdir()
        write_json(
            app_data / "settings.json",
            {
                "trustedWorkspaces": [str(existing)],
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-antigravity-spike.py"),
                "--apply",
                "--skip-yolo",
                "--app-data-dir",
                str(app_data),
                "--github-root",
                str(github_root),
                str(registry),
            ]
        )

        settings = json.loads((app_data / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [
                str(existing.resolve()),
                str(repo_b.resolve()),
                str(repo_a.resolve()),
                str(root.resolve()),
            ],
            settings["trustedWorkspaces"],
        )

    def test_prunes_only_managed_obsolete_antigravity_links(self) -> None:
        root = self.temp_path / "agents"
        registry = self._write_registry(
            root,
            [
                {
                    "skill": "kept",
                    "origin": "owned",
                    "scope": "global",
                    "repos": [],
                    "source_path": "skills-source/owned/kept",
                    "upstream_ref": "-",
                }
            ],
        )
        obsolete_source = make_skill_source(root / "skills-source/owned/obsolete", "obsolete")
        external_source = make_skill_source(self.temp_path / "external-source", "external")
        app_data = self.temp_path / "antigravity-cli"
        skills_dir = app_data / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "obsolete").symlink_to(obsolete_source)
        (skills_dir / "external").symlink_to(external_source)

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-antigravity-spike.py"),
                "--apply",
                "--skip-yolo",
                "--app-data-dir",
                str(app_data),
                str(registry),
            ]
        )

        self.assertTrue((skills_dir / "kept").is_symlink())
        self.assertFalse((skills_dir / "obsolete").exists())
        self.assertTrue((skills_dir / "external").is_symlink())
