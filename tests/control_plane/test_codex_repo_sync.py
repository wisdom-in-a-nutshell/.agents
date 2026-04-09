from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    init_git_repo,
    make_control_plane_root,
    run_command,
    visual_reviewer_agent,
    write_json,
)


class CodexRepoSyncTests(TempDirTestCase):
    def test_renders_repo_config_and_role_files_from_shared_agent_registry(self) -> None:
        root = make_control_plane_root(self.temp_path)
        adi = init_git_repo(self.temp_path / "adi")

        repo_registry_path = root / "codex/config/repo-bootstrap.json"
        mcp_registry_path = root / "mcp/config/presets.json"
        agent_registry_path = root / "agents/registry.json"

        write_json(
            repo_registry_path,
            {
                "defaults": {
                    "model": "gpt-5.4",
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "mcp_presets": ["paper"],
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(mcp_registry_path, default_mcp_registry())
        write_json(
            agent_registry_path,
            {
                "managed_agents": [
                    visual_reviewer_agent("adi"),
                ],
                "version": 1,
            },
        )

        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-repo-codex-configs.sh"),
                "--apply",
                "--registry",
                str(repo_registry_path),
                "--mcp-registry",
                str(mcp_registry_path),
                "--agent-registry",
                str(agent_registry_path),
            ]
        )

        repo_config = (adi / ".codex/config.toml").read_text(encoding="utf-8")
        repo_role = (adi / ".codex/agents/visual_reviewer.toml").read_text(encoding="utf-8")

        self.assertIn('model = "gpt-5.4"', repo_config)
        self.assertIn('model_reasoning_effort = "high"', repo_config)
        self.assertIn("[mcp_servers.paper]", repo_config)
        self.assertIn('url = "http://127.0.0.1:29979/mcp"', repo_config)
        self.assertIn("[agents.visual_reviewer]", repo_config)
        self.assertIn('config_file = "agents/visual_reviewer.toml"', repo_config)
        self.assertIn('nickname_candidates = ["Lens", "Critic", "Review"]', repo_config)

        self.assertIn("# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.", repo_role)
        self.assertIn('name = "visual_reviewer"', repo_role)
        self.assertIn('description = "Read-only reviewer for visual work such as screenshots, layouts, hierarchy, and clarity."', repo_role)
        self.assertIn('sandbox_mode = "read-only"', repo_role)
        self.assertIn("[mcp_servers.paper]", repo_role)
        self.assertIn("enabled = true", repo_role)
