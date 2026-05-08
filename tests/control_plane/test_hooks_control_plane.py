from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from hooks.control_plane import (
    HookRegistryError,
    load_hooks_registry,
    merge_claude_hooks,
    render_copilot_hooks,
    render_codex_hooks,
)
from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    default_mcp_registry,
    init_git_repo,
    make_control_plane_root,
    read_json,
    run_command,
    write_executable,
    write_json,
)


class HooksControlPlaneTests(TempDirTestCase):
    def load_stop_module(self):  # noqa: ANN201
        stop_path = REPO_ROOT / "hooks/scripts/stop.py"
        spec = importlib.util.spec_from_file_location("hooks_stop", stop_path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"Failed to load Stop hook module from {stop_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_registry_renders_codex_and_claude_hooks(self) -> None:
        registry = load_hooks_registry(REPO_ROOT / "hooks/registry.json")

        global_codex_hooks = render_codex_hooks(registry)
        self.assertEqual(set(global_codex_hooks["hooks"].keys()), {"Stop"})
        self.assertEqual(
            global_codex_hooks["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/stop.py --runtime codex",
        )
        self.assertEqual(
            global_codex_hooks["hooks"]["Stop"][0]["hooks"][0]["timeout"],
            900,
        )

        codex_hooks = render_codex_hooks(registry, repo_name="adi")
        self.assertEqual(
            set(codex_hooks["hooks"].keys()),
            {"SessionStart", "UserPromptSubmit"},
        )
        self.assertEqual(
            codex_hooks["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear",
        )
        self.assertEqual(
            codex_hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/user_prompt_submit.py --runtime codex",
        )
        self.assertEqual(
            set(render_codex_hooks(registry, repo_name="win")["hooks"].keys()),
            set(),
        )

        claude_settings = merge_claude_hooks({"permissions": {"defaultMode": "bypassPermissions"}}, registry)
        self.assertEqual(set(claude_settings["hooks"].keys()), {"Stop"})
        self.assertEqual(
            claude_settings["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/stop.py --runtime claude",
        )

        claude_settings = merge_claude_hooks(
            {"permissions": {"defaultMode": "bypassPermissions"}},
            registry,
            repo_name="adi",
        )
        self.assertEqual(
            claude_settings["hooks"]["SessionStart"][0]["matcher"],
            "startup|resume|clear|compact",
        )
        self.assertEqual(
            claude_settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/user_prompt_submit.py --runtime claude",
        )
        self.assertNotIn("Stop", claude_settings["hooks"])
        self.assertEqual(
            claude_settings["hooks"]["SessionEnd"][0]["matcher"],
            "clear|resume|logout|prompt_input_exit|bypass_permissions_disabled|other",
        )
        self.assertEqual(
            claude_settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/session_end.py --runtime claude",
        )
        self.assertEqual(
            set(merge_claude_hooks({}, registry)["hooks"].keys()),
            {"Stop"},
        )

        self.assertEqual(render_copilot_hooks(registry), {"hooks": {}, "version": 1})

        copilot_hooks = render_copilot_hooks(registry, repo_name="adi")
        self.assertEqual(
            copilot_hooks,
            {
                "hooks": {
                    "agentStop": [
                        {
                            "bash": (
                                'if [ -f "$HOME/.agents/hooks/scripts/stop.py" ]; '
                                'then python3 "$HOME/.agents/hooks/scripts/stop.py" --runtime copilot; fi'
                            ),
                            "cwd": ".",
                            "timeoutSec": 900,
                            "type": "command",
                        }
                    ],
                    "sessionEnd": [
                        {
                            "bash": (
                                'if [ -f "$HOME/.agents/hooks/scripts/session_end.py" ]; '
                                'then python3 "$HOME/.agents/hooks/scripts/session_end.py" --runtime copilot; fi'
                            ),
                            "cwd": ".",
                            "timeoutSec": 5,
                            "type": "command",
                        }
                    ],
                    "sessionStart": [
                        {
                            "bash": (
                                'if [ -f "$HOME/.agents/hooks/scripts/session_start.py" ]; '
                                'then python3 "$HOME/.agents/hooks/scripts/session_start.py" --runtime copilot; fi'
                            ),
                            "cwd": ".",
                            "timeoutSec": 5,
                            "type": "command",
                        }
                    ],
                    "userPromptSubmitted": [
                        {
                            "bash": (
                                'if [ -f "$HOME/.agents/hooks/scripts/user_prompt_submit.py" ]; '
                                'then python3 "$HOME/.agents/hooks/scripts/user_prompt_submit.py" --runtime copilot; fi'
                            ),
                            "cwd": ".",
                            "timeoutSec": 5,
                            "type": "command",
                        }
                    ],
                },
                "version": 1,
            },
        )
        self.assertEqual(
            set(render_copilot_hooks(registry, repo_name="win")["hooks"].keys()),
            {"agentStop"},
        )

    def test_registry_rejects_unsupported_runtime(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "event": "Stop",
                        "id": "bad-runtime",
                        "runtimes": ["unknown"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_registry_rejects_event_on_unsupported_runtime(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "event": "SessionEnd",
                        "id": "bad-event-runtime",
                        "runtimes": ["codex"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_registry_rejects_matcher_runtime_not_in_hook_runtimes(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "event": "SessionStart",
                        "id": "bad-matcher-runtime",
                        "matchers": {
                            "codex": "startup",
                        },
                        "runtimes": ["claude"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_registry_rejects_matcher_for_unsupported_event_runtime(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "event": "SessionEnd",
                        "id": "bad-event-matcher-runtime",
                        "matchers": {
                            "codex": "logout",
                        },
                        "runtimes": ["claude"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_registry_rejects_matchers_for_events_without_matchers(self) -> None:
        registry_path = self.temp_path / "hooks/registry.json"
        write_json(
            registry_path,
            {
                "managed_hooks": [
                    {
                        "command": "python3 hook.py --runtime {runtime}",
                        "enabled": True,
                        "event": "Stop",
                        "id": "bad-stop-matcher",
                        "matchers": {
                            "codex": "anything",
                        },
                        "runtimes": ["codex"],
                        "scope": "global",
                        "timeout": 5,
                    }
                ],
                "version": 1,
            },
        )

        with self.assertRaises(HookRegistryError):
            load_hooks_registry(registry_path)

    def test_hook_runners_are_silent_on_success(self) -> None:
        script_by_event = {
            "SessionStart": REPO_ROOT / "hooks/scripts/session_start.py",
            "UserPromptSubmit": REPO_ROOT / "hooks/scripts/user_prompt_submit.py",
            "Stop": REPO_ROOT / "hooks/scripts/stop.py",
            "SessionEnd": REPO_ROOT / "hooks/scripts/session_end.py",
        }
        home = self.temp_path / "home"
        for runtime in ("codex", "claude", "copilot"):
            for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
                if event == "SessionEnd" and runtime == "codex":
                    continue
                payload = {
                    "cwd": str(self.temp_path),
                    "hook_event_name": event,
                    "model": "gpt-5.5",
                    "session_id": "session",
                    "transcript_path": None,
                }
                result = subprocess.run(
                    [
                        sys.executable,
                        str(script_by_event[event]),
                        "--runtime",
                        runtime,
                    ],
                    input=json.dumps(payload),
                    env={**os.environ, "HOME": str(home)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_session_start_runs_repo_script_from_git_root(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        nested = repo / "nested"
        nested.mkdir()
        write_executable(
            repo / "scripts/hooks/session_start.py",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import os",
                    "payload = json.load(__import__('sys').stdin)",
                    'print("repo=" + os.environ["AGENT_REPO_ROOT"])',
                    'print("runtime=" + os.environ["AGENT_HOOK_RUNTIME"])',
                    'print("cwd=" + os.getcwd())',
                    'print("event=" + payload["hook_event_name"])',
                    'print("schema=" + payload["schema_version"])',
                    'print("repo_root=" + payload["repo_root"])',
                    'print("raw_cwd=" + payload["raw_payload"]["cwd"])',
                    "",
                ]
            ),
        )
        payload = {
            "cwd": str(nested),
            "hook_event_name": "SessionStart",
            "model": "gpt-5.5",
            "session_id": "session",
            "source": "startup",
            "transcript_path": None,
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/session_start.py"),
                "--runtime",
                "codex",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_repo = repo.resolve()
        output = json.loads(result.stdout)
        self.assertEqual(
            output,
            {
                "hookSpecificOutput": {
                    "additionalContext": (
                        f"repo={expected_repo}\nruntime=codex\ncwd={expected_repo}\nevent=SessionStart\n"
                        f"schema=1.0\nrepo_root={expected_repo}\nraw_cwd={nested}\n"
                    ),
                    "hookEventName": "SessionStart",
                }
            },
        )

    def test_session_start_suppresses_repo_stdout_for_copilot(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        write_executable(
            repo / "scripts/hooks/session_start.py",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "print('copilot startup context')",
                    "",
                ]
            ),
        )
        payload = {
            "cwd": str(repo),
            "initialPrompt": "hello",
            "source": "new",
            "timestamp": 1704614400000,
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/session_start.py"),
                "--runtime",
                "copilot",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_session_start_is_silent_when_repo_script_is_absent(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        payload = {
            "cwd": str(repo),
            "hook_event_name": "SessionStart",
            "model": "gpt-5.5",
            "session_id": "session",
            "source": "startup",
            "transcript_path": None,
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/session_start.py"),
                "--runtime",
                "claude",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_user_prompt_submit_runs_repo_script_from_git_root(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        nested = repo / "nested"
        nested.mkdir()
        write_executable(
            repo / "scripts/hooks/user_prompt_submit.py",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import os",
                    "payload = json.load(__import__('sys').stdin)",
                    'print("repo=" + os.environ["AGENT_REPO_ROOT"])',
                    'print("runtime=" + os.environ["AGENT_HOOK_RUNTIME"])',
                    'print("cwd=" + os.getcwd())',
                    'print("event=" + payload["hook_event_name"])',
                    'print("prompt=" + payload["prompt"])',
                    'print("schema=" + payload["schema_version"])',
                    'print("repo_root=" + payload["repo_root"])',
                    'print("raw_turn=" + payload["raw_payload"]["turn_id"])',
                    "",
                ]
            ),
        )
        payload = {
            "cwd": str(nested),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-5.5",
            "prompt": "ship it",
            "session_id": "session",
            "transcript_path": None,
            "turn_id": "turn",
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/user_prompt_submit.py"),
                "--runtime",
                "claude",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_repo = repo.resolve()
        output = json.loads(result.stdout)
        self.assertEqual(
            output,
            {
                "hookSpecificOutput": {
                    "additionalContext": (
                        f"repo={expected_repo}\nruntime=claude\ncwd={expected_repo}\nevent=UserPromptSubmit\nprompt=ship it\n"
                        f"schema=1.0\nrepo_root={expected_repo}\nraw_turn=turn\n"
                    ),
                    "hookEventName": "UserPromptSubmit",
                }
            },
        )

    def test_user_prompt_submit_ignores_mismatched_event_payload(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        marker = repo / "tmp/user-prompt-ran.txt"
        write_executable(
            repo / "scripts/hooks/user_prompt_submit.py",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import pathlib",
                    "pathlib.Path('tmp').mkdir(exist_ok=True)",
                    "pathlib.Path('tmp/user-prompt-ran.txt').write_text('ran', encoding='utf-8')",
                    "",
                ]
            ),
        )
        payload = {
            "cwd": str(repo),
            "hook_event_name": "SessionStart",
            "prompt": "wrong event",
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/user_prompt_submit.py"),
                "--runtime",
                "claude",
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(marker.exists())

    def test_session_end_runs_repo_script_without_forwarding_stdout(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        marker = repo / "tmp/session-end-marker.txt"
        write_executable(
            repo / "scripts/hooks/session_end.py",
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import os",
                    "import pathlib",
                    "import sys",
                    "pathlib.Path('tmp').mkdir(exist_ok=True)",
                    "payload = json.load(sys.stdin)",
                    "pathlib.Path('tmp/session-end-marker.txt').write_text(",
                    "    'runtime=' + os.environ['AGENT_HOOK_RUNTIME'] + '\\n'",
                    "    + 'event=' + payload['hook_event_name'] + '\\n'",
                    "    + 'schema=' + payload['schema_version'] + '\\n'",
                    "    + 'repo_root=' + payload['repo_root'] + '\\n'",
                    "    + 'transcript_format=' + str(payload['transcript_format']) + '\\n',",
                    "    encoding='utf-8',",
                    ")",
                    "print('debug only')",
                    "",
                ]
            ),
        )
        payload = {
            "cwd": str(repo),
            "hook_event_name": "SessionEnd",
            "model": "claude-sonnet-4.5",
            "reason": "other",
            "session_id": "session",
            "transcript_path": None,
        }

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "hooks/scripts/session_end.py"),
                "--runtime",
                "claude",
            ],
            input=json.dumps(payload),
            env={**os.environ, "HOME": str(self.temp_path / "home")},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            marker.read_text(encoding="utf-8"),
            f"runtime=claude\nevent=SessionEnd\nschema=1.0\nrepo_root={repo.resolve()}\ntranscript_format=None\n",
        )

    def test_codex_sync_config_renders_plan_mode_and_global_stop_hook(self) -> None:
        root = make_control_plane_root(self.temp_path)
        home = self.temp_path / "home"
        write_json(root / "mcp/config/presets.json", default_mcp_registry())

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
                "--hooks-registry",
                str(root / "hooks/registry.json"),
            ],
            env={"HOME": str(home)},
        )

        rendered_config = (home / ".codex/config.toml").read_text(encoding="utf-8")
        self.assertIn('model = "gpt-5.5"', rendered_config)
        self.assertIn('model_reasoning_effort = "high"', rendered_config)
        self.assertIn('plan_mode_reasoning_effort = "high"', rendered_config)
        self.assertIn("codex_hooks = true", rendered_config)
        self.assertIn('[plugins."computer-use@openai-bundled"]', rendered_config)
        self.assertIn(
            f'path = "{home}/.codex/skills/.system/plugin-creator/SKILL.md"',
            rendered_config,
        )
        self.assertNotIn("notify =", rendered_config)

        hooks = read_json(home / ".codex/hooks.json")
        self.assertEqual(
            hooks["hooks"]["Stop"][0]["hooks"][0]["command"],
            "python3 ~/.agents/hooks/scripts/stop.py --runtime codex",
        )

    def test_sync_copilot_hooks_renders_repo_local_github_hook_file(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        registry = self.temp_path / "repo-bootstrap.json"
        write_json(
            registry,
            {
                "defaults": {},
                "repos": [
                    {
                        "path": str(repo),
                    }
                ],
            },
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-hooks.sh"),
                "--apply",
                "--registry",
                str(registry),
                "--hooks-registry",
                str(REPO_ROOT / "hooks/registry.json"),
                "--repo",
                str(repo),
            ]
        )

        rendered = read_json(repo / ".github/hooks/agent-control-plane.json")
        expected = render_copilot_hooks(
            load_hooks_registry(REPO_ROOT / "hooks/registry.json"),
            repo_name=repo.name,
        )
        self.assertEqual(rendered, expected)

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-hooks.sh"),
                "--check",
                "--registry",
                str(registry),
                "--hooks-registry",
                str(REPO_ROOT / "hooks/registry.json"),
                "--repo",
                str(repo),
            ]
        )

    def test_sync_copilot_hooks_check_fails_when_repo_file_is_missing(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        registry = self.temp_path / "repo-bootstrap.json"
        write_json(
            registry,
            {
                "defaults": {},
                "repos": [
                    {
                        "path": str(repo),
                    }
                ],
            },
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-hooks.sh"),
                "--check",
                "--registry",
                str(registry),
                "--hooks-registry",
                str(REPO_ROOT / "hooks/registry.json"),
                "--repo",
                str(repo),
            ],
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repo-local Copilot hook files are out of sync", result.stderr)
        self.assertFalse((repo / ".github/hooks/agent-control-plane.json").exists())

    def test_sync_copilot_hooks_runs_under_macos_system_bash(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        registry = self.temp_path / "repo-bootstrap.json"
        write_json(
            registry,
            {
                "defaults": {},
                "repos": [
                    {
                        "path": str(repo),
                    }
                ],
            },
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/sync-copilot-hooks.sh"),
                "--apply",
                "--registry",
                str(registry),
                "--hooks-registry",
                str(REPO_ROOT / "hooks/registry.json"),
                "--repo",
                str(repo),
            ],
            env={"PATH": "/usr/bin:/bin"},
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((repo / ".github/hooks/agent-control-plane.json").is_file())

    def test_stop_hook_has_tracking_upstream_false_for_new_local_branch(self) -> None:
        module = self.load_stop_module()
        remote = init_git_repo(self.temp_path / "remote.git")
        run_command(["git", "-C", str(remote), "config", "receive.denyCurrentBranch", "updateInstead"])
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        run_command(["git", "-C", str(repo), "remote", "add", "origin", str(remote)])
        run_command(["git", "-C", str(repo), "push", "-u", "origin", "main"])
        run_command(["git", "-C", str(repo), "checkout", "-b", "feature/test"])

        self.assertFalse(module.has_tracking_upstream(str(repo)))

    def test_stop_hook_normalizes_copilot_warning_output(self) -> None:
        module = self.load_stop_module()

        self.assertEqual(
            module.normalize_output_for_runtime(
                {"systemMessage": "push failed"},
                runtime="copilot",
            ),
            {"decision": "allow", "reason": "push failed"},
        )
        self.assertEqual(
            module.normalize_output_for_runtime(
                {"decision": "block", "reason": "fix checks"},
                runtime="copilot",
            ),
            {"decision": "block", "reason": "fix checks"},
        )
        self.assertEqual(
            module.normalize_output_for_runtime(
                {"systemMessage": "push failed"},
                runtime="codex",
            ),
            {"systemMessage": "push failed"},
        )

    def test_stop_hook_uses_initial_push_for_branch_without_upstream(self) -> None:
        module = self.load_stop_module()
        remote = init_git_repo(self.temp_path / "remote.git")
        run_command(["git", "-C", str(remote), "config", "receive.denyCurrentBranch", "updateInstead"])
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        run_command(["git", "-C", str(repo), "remote", "add", "origin", str(remote)])
        run_command(["git", "-C", str(repo), "push", "-u", "origin", "main"])
        run_command(["git", "-C", str(repo), "checkout", "-b", "feature/test"])
        (repo / "note.txt").write_text("hello\n", encoding="utf-8")

        with patch.object(module, "log"):
            output = module.process_repo(str(repo), {"hook_event_name": "Stop"}, runtime="codex")

        self.assertIsNone(output)
        upstream = run_command(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            ]
        )
        self.assertEqual(upstream.stdout.strip(), "origin/feature/test")

    def test_stop_hook_uses_optimistic_push_for_branch_with_upstream(self) -> None:
        module = self.load_stop_module()
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        captured_commands: list[list[str]] = []

        def fake_run(args, cwd, *, timeout, env=None):  # noqa: ANN001, ARG001
            captured_commands.append(list(args))
            if args[:3] == ["git", "status", "--porcelain"]:
                return SimpleNamespace(returncode=0, stdout=" M file.txt\n", stderr="")
            if args[:4] == ["git", "symbolic-ref", "--quiet", "--short"]:
                return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
            if args[:3] == ["git", "config", "--get"]:
                return SimpleNamespace(returncode=0, stdout="origin\n", stderr="")
            if args[:4] == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name"]:
                return SimpleNamespace(returncode=0, stdout="origin/main\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(module, "run", side_effect=fake_run):
            with patch.object(module, "is_git_repo", return_value=True):
                with patch.object(module, "has_in_progress_ops", return_value=False):
                    with patch.object(module, "clear_stale_index_lock", return_value=True):
                        with patch.object(module, "log"):
                            output = module.process_repo(
                                str(repo),
                                {"hook_event_name": "Stop"},
                                runtime="codex",
                            )

        self.assertIsNone(output)
        self.assertIn(["git", "push", "origin", "HEAD"], captured_commands)
        self.assertNotIn(["git", "pull", "--rebase"], captured_commands)
        self.assertNotIn(["git", "push", "-u", "origin", "HEAD"], captured_commands)

    def test_stop_hook_rebases_and_retries_push_when_remote_is_ahead(self) -> None:
        module = self.load_stop_module()
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        captured_commands: list[list[str]] = []
        push_attempts = 0

        def fake_run(args, cwd, *, timeout, env=None):  # noqa: ANN001, ARG001
            nonlocal push_attempts
            captured_commands.append(list(args))
            if args[:3] == ["git", "status", "--porcelain"]:
                return SimpleNamespace(returncode=0, stdout=" M file.txt\n", stderr="")
            if args[:4] == ["git", "symbolic-ref", "--quiet", "--short"]:
                return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
            if args[:3] == ["git", "config", "--get"]:
                return SimpleNamespace(returncode=0, stdout="origin\n", stderr="")
            if args[:4] == ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name"]:
                return SimpleNamespace(returncode=0, stdout="origin/main\n", stderr="")
            if args == ["git", "push", "origin", "HEAD"]:
                push_attempts += 1
                if push_attempts == 1:
                    return SimpleNamespace(
                        returncode=1,
                        stdout="",
                        stderr="! [rejected] HEAD -> main (fetch first)\n"
                        "hint: Updates were rejected because the remote contains work.\n",
                    )
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(module, "run", side_effect=fake_run):
            with patch.object(module, "is_git_repo", return_value=True):
                with patch.object(module, "has_in_progress_ops", return_value=False):
                    with patch.object(module, "clear_stale_index_lock", return_value=True):
                        with patch.object(module, "log"):
                            output = module.process_repo(
                                str(repo),
                                {"hook_event_name": "Stop"},
                                runtime="codex",
                            )

        self.assertIsNone(output)
        self.assertEqual(push_attempts, 2)
        self.assertIn(["git", "pull", "--rebase"], captured_commands)

    def test_stop_hook_blocks_on_pre_commit_failure(self) -> None:
        module = self.load_stop_module()
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        write_executable(
            repo / ".git/hooks/pre-commit",
            "#!/bin/sh\nprintf 'repo check failed\\n' >&2\nexit 1\n",
        )
        (repo / "note.txt").write_text("hello\n", encoding="utf-8")

        with patch.object(module, "log"):
            output = module.process_repo(str(repo), {"hook_event_name": "Stop"}, runtime="codex")

        self.assertIsNotNone(output)
        assert output is not None
        self.assertEqual(output["decision"], "block")
        self.assertIn("git commit / pre-commit checks", output["reason"])
        self.assertIn("repo check failed", output["reason"])
        self.assertIn("Please fix the issue", output["reason"])
