from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.control_plane.support import TempDirTestCase, commit_all, init_git_repo, run_command


NOTIFY_PATH = Path(__file__).resolve().parents[2] / "codex/scripts/notify.py"


def load_notify_module():
    spec = importlib.util.spec_from_file_location("codex_notify", NOTIFY_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load notify module from {NOTIFY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexNotifyTests(TempDirTestCase):
    def test_has_tracking_upstream_false_for_new_local_branch(self) -> None:
        module = load_notify_module()
        remote = init_git_repo(self.temp_path / "remote.git")
        run_command(["git", "-C", str(remote), "config", "receive.denyCurrentBranch", "updateInstead"])
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        run_command(["git", "-C", str(repo), "remote", "add", "origin", str(remote)])
        run_command(["git", "-C", str(repo), "push", "-u", "origin", "main"])
        run_command(["git", "-C", str(repo), "checkout", "-b", "feature/test"])

        self.assertFalse(module.has_tracking_upstream(str(repo)))

    def test_process_repo_uses_initial_push_for_branch_without_upstream(self) -> None:
        module = load_notify_module()
        remote = init_git_repo(self.temp_path / "remote.git")
        run_command(["git", "-C", str(remote), "config", "receive.denyCurrentBranch", "updateInstead"])
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        run_command(["git", "-C", str(repo), "remote", "add", "origin", str(remote)])
        run_command(["git", "-C", str(repo), "push", "-u", "origin", "main"])
        run_command(["git", "-C", str(repo), "checkout", "-b", "feature/test"])
        (repo / "note.txt").write_text("hello\n", encoding="utf-8")

        module.process_repo(str(repo), {"type": "agent-turn-complete"})

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

    def test_process_repo_uses_pull_for_branch_with_upstream(self) -> None:
        module = load_notify_module()
        repo = init_git_repo(self.temp_path / "repo", with_initial_commit=True)
        captured_commands: list[list[str]] = []

        def fake_run(args, cwd, *, timeout, env=None):  # noqa: ANN001
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
                    with patch.object(module, "clear_stale_index_lock"):
                        with patch.object(module, "unstage_notify_artifacts"):
                            with patch.object(module, "notify_git_failure"):
                                with patch.object(module, "trigger_autofix"):
                                    with patch.object(module, "clear_autofix_state"):
                                        module.process_repo(
                                            str(repo),
                                            {"type": "agent-turn-complete"},
                                        )

        self.assertIn(["git", "pull", "--rebase"], captured_commands)
        self.assertIn(["git", "push", "origin", "HEAD"], captured_commands)
        self.assertNotIn(["git", "push", "-u", "origin", "HEAD"], captured_commands)
