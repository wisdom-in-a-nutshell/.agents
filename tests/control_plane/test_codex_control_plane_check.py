from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    default_plugins_registry,
    init_git_repo,
    make_control_plane_root,
    run_command,
    visual_reviewer_agent,
    write_json,
)


class CodexControlPlaneCheckTests(TempDirTestCase):
    def test_check_script_passes_for_rendered_repo_configs_and_mcp_assignments(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

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
                        "mcp_presets": ["paper"],
                        "plugin_mcp_presets": ["plugin-build-ios-apps-xcodebuildmcp"],
                        "path": str(adi),
                    }
                ],
            },
        )
        mcp_registry = default_mcp_registry()
        mcp_registry["plugin_presets"] = {
            "plugin-build-ios-apps-xcodebuildmcp": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "xcodebuildmcp@latest", "mcp"],
            }
        }
        write_json(root / "mcp/config/presets.json", mcp_registry)
        plugin_registry = default_plugins_registry()
        write_json(root / "plugins/registry.json", plugin_registry)
        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [
                    visual_reviewer_agent("adi"),
                ],
                "version": 1,
            },
        )

        env = {"HOME": str(home)}
        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-repo-codex-configs.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--plugin-registry",
                str(root / "plugins/registry.json"),
            ],
            env=env,
        )

        result = run_command(
            [
                str(REPO_ROOT / "codex/scripts/check-codex-control-plane.sh"),
                "--canonical-dir",
                str(root / "codex/config"),
                "--global-config",
                str(home / ".codex/config.toml"),
                "--global-agents-dir",
                str(home / ".codex/agents"),
                "--xcode-config",
                str(home / "xcode/config.toml"),
                "--xcode-agents-dir",
                str(home / "xcode/agents"),
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--repo",
                str(adi),
            ],
            env=env,
        )

        self.assertIn("OK: Codex control plane validation passed", result.stdout)
        self.assertTrue((adi / ".codex/config.toml").is_file())
        self.assertTrue((adi / ".codex/agents/visual_reviewer.toml").is_file())
