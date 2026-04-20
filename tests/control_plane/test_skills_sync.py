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
        dormant_source = make_skill_source(
            root / "skills-source/owned/dormant-helper",
            "dormant-helper",
        )
        make_skill_source(adi / ".agents/skills/local-review", "local-review")

        stale_source = make_skill_source(
            root / "skills-source/owned/stale-helper",
            "stale-helper",
        )
        stale_link = root / "skills/stale-helper"
        stale_link.parent.mkdir(parents=True, exist_ok=True)
        stale_link.symlink_to(stale_source)
        dormant_global_link = root / "skills/dormant-helper"
        dormant_global_link.parent.mkdir(parents=True, exist_ok=True)
        dormant_global_link.symlink_to(dormant_source)
        dormant_repo_link = adi / ".agents/skills/dormant-helper"
        dormant_repo_link.parent.mkdir(parents=True, exist_ok=True)
        dormant_repo_link.symlink_to(dormant_source)

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
                    {
                        "skill": "dormant-helper",
                        "origin": "owned",
                        "scope": "dormant",
                        "repos": [],
                        "source_path": "skills-source/owned/dormant-helper",
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
        self.assertFalse(dormant_global_link.exists())
        self.assertFalse(dormant_repo_link.exists())

        skills_base = root / "docs/references/registry/skills.base"
        global_item = root / "docs/references/registry/skills-items/managed/global-helper.md"
        dormant_item = root / "docs/references/registry/skills-items/managed/dormant-helper.md"
        repo_local_item = (
            root / "docs/references/registry/skills-items/repo-local/adi--local-review.md"
        )

        self.assertTrue(skills_base.is_file())
        self.assertTrue(global_item.is_file())
        self.assertTrue(dormant_item.is_file())
        self.assertTrue(repo_local_item.is_file())

        global_item_text = global_item.read_text(encoding="utf-8")
        self.assertIn('skill: "global-helper"', global_item_text)
        self.assertIn('scope: "global"', global_item_text)
        self.assertIn('source_path: "skills-source/owned/global-helper"', global_item_text)

        dormant_item_text = dormant_item.read_text(encoding="utf-8")
        self.assertIn('skill: "dormant-helper"', dormant_item_text)
        self.assertIn('scope: "dormant"', dormant_item_text)
        self.assertIn('repos_csv: "-"', dormant_item_text)
        self.assertIn('  - "-"', dormant_item_text)

        repo_local_text = repo_local_item.read_text(encoding="utf-8")
        self.assertIn('repo: "adi"', repo_local_text)
        self.assertIn('skill: "local-review"', repo_local_text)

    def test_rejects_missing_repo_local_skill_source_for_existing_repo(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        (adi / ".agents/skills/missing-local").mkdir(parents=True, exist_ok=True)

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
                    }
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "missing-local",
                    }
                ],
            },
        )

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-skills-registry.py"),
                str(registry_path),
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "missing SKILL.md for adi/missing-local",
            result.stderr,
        )


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

    def test_prunes_stale_repo_local_link_when_registry_entry_source_is_missing(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        missing_repo_local_source = adi / ".agents/skills/missing-local"
        missing_repo_local_source.mkdir(parents=True, exist_ok=True)

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
                    }
                ],
                "managed_plugin_skills": [],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "missing-local",
                    }
                ],
            },
        )
        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")

        stale_repo_link = adi / ".claude/skills/missing-local"
        stale_repo_link.parent.mkdir(parents=True, exist_ok=True)
        stale_repo_link.symlink_to(missing_repo_local_source)

        result = run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-skills.sh"),
                "--apply",
                "--registry",
                str(registry_path),
            ],
            env={"HOME": str(home)},
        )

        self.assertIn("missing SKILL.md", result.stderr)
        self.assertFalse(stale_repo_link.exists())
