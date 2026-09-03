from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    init_git_repo,
    make_control_plane_root,
    make_skill_source,
    read_json,
    run_command,
    write_json,
)


class RepoBootstrapRegistryValidationTests(TempDirTestCase):
    def test_canonical_registry_leaves_thread_selection_to_the_client(self) -> None:
        registry = read_json(REPO_ROOT / "codex/config/repo-bootstrap.json")
        global_config = (REPO_ROOT / "codex/config/global.config.toml").read_text(
            encoding="utf-8"
        )

        client_owned_keys = (
            "model",
            "model_auto_compact_token_limit",
            "model_provider",
            "model_reasoning_effort",
            "model_reasoning_summary",
            "model_verbosity",
            "plan_mode_reasoning_effort",
            "profile",
            "service_tier",
        )
        scopes = [registry.get("defaults", {}), *registry.get("repos", [])]

        for key in client_owned_keys:
            self.assertNotRegex(global_config, rf"(?m)^\s*{key}\s*=")
        self.assertNotIn("fast_mode", global_config)
        self.assertNotIn("default-service-tier", global_config)
        for key in client_owned_keys:
            for scope in scopes:
                self.assertNotIn(key, scope)
        for scope in scopes:
            self.assertNotIn("fast_mode", scope.get("features", {}))

    def test_rejects_client_owned_thread_selection(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        repo = init_git_repo(home / "GitHub/adi")
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        cases = {
            "model": "gpt-5.6-sol",
            "model_auto_compact_token_limit": 204000,
            "model_provider": "openai",
            "model_reasoning_effort": "high",
            "model_reasoning_summary": "auto",
            "model_verbosity": "low",
            "plan_mode_reasoning_effort": "high",
            "profile": "chatgpt",
            "service_tier": "fast",
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                write_json(
                    root / "codex/config/repo-bootstrap.json",
                    {"defaults": {}, "repos": [{"path": str(repo), key: value}]},
                )
                result = run_command(
                    [
                        "python3",
                        str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                        str(root / "codex/config/repo-bootstrap.json"),
                        "--mcp-registry",
                        str(root / "mcp/config/presets.json"),
                    ],
                    env={"HOME": str(home)},
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("client-owned thread selection", result.stderr)

        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {"features": {"fast_mode": True}},
                "repos": [{"path": str(repo)}],
            },
        )
        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env={"HOME": str(home)},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("features.fast_mode", result.stderr)

    def test_validates_model_instructions_clients(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        repo = init_git_repo(home / "GitHub/adi")
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        def validate(repo_entry: dict[str, object]):
            write_json(
                root / "codex/config/repo-bootstrap.json",
                {"defaults": {}, "repos": [{"path": str(repo), **repo_entry}]},
            )
            return run_command(
                [
                    "python3",
                    str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                    str(root / "codex/config/repo-bootstrap.json"),
                    "--mcp-registry",
                    str(root / "mcp/config/presets.json"),
                ],
                env={"HOME": str(home)},
                check=False,
            )

        valid = validate(
            {
                "model_instructions_file": "../dobby/constitution.md",
                "model_instructions_clients": ["codex"],
            }
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)

        cases = [
            (
                {
                    "model_instructions_file": "../dobby/constitution.md",
                    "model_instructions_clients": [],
                },
                "must be a non-empty array",
            ),
            (
                {
                    "model_instructions_file": "../dobby/constitution.md",
                    "model_instructions_clients": ["codex", "unknown"],
                },
                "has unsupported clients",
            ),
            (
                {
                    "model_instructions_file": "../dobby/constitution.md",
                    "model_instructions_clients": ["claude"],
                },
                "must include codex",
            ),
            (
                {
                    "model_instructions_file": "../dobby/constitution.md",
                    "model_instructions_clients": ["codex", "codex"],
                },
                "must not contain duplicates",
            ),
            (
                {"model_instructions_clients": ["codex"]},
                "requires model_instructions_file",
            ),
        ]
        for entry, message in cases:
            with self.subTest(message=message):
                result = validate(entry)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_validates_enabled_clients_and_identity_subset(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        repo = init_git_repo(home / "GitHub/adi")
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        def validate(repo_entry: dict[str, object]):
            write_json(
                root / "codex/config/repo-bootstrap.json",
                {"defaults": {}, "repos": [{"path": str(repo), **repo_entry}]},
            )
            return run_command(
                [
                    "python3",
                    str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                    str(root / "codex/config/repo-bootstrap.json"),
                    "--mcp-registry",
                    str(root / "mcp/config/presets.json"),
                ],
                env={"HOME": str(home)},
                check=False,
            )

        valid = validate(
            {
                "enabled_clients": ["codex"],
                "model_instructions_file": "../dobby/constitution.md",
                "model_instructions_clients": ["codex"],
            }
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)

        cases = [
            ({"enabled_clients": []}, "must be a non-empty array"),
            ({"enabled_clients": ["codex", "unknown"]}, "unsupported clients"),
            ({"enabled_clients": ["codex", "codex"]}, "must not contain duplicates"),
            ({"enabled_clients": ["claude"]}, "must include codex"),
            (
                {
                    "enabled_clients": ["codex"],
                    "model_instructions_file": "../dobby/constitution.md",
                    "model_instructions_clients": ["codex", "claude"],
                },
                "must be a subset of enabled_clients",
            ),
        ]
        for entry, message in cases:
            with self.subTest(message=message):
                result = validate(entry)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_validates_repo_mcp_and_skill_inputs_without_legacy_outputs(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        make_skill_source(root / "skills-source/owned/repo-helper", "repo-helper")
        make_skill_source(adi / ".agents/skills/local-review", "local-review")

        write_json(
            root / "skills/registry.json",
            {
                "managed_skills": [
                    {
                        "skill": "global-helper",
                        "origin": "owned",
                        "scope": "global",
                        "source_path": "skills-source/owned/global-helper",
                    },
                    {
                        "skill": "repo-helper",
                        "origin": "owned",
                        "scope": "repo",
                        "repos": ["adi"],
                        "source_path": "skills-source/owned/repo-helper",
                    },
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "local-review",
                    }
                ],
            },
        )
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {"personality": "friendly"},
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env={"HOME": str(home)},
        )

        self.assertIn("Repo bootstrap registry validated.", result.stdout)
        self.assertIn("Repos: 1", result.stdout)
        self.assertIn("MCP presets:", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())

    def test_accepts_declared_repo_local_skills_without_legacy_outputs(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        adi = init_git_repo(github_root / "adi")

        make_skill_source(root / "skills-source/owned/global-helper", "global-helper")
        (adi / ".agents/skills/missing-local").mkdir(parents=True, exist_ok=True)

        write_json(
            root / "skills/registry.json",
            {
                "managed_skills": [
                    {
                        "skill": "global-helper",
                        "origin": "owned",
                        "scope": "global",
                        "source_path": "skills-source/owned/global-helper",
                    }
                ],
                "paths": {
                    "github_root": str(github_root),
                },
                "unmanaged_repo_local_skills": [
                    {
                        "repo": "adi",
                        "skill": "missing-local",
                    }
                ],
            },
        )
        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {"personality": "friendly"},
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

        result = run_command(
            [
                "python3",
                str(REPO_ROOT / "codex/scripts/sync-repo-bootstrap-registry.py"),
                str(root / "codex/config/repo-bootstrap.json"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
            ],
            env={"HOME": str(home)},
        )

        self.assertIn("Repo bootstrap registry validated.", result.stdout)
        self.assertIn("Repos: 1", result.stdout)
        self.assertFalse((root / "docs/references/registry").exists())
