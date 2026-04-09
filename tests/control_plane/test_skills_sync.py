from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    make_control_plane_root,
    make_skill_source,
    run_command,
    write_json,
)


class ManagedSkillsRegistrySyncTests(TempDirTestCase):
    def test_syncs_managed_skill_links_and_generated_registry_views(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        global_source = make_skill_source(
            root / "skills-source/owned/global-helper",
            "global-helper",
        )
        repo_source = make_skill_source(
            root / "skills-source/owned/repo-helper",
            "repo-helper",
        )
        make_skill_source(adi / ".agents/skills/local-review", "local-review")

        stale_source = make_skill_source(
            root / "skills-source/owned/stale-helper",
            "stale-helper",
        )
        stale_link = root / "skills/stale-helper"
        stale_link.parent.mkdir(parents=True, exist_ok=True)
        stale_link.symlink_to(stale_source)

        registry_path = root / "skills/registry.json"
        write_json(
            registry_path,
            {
                "managed_skills": [
                    {
                        "skill": "global-helper",
                        "origin": "owned",
                        "scope": "global",
                        "source_path": "skills-source/owned/global-helper",
                    },
                    {
                        "skill": "repo-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/repo-helper",
                    },
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "local-review",
                    }
                ],
            },
        )

        run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-skills-registry.py"),
                "--apply",
                str(registry_path),
            ],
            env={"HOME": str(home)},
        )

        global_link = root / "skills/global-helper"
        repo_link = adi / ".agents/skills/repo-helper"

        self.assertTrue(global_link.is_symlink())
        self.assertEqual(global_source.resolve(), global_link.resolve())
        self.assertTrue(repo_link.is_symlink())
        self.assertEqual(repo_source.resolve(), repo_link.resolve())
        self.assertFalse(stale_link.exists())

        skills_base = root / "docs/references/registry/skills.base"
        global_item = root / "docs/references/registry/skills-items/managed/global-helper.md"
        repo_local_item = (
            root / "docs/references/registry/skills-items/repo-local/adi--local-review.md"
        )

        self.assertTrue(skills_base.is_file())
        self.assertTrue(global_item.is_file())
        self.assertTrue(repo_local_item.is_file())

        global_item_text = global_item.read_text(encoding="utf-8")
        self.assertIn('skill: "global-helper"', global_item_text)
        self.assertIn('scope: "global"', global_item_text)
        self.assertIn('source_path: "skills-source/owned/global-helper"', global_item_text)

        repo_local_text = repo_local_item.read_text(encoding="utf-8")
        self.assertIn('repo: "adi"', repo_local_text)
        self.assertIn('skill: "local-review"', repo_local_text)


class ClaudeSkillsSyncTests(TempDirTestCase):
    def test_syncs_claude_skill_links_and_prunes_removed_managed_links(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        global_source = make_skill_source(
            root / "skills-source/owned/global-helper",
            "global-helper",
        )
        repo_source = make_skill_source(
            root / "skills-source/owned/repo-helper",
            "repo-helper",
        )
        repo_local_source = make_skill_source(
            adi / ".agents/skills/local-review",
            "local-review",
        )
        stale_source = make_skill_source(
            root / "skills-source/owned/stale-helper",
            "stale-helper",
        )

        registry_path = root / "skills/registry.json"
        write_json(
            registry_path,
            {
                "managed_skills": [
                    {
                        "skill": "global-helper",
                        "origin": "owned",
                        "scope": "global",
                        "source_path": "skills-source/owned/global-helper",
                    },
                    {
                        "skill": "repo-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/repo-helper",
                    },
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "local-review",
                    }
                ],
            },
        )

        stale_global_link = home / ".claude/skills/stale-helper"
        stale_repo_link = adi / ".claude/skills/stale-helper"
        stale_global_link.parent.mkdir(parents=True, exist_ok=True)
        stale_repo_link.parent.mkdir(parents=True, exist_ok=True)
        stale_global_link.symlink_to(stale_source)
        stale_repo_link.symlink_to(stale_source)

        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-skills.sh"),
                "--apply",
                "--registry",
                str(registry_path),
            ],
            env={"HOME": str(home)},
        )

        global_link = home / ".claude/skills/global-helper"
        repo_link = adi / ".claude/skills/repo-helper"
        repo_local_link = adi / ".claude/skills/local-review"

        self.assertTrue(global_link.is_symlink())
        self.assertEqual(global_source.resolve(), global_link.resolve())
        self.assertTrue(repo_link.is_symlink())
        self.assertEqual(repo_source.resolve(), repo_link.resolve())
        self.assertTrue(repo_local_link.is_symlink())
        self.assertEqual(repo_local_source.resolve(), repo_local_link.resolve())
        self.assertFalse(stale_global_link.exists())
        self.assertFalse(stale_repo_link.exists())
