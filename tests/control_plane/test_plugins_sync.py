from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    make_control_plane_root,
    run_command,
    write_json,
)


class ManagedPluginsRegistrySyncTests(TempDirTestCase):
    def test_validates_native_codex_plugins_without_legacy_outputs(self) -> None:
        root = make_control_plane_root(self.temp_path)
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
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["adi"],
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

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-plugins-registry.py"),
                "--apply",
                str(registry_path),
            ]
        )

        self.assertIn("Plugin registry validated.", result.stdout)
        self.assertIn("Managed plugins: 1", result.stdout)
        self.assertIn("Enabled plugins: 1", result.stdout)
        self.assertIn("Repo-local plugins: 1", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())

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
        self.assertIn("Enabled plugins: 0", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())
