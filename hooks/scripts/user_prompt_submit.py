#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from hook_runtime import RepoHookSpec, run_lifecycle_hook


SPEC = RepoHookSpec(
    event="UserPromptSubmit",
    repo_script=Path("scripts/hooks/user_prompt_submit.py"),
    description="Shared UserPromptSubmit hook.",
    valid_runtimes=frozenset({"codex"}),
    label="user_prompt_submit",
    forward_stdout_as_context=True,
    ignore_mismatched_event_name=True,
)


def main() -> int:
    return run_lifecycle_hook(SPEC)


if __name__ == "__main__":
    raise SystemExit(main())
