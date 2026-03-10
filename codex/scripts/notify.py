#!/usr/bin/env python3
from __future__ import annotations

"""
notify.py - post-agent git automation for Codex.

This script is invoked after each Codex agent turn (via config.toml -> notify).
It auto-commits/pushes changes, and on failure can trigger a single auto-fix run.

High-level flow:
1) Skip if not in a git repo, or if a merge/rebase is in progress, or if no changes.
2) Stage all changes (git add -A).
3) Attempt git commit with a timestamp message.
4) If commit fails:
   - If hooks modified files, re-stage and retry once.
   - If the retry still fails, create a failure report and run Codex auto-fix.
5) After a successful commit, pull --rebase and push.

Auto-fix behavior:
- Per-repo lock prevents concurrent fixes.
- Repeat guard prevents looping on identical failures.
- Report and state files live under: <repo>/.codex/auto_fix/
- Non-actionable failures (auth, non-fast-forward, GPG signing) skip auto-fix.
- If nothing is left to fix (no changes), auto-fix is skipped.

Opt-out:
- Set CODEX_AUTO_FIX_DISABLE=1, or create <repo>/.codex/auto_fix/disabled
- CODEX_AUTO_FIX_ACTIVE=1 is used internally to prevent recursion.

Toggles:
- Set CODEX_NOTIFY_DRY_RUN=1 to log intended git actions without mutating repos.
- Set CODEX_NOTIFY_BELL=0 to disable completion sounds.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from time import time


MAX_LOG_BYTES = 5 * 1024 * 1024
# Auto-fix uses per-repo lock + retry guard to avoid concurrent or looping fixes.
# We keep this file Python 3.9-compatible, so we use __future__ annotations above.
AUTO_FIX_LOCK_TTL_SEC = 60 * 60
AUTO_FIX_REPEAT_TTL_SEC = 30 * 60
AUTO_FIX_TIMEOUT_SEC = 10 * 60
GIT_STATUS_TIMEOUT_SEC = 60
GIT_ADD_TIMEOUT_SEC = 120
GIT_COMMIT_TIMEOUT_SEC = 180
GIT_PULL_TIMEOUT_SEC = 300
GIT_PUSH_TIMEOUT_SEC = 300
GIT_DIFF_TIMEOUT_SEC = 120

# Auto-fix flow overview:
# 1) Agent turn completes -> notify.py runs in that repo's cwd.
# 2) If there are changes, we try `git add -A` + `git commit`.
# 3) If commit fails, we detect whether hooks modified files:
#    - If hooks changed the working tree, we re-stage and retry commit once.
#    - If the retry still fails, we trigger a Codex auto-fix run.
# 4) Auto-fix writes a report to .codex/auto_fix/last_failure.json in the repo,
#    starts a per-repo lock, runs Codex with a focused prompt, and exits.
# 5) The next agent turn re-runs notify.py and pushes the fixed commit.

# Non-actionable failures (e.g., auth errors, non-fast-forward, GPG signing issues) should not
# trigger auto-fix because they require manual intervention or credentials, not code changes.
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


def log(message: str) -> None:
    """Append a timestamped line to ~/.codex/log/notify.log, truncating if too large."""
    try:
        log_dir = Path.home() / ".codex" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "notify.log"
        if log_path.exists() and log_path.stat().st_size >= MAX_LOG_BYTES:
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - MAX_LOG_BYTES))
                tail = handle.read()
            newline = tail.find(b"\n")
            if newline != -1:
                tail = tail[newline + 1 :]
            log_path.write_bytes(tail)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{utc_now_iso_z()} {message}\n")
    except Exception:
        pass


def utc_now_iso_z() -> str:
    """Return UTC timestamp in ISO format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_now_commit_timestamp() -> str:
    """Return UTC timestamp for commit messages."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def env_flag(name: str, default: bool) -> bool:
    """Parse boolean-style env vars with a default fallback."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def is_notify_dry_run() -> bool:
    """Return True when notify should not mutate git state."""
    return env_flag("CODEX_NOTIFY_DRY_RUN", False)


def is_notify_bell_enabled() -> bool:
    """Return True when completion bell/audio is enabled."""
    return env_flag("CODEX_NOTIFY_BELL", True)


def run(cmd, cwd, env=None, timeout=None):
    """Run a subprocess and capture stdout/stderr as text."""
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
    """Return True if cwd is inside a git work tree."""
    result = run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_dir(cwd: str) -> str | None:
    """Return .git directory path for cwd, or None if not a git repo."""
    result = run(["git", "rev-parse", "--git-dir"], cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repo_root(cwd: str) -> str | None:
    """Return repository root path, or None if not a git repo."""
    result = run(["git", "rev-parse", "--show-toplevel"], cwd)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def resolve_target_repo(payload: dict) -> str:
    """
    Resolve the repository target for this notify event.

    This notify hook intentionally operates on a single repo: payload cwd.
    """
    primary = payload.get("cwd") or os.getcwd()
    root = repo_root(primary)
    if root:
        return root
    return primary


def auto_fix_dir(cwd: str) -> Path | None:
    """Return <repo>/.codex/auto_fix path, or None if cwd is not a repo."""
    root = repo_root(cwd)
    if not root:
        return None
    return Path(root) / ".codex" / "auto_fix"


def is_auto_fix_disabled(cwd: str) -> bool:
    """Check env or sentinel file to disable auto-fix for this repo."""
    if os.environ.get("CODEX_AUTO_FIX_DISABLE", "").strip().lower() in {"1", "true", "yes"}:
        return True
    base = auto_fix_dir(cwd)
    if not base:
        return False
    return (base / "disabled").exists()


def acquire_auto_fix_lock(lock_path: Path, lock_payload: dict) -> bool:
    """
    Acquire per-repo auto-fix lock atomically.

    Returns True when acquired. Automatically clears stale locks.
    """
    for _ in range(2):
        try:
            # O_EXCL makes creation atomic: only one process can create the lock.
            fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                os.write(
                    fd,
                    json.dumps(lock_payload, indent=2).encode("utf-8"),
                )
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            try:
                age = time() - lock_path.stat().st_mtime
                if age <= AUTO_FIX_LOCK_TTL_SEC:
                    return False
            except Exception:
                return False
            try:
                lock_path.unlink()
            except Exception:
                return False
        except Exception:
            return False
    return False


def release_auto_fix_lock(lock_path: Path) -> None:
    """Best-effort lock cleanup."""
    try:
        lock_path.unlink()
    except Exception:
        pass


def autofix_state_path(cwd: str) -> Path | None:
    """Return path to the last auto-fix attempt record."""
    base = auto_fix_dir(cwd)
    if not base:
        return None
    return base / "last_attempt.json"


def failure_fingerprint(reason: str, command: list[str], result: subprocess.CompletedProcess) -> str:
    # Stable fingerprint to suppress repeating the exact same failure too quickly.
    data = {
        "reason": reason,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


def is_repeat_failure(cwd: str, fingerprint: str) -> bool:
    """Return True if the same failure was attempted recently."""
    state_path = autofix_state_path(cwd)
    if not state_path or not state_path.exists():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("fingerprint") != fingerprint:
            return False
        timestamp = state.get("timestamp")
        if not timestamp:
            return False
        seen_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        return (time() - seen_at) <= AUTO_FIX_REPEAT_TTL_SEC
    except Exception:
        return False


def write_autofix_state(cwd: str, fingerprint: str, reason: str) -> None:
    """Persist last auto-fix attempt metadata for repeat suppression."""
    state_path = autofix_state_path(cwd)
    if not state_path:
        return
    payload = {
        "timestamp": utc_now_iso_z(),
        "fingerprint": fingerprint,
        "reason": reason,
    }
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_failure_report(cwd: str, command: list[str], result: subprocess.CompletedProcess) -> Path | None:
    # Save context for the auto-fix agent to read.
    base = auto_fix_dir(cwd)
    if not base:
        return None
    base.mkdir(parents=True, exist_ok=True)
    report_path = base / "last_failure.json"
    status = run(["git", "status", "--porcelain"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    diff = run(["git", "diff"], cwd, timeout=GIT_DIFF_TIMEOUT_SEC)
    diff_staged = run(["git", "diff", "--staged"], cwd, timeout=GIT_DIFF_TIMEOUT_SEC)
    payload = {
        "timestamp": utc_now_iso_z(),
        "cwd": cwd,
        "repo_root": repo_root(cwd),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "git_status": status.stdout if status.returncode == 0 else "",
        "git_diff": diff.stdout if diff.returncode == 0 else "",
        "git_diff_staged": diff_staged.stdout if diff_staged.returncode == 0 else "",
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path


def build_autofix_prompt(report_path: Path, cwd: str, reason: str) -> str:
    """Build a concise prompt pointing to the failure report."""
    root = repo_root(cwd) or cwd
    return (
        "Auto-fix git failure.\n"
        f"Repository: {root}\n"
        f"Reason: {reason}\n"
        f"Report: {report_path}\n\n"
        "Fix the underlying issue so git commit and git push will succeed.\n"
        "Use repo conventions and only touch relevant files.\n"
        "Do not commit or push; leave changes ready for the next notify run.\n"
    )


def is_non_actionable_failure(command: list[str], result: subprocess.CompletedProcess) -> tuple[bool, str]:
    """Return (True, reason) when auto-fix should be skipped."""
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


def unstage_notify_artifacts(cwd: str) -> None:
    """
    Prevent notify internals from being committed when not ignored by repo config.

    This is a safety belt for repos that do not ignore `.codex/auto_fix/`.
    """
    run(["git", "reset", "-q", "--", ".codex/auto_fix"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)


def resolve_push_remote(cwd: str) -> str | None:
    """Resolve preferred git remote for pull/push for the current branch."""
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


def commit_with_retry(
    cwd: str,
    message: str,
    pre_commit_status: str,
) -> tuple[subprocess.CompletedProcess, bool]:
    # Some hooks (formatters/EOF fixers) intentionally modify files and fail the commit
    # so the user can re-run. We detect changes after the first commit attempt and retry
    # once (re-staging) before escalating to auto-fix.
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
        log(f"git add (retry) failed in {cwd}: {add_retry.stderr.strip()}")
        return commit, False
    unstage_notify_artifacts(cwd)
    retry = run(
        ["git", "commit", "-m", message],
        cwd,
        timeout=GIT_COMMIT_TIMEOUT_SEC,
    )
    return retry, True


def trigger_autofix(cwd: str, reason: str, command: list[str], result: subprocess.CompletedProcess) -> None:
    # Avoid recursive auto-fix runs and honor opt-out.
    if os.environ.get("CODEX_AUTO_FIX_ACTIVE") == "1":
        return
    if is_auto_fix_disabled(cwd):
        return
    if not has_changes(cwd):
        log(f"skip: no changes left to fix in {cwd}")
        return
    skip, skip_reason = is_non_actionable_failure(command, result)
    if skip:
        log(f"skip: non-actionable failure in {cwd}: {skip_reason}")
        return
    base = auto_fix_dir(cwd)
    if not base:
        return
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / "lock"
    lock_payload = {
        "timestamp": utc_now_iso_z(),
        "pid": os.getpid(),
        "cwd": cwd,
        "reason": reason,
    }
    if not acquire_auto_fix_lock(lock_path, lock_payload):
        log(f"skip: auto-fix lock active in {cwd}")
        return
    if not shutil.which("codex"):
        log("skip: codex not found in PATH")
        release_auto_fix_lock(lock_path)
        return
    report_path = write_failure_report(cwd, command, result)
    if not report_path:
        release_auto_fix_lock(lock_path)
        return
    fingerprint = failure_fingerprint(reason, command, result)
    if is_repeat_failure(cwd, fingerprint):
        log(f"skip: repeated auto-fix failure in {cwd}")
        release_auto_fix_lock(lock_path)
        return
    write_autofix_state(cwd, fingerprint, reason)
    prompt = build_autofix_prompt(report_path, cwd, reason)
    env = dict(os.environ)
    env["CODEX_AUTO_FIX_ACTIVE"] = "1"
    env["CODEX_AUTO_FIX_REPORT"] = str(report_path)
    log(
        "auto-fix start "
        f"cwd={cwd} reason={reason} report={report_path} "
        f"cmd=codex exec -p autofix -C {repo_root(cwd) or cwd}"
    )
    try:
        result = run(
            ["codex", "exec", "-p", "autofix", "-C", repo_root(cwd) or cwd, prompt],
            cwd,
            env=env,
            timeout=AUTO_FIX_TIMEOUT_SEC,
        )
        if result.returncode == 0:
            log("auto-fix exit code=0")
        else:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            log(
                "auto-fix exit "
                f"code={result.returncode} "
                f"stdout={stdout[:1000]} "
                f"stderr={stderr[:1000]}"
            )
        if result.returncode != 0:
            log(f"auto-fix failed in {cwd}: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        log(f"auto-fix timed out in {cwd} after {AUTO_FIX_TIMEOUT_SEC}s")
    finally:
        release_auto_fix_lock(lock_path)


def has_in_progress_ops(cwd: str) -> bool:
    """Return True if rebase/merge/cherry-pick/revert is in progress."""
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
    """Return absolute path to git index.lock for cwd, or None."""
    git_dir_path = git_dir(cwd)
    if not git_dir_path:
        return None
    base = Path(git_dir_path)
    if not base.is_absolute():
        base = Path(cwd) / base
    return base / "index.lock"


def is_lock_held(lock_path: Path) -> bool:
    """
    Return True when a process currently has the lock file open.

    We only remove lock files when we can verify they are stale.
    """
    if not lock_path.exists():
        return False
    if not shutil.which("lsof"):
        # Be conservative when we cannot check lock ownership.
        return True
    result = run(["lsof", str(lock_path)], str(lock_path.parent), timeout=GIT_STATUS_TIMEOUT_SEC)
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def clear_stale_index_lock(cwd: str) -> None:
    """Remove stale git index.lock if no process currently holds it."""
    lock_path = git_index_lock_path(cwd)
    if not lock_path or not lock_path.exists():
        return
    if is_lock_held(lock_path):
        log(f"skip: index.lock appears active in {cwd}: {lock_path}")
        return
    try:
        lock_path.unlink()
        log(f"removed stale index.lock in {cwd}: {lock_path}")
    except Exception as exc:
        log(f"failed to remove stale index.lock in {cwd}: {exc}")


def has_changes(cwd: str) -> bool:
    """Return True if git status shows any changes."""
    result = run(["git", "status", "--porcelain"], cwd, timeout=GIT_STATUS_TIMEOUT_SEC)
    return result.returncode == 0 and bool(result.stdout.strip())


def process_repo(cwd: str, payload: dict) -> None:
    """
    Process one repository for auto stage/commit/pull/push.

    Failures are logged and do not raise.
    """
    try:
        if not is_git_repo(cwd):
            log(f"skip: not a git repo: {cwd}")
            return
        if has_in_progress_ops(cwd):
            log(f"skip: in-progress git operation in {cwd}")
            return
        clear_stale_index_lock(cwd)
        if not has_changes(cwd):
            return

        message = build_commit_message(payload)
        dry_run = is_notify_dry_run()
        if dry_run:
            remote = resolve_push_remote(cwd)
            if remote:
                log(
                    "dry-run "
                    f"cwd={cwd} "
                    "would_run="
                    f"git add -A; git commit -m {message!r}; "
                    f"git pull --rebase {remote}; git push {remote} HEAD"
                )
            else:
                log(
                    "dry-run "
                    f"cwd={cwd} "
                    "would_run="
                    f"git add -A; git commit -m {message!r}; "
                    "skip pull/push (no remote)"
                )
            return

        add = run(["git", "add", "-A"], cwd, timeout=GIT_ADD_TIMEOUT_SEC)
        if add.returncode != 0:
            if "index.lock" in f"{add.stdout}\n{add.stderr}".lower():
                clear_stale_index_lock(cwd)
                add = run(["git", "add", "-A"], cwd, timeout=GIT_ADD_TIMEOUT_SEC)
                if add.returncode == 0:
                    log(f"git add recovered after stale lock cleanup in {cwd}")
            if add.returncode != 0:
                log(f"git add failed in {cwd}: {add.stderr.strip()}")
                return
        # Keep notify-internal artifacts out of commits unless explicitly desired.
        unstage_notify_artifacts(cwd)

        pre_commit_status = run(
            ["git", "status", "--porcelain"],
            cwd,
            timeout=GIT_STATUS_TIMEOUT_SEC,
        )
        pre_commit_snapshot = pre_commit_status.stdout if pre_commit_status.returncode == 0 else ""
        commit, retried = commit_with_retry(cwd, message, pre_commit_snapshot)
        if commit.returncode != 0:
            log(f"git commit failed in {cwd}: {commit.stderr.strip()}")
            if retried:
                log(f"git commit retry failed in {cwd}")
            trigger_autofix(cwd, "git commit", ["git", "commit", "-m", message], commit)
            return

        remote = resolve_push_remote(cwd)
        if not remote:
            log(f"skip: cannot resolve push remote in {cwd}")
            return

        pull_cmd = ["git", "pull", "--rebase", remote]
        pull = run(pull_cmd, cwd, timeout=GIT_PULL_TIMEOUT_SEC)
        if pull.returncode != 0:
            log(f"git pull --rebase failed in {cwd}: {pull.stderr.strip()}")
            return

        push_cmd = ["git", "push", remote, "HEAD"]
        push = run(push_cmd, cwd, timeout=GIT_PUSH_TIMEOUT_SEC)
        if push.returncode != 0:
            log(f"git push failed in {cwd}: {push.stderr.strip()}")
            trigger_autofix(cwd, "git push", push_cmd, push)
            return
    except subprocess.TimeoutExpired as exc:
        cmd = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        timeout = exc.timeout if exc.timeout is not None else "unknown"
        log(f"timeout in {cwd}: cmd={cmd} timeout={timeout}s")
    except Exception as exc:
        log(f"unexpected error in {cwd}: {exc}")


def build_commit_message(payload: dict) -> str:
    """Return an auto-commit message for Codex changes."""
    # TODO: replace with a smarter summary (e.g., diff-based) later.
    timestamp = utc_now_commit_timestamp()
    return f"Codex: {timestamp}"


def play_bell() -> None:
    """Play an audible notification on completion (best-effort)."""
    if not is_notify_bell_enabled():
        return
    if shutil.which("afplay"):
        subprocess.run(["afplay", "/System/Library/Sounds/Blow.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if shutil.which("osascript"):
        subprocess.run(["osascript", "-e", "beep 1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def main() -> int:
    """Entry point used by the notify hook."""
    log(f"notify invoked argv_count={len(sys.argv)} cwd={os.getcwd()}")
    if len(sys.argv) < 2:
        return 0
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        log("notify payload decode failed")
        return 0

    if payload.get("type") != "agent-turn-complete":
        log(f"notify skip: type={payload.get('type')}")
        return 0

    target_repo = resolve_target_repo(payload)
    log(f"notify handle: target_repo={target_repo}")

    try:
        process_repo(target_repo, payload)
    finally:
        play_bell()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
