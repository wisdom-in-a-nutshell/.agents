#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_RUNTIMES = {"codex", "claude", "copilot"}

GIT_STATUS_TIMEOUT_SEC = 60
GIT_ADD_TIMEOUT_SEC = 120
GIT_COMMIT_TIMEOUT_SEC = 180
GIT_PULL_TIMEOUT_SEC = 300
GIT_PUSH_TIMEOUT_SEC = 300
MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_REASON_CHARS = 12000
MAX_COMMAND_OUTPUT_CHARS = 3500

NON_ACTIONABLE_PUSH_PATTERNS = {
    "permission denied": "permission denied",
    "authentication failed": "authentication failed",
    "could not read username": "missing credentials",
    "repository not found": "repository not found",
    "fatal: unable to access": "remote unreachable",
    "could not resolve host": "dns failure",
    "failed to push some refs": "push rejected",
    "updates were rejected": "push rejected",
    "non-fast-forward": "non-fast-forward",
    "pre-receive hook declined": "remote hook declined",
    "protected branch hook declined": "remote hook declined",
    "remote rejected": "remote rejected",
    "no configured push destination": "no push destination",
    "has no upstream branch": "no upstream branch",
}

NON_ACTIONABLE_COMMIT_PATTERNS = {
    "nothing to commit": "nothing to commit",
    "no changes added to commit": "nothing to commit",
    "gpg failed to sign the data": "gpg signing failed",
    "failed to sign the data": "gpg signing failed",
    "no signing key": "gpg signing failed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared Stop hook for end-of-turn git finalization.")
    parser.add_argument("--runtime", choices=sorted(VALID_RUNTIMES), required=True)
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Accepted for non-interactive client compatibility; hooks never prompt.",
    )
    parser.add_argument("--debug", action="store_true", help="Write diagnostics to stderr.")
    return parser.parse_args()


def utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_now_commit_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def log(runtime: str, message: str) -> None:
    try:
        log_dir = Path.home() / ".local" / "state" / "agents-control-plane" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "hooks-stop.log"
        if log_path.exists() and log_path.stat().st_size >= MAX_LOG_BYTES:
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - MAX_LOG_BYTES))
                tail = handle.read()
            newline = tail.find(b"\n")
            if newline != -1:
                tail = tail[newline + 1 :]
            log_path.write_bytes(tail)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now_iso_z()} runtime={runtime} {message}\n")
    except Exception:
        pass


def truncate_text(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    suffix = "\n...[truncated]"
    return value[: max(0, limit - len(suffix))] + suffix


def emit_json(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True))
    sys.stdout.write("\n")
    return 0


def continuation(reason: str) -> dict[str, Any]:
    return {
        "decision": "block",
        "reason": truncate_text(reason, MAX_REASON_CHARS),
    }


def warning(message: str) -> dict[str, Any]:
    return {
        "systemMessage": truncate_text(message, MAX_REASON_CHARS),
    }


def normalize_output_for_runtime(
    output: dict[str, Any] | None,
    *,
    runtime: str,
) -> dict[str, Any] | None:
    if runtime == "copilot" and output and "systemMessage" in output:
        return {
            "decision": "allow",
            "reason": truncate_text(str(output["systemMessage"]), MAX_REASON_CHARS),
        }
    return output


def read_payload(debug: bool) -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if debug:
            print(f"stop: invalid JSON payload: {exc}", file=sys.stderr)
        return None
    if not isinstance(payload, dict):
        if debug:
            print("stop: payload root is not an object", file=sys.stderr)
        return None
    return payload


def run(
    cmd: list[str],
    cwd: str,
    *,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def is_git_repo(cwd: str) -> bool:
    result = run(["git", "rev-parse", "--is-inside-work-tree"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_dir(cwd: str) -> str | None:
    result = run(["git", "rev-parse", "--git-dir"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repo_root(cwd: str) -> str | None:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def has_changes(cwd: str) -> bool:
    result = run(["git", "status", "--porcelain"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    return result.returncode == 0 and bool(result.stdout.strip())


def git_status(cwd: str) -> str:
    result = run(["git", "status", "--porcelain"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    if result.returncode != 0:
        return ""
    return result.stdout


def current_branch_name(cwd: str) -> str:
    result = run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    if result.returncode != 0:
        return "DETACHED"
    return result.stdout.strip() or "DETACHED"


def has_in_progress_ops(cwd: str) -> bool:
    git_dir_path = git_dir(cwd)
    if not git_dir_path:
        return False
    base = Path(git_dir_path)
    if not base.is_absolute():
        base = Path(cwd) / base
    markers = [
        base / "rebase-apply",
        base / "rebase-merge",
        base / "MERGE_HEAD",
        base / "CHERRY_PICK_HEAD",
        base / "REVERT_HEAD",
    ]
    return any(marker.exists() for marker in markers)


def git_index_lock_path(cwd: str) -> Path | None:
    git_dir_path = git_dir(cwd)
    if not git_dir_path:
        return None
    base = Path(git_dir_path)
    if not base.is_absolute():
        base = Path(cwd) / base
    return base / "index.lock"


def is_lock_held(lock_path: Path) -> bool:
    if not lock_path.exists():
        return False
    if not shutil.which("lsof"):
        return True
    result = run(["lsof", str(lock_path)], str(lock_path.parent), timeout=GIT_STATUS_TIMEOUT_SEC)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def clear_stale_index_lock(cwd: str) -> bool:
    lock_path = git_index_lock_path(cwd)
    if not lock_path or not lock_path.exists():
        return True
    if is_lock_held(lock_path):
        return False
    try:
        lock_path.unlink()
        return True
    except Exception:
        return False


def resolve_push_remote(cwd: str) -> str | None:
    branch = run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    branch_name = branch.stdout.strip() if branch.returncode == 0 else ""
    if branch_name:
        branch_remote = run(
            ["git", "config", "--get", f"branch.{branch_name}.remote"],
            cwd,
            timeout=GIT_STATUS_TIMEOUT_SEC,
        )
        remote_name = branch_remote.stdout.strip()
        if branch_remote.returncode == 0 and remote_name:
            return remote_name

    remotes = run(["git", "remote"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    if remotes.returncode != 0:
        return None
    names = [line.strip() for line in remotes.stdout.splitlines() if line.strip()]
    if "origin" in names:
        return "origin"
    if len(names) == 1:
        return names[0]
    return None


def has_tracking_upstream(cwd: str) -> bool:
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def build_commit_message(payload: dict[str, Any]) -> str:
    _ = payload
    return f"Agent: {utc_now_commit_timestamp()}"


def command_text(command: list[str]) -> str:
    return " ".join(command)


def command_failure_reason(
    cwd: str,
    phase: str,
    command: list[str],
    result: subprocess.CompletedProcess[str],
    *,
    retryable: bool = True,
) -> str:
    root = repo_root(cwd) or cwd
    lines = [
        f"I tried to commit and publish the changes from this turn, but `{phase}` failed.",
        "",
        f"Repository: {root}",
        f"Branch: {current_branch_name(cwd)}",
        f"Command: {command_text(command)}",
        f"Exit code: {result.returncode}",
    ]
    if retryable:
        lines[1:1] = [
            "",
            "Please fix the issue below, then finish again. The Stop hook will retry the commit.",
        ]
    else:
        lines[1:1] = [
            "",
            "This does not look like a code or repo-check issue, so the hook is reporting it without requesting another continuation.",
        ]
    stderr = truncate_text(result.stderr, MAX_COMMAND_OUTPUT_CHARS)
    stdout = truncate_text(result.stdout, MAX_COMMAND_OUTPUT_CHARS)
    status = truncate_text(git_status(cwd), 2000)
    if stderr:
        lines.extend(["", "stderr:", "```", stderr, "```"])
    if stdout:
        lines.extend(["", "stdout:", "```", stdout, "```"])
    if status:
        lines.extend(["", "git status --porcelain:", "```", status, "```"])
    return "\n".join(lines)


def state_failure_reason(cwd: str, message: str) -> str:
    root = repo_root(cwd) or cwd
    status = truncate_text(git_status(cwd), 2000)
    lines = [
        f"I tried to finalize the turn, but the repository needs attention: {message}",
        "",
        "Please fix the issue, then finish again. The Stop hook will retry the commit.",
        "",
        f"Repository: {root}",
        f"Branch: {current_branch_name(cwd)}",
    ]
    if status:
        lines.extend(["", "git status --porcelain:", "```", status, "```"])
    return "\n".join(lines)


def commit_with_retry(
    cwd: str,
    message: str,
    pre_commit_status: str,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    commit = run(["git", "commit", "-m", message], cwd, timeout=GIT_COMMIT_TIMEOUT_SEC)
    if commit.returncode == 0:
        return commit, False
    post_status = run(
        ["git", "status", "--porcelain"],
        cwd,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    if post_status.returncode != 0:
        return commit, False
    if post_status.stdout == pre_commit_status:
        return commit, False
    add_retry = run(["git", "add", "-A"], cwd, timeout=GIT_ADD_TIMEOUT_SEC)
    if add_retry.returncode != 0:
        return commit, False
    retry = run(
        ["git", "commit", "-m", message],
        cwd,
        timeout=GIT_COMMIT_TIMEOUT_SEC,
    )
    return retry, True


def is_non_actionable_failure(command: list[str], result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    output = f"{result.stdout}\n{result.stderr}".lower()
    if len(command) >= 2 and command[0] == "git" and command[1] == "commit":
        for pattern, reason in NON_ACTIONABLE_COMMIT_PATTERNS.items():
            if pattern in output:
                return True, reason
    if len(command) >= 2 and command[0] == "git" and command[1] == "push":
        for pattern, reason in NON_ACTIONABLE_PUSH_PATTERNS.items():
            if pattern in output:
                return True, reason
    return False, ""


def maybe_continue(
    payload: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if payload.get("stop_hook_active") is True:
        return warning(
            "Stop hook finalization is still failing after a continuation turn.\n\n"
            + reason
        )
    return continuation(reason)


def process_repo(cwd: str, payload: dict[str, Any], *, runtime: str) -> dict[str, Any] | None:
    if not is_git_repo(cwd):
        log(runtime, f"skip not-git cwd={cwd}")
        return None
    root = repo_root(cwd) or cwd
    if has_in_progress_ops(root):
        log(runtime, f"block in-progress-git-op repo={root}")
        return maybe_continue(payload, state_failure_reason(root, "a merge, rebase, cherry-pick, or revert is in progress"))
    if not clear_stale_index_lock(root):
        log(runtime, f"block active-index-lock repo={root}")
        return maybe_continue(payload, state_failure_reason(root, "git index.lock appears active"))
    if not has_changes(root):
        log(runtime, f"skip clean repo={root}")
        return None

    message = build_commit_message(payload)
    add = run(["git", "add", "-A"], root, timeout=GIT_ADD_TIMEOUT_SEC)
    if add.returncode != 0:
        if "index.lock" in f"{add.stdout}\n{add.stderr}".lower() and clear_stale_index_lock(root):
            add = run(["git", "add", "-A"], root, timeout=GIT_ADD_TIMEOUT_SEC)
        if add.returncode != 0:
            log(runtime, f"block git-add repo={root} exit={add.returncode}")
            return maybe_continue(payload, command_failure_reason(root, "git add", ["git", "add", "-A"], add))

    pre_commit_status = run(
        ["git", "status", "--porcelain"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    pre_commit_snapshot = pre_commit_status.stdout if pre_commit_status.returncode == 0 else ""
    commit, _retried = commit_with_retry(root, message, pre_commit_snapshot)
    if commit.returncode != 0:
        skip, skip_reason = is_non_actionable_failure(["git", "commit", "-m", message], commit)
        if skip and skip_reason == "nothing to commit":
            log(runtime, f"skip nothing-to-commit repo={root}")
            return None
        if skip:
            log(runtime, f"warn git-commit repo={root} reason={skip_reason} exit={commit.returncode}")
            return warning(
                command_failure_reason(
                    root,
                    f"git commit ({skip_reason})",
                    ["git", "commit", "-m", message],
                    commit,
                    retryable=False,
                )
            )
        log(runtime, f"block git-commit repo={root} exit={commit.returncode}")
        return maybe_continue(
            payload,
            command_failure_reason(root, "git commit / pre-commit checks", ["git", "commit", "-m", message], commit),
        )

    remote = resolve_push_remote(root)
    if not remote:
        log(runtime, f"warn no-remote repo={root}")
        return warning(f"Committed changes in {root}, but no push remote could be resolved.")

    if has_tracking_upstream(root):
        pull_cmd = ["git", "pull", "--rebase"]
        pull = run(pull_cmd, root, timeout=GIT_PULL_TIMEOUT_SEC)
        if pull.returncode != 0:
            log(runtime, f"block git-pull-rebase repo={root} exit={pull.returncode}")
            return maybe_continue(payload, command_failure_reason(root, "git pull --rebase", pull_cmd, pull))
        push_cmd = ["git", "push", remote, "HEAD"]
    else:
        log(runtime, f"initial-push repo={root} remote={remote} branch={current_branch_name(root)}")
        push_cmd = ["git", "push", "-u", remote, "HEAD"]

    push = run(push_cmd, root, timeout=GIT_PUSH_TIMEOUT_SEC)
    if push.returncode != 0:
        skip, skip_reason = is_non_actionable_failure(push_cmd, push)
        if skip:
            log(runtime, f"warn git-push repo={root} reason={skip_reason} exit={push.returncode}")
            return warning(
                command_failure_reason(root, f"git push ({skip_reason})", push_cmd, push, retryable=False)
            )
        log(runtime, f"block git-push repo={root} exit={push.returncode}")
        return maybe_continue(payload, command_failure_reason(root, "git push", push_cmd, push))

    log(runtime, f"ok committed-and-pushed repo={root} branch={current_branch_name(root)} remote={remote}")
    return None


def main() -> int:
    args = parse_args()
    payload = read_payload(args.debug) or {}
    if payload.get("hook_event_name") not in {None, "Stop"}:
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())

    try:
        output = process_repo(cwd, payload, runtime=args.runtime)
    except subprocess.TimeoutExpired as exc:
        cmd = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        timeout = exc.timeout if exc.timeout is not None else "unknown"
        output = maybe_continue(
            payload,
            state_failure_reason(cwd, f"command timed out after {timeout}s: {cmd}"),
        )
    except Exception as exc:
        log(args.runtime, f"unexpected-error cwd={cwd} error={exc}")
        output = warning(f"Stop hook failed unexpectedly at {utc_now_iso_z()}: {exc}")

    output = normalize_output_for_runtime(output, runtime=args.runtime)
    if output:
        return emit_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
