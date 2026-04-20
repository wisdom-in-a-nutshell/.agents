from __future__ import annotations

import os
import time

from tests.control_plane.support import REPO_ROOT, TempDirTestCase, run_command, write_text


class CodexShellTests(TempDirTestCase):
    def test_codex_jump_ranks_quoted_usage_paths_by_recency(self) -> None:
        home = self.temp_path / "home"
        github_root = home / "GitHub"
        win = github_root / "win"
        scripts = github_root / "scripts"
        win.mkdir(parents=True)
        scripts.mkdir(parents=True)

        dirs_file = home / ".agents/codex/shell/codex-jump-dirs.txt"
        write_text(
            dirs_file,
            "\n".join(
                [
                    "$HOME/GitHub/win",
                    "$HOME/GitHub/scripts",
                    "",
                ]
            ),
        )

        now = int(time.time())
        usage_file = home / ".local/state/codex-jump-usage.tsv"
        write_text(
            usage_file,
            "\n".join(
                [
                    f'"{win}"\t4\t{now - 30 * 86400}',
                    f'"{scripts}"\t1\t{now}',
                    "",
                ]
            ),
        )

        capture_file = self.temp_path / "fzf-input.tsv"
        fake_bin = self.temp_path / "bin"
        fake_fzf = fake_bin / "fzf"
        write_text(
            fake_fzf,
            "#!/usr/bin/env bash\ncat > \"$CODEX_JUMP_TEST_CAPTURE\"\nexit 1\n",
        )
        fake_fzf.chmod(0o755)

        env = {
            "CODEX_JUMP_TEST_CAPTURE": str(capture_file),
            "HOME": str(home),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        }
        result = run_command(
            [
                "zsh",
                "-fc",
                (
                    "unset CODEX_SHELL_LOADED; "
                    f"source {REPO_ROOT / 'codex/shell/codex-shell.zsh'}; "
                    "CODEX_JUMP_GITHUB_ROOT=$HOME/GitHub codex_jump"
                ),
            ],
            cwd=github_root,
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        rows = capture_file.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual("scripts", rows[0].split("\t", 1)[0])
        self.assertEqual("win", rows[1].split("\t", 1)[0])
