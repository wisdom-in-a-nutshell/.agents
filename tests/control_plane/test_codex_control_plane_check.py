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
        write_json(root / "mcp/config/presets.json", mcp_registry)
        return root, home, adi

    def _check_command(self, root, home, repo):  # noqa: ANN001, ANN202
        return [
            str(REPO_ROOT / "codex/scripts/check-codex-control-plane.sh"),
            "--canonical-dir",
            str(root / "codex/config"),
            "--global-config",
            str(home / ".codex/config.toml"),
            "--registry",
            str(root / "codex/config/repo-bootstrap.json"),
            "--mcp-registry",
            str(root / "mcp/config/presets.json"),
            "--hooks-registry",
            str(root / "hooks/registry.json"),
            "--plugin-registry",
            str(root / "plugins/registry.json"),
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
                "--plugin-registry",
                str(root / "plugins/registry.json"),
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

    def test_check_script_fails_when_global_plugin_config_is_missing(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        self._render_repo_configs(root, home)
        write_json(
            root / "codex/config/bundled-skills-policy.json",
            {"version": 1, "roots": {}},
        )
        write_text(
            home / ".codex/config.toml",
            'model = "gpt-5.5"\n\n[features]\nhooks = false\n',
        )

        result = run_command(
            self._check_command(root, home, adi),
            env={
                "HOME": str(home),
                "CODEX_BUNDLED_MARKETPLACE": str(home / "missing-bundled-marketplace"),
            },
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "global Codex config missing managed plugin `computer-use@openai-bundled`",
            result.stderr,
        )

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

    def test_sync_config_xcode_only_preserves_xcode_owned_blocks(self) -> None:
        root, home, _adi = self._make_codex_repo_fixture()
        xcode_config = home / "Library/Developer/Xcode/CodingAssistant/codex/config.toml"
        xcode_rules = home / "Library/Developer/Xcode/CodingAssistant/codex/rules/xcode.rules"
        global_auth = home / ".codex/auth.json"
        global_mcp_credentials = home / ".codex/.credentials.json"
        xcode_auth = xcode_config.parent / "auth.json"
        xcode_mcp_credentials = xcode_config.parent / ".credentials.json"
        write_text(global_auth, '{"auth_mode":"chatgpt"}\n')
        write_text(global_mcp_credentials, '{"mcp":"oauth"}\n')
        write_text(
            xcode_config,
            "\n".join(
                [
                    'model = "old-model"',
                    'developer_instructions = """',
                    "Use Xcode's own docs and build tools.",
                    '"""',
                    "",
                    "[mcp_servers.xcode-tools]",
                    'args = ["mcpbridge"]',
                    'command = "xcrun"',
                    "enabled = true",
                    "",
                    "[mcp_servers.xcode-tools.env]",
                    'MCP_XCODE_PID = "123"',
                    'MCP_XCODE_SESSION_ID = "session-123"',
                    "",
                    "[features]",
                    "codex_hooks = true",
                    "",
                    "[apps.xcode-owned]",
                    "enabled = true",
                    "",
                ]
            ),
        )

        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-config.sh"),
                "--apply",
                "--xcode-only",
                "--canonical-dir",
                str(root / "codex/config"),
                "--xcode-config",
                str(xcode_config),
                "--xcode-rules",
                str(xcode_rules),
            ],
            env={"HOME": str(home)},
        )

        rendered = xcode_config.read_text(encoding="utf-8")
        self.assertIn('model = "gpt-5.5"', rendered)
        self.assertIn('approval_policy = "never"', rendered)
        self.assertIn('sandbox_mode = "danger-full-access"', rendered)
        self.assertIn(f'writable_roots = ["{home}/GitHub"]', rendered)
        self.assertIn('model_reasoning_effort = "high"', rendered)
        self.assertIn('plan_mode_reasoning_effort = "high"', rendered)
        self.assertIn("Use Xcode's own docs and build tools.", rendered)
        self.assertIn("[mcp_servers.xcode-tools]", rendered)
        self.assertIn('MCP_XCODE_SESSION_ID = "session-123"', rendered)
        self.assertIn("[apps.xcode-owned]", rendered)
        self.assertNotIn("codex_hooks", rendered)
        self.assertEqual(
            (root / "codex/config/xcode.rules").read_text(encoding="utf-8"),
            xcode_rules.read_text(encoding="utf-8"),
        )
        self.assertTrue(xcode_auth.is_symlink())
        self.assertTrue(xcode_mcp_credentials.is_symlink())
        self.assertEqual(global_auth.resolve(), xcode_auth.resolve())
        self.assertEqual(global_mcp_credentials.resolve(), xcode_mcp_credentials.resolve())

    def test_check_script_fails_when_xcode_auth_link_is_missing(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        self._render_repo_configs(root, home)
        xcode_config = home / "Library/Developer/Xcode/CodingAssistant/codex/config.toml"
        xcode_rules = home / "Library/Developer/Xcode/CodingAssistant/codex/rules/xcode.rules"
        write_text(
            xcode_config,
            (root / "codex/config/xcode.config.toml")
            .read_text(encoding="utf-8")
            .replace("writable_roots = []", f'writable_roots = ["{home}/GitHub"]'),
        )
        write_text(xcode_rules, (root / "codex/config/xcode.rules").read_text(encoding="utf-8"))
        write_text(home / ".codex/auth.json", '{"auth_mode":"chatgpt"}\n')

        result = run_command(
            [
                *self._check_command(root, home, adi),
                "--xcode-config",
                str(xcode_config),
                "--xcode-rules",
                str(xcode_rules),
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Xcode Codex auth.json is not linked", result.stderr)

    def test_check_script_fails_when_xcode_config_drifted_from_template(self) -> None:
        root, home, adi = self._make_codex_repo_fixture()
        self._render_repo_configs(root, home)
        xcode_config = home / "Library/Developer/Xcode/CodingAssistant/codex/config.toml"
        xcode_rules = home / "Library/Developer/Xcode/CodingAssistant/codex/rules/xcode.rules"
        write_text(
            xcode_config,
            (root / "codex/config/xcode.config.toml")
            .read_text(encoding="utf-8")
            .replace("writable_roots = []", f'writable_roots = ["{home}/GitHub"]')
            .replace('model = "gpt-5.5"', 'model = "gpt-5.3"'),
        )
        write_text(xcode_rules, (root / "codex/config/xcode.rules").read_text(encoding="utf-8"))

        result = run_command(
            [
                *self._check_command(root, home, adi),
                "--xcode-config",
                str(xcode_config),
                "--xcode-rules",
                str(xcode_rules),
            ],
            env={"HOME": str(home)},
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Xcode Codex config drift", result.stderr)
        self.assertIn("model", result.stderr)

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
