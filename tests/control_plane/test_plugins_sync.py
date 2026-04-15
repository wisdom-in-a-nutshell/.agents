from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    make_control_plane_root,
    make_plugin_source,
    run_command,
    write_json,
)


class ManagedPluginsRegistrySyncTests(TempDirTestCase):
    def test_syncs_managed_plugin_links_marketplaces_and_generated_registry_views(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        global_source = make_plugin_source(
            root / "plugins-source/owned/build-global",
            "build-global",
        )
        repo_source = make_plugin_source(
            root / "plugins-source/owned/build-repo",
            "build-repo",
        )
        stale_source = make_plugin_source(
            root / "plugins-source/owned/stale-plugin",
            "stale-plugin",
        )

        stale_link = home / ".codex/plugins/stale-plugin"
        stale_link.parent.mkdir(parents=True, exist_ok=True)
        stale_link.symlink_to(stale_source)

        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "managed_plugins": [
                    {
                        "plugin": "build-global",
                        "origin": "owned",
                        "scope": "global",
                        "repos": [],
                        "source_path": "plugins-source/owned/build-global",
                        "category": "Coding",
                        "policy": {
                            "installation": "INSTALLED_BY_DEFAULT",
                            "authentication": "ON_INSTALL",
                        },
                    },
                    {
                        "plugin": "build-repo",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "plugins-source/owned/build-repo",
                        "category": "Coding",
                        "policy": {
                            "installation": "INSTALLED_BY_DEFAULT",
                            "authentication": "ON_USE",
                        },
                    },
                ],
                "marketplaces": {
                    "global": {
                        "name": "managed-plugins",
                        "display_name": "Managed Plugins",
                    }
                },
                "paths": {
                    "github_root": str(github_root),
                    "codex_plugin_root": str(home / ".codex/plugins"),
                },
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
            ],
            env={"HOME": str(home)},
        )

        global_link = home / ".codex/plugins/build-global"
        repo_link = adi / "plugins/build-repo"

        self.assertTrue(global_link.is_symlink())
        self.assertEqual(global_source.resolve(), global_link.resolve())
        self.assertTrue(repo_link.is_symlink())
        self.assertEqual(repo_source.resolve(), repo_link.resolve())
        self.assertFalse(stale_link.exists())

        plugins_base = root / "docs/references/registry/plugins.base"
        global_item = root / "docs/references/registry/plugins-items/managed/build-global.md"
        repo_local_item = (
            root / "docs/references/registry/plugins-items/repo-local/adi--local-review.md"
        )
        global_marketplace = root / "plugins/marketplace.json"
        repo_marketplace = adi / ".agents/plugins/marketplace.json"

        self.assertTrue(plugins_base.is_file())
        self.assertTrue(global_item.is_file())
        self.assertTrue(repo_local_item.is_file())
        self.assertTrue(global_marketplace.is_file())
        self.assertTrue(repo_marketplace.is_file())

        global_item_text = global_item.read_text(encoding="utf-8")
        self.assertIn('plugin: "build-global"', global_item_text)
        self.assertIn('scope: "global"', global_item_text)
        self.assertIn('category: "Coding"', global_item_text)
        self.assertIn('installation_policy: "INSTALLED_BY_DEFAULT"', global_item_text)

        global_marketplace_text = global_marketplace.read_text(encoding="utf-8")
        self.assertIn('"name": "managed-plugins"', global_marketplace_text)
        self.assertIn('"path": "./.codex/plugins/build-global"', global_marketplace_text)

        repo_marketplace_text = repo_marketplace.read_text(encoding="utf-8")
        self.assertIn('"path": "./plugins/build-repo"', repo_marketplace_text)
        self.assertIn('"authentication": "ON_USE"', repo_marketplace_text)
        self.assertIn('"installation": "INSTALLED_BY_DEFAULT"', repo_marketplace_text)

    def test_repo_only_plugins_do_not_render_empty_global_marketplace(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        repo_source = make_plugin_source(
            root / "plugins-source/owned/build-repo",
            "build-repo",
        )

        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "managed_plugins": [
                    {
                        "plugin": "build-repo",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "plugins-source/owned/build-repo",
                        "category": "Coding",
                    }
                ],
                "marketplaces": {
                    "global": {
                        "name": "managed-plugins",
                        "display_name": "Managed Plugins",
                    }
                },
                "paths": {
                    "github_root": str(github_root),
                    "codex_plugin_root": str(home / ".codex/plugins"),
                },
                "unmanaged_repo_local_plugins": [],
            },
        )

        run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-plugins-registry.py"),
                "--apply",
                str(registry_path),
            ],
            env={"HOME": str(home)},
        )

        repo_link = adi / "plugins/build-repo"
        repo_marketplace = adi / ".agents/plugins/marketplace.json"
        global_marketplace = root / "plugins/marketplace.json"

        self.assertTrue(repo_link.is_symlink())
        self.assertEqual(repo_source.resolve(), repo_link.resolve())
        self.assertTrue(repo_marketplace.is_file())
        self.assertFalse(global_marketplace.exists())
