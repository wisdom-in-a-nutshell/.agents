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


class CodexControlPlaneCheckTests(TempDirTestCase):
    def _make_codex_repo_fixture(self):  # noqa: ANN202
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

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
                        "mcp_presets": ["cloudflare-docs", "xcodebuildmcp"],
                        "path": str(adi),
                    }
                ],
            },
        )
        mcp_registry = default_mcp_registry()
        mcp_registry["presets"]["xcodebuildmcp"] = {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "xcodebuildmcp@latest", "mcp"],
        }
        write_json(root / "mcp/config/presets.json", mcp_registry)
        return root, home, adi

    def _check_command(self, root, home, repo):  # noqa: ANN001, ANN202
        return [
            str(REPO_ROOT / "codex/scripts/check-codex-control-plane.sh"),
            "--canonical-dir",
            str(root / "codex/config"),
            "--global-config",
            str(home / ".codex/config.toml"),
            "--xcode-config",
            str(home / "xcode/config.toml"),
            "--registry",
            str(root / "codex/config/repo-bootstrap.json"),
            "--mcp-registry",
            str(root / "mcp/config/presets.json"),
            "--hooks-registry",
            str(root / "hooks/registry.json"),
            "--repo",
            str(repo),
        ]

    def _render_repo_configs(self, root, home):  # noqa: ANN001
        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-repo-codex-configs.sh"),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env={"HOME": str(home)},
        )

    def test_check_script_passes_for_rendered_repo_configs_and_mcp_assignments(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()

        env = {"HOME": str(home)}
        self._render_repo_configs(root, home)

        result = run_command(
            self._check_command(root, home, adi),
            env=env,
        )

        self.assertIn("OK: Codex control plane validation passed", result.stdout)
        self.assertTrue((adi / ".codex/config.toml").is_file())
        self.assertTrue((adi / ".codex/hooks.json").is_file())

    def test_check_script_fails_for_deprecated_codex_feature_flag(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        global_template = root / "codex/config/global.config.toml"
        global_template.write_text(
            global_template.read_text(encoding="utf-8").replace(
                "hooks = true",
                "codex_hooks = true",
            ),
            encoding="utf-8",
        )

        result = run_command(
            self._check_command(root, home, adi),
            env={"HOME": str(home), "CODEX_FEATURES_LIST_OUTPUT": "hooks stable true\n"},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uses deprecated Codex feature flag `codex_hooks`", result.stderr)

    def test_check_script_fails_when_repo_config_missing_for_managed_repo(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()

        result = run_command(
            self._check_command(root, home, adi),
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repo-local Codex files are out of sync", result.stderr)
        self.assertIn(".codex/config.toml", result.stderr)

    def test_check_script_fails_when_repo_config_drifted_from_registry(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        self._render_repo_configs(root, home)
        config_path = adi / ".codex/config.toml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8").replace(
                'model = "gpt-5.5"',
                'model = "gpt-5.3"',
            ),
            encoding="utf-8",
        )

        result = run_command(
            self._check_command(root, home, adi),
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repo-local Codex files are out of sync", result.stderr)
        self.assertIn('-model = "gpt-5.3"', result.stderr)
        self.assertIn('+model = "gpt-5.5"', result.stderr)

    def test_check_script_fails_for_unclassified_bundled_codex_skill(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        write_text(
            home / ".codex/skills/.system/new-bundled-skill/SKILL.md",
            "---\nname: new-bundled-skill\ndescription: Fixture.\n---\n",
        )

        result = run_command(
            self._check_command(root, home, adi),
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unclassified bundled Codex skill(s)", result.stderr)
        self.assertIn("new-bundled-skill", result.stderr)
        self.assertIn("bundled-skills-policy.json", result.stderr)
