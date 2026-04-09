from __future__ import annotations

from pathlib import Path

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    external_researcher_agent,
    init_git_repo,
    make_control_plane_root,
    read_json,
    run_command,
    visual_reviewer_agent,
    write_json,
)


class ClaudeSubagentSyncTests(TempDirTestCase):
    def _script_path(self) -> str:
        return str(REPO_ROOT / "claude/scripts/sync-subagents.sh")

    def test_renders_expected_frontmatter_and_full_access_mapping(self) -> None:
        root = make_control_plane_root(self.temp_path)
        adi = init_git_repo(self.temp_path / "adi")
        global_agents_dir = self.temp_path / "home/.claude/agents"

        write_json(
            root / "codex/config/repo-bootstrap.json",
            {
                "defaults": {},
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )

        hot_agent = {
            "access_profile": "full_access",
            "agent": "research-hot",
            "claude": {
                "prompt_file": "external-researcher.md",
                "tools": ["Read"],
            },
            "description": "Full-access Claude-only research worker.",
            "repos": [],
            "scope": "global",
        }

        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [
                    external_researcher_agent(),
                    visual_reviewer_agent("adi"),
                    hot_agent,
                ],
                "version": 1,
            },
        )

        run_command(
            [
                self._script_path(),
                "--apply",
                "--registry",
                str(root / "codex/config/repo-bootstrap.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--global-agents-dir",
                str(global_agents_dir),
            ]
        )

        global_external = global_agents_dir / "external-researcher.md"
        global_hot = global_agents_dir / "research-hot.md"
        repo_reviewer = adi / ".claude/agents/visual-reviewer.md"

        self.assertTrue(global_external.is_file())
        self.assertTrue(global_hot.is_file())
        self.assertTrue(repo_reviewer.is_file())

        external_text = global_external.read_text(encoding="utf-8")
        self.assertIn('name: "external-researcher"', external_text)
        self.assertIn('description: "Read-only researcher for information outside the local codebase and runtime."', external_text)
        self.assertIn('  - "WebFetch"', external_text)
        self.assertNotIn("permissionMode", external_text)

        hot_text = global_hot.read_text(encoding="utf-8")
        self.assertIn('name: "research-hot"', hot_text)
        self.assertIn('permissionMode: "bypassPermissions"', hot_text)

        reviewer_text = repo_reviewer.read_text(encoding="utf-8")
        self.assertIn('name: "visual-reviewer"', reviewer_text)
        self.assertIn('color: "cyan"', reviewer_text)
        self.assertIn("Stay in visual review mode.", reviewer_text)

        global_manifest = read_json(global_agents_dir / ".managed-subagents.json")
        self.assertEqual(
            ["external-researcher.md", "research-hot.md"],
            global_manifest["files"],
        )
        repo_manifest = read_json(adi / ".claude/agents/.managed-subagents.json")
        self.assertEqual(["visual-reviewer.md"], repo_manifest["files"])

    def test_prunes_removed_managed_repo_subagent(self) -> None:
        root = make_control_plane_root(self.temp_path)
        adi = init_git_repo(self.temp_path / "adi")
        global_agents_dir = self.temp_path / "home/.claude/agents"

        repo_registry_path = root / "codex/config/repo-bootstrap.json"
        agent_registry_path = root / "agents/registry.json"

        write_json(
            repo_registry_path,
            {
                "defaults": {},
                "repos": [
                    {
                        "path": str(adi),
                    }
                ],
            },
        )
        write_json(
            agent_registry_path,
            {
                "managed_agents": [
                    external_researcher_agent(),
                    visual_reviewer_agent("adi"),
                ],
                "version": 1,
            },
        )

        sync_args = [
            self._script_path(),
            "--apply",
            "--registry",
            str(repo_registry_path),
            "--agent-registry",
            str(agent_registry_path),
            "--global-agents-dir",
            str(global_agents_dir),
        ]
        run_command(sync_args)

        repo_agents_dir = adi / ".claude/agents"
        self.assertTrue((repo_agents_dir / "visual-reviewer.md").is_file())
        self.assertTrue((repo_agents_dir / ".managed-subagents.json").is_file())

        write_json(
            agent_registry_path,
            {
                "managed_agents": [
                    external_researcher_agent(),
                ],
                "version": 1,
            },
        )

        run_command(sync_args)

        self.assertFalse((repo_agents_dir / "visual-reviewer.md").exists())
        self.assertFalse((repo_agents_dir / ".managed-subagents.json").exists())
        self.assertTrue((global_agents_dir / "external-researcher.md").is_file())
