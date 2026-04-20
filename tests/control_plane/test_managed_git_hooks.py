from __future__ import annotations

import os

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    run_command,
    write_executable,
    write_json,
    write_text,
)


class ManagedGitHooksTests(TempDirTestCase):
    def test_sync_managed_git_hooks_sets_local_core_hooks_path(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        registry = self.temp_path / "repo-bootstrap.json"
        hooks_path = REPO_ROOT / "hooks/git"
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

        dry_run = run_command(
            [
                str(REPO_ROOT / "scripts/sync-managed-git-hooks.sh"),
                "--registry",
                str(registry),
                "--hooks-path",
                str(hooks_path),
            ]
        )
        self.assertIn("Would update", dry_run.stdout)
        self.assertEqual(
            "",
            run_command(["git", "-C", str(repo), "config", "--local", "--get", "core.hooksPath"], check=False).stdout,
        )

        run_command(
            [
                str(REPO_ROOT / "scripts/sync-managed-git-hooks.sh"),
                "--apply",
                "--registry",
                str(registry),
                "--hooks-path",
                str(hooks_path),
            ]
        )

        self.assertEqual(
            str(hooks_path),
            run_command(["git", "-C", str(repo), "config", "--local", "--get", "core.hooksPath"]).stdout.strip(),
        )
        check = run_command(
            [
                str(REPO_ROOT / "scripts/sync-managed-git-hooks.sh"),
                "--check",
                "--registry",
                str(registry),
                "--hooks-path",
                str(hooks_path),
            ]
        )
        self.assertIn("OK", check.stdout)

    def test_shared_git_hook_runs_pre_commit_config_when_present(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        fake_bin = self.temp_path / "bin"
        log_path = self.temp_path / "pre-commit.log"
        write_text(repo / ".pre-commit-config.yaml", "repos: []\n")
        write_executable(
            fake_bin / "pre-commit",
            f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > {log_path}\n",
        )

        run_command(
            [str(REPO_ROOT / "hooks/git/pre-commit")],
            cwd=repo,
            env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
        )

        self.assertEqual("run", log_path.read_text(encoding="utf-8").strip())

    def test_shared_git_hook_delegates_to_husky_when_no_pre_commit_config(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        log_path = self.temp_path / "husky.log"
        write_executable(
            repo / ".husky/pre-commit",
            f"#!/usr/bin/env bash\nprintf '%s\\n' husky > {log_path}\n",
        )

        run_command([str(REPO_ROOT / "hooks/git/pre-commit")], cwd=repo)

        self.assertEqual("husky", log_path.read_text(encoding="utf-8").strip())
