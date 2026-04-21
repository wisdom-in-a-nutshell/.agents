#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from hook_runtime import RepoHookSpec, run_lifecycle_hook


SPEC = RepoHookSpec(
    event="SessionStart",
    repo_script=Path("scripts/hooks/session_start.py"),
    description="Shared SessionStart hook.",
    valid_runtimes=frozenset({"codex", "claude", "copilot"}),
    label="session_start",
    forward_stdout_as_context=True,
)


def main() -> int:
    return run_lifecycle_hook(SPEC)


if __name__ == "__main__":
    raise SystemExit(main())
