from __future__ import annotations

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    init_git_repo,
    read_json,
    run_command,
    write_json,
)


class ManagedRepoEnrollmentTests(TempDirTestCase):
    def test_enrolls_direct_child_git_repos_without_remote_requirement(self) -> None:
        github_root = self.temp_path / "GitHub"
        already = init_git_repo(github_root / "already")
        new_repo = init_git_repo(github_root / "new-repo")
        nested_repo = init_git_repo(new_repo / "nested")
        (github_root / "not-git").mkdir(parents=True)

        registry_path = self.temp_path / ".agents/codex/config/repo-bootstrap.json"
        write_json(
            registry_path,
            {
                "defaults": {
                    "model": "gpt-5.5",
                },
                "repos": [
                    {
                        "path": str(already),
                    }
                ],
            },
        )

        result = run_command(
            [
                str(REPO_ROOT / "scripts/enroll-managed-repos.sh"),
                "--apply",
                "--github-root",
                str(github_root),
                "--registry",
                str(registry_path),
            ]
        )

        self.assertIn("ADD", result.stdout)
        data = read_json(registry_path)
        paths = [item["path"] for item in data["repos"]]
        self.assertEqual(
            [
                str(already),
                str(new_repo.resolve()),
            ],
            paths,
        )
        self.assertNotIn(str(nested_repo), paths)

    def test_dry_run_reports_missing_repos_without_writing_registry(self) -> None:
        github_root = self.temp_path / "GitHub"
        new_repo = init_git_repo(github_root / "new-repo")
        registry_path = self.temp_path / ".agents/codex/config/repo-bootstrap.json"
        write_json(registry_path, {"defaults": {}, "repos": []})
        before = registry_path.read_text(encoding="utf-8")

        result = run_command(
            [
                str(REPO_ROOT / "scripts/enroll-managed-repos.sh"),
                "--github-root",
                str(github_root),
                "--registry",
                str(registry_path),
            ]
        )

        self.assertIn(f"ADD {new_repo.resolve()}", result.stdout)
        self.assertEqual(before, registry_path.read_text(encoding="utf-8"))
