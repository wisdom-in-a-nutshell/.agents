from __future__ import annotations

import json

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_json, write_text


class AgentRuntimeDriftAuditTests(TempDirTestCase):
    def _write_live_codex_config(  # noqa: ANN001
        self,
        home,
        *,
        include_chrome: bool = True,
        include_computer_use: bool = True,
    ):
        sections = [
            '[plugins."browser-use@openai-bundled"]\n'
            "enabled = true\n",
            '[plugins."build-ios-apps@openai-curated"]\n'
            "enabled = true\n",
        ]
        if include_chrome:
            sections.append(
                '[plugins."chrome@openai-bundled"]\n'
                "enabled = true\n"
            )
        if include_computer_use:
            sections.append(
                '[plugins."computer-use@openai-bundled"]\n'
                "enabled = true\n"
            )
        write_text(home / ".codex/config.toml", "\n".join(sections))

    def _write_plugin(self, home, marketplace: str, name: str, version: str = "1.0.0") -> None:  # noqa: ANN001
        write_json(
            home / ".codex/plugins/cache" / marketplace / name / version / ".codex-plugin/plugin.json",
            {
                "name": name,
                "version": version,
                "interface": {
                    "displayName": name,
                },
            },
        )

    def _write_required_plugins(self, home, *, include_chrome: bool = True, include_computer_use: bool = True) -> None:  # noqa: ANN001
        self._write_plugin(home, "openai-bundled", "browser-use")
        self._write_plugin(home, "openai-curated", "build-ios-apps")
        if include_chrome:
            self._write_plugin(home, "openai-bundled", "chrome")
        if include_computer_use:
            self._write_plugin(home, "openai-bundled", "computer-use")

    def test_audit_passes_for_known_required_codex_plugin(self) -> None:
        home = self.temp_path / "home"
        self._write_live_codex_config(home)
        self._write_required_plugins(home)

        result = run_command(
            [
                str(REPO_ROOT / "scripts/audit-agent-runtime-drift.py"),
                "--json",
                "--skip-control-plane-check",
                "--home",
                str(home),
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["summary"]["errors"], 0)

    def test_audit_fails_for_unknown_openai_plugin(self) -> None:
        home = self.temp_path / "home"
        self._write_live_codex_config(home)
        self._write_required_plugins(home)
        self._write_plugin(home, "openai-curated", "surprise-plugin")

        result = run_command(
            [
                str(REPO_ROOT / "scripts/audit-agent-runtime-drift.py"),
                "--plain",
                "--skip-control-plane-check",
                "--home",
                str(home),
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("unclassified OpenAI Codex plugin", result.stdout)
        self.assertIn("surprise-plugin@openai-curated", result.stdout)

    def test_audit_allows_primary_runtime_artifact_plugins(self) -> None:
        home = self.temp_path / "home"
        self._write_live_codex_config(home)
        self._write_required_plugins(home)
        self._write_plugin(home, "openai-primary-runtime", "documents")
        self._write_plugin(home, "openai-primary-runtime", "presentations")
        self._write_plugin(home, "openai-primary-runtime", "spreadsheets")

        result = run_command(
            [
                str(REPO_ROOT / "scripts/audit-agent-runtime-drift.py"),
                "--json",
                "--skip-control-plane-check",
                "--home",
                str(home),
            ]
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["summary"]["errors"], 0)

    def test_audit_fails_when_required_plugin_is_not_enabled_live(self) -> None:
        home = self.temp_path / "home"
        self._write_live_codex_config(home, include_computer_use=False)
        self._write_required_plugins(home)

        result = run_command(
            [
                str(REPO_ROOT / "scripts/audit-agent-runtime-drift.py"),
                "--plain",
                "--skip-control-plane-check",
                "--home",
                str(home),
            ],
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("required Codex plugin availability check failed", result.stdout)
        self.assertIn("computer-use@openai-bundled is not enabled", result.stdout)
