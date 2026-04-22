from __future__ import annotations

import json

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    default_skills_registry,
    external_researcher_agent,
    init_git_repo,
    make_control_plane_root,
    make_skill_source,
    read_json,
    run_command,
    visual_reviewer_agent,
    write_json,
    write_text,
)


class ClaudeControlPlaneCheckTests(TempDirTestCase):
    def test_check_script_passes_for_rendered_skills_mcp_and_subagents(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")
        write_text(adi / "AGENTS.md", "# Repo Guidance\n")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        make_skill_source(root / "skills-source/owned/repo-helper", "repo-helper")

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
                "unmanaged_repo_local_skills": [],
            },
        )
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {},
                "repos": [
                    {
                        "mcp_presets": ["cloudflare-docs"],
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())
        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [
                    external_researcher_agent(),
                    visual_reviewer_agent("adi"),
                ],
                "version": 1,
            },
        )

        env = {"HOME": str(home)}
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-global-claude-md.sh"),
                "--apply",
                "--global-claude-md",
                str(home / ".claude/CLAUDE.md"),
                "--canonical-claude",
                str(root / "claude/config/global.claude.md"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-settings.sh"),
                "--apply",
                "--global-settings",
                str(home / ".claude/settings.json"),
                "--canonical-settings",
                str(root / "claude/config/settings.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-global-mcp.sh"),
                "--apply",
                "--global-config",
                str(home / ".claude.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-subagents.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--global-agents-dir",
                str(home / ".claude/agents"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-skills.sh"),
                "--apply",
                "--registry",
                str(root / "skills/registry.json"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-repo-claude-configs.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--bootstrap",
                str(root / "claude/config/bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env=env,
        )

        (home / ".claude.json").write_text(
            json.dumps(read_json(home / ".claude.json"), ensure_ascii=False),
            encoding="utf-8",
        )
        (adi / ".mcp.json").write_text(
            json.dumps(read_json(adi / ".mcp.json"), ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_command(
            [
                str(REPO_ROOT / "claude/scripts/check-claude-control-plane.sh"),
                "--canonical-dir",
                str(root / "claude/config"),
                "--global-claude-md",
                str(home / ".claude/CLAUDE.md"),
                "--global-settings",
                str(home / ".claude/settings.json"),
                "--global-config",
                str(home / ".claude.json"),
                "--global-agents-dir",
                str(home / ".claude/agents"),
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--bootstrap",
                str(root / "claude/config/bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--skills-registry",
                str(root / "skills/registry.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
                "--repo",
                str(adi),
            ],
            env=env,
        )

        self.assertIn("Claude control plane validation passed.", result.stdout)
        self.assertTrue((root / "claude/config/global.claude.md").is_symlink())
        self.assertEqual(
            (root / "codex/config/global.agents.md").resolve(),
            (root / "claude/config/global.claude.md").resolve(),
        )
        self.assertTrue((home / ".claude/CLAUDE.md").is_symlink())
        self.assertEqual(
            (root / "claude/config/global.claude.md").resolve(),
            (home / ".claude/CLAUDE.md").resolve(),
        )
        self.assertTrue((home / ".claude/settings.json").is_file())
        self.assertEqual(
            {
                "openaiDeveloperDocs": {
                    "type": "http",
                    "url": "https://developers.openai.com/mcp",
                }
            },
            read_json(home / ".claude.json")["mcpServers"],
        )
        self.assertTrue((home / ".claude/agents/external-researcher.md").is_file())
        self.assertTrue((adi / ".claude/agents/visual-reviewer.md").is_file())
        self.assertTrue((home / ".claude/skills/global-helper").is_symlink())
        self.assertTrue((adi / ".claude/skills/repo-helper").is_symlink())
        self.assertTrue((adi / ".claude/settings.json").is_file())
        self.assertTrue((adi / ".mcp.json").is_file())
        self.assertTrue((adi / "CLAUDE.md").is_file())

    def test_check_script_fails_for_untracked_claude_skill_in_tracked_surface(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi", with_initial_commit=True)
        write_text(adi / "AGENTS.md", "# Repo Guidance\n")

        make_skill_source(root / "skills-source/owned/existing-helper", "existing-helper")
        make_skill_source(root / "skills-source/owned/repo-helper", "repo-helper")

        registry_path = root / "skills/registry.json"
        write_json(
            registry_path,
            {
                "managed_skills": [
                    {
                        "skill": "existing-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/existing-helper",
                    }
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [],
            },
        )
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {},
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
            {
                "managed_agents": [
                    external_researcher_agent(),
                ],
                "version": 1,
            },
        )

        env = {"HOME": str(home)}
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-global-claude-md.sh"),
                "--apply",
                "--global-claude-md",
                str(home / ".claude/CLAUDE.md"),
                "--canonical-claude",
                str(root / "claude/config/global.claude.md"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-settings.sh"),
                "--apply",
                "--global-settings",
                str(home / ".claude/settings.json"),
                "--canonical-settings",
                str(root / "claude/config/settings.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-global-mcp.sh"),
                "--apply",
                "--global-config",
                str(home / ".claude.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-subagents.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--global-agents-dir",
                str(home / ".claude/agents"),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-skills.sh"),
                "--apply",
                "--registry",
                str(registry_path),
            ],
            env=env,
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-repo-claude-configs.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--bootstrap",
                str(root / "claude/config/bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env=env,
        )
        run_command(
            [
                "git",
                "-C",
                str(adi),
                "add",
                ".claude/skills/existing-helper",
                "AGENTS.md",
            ],
            env=env,
        )
        run_command(
            [
                "git",
                "-C",
                str(adi),
                "commit",
                "-q",
                "-m",
                "track existing Claude skill",
            ],
            env=env,
        )

        write_json(
            registry_path,
            {
                "managed_skills": [
                    {
                        "skill": "existing-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/existing-helper",
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
                "unmanaged_repo_local_skills": [],
            },
        )
        run_command(
            [
                str(REPO_ROOT / "claude/scripts/sync-skills.sh"),
                "--apply",
                "--registry",
                str(registry_path),
            ],
            env=env,
        )

        result = run_command(
            [
                str(REPO_ROOT / "claude/scripts/check-claude-control-plane.sh"),
                "--canonical-dir",
                str(root / "claude/config"),
                "--global-claude-md",
                str(home / ".claude/CLAUDE.md"),
                "--global-settings",
                str(home / ".claude/settings.json"),
                "--global-config",
                str(home / ".claude.json"),
                "--global-agents-dir",
                str(home / ".claude/agents"),
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--bootstrap",
                str(root / "claude/config/bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--skills-registry",
                str(registry_path),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
                "--repo",
                str(adi),
            ],
            env=env,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Managed repo-local Claude files need git attention:", result.stderr)
        self.assertIn("surface: .claude/skills", result.stderr)
        self.assertIn(".claude/skills/repo-helper", result.stderr)

    def test_validate_inputs_fails_when_global_claude_forks_global_agents(self) -> None:
        root = make_control_plane_root(self.temp_path)
        write_json(root / "codex/config/repo-bootstrap.json", {"defaults": {}, "repos": []})
        write_json(root / "mcp/config/presets.json", default_mcp_registry())
        write_json(root / "skills/registry.json", default_skills_registry())
        write_json(root / "agents/registry.json", {"managed_agents": [], "version": 1})

        (root / "claude/config/global.claude.md").unlink()
        write_text(root / "claude/config/global.claude.md", "# Forked Claude Guidance\n")

        result = run_command(
            [
                "python3",
                "-m",
                "claude.control_plane.validate_inputs",
                "--canonical-dir",
                str(root / "claude/config"),
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--bootstrap",
                str(root / "claude/config/bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--skills-registry",
                str(root / "skills/registry.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
                "--global-agents",
                str(root / "codex/config/global.agents.md"),
            ],
            cwd=REPO_ROOT,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("must be a symlink to shared global AGENTS guidance", result.stderr)
