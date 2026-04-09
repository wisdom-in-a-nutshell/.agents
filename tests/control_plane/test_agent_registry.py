from __future__ import annotations

from pathlib import Path

from agents.registry import load_agent_registry

from tests.control_plane.support import (
    TempDirTestCase,
    external_researcher_agent,
    make_control_plane_root,
    visual_reviewer_agent,
    write_json,
)


class LoadAgentRegistryTests(TempDirTestCase):
    def test_normalizes_runtime_metadata_and_source_paths(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "agents/registry.json"
        write_json(
            registry_path,
            {
                "managed_agents": [
                    external_researcher_agent(),
                    visual_reviewer_agent("adi"),
                ],
                "version": 1,
            },
        )

        agents = load_agent_registry(
            registry_path,
            root_dir=root,
            valid_repo_names={"adi"},
        )

        self.assertEqual(2, len(agents))

        external = agents[0]
        self.assertEqual("external-researcher", external["agent"])
        self.assertEqual("global", external["scope"])
        self.assertEqual([], external["repos"])
        self.assertEqual(
            root / "codex/config/agents/external_researcher.toml",
            Path(external["codex"]["source_path"]),
        )
        self.assertEqual(
            root / "claude/config/agents/external-researcher.md",
            Path(external["claude"]["source_path"]),
        )
        self.assertEqual(
            ["Read", "Grep", "Glob", "WebFetch"],
            external["claude"]["tools"],
        )

        reviewer = agents[1]
        self.assertEqual("visual-reviewer", reviewer["agent"])
        self.assertEqual("repo", reviewer["scope"])
        self.assertEqual(["adi"], reviewer["repos"])
        self.assertEqual("visual_reviewer", reviewer["codex"]["name"])
        self.assertEqual(
            ["Lens", "Critic", "Review"],
            reviewer["codex"]["nickname_candidates"],
        )
        self.assertEqual("cyan", reviewer["claude"]["color"])

    def test_rejects_invalid_claude_tools_shape(self) -> None:
        root = make_control_plane_root(self.temp_path)
        registry_path = root / "agents/registry.json"
        invalid = visual_reviewer_agent("adi")
        invalid["claude"]["tools"] = "Read"  # type: ignore[index]
        write_json(
            registry_path,
            {
                "managed_agents": [invalid],
                "version": 1,
            },
        )

        with self.assertRaisesRegex(
            ValueError,
            r"managed_agents\[0\]\.claude\.tools must be an array of strings",
        ):
            load_agent_registry(
                registry_path,
                root_dir=root,
                valid_repo_names={"adi"},
            )
