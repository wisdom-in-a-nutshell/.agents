from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    init_git_repo,
    make_control_plane_root,
    run_command,
    write_json,
    write_text,
)


class CodexRepoSyncTests(TempDirTestCase):
    def test_renders_repo_config_and_prunes_stale_managed_role_files(self) -> None:
        root = make_control_plane_root(self.temp_path)
        adi = init_git_repo(self.temp_path / "adi")

        repo_registry_path = root / "codex/config/repo-bootstrap.json"
        mcp_registry_path = root / "mcp/config/presets.json"
        plugin_registry_path = root / "plugins/registry.json"
        stale_managed_role = write_text(
            adi / ".codex/agents/writer.toml",
            "\n".join(
                [
                    "# Managed by ~/.agents/codex/scripts/sync-repo-codex-configs.sh.",
                    "# Old generated file.",
                    'name = "writer"',
                    'description = "Stale managed writer."',
                    "",
                ]
            ),
        )
        write_json(
            repo_registry_path,
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_auto_compact_token_limit": 204000,
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [
                    {
                        "mcp_presets": ["cloudflare-docs", "fixture-stdio"],
                        "path": str(adi),
                    }
                ],
            },
        )
        mcp_registry = default_mcp_registry()
        mcp_registry["presets"]["fixture-stdio"] = {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "fixture-mcp@latest", "mcp"],
        }
        write_json(mcp_registry_path, mcp_registry)

        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-repo-codex-configs.sh"),
                "--apply",
                "--registry",
                str(repo_registry_path),
                "--mcp-registry",
                str(mcp_registry_path),
                "--plugin-registry",
                str(plugin_registry_path),
            ]
        )

        repo_config = (adi / ".codex/config.toml").read_text(encoding="utf-8")
        repo_hooks = (adi / ".codex/hooks.json").read_text(encoding="utf-8")

        self.assertIn('model = "gpt-5.5"', repo_config)
        self.assertIn("model_auto_compact_token_limit = 204000", repo_config)
        self.assertIn('model_reasoning_effort = "high"', repo_config)
        self.assertIn("[mcp_servers.cloudflare-docs]", repo_config)
        self.assertIn('url = "https://docs.mcp.cloudflare.com/mcp"', repo_config)
        self.assertIn("[mcp_servers.fixture-stdio]", repo_config)
        self.assertIn('command = "npx"', repo_config)
        self.assertNotIn("[agents.", repo_config)
        self.assertIn('"SessionStart"', repo_hooks)

        self.assertFalse(stale_managed_role.exists())

    def test_renders_repo_scoped_plugins_only_for_assigned_repo(self) -> None:
        root = make_control_plane_root(self.temp_path)
        github_root = self.temp_path / "GitHub"
        adi = init_git_repo(github_root / "adi")
        win = init_git_repo(github_root / "win")

        repo_registry_path = root / "codex/config/repo-bootstrap.json"
        mcp_registry_path = root / "mcp/config/presets.json"
        plugin_registry_path = root / "plugins/registry.json"

        write_json(
            repo_registry_path,
            {
                "defaults": {},
                "repos": [
                    {"path": str(adi)},
                    {"path": str(win)},
                ],
            },
        )
        write_json(mcp_registry_path, default_mcp_registry())
        write_json(
            plugin_registry_path,
            {
                "version": 1,
                "paths": {
                    "github_root": str(github_root),
                },
                "managed_plugins": [
                    {
                        "plugin": "computer-use",
                        "marketplace": "openai-bundled",
                        "enabled": True,
                        "scope": "global",
                        "repos": [],
                        "category": "Productivity",
                    },
                    {
                        "plugin": "build-ios-apps",
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["adi"],
                        "category": "Coding",
                    },
                ],
                "unmanaged_repo_local_plugins": [],
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
                "--plugin-registry",
                str(plugin_registry_path),
            ]
        )

        adi_config = (adi / ".codex/config.toml").read_text(encoding="utf-8")
        win_config = (win / ".codex/config.toml").read_text(encoding="utf-8")

        self.assertIn('[plugins."build-ios-apps@openai-curated"]', adi_config)
        self.assertIn("enabled = true", adi_config)
        self.assertNotIn('[plugins."computer-use@openai-bundled"]', adi_config)
        self.assertNotIn("build-ios-apps@openai-curated", win_config)
