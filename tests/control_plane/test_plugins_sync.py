from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    make_control_plane_root,
    run_command,
    write_executable,
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


class CodexPluginInstallSyncTests(TempDirTestCase):
    def test_dry_run_reports_missing_enabled_non_bundled_plugin(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "plugins/registry.json"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {"github_root": str(self.temp_path)},
                "managed_plugins": [
                    {
                        "plugin": "build-ios-apps",
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["dobby-ios"],
                        "category": "Coding",
                    },
                    {
                        "plugin": "browser",
                        "marketplace": "openai-bundled",
                        "enabled": True,
                        "scope": "global",
                        "repos": [],
                        "category": "Engineering",
                    },
                ],
                "unmanaged_repo_local_plugins": [],
            },
        )

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-codex-plugin-installs.py"),
                "--registry-file",
                str(registry_path),
                "--home",
                str(self.temp_path / "home"),
            ]
        )

        self.assertIn("Required non-bundled Codex plugins: 1", result.stdout)
        self.assertIn("Missing non-bundled Codex plugins: 1", result.stdout)
        self.assertIn("WOULD INSTALL build-ios-apps@openai-curated", result.stdout)
        self.assertNotIn("browser@openai-bundled", result.stdout)

    def test_apply_installs_missing_enabled_non_bundled_plugin(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "plugins/registry.json"
        home = self.temp_path / "home"
        log = self.temp_path / "codex.log"
        codex_bin = self.temp_path / "codex"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {"github_root": str(self.temp_path)},
                "managed_plugins": [
                    {
                        "plugin": "build-ios-apps",
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["dobby-ios"],
                        "category": "Coding",
                    }
                ],
                "unmanaged_repo_local_plugins": [],
            },
        )
        write_executable(
            codex_bin,
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    f"printf '%s\\n' \"$*\" >> {str(log)!r}",
                    "echo 'fake install ok'",
                ]
            ),
        )

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-codex-plugin-installs.py"),
                "--apply",
                "--registry-file",
                str(registry_path),
                "--home",
                str(home),
                "--codex-bin",
                str(codex_bin),
            ]
        )

        self.assertIn("INSTALL build-ios-apps@openai-curated", result.stdout)
        self.assertIn("fake install ok", result.stdout)
        self.assertEqual("plugin add build-ios-apps@openai-curated\n", log.read_text(encoding="utf-8"))

    def test_apply_skips_already_installed_plugin(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "plugins/registry.json"
        home = self.temp_path / "home"
        codex_bin = self.temp_path / "codex"
        write_json(
            registry_path,
            {
                "version": 1,
                "paths": {"github_root": str(self.temp_path)},
                "managed_plugins": [
                    {
                        "plugin": "build-ios-apps",
                        "marketplace": "openai-curated",
                        "enabled": True,
                        "scope": "repo",
                        "repos": ["dobby-ios"],
                        "category": "Coding",
                    }
                ],
                "unmanaged_repo_local_plugins": [],
            },
        )
        write_json(
            home
            / ".codex/plugins/cache/openai-curated/build-ios-apps/1.0.0/.codex-plugin/plugin.json",
            {"name": "build-ios-apps", "version": "1.0.0"},
        )
        write_executable(codex_bin, "#!/usr/bin/env bash\nexit 99\n")

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "scripts/sync-codex-plugin-installs.py"),
                "--apply",
                "--registry-file",
                str(registry_path),
                "--home",
                str(home),
                "--codex-bin",
                str(codex_bin),
            ]
        )

        self.assertIn("Missing non-bundled Codex plugins: 0", result.stdout)
