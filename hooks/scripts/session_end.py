#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from hook_runtime import RepoHookSpec, run_lifecycle_hook


SPEC = RepoHookSpec(
    event="SessionEnd",
    repo_script=Path("scripts/hooks/session_end.py"),
    description="Shared SessionEnd hook.",
    valid_runtimes=frozenset({"claude", "copilot"}),
    label="session_end",
    ignore_mismatched_event_name=True,
    log_stdout=True,
    return_repo_exit_code=False,
)


def main() -> int:
    return run_lifecycle_hook(SPEC)


if __name__ == "__main__":
    raise SystemExit(main())
