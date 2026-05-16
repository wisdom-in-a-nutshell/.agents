from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        cmd = " ".join(args)
        raise AssertionError(
            f"Command failed: {cmd}\n"
            f"exit={result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_executable(path: Path, content: str) -> Path:
    write_text(path, content)
    path.chmod(0o755)
    return path


def write_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_repo_file(relative_path: str, destination_root: Path, *, destination: str | None = None) -> Path:
    source = REPO_ROOT / relative_path
    target = destination_root / (destination or relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
        return target
    shutil.copy2(source, target)
    return target


def copy_repo_files(relative_paths: list[str], destination_root: Path) -> list[Path]:
    return [copy_repo_file(relative_path, destination_root) for relative_path in relative_paths]


def init_git_repo(path: Path, *, with_initial_commit: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run_command(["git", "init", "-q", str(path)])
    run_command(["git", "-C", str(path), "config", "user.email", "tests@example.com"])
    run_command(["git", "-C", str(path), "config", "user.name", "Control Plane Tests"])
    if with_initial_commit:
        write_text(path / "README.md", f"# {path.name}\n")
        commit_all(path, "initial")
    return path


def commit_all(path: Path, message: str) -> None:
    run_command(["git", "-C", str(path), "add", "-A"])
    run_command(["git", "-C", str(path), "commit", "-q", "-m", message])


def make_control_plane_root(base_dir: Path) -> Path:
    root = base_dir / "control-plane-root"
    for relative_path in (
        "codex/config/bundled-skills-policy.json",
        "codex/config/global.agents.md",
        "codex/config/global.config.toml",
        "hooks/__init__.py",
        "hooks/control_plane.py",
        "hooks/registry.json",
        "plugins/derived.py",
    ):
        copy_repo_file(relative_path, root)
    (root / "codex/config").mkdir(parents=True, exist_ok=True)
    (root / "mcp/config").mkdir(parents=True, exist_ok=True)
    (root / "plugins").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "docs/references/registry").mkdir(parents=True, exist_ok=True)
    write_json(root / "plugins/registry.json", default_plugin_registry())
    return root


def make_skill_source(path: Path, skill_name: str, *, description: str | None = None) -> Path:
    title = description or f"{skill_name} skill"
    write_text(
        path / "SKILL.md",
        "\n".join(
            [
                "---",
                f"name: {skill_name}",
                f"description: {title}",
                "---",
                "",
                f"# {skill_name}",
                "",
                "Fixture skill for control-plane tests.",
                "",
            ]
        ),
    )
    return path


def make_plugin_source(path: Path, plugin_name: str) -> Path:
    write_json(
        path / ".codex-plugin" / "plugin.json",
        {
            "name": plugin_name,
        },
    )
    return path


def default_mcp_registry() -> dict[str, Any]:
    return {
        "global_presets": ["openaiDeveloperDocs"],
        "plugin_global_presets": [],
        "plugin_presets": {},
        "presets": {
            "openaiDeveloperDocs": {
                "transport": "http",
                "url": "https://developers.openai.com/mcp",
            },
            "cloudflare-docs": {
                "transport": "http",
                "url": "https://docs.mcp.cloudflare.com/mcp",
            },
        },
    }


def default_plugin_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "paths": {
            "github_root": "~/GitHub",
        },
        "managed_plugins": [
            {
                "plugin": "computer-use",
                "marketplace": "openai-bundled",
                "enabled": True,
                "scope": "global",
                "repos": [],
                "category": "Productivity",
            }
        ],
        "unmanaged_repo_local_plugins": [],
    }


def default_skills_registry() -> dict[str, Any]:
    return {
        "managed_skills": [],
        "managed_plugin_skills": [],
        "paths": {
            "github_root": "~/GitHub",
        },
        "unmanaged_repo_local_skills": [],
    }


class TempDirTestCase(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temp_dir.name)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()
