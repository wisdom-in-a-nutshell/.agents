from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    init_git_repo,
    make_control_plane_root,
    make_skill_source,
    run_command,
    write_json,
)


class RepoBootstrapRegistryValidationTests(TempDirTestCase):
    def test_validates_repo_mcp_and_skill_inputs_without_legacy_outputs(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        make_skill_source(root / "skills-source/owned/repo-helper", "repo-helper")
        make_skill_source(adi / ".agents/skills/local-review", "local-review")

        write_json(
            root / "skills/registry.json",
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
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env={"HOME": str(home)},
        )

        self.assertIn("Repo bootstrap registry validated.", result.stdout)
        self.assertIn("Repos: 1", result.stdout)
        self.assertIn("MCP presets:", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())

    def test_accepts_declared_repo_local_skills_without_legacy_outputs(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        (adi / ".agents/skills/missing-local").mkdir(parents=True, exist_ok=True)

        write_json(
            root / "skills/registry.json",
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
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env={"HOME": str(home)},
        )

        self.assertIn("Repo bootstrap registry validated.", result.stdout)
        self.assertIn("Repos: 1", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())
