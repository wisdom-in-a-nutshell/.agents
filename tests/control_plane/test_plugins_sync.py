from __future__ import annotations

import json

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    default_skills_registry,
    init_git_repo,
    make_control_plane_root,
    run_command,
    write_json,
    write_text,
)


class ManagedPluginsRegistrySyncTests(TempDirTestCase):
    def test_generates_registry_views_and_derived_skill_mcp_state(self) -> None:
        root = make_control_plane_root(self.temp_path)
        adi = init_git_repo(self.temp_path / "adi")
        write_json(root / "skills/registry.json", default_skills_registry())
        write_json(root / "mcp/config/presets.json", default_mcp_registry())
        plugin_root = root / "plugins-source/external/build-ios-apps"
        (plugin_root / "skills/ios-debugger-agent").mkdir(parents=True, exist_ok=True)
        (plugin_root / "skills/swiftui-ui-patterns").mkdir(parents=True, exist_ok=True)
        write_text(plugin_root / "skills/ios-debugger-agent/SKILL.md", "---\nname: ios-debugger-agent\n---\n")
        write_text(plugin_root / "skills/swiftui-ui-patterns/SKILL.md", "---\nname: swiftui-ui-patterns\n---\n")
        write_text(
            plugin_root / ".mcp.json",
            json.dumps(
                {
                    "mcpServers": {
                        "xcodebuildmcp": {
                            "command": "npx",
                            "args": ["-y", "xcodebuildmcp@latest", "mcp"],
                            "env": {
                                "XCODEBUILDMCP_ENABLED_WORKFLOWS": "simulator,ui-automation,debugging,logging"
                            },
                        }
                    }
                },
                indent=2,
            )
            + "\n",
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
        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {
                    "github_root": str(self.temp_path),
                },
                "managed_plugins": [
                    {
                        "plugin": "build-ios-apps",
                        "origin": "external",
                        "scope": "repo",
                        "repos": [str(adi)],
                        "mcp_scope": "repo",
                        "mcp_repos": [str(adi)],
                        "source_path": "plugins-source/external/build-ios-apps",
                        "upstream_ref": "openai/plugins:plugins/build-ios-apps@main",
                        "category": "Coding",
                    }
                ],
                "unmanaged_repo_local_plugins": [
                    {
                        "repo": "adi",
                        "plugin": "local-review",
                    }
                ],
            },
        )

        run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-plugins-registry.py"),
                "--apply",
                str(registry_path),
            ]
        )

        plugins_base = root / "docs/references/registry/plugins.base"
        managed_item = root / "docs/references/registry/plugins-items/managed/build-ios-apps.md"
        repo_local_item = (
            root / "docs/references/registry/plugins-items/repo-local/adi--local-review.md"
        )

        self.assertTrue(plugins_base.is_file())
        self.assertTrue(managed_item.is_file())
        self.assertTrue(repo_local_item.is_file())

        managed_text = managed_item.read_text(encoding="utf-8")
        self.assertIn('plugin: "build-ios-apps"', managed_text)
        self.assertIn('origin: "external"', managed_text)
        self.assertIn('scope: "repo"', managed_text)
        self.assertIn('mcp_scope: "repo"', managed_text)
        self.assertIn('source_path: "plugins-source/external/build-ios-apps"', managed_text)

        skills_registry = json.loads((root / "skills/registry.json").read_text(encoding="utf-8"))
        managed_plugin_skills = skills_registry.get("managed_plugin_skills", [])
        self.assertEqual(2, len(managed_plugin_skills))
        self.assertEqual(
            ["ios-debugger-agent", "swiftui-ui-patterns"],
            sorted(item["skill"] for item in managed_plugin_skills),
        )
        self.assertTrue(
            all(item["source_plugin"] == "build-ios-apps" for item in managed_plugin_skills)
        )

        mcp_registry = json.loads((root / "mcp/config/presets.json").read_text(encoding="utf-8"))
        self.assertIn(
            "xcodebuildmcp",
            mcp_registry.get("plugin_presets", {}),
        )

        repo_bootstrap = json.loads(
            (root / "codex/config/repo-bootstrap.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["xcodebuildmcp"],
            repo_bootstrap["repos"][0]["plugin_mcp_presets"],
        )

    def test_empty_managed_plugins_is_valid(self) -> None:
        root = make_control_plane_root(self.temp_path)
        write_json(root / "skills/registry.json", default_skills_registry())
        write_json(root / "mcp/config/presets.json", default_mcp_registry())
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {
                    "model": "gpt-5.5",
                    "model_reasoning_effort": "high",
                    "service_tier": None,
                },
                "repos": [],
            },
        )
        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {
                    "github_root": "~/GitHub",
                },
                "managed_plugins": [],
                "unmanaged_repo_local_plugins": [],
            },
        )

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-plugins-registry.py"),
                str(registry_path),
            ]
        )

        self.assertIn("Managed plugins: 0", result.stdout)
        self.assertIn("Derived skills: 0", result.stdout)
        self.assertIn("Derived MCP presets: 0", result.stdout)
        self.assertTrue((root / "docs/references/registry/plugins.base").is_file())
