from __future__ import annotations

import unittest

from mcp.control_plane import (
    McpRegistryError,
    claude_server_from_preset,
    copilot_server_from_preset,
    load_mcp_catalog_data,
)


REPOS = [
    {"path": "~/GitHub/agents"},
    {"path": "~/GitHub/frontier-lab-intelligence"},
]


class McpControlPlaneTests(unittest.TestCase):
    def test_compiles_repo_and_client_axes_with_union_semantics(self) -> None:
        catalog = load_mcp_catalog_data(
            {
                "version": 2,
                "presets": {
                    "docs": {
                        "transport": "http",
                        "url": "https://example.com/mcp",
                        "targets": [
                            {"clients": "all", "repos": ["~/GitHub/agents"]}
                        ],
                    },
                    "playwright": {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "targets": [
                            {
                                "clients": ["copilot"],
                                "repos": ["~/GitHub/frontier-lab-intelligence"],
                            },
                            {
                                "clients": ["codex"],
                                "repos": ["~/GitHub/frontier-lab-intelligence"],
                            },
                        ],
                    },
                },
            },
            REPOS,
        )

        self.assertEqual(
            catalog.clients_for("docs", "~/GitHub/agents"),
            ("codex", "claude", "copilot"),
        )
        self.assertEqual(
            catalog.clients_for("playwright", "~/GitHub/frontier-lab-intelligence"),
            ("codex", "copilot"),
        )
        self.assertEqual(
            [name for name, _ in catalog.presets_for("~/GitHub/agents", "copilot")],
            ["docs"],
        )
        self.assertEqual(catalog.exclusive_global_presets_for("copilot"), [])

    def test_identifies_client_exclusive_global_target(self) -> None:
        catalog = load_mcp_catalog_data(
            {
                "version": 2,
                "presets": {
                    "playwright": {
                        "transport": "stdio",
                        "command": "npx",
                        "targets": [{"clients": ["copilot"], "repos": "all"}],
                    }
                },
            },
            REPOS,
        )

        self.assertEqual(catalog.global_clients_used_by("playwright"), ["copilot"])
        self.assertEqual(
            [name for name, _ in catalog.exclusive_global_presets_for("copilot")],
            ["playwright"],
        )

    def test_rejects_workspace_files_that_current_copilot_cli_does_not_merge(self) -> None:
        with self.assertRaisesRegex(McpRegistryError, "does not merge: playwright"):
            load_mcp_catalog_data(
                {
                    "version": 2,
                    "presets": {
                        "docs": {
                            "transport": "http",
                            "url": "https://example.com/mcp",
                            "targets": [
                                {
                                    "clients": ["claude", "copilot"],
                                    "repos": ["~/GitHub/agents"],
                                }
                            ],
                        },
                        "playwright": {
                            "transport": "stdio",
                            "command": "npx",
                            "targets": [
                                {
                                    "clients": ["copilot"],
                                    "repos": ["~/GitHub/agents"],
                                }
                            ],
                        },
                    },
                },
                REPOS,
            )

    def test_rejects_unknown_repo(self) -> None:
        with self.assertRaisesRegex(McpRegistryError, "missing from repo-bootstrap.json"):
            load_mcp_catalog_data(
                {
                    "version": 2,
                    "presets": {
                        "tool": {
                            "transport": "http",
                            "url": "https://example.com/mcp",
                            "targets": [
                                {
                                    "clients": ["copilot"],
                                    "repos": ["~/GitHub/not-managed"],
                                }
                            ],
                        }
                    },
                },
                REPOS,
            )

    def test_rejects_claude_only_target_because_surface_is_shared(self) -> None:
        with self.assertRaisesRegex(McpRegistryError, "Claude without Copilot"):
            load_mcp_catalog_data(
                {
                    "version": 2,
                    "presets": {
                        "tool": {
                            "transport": "http",
                            "url": "https://example.com/mcp",
                            "targets": [
                                {
                                    "clients": ["claude"],
                                    "repos": ["~/GitHub/agents"],
                                }
                            ],
                        }
                    },
                },
                REPOS,
            )

    def test_translates_neutral_definition_for_shared_and_copilot_surfaces(self) -> None:
        preset = {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest"],
            "env": {"MODE": "test"},
        }

        self.assertEqual(
            claude_server_from_preset("playwright", preset),
            {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
                "env": {"MODE": "test"},
            },
        )
        self.assertEqual(
            copilot_server_from_preset("playwright", preset),
            {
                "tools": ["*"],
                "type": "local",
                "command": "npx",
                "args": ["-y", "@playwright/mcp@latest"],
                "env": {"MODE": "test"},
            },
        )


if __name__ == "__main__":
    unittest.main()
