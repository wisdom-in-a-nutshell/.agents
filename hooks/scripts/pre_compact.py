#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from hook_runtime import RepoHookSpec, run_lifecycle_hook


SPEC = RepoHookSpec(
    event="PreCompact",
    repo_script=Path("scripts/hooks/pre_compact.py"),
    description="Shared PreCompact hook.",
    valid_runtimes=frozenset({"codex"}),
    label="pre_compact",
    forward_stdout_raw=True,
    ignore_mismatched_event_name=True,
)


def main() -> int:
    return run_lifecycle_hook(SPEC)


if __name__ == "__main__":
    raise SystemExit(main())
