from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    make_control_plane_root,
    run_command,
    write_json,
)


class ManagedPluginsRegistrySyncTests(TempDirTestCase):
    def test_generates_registry_views_for_managed_official_plugins(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {
                    "github_root": "~/GitHub",
                },
                "managed_plugins": [
                    {
                        "plugin_id": "build-ios-apps@openai-curated",
                        "scope": "repo",
                        "repos": ["adi"],
                        "enabled": True,
                        "category": "Coding",
                    },
                    {
                        "plugin_id": "build-web-apps@openai-curated",
                        "scope": "global",
                        "repos": [],
                        "enabled": False,
                        "category": "Coding",
                    },
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
        managed_item = (
            root
            / "docs/references/registry/plugins-items/managed/build-ios-apps-openai-curated.md"
        )
        repo_local_item = (
            root / "docs/references/registry/plugins-items/repo-local/adi--local-review.md"
        )

        self.assertTrue(plugins_base.is_file())
        self.assertTrue(managed_item.is_file())
        self.assertTrue(repo_local_item.is_file())
        self.assertFalse((root / "plugins/marketplace.json").exists())

        managed_text = managed_item.read_text(encoding="utf-8")
        self.assertIn('plugin_id: "build-ios-apps@openai-curated"', managed_text)
        self.assertIn('plugin_name: "build-ios-apps"', managed_text)
        self.assertIn('marketplace: "openai-curated"', managed_text)
        self.assertIn('scope: "repo"', managed_text)
        self.assertIn("enabled: true", managed_text)
        self.assertIn('repos_csv: "adi"', managed_text)

    def test_empty_managed_plugins_is_valid(self) -> None:
        root = make_control_plane_root(self.temp_path)
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
        self.assertTrue((root / "docs/references/registry/plugins.base").is_file())
