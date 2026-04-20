from __future__ import annotations

import json
import subprocess
import sys

from hooks.control_plane import (
    HookRegistryError,
    load_hooks_registry,
    merge_claude_hooks,
    render_codex_hooks,
)
from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    external_researcher_agent,
    make_control_plane_root,
    read_json,
    run_command,
    write_json,
)


class HooksControlPlaneTests(TempDirTestCase):
    def test_registry_renders_codex_and_claude_lifecycle_hooks(self) -> None:
        registry = load_hooks_registry(REPO_ROOT / "hooks/registry.json")

        codex_hooks = render_codex_hooks(registry)
        self.assertEqual(
            set(codex_hooks["hooks"].keys()),
            {"SessionStart", "Stop"},
        )
        self.assertEqual(
            codex_hooks["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear",
        )
        self.assertNotIn("matcher", codex_hooks["hooks"]["Stop"][0])
        self.assertEqual(
            codex_hooks["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/lifecycle.py --runtime codex --event Stop",
        )

        claude_settings = merge_claude_hooks({"permissions": {"defaultMode": "bypassPermissions"}}, registry)
        self.assertEqual(
            claude_settings["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear|compact",
        )
        self.assertEqual(
            claude_settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/lifecycle.py --runtime claude --event Stop",
        )

    def test_registry_rejects_unsupported_runtime(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime} --event {event}",
                        "enabled": True,
                        "event": "Stop",
                        "id": "bad-runtime",
                        "runtimes": ["copilot"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_lifecycle_runner_is_silent_success_for_supported_events(self) -> None:
        for runtime in ("codex", "claude"):
            for event in ("SessionStart", "Stop"):
                payload = {
                    "cwd": str(self.temp_path),
                    "hook_event_name": event,
                    "model": "gpt-5.4",
                    "session_id": "session",
                    "transcript_path": None,
                }
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "hooks/scripts/lifecycle.py"),
                        "--runtime",
                        runtime,
                        "--event",
                        event,
                    ],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_codex_sync_config_renders_plan_mode_and_global_hooks(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        write_json(root / "mcp/config/presets.json", default_mcp_registry())
        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [external_researcher_agent()],
                "version": 1,
            },
        )

        run_command(
            [
                str(REPO_ROOT / "codex/scripts/sync-config.sh"),
                "--apply",
                "--global-only",
                "--global-config",
                str(home / ".codex/config.toml"),
                "--global-hooks",
                str(home / ".codex/hooks.json"),
                "--canonical-dir",
                str(root / "codex/config"),
                "--mcp-registry",
                str(root / "mcp/config/presets.json"),
                "--agent-registry",
                str(root / "agents/registry.json"),
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env={"HOME": str(home)},
        )

        rendered_config = (home / ".codex/config.toml").read_text(encoding="utf-8")
        self.assertIn('model = "gpt-5.4"', rendered_config)
        self.assertIn('model_reasoning_effort = "high"', rendered_config)
        self.assertIn('plan_mode_reasoning_effort = "high"', rendered_config)
        self.assertIn("codex_hooks = true", rendered_config)

        hooks = read_json(home / ".codex/hooks.json")
        self.assertEqual(
            hooks["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/lifecycle.py --runtime codex --event Stop",
        )
