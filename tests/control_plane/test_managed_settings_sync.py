from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.control_plane.support import (
    REPO_ROOT,
    TempDirTestCase,
    run_command,
    write_json,
    write_text,
)


SYNC_SCRIPT = REPO_ROOT / "claude/scripts/sync-managed-settings.sh"


def _make_canonical(canonical_path: Path, payload: dict) -> Path:
    """Materialize a canonical managed-settings.json under a temp tree."""
    write_json(canonical_path, payload)
    return canonical_path


class ManagedSettingsSyncTests(TempDirTestCase):
    def test_dry_run_against_missing_target_reports_diff(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        _make_canonical(canonical, {"enabledPlugins": {"foo@bar": False}})

        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--dry-run",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ],
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertFalse(target.exists(), "dry-run must not write the target")
        # diff -u against /dev/null surfaces +++ rendered lines for additions.
        self.assertIn("+++", result.stdout + result.stderr)

    def test_apply_creates_target_with_canonical_content(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        payload = {
            "$schema": "https://json.schemastore.org/claude-code-settings.json",
            "enabledPlugins": {"anthropic-skills@anthropic": False},
        }
        _make_canonical(canonical, payload)

        run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ]
        )
        self.assertTrue(target.is_file(), "apply must create the target")
        rendered = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(rendered, payload)

    def test_apply_is_idempotent(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        _make_canonical(canonical, {"enabledPlugins": {"foo@bar": True}})

        run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ]
        )
        first_mtime = target.stat().st_mtime_ns

        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ]
        )
        self.assertIn("No change:", result.stdout)
        self.assertEqual(target.stat().st_mtime_ns, first_mtime,
                         "second apply must not rewrite the target")

    def test_apply_rewrites_when_target_drifts(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        canonical_payload = {"enabledPlugins": {"foo@bar": False}}
        _make_canonical(canonical, canonical_payload)
        # Pre-write a different policy file to simulate hand-editing or version drift.
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, {"enabledPlugins": {"foo@bar": True}})

        run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ]
        )
        rendered = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(rendered, canonical_payload)

    def test_missing_canonical_raises_clear_error(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        # Intentionally do not create canonical.

        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing canonical policy file", result.stderr)
        self.assertFalse(target.exists())

    def test_invalid_canonical_root_raises_clear_error(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        target = self.temp_path / "policy/managed-settings.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        # Write a JSON array — root must be an object.
        canonical.write_text("[]\n", encoding="utf-8")

        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                str(target),
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an object", result.stderr)

    def test_relative_canonical_path_is_rejected(self) -> None:
        target = self.temp_path / "policy/managed-settings.json"
        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                "relative/path.json",
                "--policy-target",
                str(target),
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an absolute path", result.stderr)

    def test_relative_target_path_is_rejected(self) -> None:
        canonical = self.temp_path / "claude/config/managed-settings.json"
        _make_canonical(canonical, {"enabledPlugins": {}})
        result = run_command(
            [
                "bash",
                str(SYNC_SCRIPT),
                "--apply",
                "--canonical-policy",
                str(canonical),
                "--policy-target",
                "relative/policy.json",
            ],
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an absolute path", result.stderr)
