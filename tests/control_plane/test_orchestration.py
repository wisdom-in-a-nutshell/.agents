from __future__ import annotations

from pathlib import Path

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    commit_all,
    copy_repo_file,
    init_git_repo,
    run_command,
    write_executable,
    write_json,
    write_text,
)


STUB_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail
printf '%s|%s\\n' "$(basename "$0")" "$*" >> "${LOG_FILE:?}"
"""


class SharedBootstrapWrapperTests(TempDirTestCase):
    def _make_stub_control_plane(self) -> tuple[Path, Path]:
        root = self.temp_path / "stub-agents"
        log_path = self.temp_path / "bootstrap.log"
        script_path = copy_repo_file(
            "scripts/bootstrap-machine-agent-control-planes.sh",
            root,
        )
        script_path.chmod(0o755)
        write_executable(root / "scripts/sync-skills-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-plugins-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-codex-plugin-installs.py", STUB_SCRIPT)
        write_executable(root / "scripts/sync-claude.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-copilot.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-managed-git-hooks.sh", STUB_SCRIPT)
        write_executable(root / "codex/scripts/bootstrap-machine-codex.sh", STUB_SCRIPT)
        return root, log_path

    def test_apply_mode_runs_shared_bootstrap_steps_with_forwarded_args(self) -> None:
        root, log_path = self._make_stub_control_plane()
        github_root = self.temp_path / "GitHub"
        repo_a = self.temp_path / "repo-a"
        repo_b = self.temp_path / "repo-b"

        result = run_command(
            [
                str(root / "scripts/bootstrap-machine-agent-control-planes.sh"),
                "--apply",
                "--github-root",
                str(github_root),
                "--repo",
                str(repo_a),
                "--repo",
                str(repo_b),
            ],
            env={"LOG_FILE": str(log_path)},
        )

        self.assertIn("SKIP Antigravity spike sync (disabled)", result.stdout)
        self.assertEqual(
            [
                f"sync-skills-registry.sh|--apply --repo {repo_a} --repo {repo_b}",
                "sync-plugins-registry.sh|--apply",
                "sync-codex-plugin-installs.py|--apply --no-input",
                f"sync-claude.sh|--apply --github-root {github_root} --repo {repo_a} --repo {repo_b}",
                f"sync-copilot.sh|--apply --github-root {github_root} --repo {repo_a} --repo {repo_b}",
                f"sync-managed-git-hooks.sh|--apply --repo {repo_a} --repo {repo_b}",
                f"bootstrap-machine-codex.sh|--apply --github-root {github_root} --repo {repo_a} --repo {repo_b}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )


class SharedCheckWrapperTests(TempDirTestCase):
    def _make_stub_control_plane(self) -> tuple[Path, Path]:
        root = self.temp_path / "stub-agents"
        log_path = self.temp_path / "check.log"
        script_path = copy_repo_file(
            "scripts/check-agent-control-planes.sh",
            root,
        )
        script_path.chmod(0o755)
        write_executable(root / "scripts/check-repo-hygiene.sh", STUB_SCRIPT)
        write_executable(root / "scripts/check-skills-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/check-plugins-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-copilot.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-managed-git-hooks.sh", STUB_SCRIPT)
        write_executable(root / "codex/scripts/check-codex-control-plane.sh", STUB_SCRIPT)
        write_executable(root / "scripts/audit-agent-runtime-drift.py", STUB_SCRIPT)
        write_executable(root / "scripts/test-control-plane.sh", STUB_SCRIPT)
        return root, log_path

    def test_repo_filter_is_forwarded_to_codex_checks(self) -> None:
        root, log_path = self._make_stub_control_plane()
        repo_a = self.temp_path / "repo-a"
        repo_b = self.temp_path / "repo-b"

        run_command(
            [
                str(root / "scripts/check-agent-control-planes.sh"),
                "--repo",
                str(repo_a),
                "--repo",
                str(repo_b),
            ],
            env={"LOG_FILE": str(log_path)},
        )

        self.assertEqual(
            [
                "check-repo-hygiene.sh|",
                "check-skills-registry.sh|",
                "check-plugins-registry.sh|",
                f"sync-copilot.sh|--check --repo {repo_a} --repo {repo_b}",
                f"sync-managed-git-hooks.sh|--check --repo {repo_a} --repo {repo_b}",
                f"check-codex-control-plane.sh|--repo {repo_a} --repo {repo_b}",
                "audit-agent-runtime-drift.py|--plain --skip-control-plane-check --no-input",
                "test-control-plane.sh|",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )


class AutoApplyRoutingTests(TempDirTestCase):
    def _make_agents_repo(self) -> tuple[Path, Path, Path]:
        root = init_git_repo(self.temp_path / "agents-repo")
        log_path = self.temp_path / "auto-apply.log"
        stamp_file = self.temp_path / "last-reconciled.sha"

        for relative_path in (
            "plugins/registry.json",
            "skills/registry.json",
            "mcp/config/presets.json",
            "codex/config/repo-bootstrap.json",
            "hooks/registry.json",
            "dev-servers/registry.json",
        ):
            write_text(root / relative_path, "{}\n")

        write_executable(root / "scripts/bootstrap-machine-agent-control-planes.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-skills-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-plugins-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-copilot.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-managed-git-hooks.sh", STUB_SCRIPT)
        write_executable(root / "codex/scripts/bootstrap-machine-codex.sh", STUB_SCRIPT)
        commit_all(root, "initial")
        return root, log_path, stamp_file

    def _run_auto_apply(
        self,
        root: Path,
        log_path: Path,
        stamp_file: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> str:
        home = self.temp_path / "home"
        result = run_command(
            [
                str(REPO_ROOT / "scripts/auto-apply-agent-control-planes.sh"),
                "--apply",
                "--agents-repo",
                str(root),
                "--github-root",
                str(self.temp_path / "GitHub"),
                "--stamp-file",
                str(stamp_file),
            ],
            env={
                "HOME": str(home),
                "LOG_FILE": str(log_path),
                **(env or {}),
            },
        )
        return result.stdout

    def test_first_reconcile_runs_root_bootstrap_only(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: no prior reconcile stamp", output)
        self.assertEqual(
            [
                f"bootstrap-machine-agent-control-planes.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )
        head_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        self.assertEqual(head_sha, stamp_file.read_text(encoding="utf-8").strip())

    def test_skills_registry_change_triggers_skill_sync_and_codex_bootstrap(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_json(
            root / "skills/registry.json",
            {
                "managed_skills": [],
                "paths": {
                    "github_root": "~/GitHub",
                },
                "unmanaged_repo_local_skills": [],
            },
        )
        commit_all(root, "update skills registry")

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                "sync-skills-registry.sh|--apply",
                f"bootstrap-machine-codex.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_plugins_registry_change_triggers_plugin_sync_and_codex_bootstrap(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_json(
            root / "plugins/registry.json",
            {
                "version": 1,
                "paths": {
                    "github_root": "~/GitHub",
                },
                "managed_plugins": [],
                "unmanaged_repo_local_plugins": [],
            },
        )
        commit_all(root, "update plugins registry")

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                "sync-plugins-registry.sh|--apply",
                f"bootstrap-machine-codex.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_hooks_registry_change_triggers_codex_bootstrap(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_json(
            root / "hooks/registry.json",
            {
                "managed_hooks": [],
                "version": 1,
            },
        )
        commit_all(root, "update hooks registry")

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                f"bootstrap-machine-codex.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_root_bootstrap_wrapper_change_runs_root_bootstrap(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_executable(
            root / "scripts/bootstrap-machine-agent-control-planes.sh",
            STUB_SCRIPT + "\n# changed\n",
        )
        commit_all(root, "update root bootstrap wrapper")

        output = self._run_auto_apply(
            root,
            log_path,
            stamp_file,
            env={"PATH": "/usr/bin:/bin"},
        )

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                f"bootstrap-machine-agent-control-planes.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_dev_server_registry_change_runs_root_bootstrap(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_json(
            root / "dev-servers/registry.json",
            {
                "version": 1,
                "managed_dev_servers": [
                    {
                        "repo": "repo-a",
                        "servers": [
                            {
                                "name": "Preview",
                                "runtimeExecutable": "pnpm",
                                "runtimeArgs": ["dev"],
                                "port": 3000,
                            }
                        ],
                    }
                ],
            },
        )
        commit_all(root, "update dev server registry")

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                f"bootstrap-machine-agent-control-planes.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )
