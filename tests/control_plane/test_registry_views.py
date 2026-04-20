from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    external_researcher_agent,
    init_git_repo,
    make_control_plane_root,
    make_skill_source,
    run_command,
    visual_reviewer_agent,
    write_json,
)


class RegistryViewsGenerationTests(TempDirTestCase):
    def test_generates_repo_mcp_and_agent_registry_views_from_shared_inputs(self) -> None:
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
                    "model": "gpt-5.4",
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "mcp_presets": ["cloudflare-docs"],
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        hot_agent = {
            "access_profile": "full_access",
            "agent": "research-hot",
            "claude": {
                "prompt_file": "external-researcher.md",
                "tools": ["Read"],
            },
            "description": "Full-access Claude-only research worker.",
            "repos": [],
            "scope": "global",
        }
        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [
                    external_researcher_agent(),
                    visual_reviewer_agent("adi"),
                    hot_agent,
                ],
                "version": 1,
            },
        )

        run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
            ],
            env={"HOME": str(home)},
        )

        repo_item = root / "docs/references/registry/repo-bootstrap-items/adi.md"
        cloudflare_item = root / "docs/references/registry/mcp-registry-items/cloudflare-docs.md"
        hot_agent_item = root / "docs/references/registry/agent-registry-items/research-hot.md"
        reviewer_item = (
            root / "docs/references/registry/agent-registry-items/visual-reviewer.md"
        )

        self.assertTrue(repo_item.is_file())
        self.assertTrue(cloudflare_item.is_file())
        self.assertTrue(hot_agent_item.is_file())
        self.assertTrue(reviewer_item.is_file())

        repo_text = repo_item.read_text(encoding="utf-8")
        self.assertIn('repo_name: "adi"', repo_text)
        self.assertIn('custom_agents:', repo_text)
        self.assertIn('  - "visual_reviewer"', repo_text)
        self.assertIn('skills:', repo_text)
        self.assertIn('  - "global-helper"', repo_text)
        self.assertIn('  - "repo-helper"', repo_text)
        self.assertIn('  - "local-review"', repo_text)

        cloudflare_text = cloudflare_item.read_text(encoding="utf-8")
        self.assertIn('mcp_name: "cloudflare-docs"', cloudflare_text)
        self.assertIn('effective_scope: "repo"', cloudflare_text)
        self.assertIn('transport: "http"', cloudflare_text)
        self.assertIn('  - "adi"', cloudflare_text)

        hot_agent_text = hot_agent_item.read_text(encoding="utf-8")
        self.assertIn('agent_name: "research-hot"', hot_agent_text)
        self.assertIn('runtimes: "claude"', hot_agent_text)
        self.assertIn('claude_permission_mode: "bypassPermissions"', hot_agent_text)

        reviewer_text = reviewer_item.read_text(encoding="utf-8")
        self.assertIn('agent_name: "visual-reviewer"', reviewer_text)
        self.assertIn('runtimes: "codex, claude"', reviewer_text)
        self.assertIn('claude_name: "visual-reviewer"', reviewer_text)
        self.assertIn('codex_name: "visual_reviewer"', reviewer_text)

    def test_omits_missing_repo_local_skills_from_repo_bootstrap_views(self) -> None:
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
                    "model": "gpt-5.4",
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
        write_json(
            root / "agents/registry.json",
            {"managed_agents": [external_researcher_agent()], "version": 1},
        )

        run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
            ],
            env={"HOME": str(home)},
        )

        repo_item = root / "docs/references/registry/repo-bootstrap-items/adi.md"
        repo_text = repo_item.read_text(encoding="utf-8")
        self.assertIn('repo_name: "adi"', repo_text)
        self.assertIn('repo_local_skill_count: 0', repo_text)
        self.assertNotIn('  - "missing-local"', repo_text)
