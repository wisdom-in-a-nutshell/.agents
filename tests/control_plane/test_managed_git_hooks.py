from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    run_command,
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

    def test_shared_git_hook_runs_repo_check_fast_when_present(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")
        log_path = self.temp_path / "check-fast.log"
        write_text(
            repo / "scripts/check-fast.sh",
            f"#!/usr/bin/env bash\nprintf '%s\\n' check-fast > {log_path}\n",
        )

        run_command([str(REPO_ROOT / "hooks/git/pre-commit")], cwd=repo)

        self.assertEqual("check-fast", log_path.read_text(encoding="utf-8").strip())

    def test_shared_git_hook_exits_successfully_when_repo_has_no_check_fast(self) -> None:
        repo = init_git_repo(self.temp_path / "repo")

        result = run_command([str(REPO_ROOT / "hooks/git/pre-commit")], cwd=repo)

        self.assertEqual("", result.stdout)
        self.assertEqual("", result.stderr)
