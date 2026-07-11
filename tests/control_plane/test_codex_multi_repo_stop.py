from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from hooks.scripts import codex_turn_changes
from hooks.scripts import stop
from tests.control_plane.support import (
    TempDirTestCase,
    init_git_repo,
    run_command,
    write_executable,
)


class FakeAppServerClient:
    def __init__(self, responses, **_kwargs):  # noqa: ANN001
        self.responses = responses

    def __enter__(self):  # noqa: ANN201
        return self

    def __exit__(self, *_args):  # noqa: ANN001, ANN201
        return None

    def request(self, method, params):  # noqa: ANN001, ANN201
        key = (method, params.get("threadId") or params.get("cursor") or "first")
        return self.responses[key]


class CodexTurnChangesTests(TempDirTestCase):
    def test_collects_parent_subagent_and_active_competitor_paths(self) -> None:
        root_path = str(self.temp_path / "root.txt")
        child_path = str(self.temp_path / "child.txt")
        moved_path = str(self.temp_path / "moved.txt")
        competitor_path = str(self.temp_path / "competitor.txt")
        responses = {
            ("thread/read", "root"): {
                "thread": {
                    "id": "root",
                    "sessionId": "tree",
                    "turns": [
                        {
                            "id": "turn-root",
                            "startedAt": 100,
                            "items": [
                                {
                                    "type": "fileChange",
                                    "status": "completed",
                                    "changes": [{"path": root_path, "kind": {"type": "update"}}],
                                }
                            ],
                        }
                    ],
                }
            },
            ("thread/list", "first"): {
                "data": [
                    {"id": "root", "sessionId": "tree", "createdAt": 50, "status": {"type": "idle"}},
                    {"id": "child", "sessionId": "tree", "createdAt": 110, "status": {"type": "idle"}},
                    {"id": "old-child", "sessionId": "tree", "createdAt": 90, "status": {"type": "idle"}},
                    {
                        "id": "competitor",
                        "sessionId": "other-tree",
                        "createdAt": 120,
                        "cwd": str(self.temp_path),
                        "status": {"type": "active"},
                    },
                    {
                        "id": "stale-child",
                        "sessionId": "tree",
                        "createdAt": 10,
                        "updatedAt": 99,
                        "status": {"type": "idle"},
                    },
                ],
                "nextCursor": None,
            },
            ("thread/read", "child"): {
                "thread": {
                    "id": "child",
                    "turns": [
                        {
                            "id": "turn-child",
                            "startedAt": 115,
                            "items": [
                                {
                                    "type": "fileChange",
                                    "changes": [
                                        {
                                            "path": child_path,
                                            "kind": {"type": "move", "move_path": moved_path},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
            ("thread/read", "old-child"): {
                "thread": {
                    "id": "old-child",
                    "turns": [
                        {
                            "id": "old-turn",
                            "startedAt": 90,
                            "items": [
                                {
                                    "type": "fileChange",
                                    "changes": [
                                        {
                                            "path": str(self.temp_path / "old.txt"),
                                            "kind": {"type": "update"},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
            ("thread/read", "competitor"): {
                "thread": {
                    "id": "competitor",
                    "turns": [
                        {
                            "id": "turn-competitor",
                            "startedAt": 125,
                            "items": [
                                {
                                    "type": "fileChange",
                                    "changes": [{"path": competitor_path, "kind": {"type": "update"}}],
                                }
                            ],
                        }
                    ],
                }
            },
        }

        with patch.object(
            codex_turn_changes,
            "AppServerClient",
            side_effect=lambda **kwargs: FakeAppServerClient(responses, **kwargs),
        ):
            result = codex_turn_changes.collect_codex_turn_changes("root")

        self.assertEqual(result.session_id, "tree")
        self.assertEqual(result.parent_thread_id, "")
        self.assertEqual(
            set(result.touched_paths),
            {root_path, child_path, moved_path},
        )
        self.assertEqual(len(result.active_competitors), 1)
        self.assertEqual(
            result.active_competitors[0].touched_paths,
            (competitor_path,),
        )


class CodexMultiRepoStopTests(TempDirTestCase):
    def make_published_repo(self, name: str):  # noqa: ANN201
        remote = init_git_repo(self.temp_path / f"{name}-remote.git")
        run_command(
            ["git", "-C", str(remote), "config", "receive.denyCurrentBranch", "updateInstead"]
        )
        repo = init_git_repo(self.temp_path / name, with_initial_commit=True)
        run_command(["git", "-C", str(repo), "remote", "add", "origin", str(remote)])
        run_command(["git", "-C", str(repo), "push", "-u", "origin", "main"])
        return repo, remote

    def changes(self, paths, competitors=()):  # noqa: ANN001, ANN201
        return SimpleNamespace(
            touched_paths=tuple(str(path) for path in paths),
            active_competitors=tuple(competitors),
            parent_thread_id="",
        )

    def test_commits_and_pushes_two_attributed_repositories(self) -> None:
        first, first_remote = self.make_published_repo("first")
        second, second_remote = self.make_published_repo("second")
        first_file = first / "first.txt"
        second_file = second / "second.txt"
        first_file.write_text("first\n", encoding="utf-8")
        second_file.write_text("second\n", encoding="utf-8")

        home = self.temp_path / "home"
        with patch.dict(os.environ, {"HOME": str(home)}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([first_file, second_file]),
            ):
                with patch.object(stop, "avoid_stop_continuation", return_value=False):
                    output = stop.process_codex_repositories(
                        str(first),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )

        self.assertIsNone(output)
        self.assertEqual(run_command(["git", "-C", str(first), "status", "--porcelain"]).stdout, "")
        self.assertEqual(run_command(["git", "-C", str(second), "status", "--porcelain"]).stdout, "")
        self.assertEqual(
            run_command(["git", "-C", str(first_remote), "show", "HEAD:first.txt"]).stdout,
            "first\n",
        )
        self.assertEqual(
            run_command(["git", "-C", str(second_remote), "show", "HEAD:second.txt"]).stdout,
            "second\n",
        )
        self.assertFalse(stop.codex_transaction_path("thread").exists())

    def test_refuses_unattributed_pre_staged_file(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        attributed = repo / "attributed.txt"
        unrelated = repo / "unrelated.txt"
        attributed.write_text("mine\n", encoding="utf-8")
        unrelated.write_text("other\n", encoding="utf-8")
        run_command(["git", "-C", str(repo), "add", "unrelated.txt"])

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([attributed]),
            ):
                with patch.object(stop, "avoid_stop_continuation", return_value=False):
                    output = stop.process_codex_repositories(
                        str(repo),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )

        self.assertEqual(output["decision"], "block")
        self.assertIn("unrelated.txt", output["reason"])
        self.assertEqual(
            run_command(["git", "-C", str(repo), "rev-list", "--count", "HEAD"]).stdout.strip(),
            "1",
        )

    def test_preflights_every_repo_before_any_commit(self) -> None:
        first, _first_remote = self.make_published_repo("first")
        second, _second_remote = self.make_published_repo("second")
        first_file = first / "first.txt"
        second_file = second / "second.txt"
        first_file.write_text("first\n", encoding="utf-8")
        second_file.write_text("second\n", encoding="utf-8")
        write_executable(
            second / "scripts/check-fast.sh",
            "#!/usr/bin/env bash\nprintf 'second repo failed\\n' >&2\nexit 1\n",
        )
        before = {
            str(repo): run_command(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
            for repo in (first, second)
        }

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([first_file, second_file, second / "scripts/check-fast.sh"]),
            ):
                with patch.object(stop, "avoid_stop_continuation", return_value=False):
                    output = stop.process_codex_repositories(
                        str(first),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )
            pending = stop.load_codex_transaction("thread")

        self.assertEqual(output["decision"], "block")
        self.assertIn("second repo failed", output["reason"])
        for repo in (first, second):
            self.assertEqual(
                run_command(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip(),
                before[str(repo)],
            )
        self.assertEqual(set(pending), {str(first.resolve()), str(second.resolve())})

    def test_blocks_an_exact_path_overlap_with_an_active_thread(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        path = repo / "shared.txt"
        path.write_text("shared\n", encoding="utf-8")
        competitor = SimpleNamespace(
            thread_id="other-thread",
            session_id="other-session",
            cwd=str(repo),
            touched_paths=(str(path),),
        )

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([path], [competitor]),
            ):
                with patch.object(stop, "avoid_stop_continuation", return_value=False):
                    output = stop.process_codex_repositories(
                        str(repo),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )

        self.assertEqual(output["decision"], "block")
        self.assertIn("other-thread", output["reason"])
        self.assertIn("shared.txt", output["reason"])

    def test_blocks_overlap_held_by_active_competitor_transaction(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        path = repo / "shared.txt"
        path.write_text("shared\n", encoding="utf-8")
        competitor = SimpleNamespace(
            thread_id="other-thread",
            session_id="other-session",
            cwd=str(self.temp_path),
            touched_paths=(),
        )
        other_state = {
            str(repo.resolve()): stop.RepoFinalization(
                root=str(repo.resolve()),
                paths={"shared.txt"},
            )
        }

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            stop.save_codex_transaction("other-thread", other_state)
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([path], [competitor]),
            ):
                with patch.object(stop, "avoid_stop_continuation", return_value=False):
                    output = stop.process_codex_repositories(
                        str(repo),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )

        self.assertEqual(output["decision"], "block")
        self.assertIn("pending transaction", output["reason"])
        self.assertIn("shared.txt", output["reason"])

    def test_subagent_stop_defers_to_parent_turn(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        path = repo / "child.txt"
        path.write_text("child\n", encoding="utf-8")
        changes = self.changes([path])
        changes.parent_thread_id = "parent-thread"

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(stop, "collect_codex_turn_changes", return_value=changes):
                output = stop.process_codex_repositories(
                    str(repo),
                    {"session_id": "child-thread", "hook_event_name": "Stop"},
                )

        self.assertIsNone(output)
        self.assertIn(
            "child.txt",
            run_command(["git", "-C", str(repo), "status", "--porcelain"]).stdout,
        )

    def test_clean_attributed_repo_skips_fast_checks(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        tracked_path = repo / "README.md"

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([tracked_path]),
            ):
                with patch.object(
                    stop,
                    "preflight_repo_check",
                    side_effect=AssertionError("clean repo should not run checks"),
                ):
                    output = stop.process_codex_repositories(
                        str(repo),
                        {"session_id": "thread", "hook_event_name": "Stop"},
                    )
            pending = stop.load_codex_transaction("thread")

        self.assertIsNone(output)
        self.assertEqual(pending, {})

    def test_retries_a_committed_repository_after_partial_push_failure(self) -> None:
        first, _first_remote = self.make_published_repo("first")
        second, _second_remote = self.make_published_repo("second")
        first_file = first / "first.txt"
        second_file = second / "second.txt"
        first_file.write_text("first\n", encoding="utf-8")
        second_file.write_text("second\n", encoding="utf-8")
        success = SimpleNamespace(returncode=0, stdout="", stderr="")
        failure = SimpleNamespace(returncode=1, stdout="", stderr="temporary failure")
        push_results = [
            (success, ["git", "push", "origin", "HEAD"], "git push failed"),
            (failure, ["git", "push", "origin", "HEAD"], "git push failed"),
            (success, ["git", "push", "origin", "HEAD"], "git push failed"),
        ]
        payload = {"session_id": "thread", "hook_event_name": "Stop"}

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(stop, "avoid_stop_continuation", return_value=False):
                with patch.object(
                    stop,
                    "collect_codex_turn_changes",
                    return_value=self.changes([first_file, second_file]),
                ):
                    with patch.object(stop, "push_committed_repo", side_effect=push_results):
                        first_output = stop.process_codex_repositories(str(first), payload)
                        state_after_failure = stop.load_codex_transaction("thread")
                        with patch.object(
                            stop,
                            "collect_codex_turn_changes",
                            return_value=self.changes([]),
                        ):
                            second_output = stop.process_codex_repositories(str(first), payload)

            final_state = stop.load_codex_transaction("thread")

        self.assertEqual(first_output["decision"], "block")
        self.assertEqual(len(state_after_failure), 1)
        remaining = next(iter(state_after_failure.values()))
        self.assertEqual(remaining.phase, "committed")
        self.assertIsNone(second_output)
        self.assertEqual(final_state, {})

    def test_same_path_fix_after_partial_push_is_committed_before_retry(self) -> None:
        first, _first_remote = self.make_published_repo("first")
        second, _second_remote = self.make_published_repo("second")
        first_file = first / "first.txt"
        second_file = second / "second.txt"
        first_file.write_text("first\n", encoding="utf-8")
        second_file.write_text("second\n", encoding="utf-8")
        success = SimpleNamespace(returncode=0, stdout="", stderr="")
        failure = SimpleNamespace(returncode=1, stdout="", stderr="temporary failure")
        payload = {"session_id": "thread", "hook_event_name": "Stop"}

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(stop, "avoid_stop_continuation", return_value=False):
                with patch.object(
                    stop,
                    "collect_codex_turn_changes",
                    return_value=self.changes([first_file, second_file]),
                ):
                    with patch.object(
                        stop,
                        "push_committed_repo",
                        side_effect=[
                            (success, ["git", "push", "origin", "HEAD"], "git push failed"),
                            (failure, ["git", "push", "origin", "HEAD"], "git push failed"),
                        ],
                    ):
                        first_output = stop.process_codex_repositories(str(first), payload)

                previous_head = run_command(
                    ["git", "-C", str(second), "rev-parse", "HEAD"]
                ).stdout.strip()
                second_file.write_text("fixed\n", encoding="utf-8")
                with patch.object(
                    stop,
                    "collect_codex_turn_changes",
                    return_value=self.changes([second_file]),
                ):
                    with patch.object(
                        stop,
                        "push_committed_repo",
                        return_value=(
                            success,
                            ["git", "push", "origin", "HEAD"],
                            "git push failed",
                        ),
                    ):
                        second_output = stop.process_codex_repositories(str(second), payload)
                final_state = stop.load_codex_transaction("thread")

        self.assertEqual(first_output["decision"], "block")
        self.assertIsNone(second_output)
        self.assertNotEqual(
            run_command(["git", "-C", str(second), "rev-parse", "HEAD"]).stdout.strip(),
            previous_head,
        )
        self.assertEqual(
            run_command(["git", "-C", str(second), "show", "HEAD:second.txt"]).stdout,
            "fixed\n",
        )
        self.assertEqual(final_state, {})

    def test_clean_rediscovered_path_preserves_pending_push(self) -> None:
        repo, remote = self.make_published_repo("repo")
        path = repo / "pending.txt"
        path.write_text("pending\n", encoding="utf-8")
        run_command(["git", "-C", str(repo), "add", "pending.txt"])
        run_command(["git", "-C", str(repo), "commit", "-m", "pending"])
        pending_commit = run_command(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
        state = {
            str(repo.resolve()): stop.RepoFinalization(
                root=str(repo.resolve()),
                paths={"pending.txt"},
                phase="committed",
                commit=pending_commit,
            )
        }

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            stop.save_codex_transaction("thread", state)
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([path]),
            ):
                output = stop.process_codex_repositories(
                    str(repo),
                    {"session_id": "thread", "hook_event_name": "Stop"},
                )
            final_state = stop.load_codex_transaction("thread")

        self.assertIsNone(output)
        self.assertEqual(final_state, {})
        self.assertEqual(
            run_command(["git", "-C", str(remote), "show", "HEAD:pending.txt"]).stdout,
            "pending\n",
        )

    def test_commit_only_excludes_file_staged_by_precommit_hook(self) -> None:
        repo, remote = self.make_published_repo("repo")
        attributed = repo / "attributed.txt"
        unrelated = repo / "unrelated.txt"
        attributed.write_text("mine\n", encoding="utf-8")
        unrelated.write_text("other\n", encoding="utf-8")
        write_executable(
            repo / ".git/hooks/pre-commit",
            "#!/usr/bin/env bash\ngit add unrelated.txt\n",
        )

        with patch.dict(os.environ, {"HOME": str(self.temp_path / "home")}):
            with patch.object(
                stop,
                "collect_codex_turn_changes",
                return_value=self.changes([attributed]),
            ):
                output = stop.process_codex_repositories(
                    str(repo),
                    {"session_id": "thread", "hook_event_name": "Stop"},
                )

        self.assertIsNone(output)
        self.assertEqual(
            run_command(["git", "-C", str(remote), "show", "HEAD:attributed.txt"]).stdout,
            "mine\n",
        )
        remote_unrelated = run_command(
            ["git", "-C", str(remote), "show", "HEAD:unrelated.txt"],
            check=False,
        )
        self.assertNotEqual(remote_unrelated.returncode, 0)
        self.assertIn(
            "unrelated.txt",
            run_command(["git", "-C", str(repo), "status", "--porcelain"]).stdout,
        )

    def test_tracked_file_symlink_maps_to_its_repository_path(self) -> None:
        repo, _remote = self.make_published_repo("repo")
        outside = self.temp_path / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        link = repo / "linked.txt"
        link.symlink_to(outside)

        resolved = stop.attributed_repo_path(str(link))

        self.assertEqual(resolved, (str(repo.resolve()), "linked.txt"))
