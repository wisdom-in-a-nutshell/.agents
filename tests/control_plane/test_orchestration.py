from __future__ import annotations

from datetime import datetime, timezone
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
        write_executable(root / "codex/scripts/bootstrap-machine-codex.sh", STUB_SCRIPT)
        write_executable(root / "claude/scripts/bootstrap-machine-claude.sh", STUB_SCRIPT)
        return root, log_path

    def test_apply_mode_runs_shared_bootstrap_steps_with_forwarded_args(self) -> None:
        root, log_path = self._make_stub_control_plane()
        github_root = self.temp_path / "GitHub"
        repo_a = self.temp_path / "repo-a"
        repo_b = self.temp_path / "repo-b"

        run_command(
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

        self.assertEqual(
            [
                "sync-skills-registry.sh|--apply",
                "sync-plugins-registry.sh|--apply",
                f"bootstrap-machine-codex.sh|--apply --github-root {github_root}",
                f"bootstrap-machine-claude.sh|--apply --repo {repo_a} --repo {repo_b}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )


class AutoApplyRoutingTests(TempDirTestCase):
    def _make_agents_repo(self) -> tuple[Path, Path, Path]:
        root = init_git_repo(self.temp_path / "agents-repo")
        log_path = self.temp_path / "auto-apply.log"
        stamp_file = self.temp_path / "last-reconciled.sha"

        for relative_path in (
            "agents/registry.json",
            "plugins/registry.json",
            "skills/registry.json",
            "mcp/config/presets.json",
            "codex/config/repo-bootstrap.json",
            "claude/config/bootstrap.json",
        ):
            write_text(root / relative_path, "{}\n")

        write_executable(root / "scripts/bootstrap-machine-agent-control-planes.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-skills-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/sync-plugins-registry.sh", STUB_SCRIPT)
        write_executable(root / "scripts/refresh-external-plugins.sh", STUB_SCRIPT)
        write_executable(root / "codex/scripts/bootstrap-machine-codex.sh", STUB_SCRIPT)
        write_executable(root / "claude/scripts/bootstrap-machine-claude.sh", STUB_SCRIPT)
        commit_all(root, "initial")
        return root, log_path, stamp_file

    def _run_auto_apply(
        self,
        root: Path,
        log_path: Path,
        stamp_file: Path,
        *,
        skip_daily_plugin_refresh: bool = True,
    ) -> str:
        home = self.temp_path / "home"
        if skip_daily_plugin_refresh:
            refresh_stamp = (
                home
                / ".local/state/agents-control-plane/last-external-plugin-refresh.date"
            )
            refresh_stamp.parent.mkdir(parents=True, exist_ok=True)
            refresh_stamp.write_text(
                datetime.now(timezone.utc).date().isoformat() + "\n",
                encoding="utf-8",
            )
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
            env={"HOME": str(home), "LOG_FILE": str(log_path)},
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

    def test_agents_registry_change_triggers_codex_and_claude_bootstraps(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()
        baseline_sha = run_command(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
        ).stdout.strip()
        write_text(stamp_file, baseline_sha + "\n")

        write_json(
            root / "agents/registry.json",
            {
                "managed_agents": [],
                "version": 1,
            },
        )
        commit_all(root, "update agent registry")

        output = self._run_auto_apply(root, log_path, stamp_file)

        self.assertIn("APPLY: detected shared agent control-plane changes", output)
        self.assertEqual(
            [
                f"bootstrap-machine-codex.sh|--apply --github-root {self.temp_path / 'GitHub'}",
                "bootstrap-machine-claude.sh|--apply",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )

    def test_skills_registry_change_triggers_skill_sync_and_both_runtimes(self) -> None:
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
                "bootstrap-machine-claude.sh|--apply",
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

    def test_due_daily_plugin_refresh_runs_before_reconcile(self) -> None:
        root, log_path, stamp_file = self._make_agents_repo()

        output = self._run_auto_apply(
            root,
            log_path,
            stamp_file,
            skip_daily_plugin_refresh=False,
        )

        self.assertIn("APPLY: external plugin refresh is due", output)
        self.assertEqual(
            [
                "refresh-external-plugins.sh|--apply",
                "sync-plugins-registry.sh|--apply",
                f"bootstrap-machine-agent-control-planes.sh|--apply --github-root {self.temp_path / 'GitHub'}",
            ],
            log_path.read_text(encoding="utf-8").splitlines(),
        )
