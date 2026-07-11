#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

try:
    from hooks.scripts.codex_turn_changes import (
        CodexTurnChangesError,
        collect_codex_turn_changes,
    )
except ModuleNotFoundError:  # Direct script execution adds this directory to sys.path.
    from codex_turn_changes import CodexTurnChangesError, collect_codex_turn_changes


VALID_RUNTIMES = {"antigravity", "claude", "codex", "copilot"}

GIT_STATUS_TIMEOUT_SEC = 60
GIT_ADD_TIMEOUT_SEC = 120
GIT_COMMIT_TIMEOUT_SEC = 180
GIT_PULL_TIMEOUT_SEC = 300
GIT_PUSH_TIMEOUT_SEC = 300
MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_REASON_CHARS = 12000
MAX_COMMAND_OUTPUT_CHARS = 3500
AZURE_PROVIDER_RE = re.compile(r"^azure(?:$|[-_])", re.IGNORECASE)
AGENT_COMMIT_COMMAND_RE = re.compile(
    r"(?m)^(Command:\s+git commit -m Agent: )\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z$"
)
FEEDBACK_COOLDOWN_SEC = 20 * 60
CODEX_REPO_LOCK_TIMEOUT_SEC = 30.0
CODEX_CHECK_WORKERS = 4
MAX_CODEX_ATTRIBUTED_PATHS = 2000
MAX_CODEX_REPOSITORIES = 32
MAX_CONSOLIDATION_PASSES = 3

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


def record_timing(timings: list[tuple[str, float]], phase: str, started_at: float) -> None:
    timings.append((phase, max(0.0, time.monotonic() - started_at)))


def format_ms(seconds: float) -> str:
    return f"{seconds * 1000:.1f}"


def log_timing(
    runtime: str,
    *,
    repo: str,
    outcome: str,
    total_started_at: float,
    timings: list[tuple[str, float]],
) -> None:
    parts = [
        f"outcome={outcome}",
        f"repo={repo}",
        f"total_ms={format_ms(max(0.0, time.monotonic() - total_started_at))}",
    ]
    parts.extend(f"{phase}_ms={format_ms(duration)}" for phase, duration in timings)
    log(runtime, "timing " + " ".join(parts))


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


def is_azure_provider(provider: object) -> bool:
    return isinstance(provider, str) and bool(AZURE_PROVIDER_RE.match(provider.strip()))


def provider_from_thread_db(session_id: object) -> str | None:
    if not isinstance(session_id, str) or not session_id.strip():
        return None

    state_db = Path.home() / ".codex" / "state_5.sqlite"
    if not state_db.is_file():
        return None

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True, timeout=1.0)
        row = conn.execute(
            "SELECT model_provider FROM threads WHERE id = ?",
            (session_id,),
        ).fetchone()
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()

    if not row:
        return None
    provider = row[0]
    return provider if isinstance(provider, str) and provider.strip() else None


def provider_from_global_config() -> str | None:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.is_file():
        return None

    top_level_provider = re.compile(r'^\s*model_provider\s*=\s*"([^"]+)"\s*(?:#.*)?$')
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                break
            match = top_level_provider.match(line)
            if match:
                return match.group(1)
    except Exception:
        return None
    return None


def current_model_provider(payload: dict[str, Any]) -> str | None:
    for key in ("model_provider", "modelProvider"):
        provider = payload.get(key)
        if isinstance(provider, str) and provider.strip():
            return provider
    return provider_from_thread_db(payload.get("session_id")) or provider_from_global_config()


def avoid_stop_continuation(payload: dict[str, Any]) -> bool:
    return is_azure_provider(current_model_provider(payload))


def feedback_turn_state_path() -> Path:
    return Path.home() / ".local/state/agents-control-plane/stop-feedback-turns.json"


def normalize_feedback_reason(reason: str) -> str:
    return AGENT_COMMIT_COMMAND_RE.sub(r"\1<TIMESTAMP>", reason)


def feedback_reason_key(thread_id: str, reason: str) -> str:
    digest = hashlib.sha256()
    digest.update(thread_id.encode("utf-8", errors="replace"))
    digest.update(b"\0")
    digest.update(normalize_feedback_reason(reason).encode("utf-8", errors="replace"))
    return digest.hexdigest()


def recently_queued_feedback_turn(thread_id: str, reason: str, *, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    path = feedback_turn_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    value = data.get(feedback_reason_key(thread_id, reason))
    if not isinstance(value, (int, float)):
        return False
    return now - float(value) < FEEDBACK_COOLDOWN_SEC


def mark_feedback_turn_queued(thread_id: str, reason: str, *, now: float | None = None) -> None:
    now = time.time() if now is None else now
    path = feedback_turn_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    cutoff = now - FEEDBACK_COOLDOWN_SEC
    compacted = {str(key): value for key, value in data.items() if isinstance(value, (int, float)) and value >= cutoff}
    compacted[feedback_reason_key(thread_id, reason)] = now
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(compacted, sort_keys=True) + "\n", encoding="utf-8")


def queue_feedback_turn(payload: dict[str, Any], reason: str, cwd: str) -> str | None:
    thread_id = payload.get("session_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        return None
    if recently_queued_feedback_turn(thread_id, reason):
        return "recent"

    script = Path(__file__).with_name("stop_feedback_turn.py")
    if not script.is_file():
        return None

    state_dir = Path.home() / ".local/state/agents-control-plane/stop-feedback-turns"
    state_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix="reason-",
        suffix=".txt",
        dir=state_dir,
        delete=False,
    )
    reason_file = Path(handle.name)
    try:
        with handle:
            handle.write(reason)
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--thread-id",
                thread_id,
                "--cwd",
                cwd,
                "--reason-file",
                str(reason_file),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        mark_feedback_turn_queued(thread_id, reason)
        return "queued"
    except Exception:
        try:
            reason_file.unlink()
        except OSError:
            pass
        return None


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


def push_needs_rebase(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}".lower()
    return any(
        pattern in output
        for pattern in (
            "non-fast-forward",
            "fetch first",
            "remote contains work",
            "updates were rejected because",
            "tip of your current branch is behind",
        )
    )


def maybe_continue(
    payload: dict[str, Any],
    reason: str,
    *,
    cwd: str | None = None,
) -> dict[str, Any]:
    if payload.get("stop_hook_active") is True:
        return warning(
            "Stop hook finalization is still failing after a continuation turn.\n\n"
            + reason
        )
    if avoid_stop_continuation(payload):
        # FIXME: Remove this Azure-specific fallback once upstream Codex fixes
        # Stop-hook continuation replay for local UUID message IDs:
        # https://github.com/openai/codex/issues/20783
        queue_result = queue_feedback_turn(payload, reason, cwd) if cwd else None
        if queue_result == "queued":
            return warning("Stop hook finalization failed; queued a follow-up turn with commit/check feedback.")
        if queue_result == "recent":
            return warning(
                "Stop hook finalization failed; a matching follow-up turn was already queued recently."
            )
        return warning(
            "Stop hook finalization needs attention, but this Azure-backed Codex thread could not queue "
            "a follow-up feedback turn.\n\n"
            + reason
        )
    return continuation(reason)


class RepoFinalization:
    """Durable state for one repository in a Codex turn transaction."""

    def __init__(
        self,
        *,
        root: str,
        paths: set[str] | None = None,
        phase: str = "pending",
        commit: str = "",
    ) -> None:
        self.root = root
        self.paths = paths or set()
        self.phase = phase
        self.commit = commit


def codex_transaction_path(thread_id: str) -> Path:
    digest = hashlib.sha256(thread_id.encode("utf-8", errors="replace")).hexdigest()
    return (
        Path.home()
        / ".local/state/agents-control-plane/codex-stop-transactions"
        / f"{digest}.json"
    )


def load_codex_transaction(thread_id: str) -> dict[str, RepoFinalization]:
    path = codex_transaction_path(thread_id)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise RuntimeError(f"could not read pending Codex Stop transaction: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("thread_id") != thread_id:
        raise RuntimeError("pending Codex Stop transaction has an invalid owner")
    entries = raw.get("repositories")
    if not isinstance(entries, list):
        raise RuntimeError("pending Codex Stop transaction is malformed")
    result: dict[str, RepoFinalization] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("pending Codex Stop repository entry is malformed")
        root = str(entry.get("root") or "").strip()
        paths = entry.get("paths")
        phase = str(entry.get("phase") or "pending")
        if not root or not isinstance(paths, list) or phase not in {"pending", "committed"}:
            raise RuntimeError("pending Codex Stop repository entry is invalid")
        normalized_paths = {
            str(value)
            for value in paths
            if isinstance(value, str)
            and value
            and not Path(value).is_absolute()
            and ".." not in Path(value).parts
        }
        result[root] = RepoFinalization(
            root=root,
            paths=normalized_paths,
            phase=phase,
            commit=str(entry.get("commit") or ""),
        )
    return result


def save_codex_transaction(
    thread_id: str,
    repositories: dict[str, RepoFinalization],
) -> None:
    path = codex_transaction_path(thread_id)
    if not repositories:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "thread_id": thread_id,
        "updated_at": utc_now_iso_z(),
        "repositories": [
            {
                "root": item.root,
                "paths": sorted(item.paths),
                "phase": item.phase,
                "commit": item.commit,
            }
            for item in sorted(repositories.values(), key=lambda value: value.root)
        ],
    }
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def existing_ancestor(path: Path) -> Path | None:
    candidate = path if path.is_dir() else path.parent
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate


def attributed_repo_path(path_text: str) -> tuple[str, str] | None:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        return None
    ancestor = existing_ancestor(path)
    if ancestor is None:
        return None
    root_text = repo_root(str(ancestor))
    if not root_text:
        return None
    root = Path(root_text).resolve()
    # Resolve parent aliases such as macOS /var -> /private/var without following
    # a tracked file symlink out of the worktree.
    normalized_path = Path(os.path.realpath(path.parent)) / path.name
    try:
        relative = normalized_path.relative_to(root)
    except ValueError:
        return None
    if not relative.parts or relative.parts[0] == ".git":
        return None
    return str(root), relative.as_posix()


def repositories_from_paths(paths: tuple[str, ...]) -> dict[str, RepoFinalization]:
    repositories: dict[str, RepoFinalization] = {}
    for path in paths:
        resolved = attributed_repo_path(path)
        if resolved is None:
            continue
        root, relative = resolved
        item = repositories.setdefault(root, RepoFinalization(root=root))
        item.paths.add(relative)
    return repositories


def merge_codex_transactions(
    pending: dict[str, RepoFinalization],
    discovered: dict[str, RepoFinalization],
) -> dict[str, RepoFinalization]:
    merged = {
        root: RepoFinalization(
            root=item.root,
            paths=set(item.paths),
            phase=item.phase,
            commit=item.commit,
        )
        for root, item in pending.items()
    }
    for root, item in discovered.items():
        existing = merged.get(root)
        if existing is None:
            merged[root] = item
            continue
        existing.paths.update(item.paths)
    return merged


def lock_path_for_repo(root: str) -> Path:
    digest = hashlib.sha256(root.encode("utf-8", errors="replace")).hexdigest()
    return Path.home() / ".local/state/agents-control-plane/repo-locks" / f"{digest}.lock"


@contextmanager
def lock_codex_repositories(roots: list[str]) -> Iterator[None]:
    handles: list[Any] = []
    try:
        for root in sorted(set(roots)):
            path = lock_path_for_repo(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+", encoding="utf-8")
            deadline = time.monotonic() + CODEX_REPO_LOCK_TIMEOUT_SEC
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        handle.close()
                        raise RuntimeError(
                            f"another Codex Stop hook is finalizing repository {root}"
                        )
                    time.sleep(0.05)
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()} thread-safe-lock root={root}\n")
            handle.flush()
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def null_separated_paths(result: subprocess.CompletedProcess[str]) -> set[str]:
    if result.returncode != 0:
        return set()
    return {value for value in result.stdout.split("\0") if value}


def staged_paths(root: str) -> tuple[set[str], subprocess.CompletedProcess[str]]:
    result = run(
        ["git", "--literal-pathspecs", "diff", "--cached", "--name-only", "-z"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    return null_separated_paths(result), result


def unstaged_paths(root: str) -> tuple[set[str], list[subprocess.CompletedProcess[str]]]:
    diff = run(
        ["git", "diff", "--no-renames", "--name-only", "-z"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    untracked = run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    return null_separated_paths(diff) | null_separated_paths(untracked), [diff, untracked]


def worktree_changed_paths(root: str) -> tuple[set[str], bool]:
    staged, staged_result = staged_paths(root)
    unstaged, unstaged_results = unstaged_paths(root)
    ok = staged_result.returncode == 0 and all(
        result.returncode == 0 for result in unstaged_results
    )
    return staged | unstaged, ok


def codex_failure_reason(title: str, failures: list[str]) -> str:
    lines = [title, "", "Please fix every issue below, then finish again. The Codex Stop hook will retry all repositories."]
    for failure in failures:
        lines.extend(["", failure])
    return truncate_text("\n".join(lines), MAX_REASON_CHARS)


def preflight_repo_check(item: RepoFinalization) -> tuple[str, subprocess.CompletedProcess[str] | None]:
    script = Path(item.root) / "scripts/check-fast.sh"
    if not script.is_file():
        return item.root, None
    return item.root, run(
        ["bash", "scripts/check-fast.sh"],
        item.root,
        timeout=GIT_COMMIT_TIMEOUT_SEC,
    )


def head_commit(root: str) -> str:
    result = run(["git", "rev-parse", "HEAD"], root, timeout=GIT_STATUS_TIMEOUT_SEC)
    return result.stdout.strip() if result.returncode == 0 else ""


def unpushed_head(root: str) -> str:
    head = head_commit(root)
    if not head or not resolve_push_remote(root):
        return ""
    if not has_tracking_upstream(root):
        return head
    result = run(
        ["git", "rev-list", "--count", "@{upstream}..HEAD"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    if result.returncode != 0:
        return ""
    try:
        return head if int(result.stdout.strip()) > 0 else ""
    except ValueError:
        return ""


def push_committed_repo(
    root: str,
) -> tuple[subprocess.CompletedProcess[str] | None, list[str], str]:
    remote = resolve_push_remote(root)
    if not remote:
        return None, [], "no push remote could be resolved"
    tracked = has_tracking_upstream(root)
    push_cmd = ["git", "push", remote, "HEAD"] if tracked else ["git", "push", "-u", remote, "HEAD"]
    push = run(push_cmd, root, timeout=GIT_PUSH_TIMEOUT_SEC)
    if push.returncode != 0 and tracked and push_needs_rebase(push):
        pull_cmd = ["git", "pull", "--rebase"]
        pull = run(pull_cmd, root, timeout=GIT_PULL_TIMEOUT_SEC)
        if pull.returncode != 0:
            return pull, pull_cmd, "git pull --rebase failed"
        push = run(push_cmd, root, timeout=GIT_PUSH_TIMEOUT_SEC)
    return push, push_cmd, "git push failed"


def process_codex_repositories(
    cwd: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Finalize exactly the repositories attributed to this Codex turn tree."""
    thread_id = str(payload.get("session_id") or "").strip()
    if not thread_id:
        log("codex", "fallback single-repo reason=missing-session-id")
        return process_repo(cwd, payload, runtime="codex")

    try:
        pending = load_codex_transaction(thread_id)
        changes = collect_codex_turn_changes(thread_id)
    except (CodexTurnChangesError, RuntimeError) as exc:
        log("codex", f"turn-attribution-failed thread={thread_id} error={exc}")
        if "pending" in locals() and pending:
            log(
                "codex",
                f"resume pending-without-attribution thread={thread_id} repos={len(pending)}",
            )
            changes = SimpleNamespace(
                parent_thread_id="",
                touched_paths=(),
            )
        else:
            log("codex", f"fallback primary-repo-only thread={thread_id}")
            return process_repo(cwd, payload, runtime="codex")

    if changes.parent_thread_id:
        log(
            "codex",
            f"skip subagent-stop thread={thread_id} parent={changes.parent_thread_id}",
        )
        return None

    repositories = merge_codex_transactions(
        pending,
        repositories_from_paths(changes.touched_paths),
    )
    primary_root = repo_root(cwd) if is_git_repo(cwd) else None
    if primary_root:
        primary_root = str(Path(primary_root).resolve())
        primary_changes, primary_status_ok = worktree_changed_paths(primary_root)
        primary_unpushed = unpushed_head(primary_root)
        if not primary_status_ok:
            return maybe_continue(
                payload,
                state_failure_reason(primary_root, "could not inspect the primary repository status"),
                cwd=primary_root,
            )
        if primary_changes or primary_unpushed:
            primary = repositories.setdefault(
                primary_root,
                RepoFinalization(root=primary_root),
            )
            primary.paths.update(primary_changes)
            if primary_unpushed and not primary.commit:
                primary.commit = primary_unpushed
            if primary.commit and not primary_changes:
                primary.phase = "committed"
    if not repositories:
        log("codex", f"skip no-attributed-files thread={thread_id}")
        save_codex_transaction(thread_id, {})
        return None

    attributed_path_count = sum(len(item.paths) for item in repositories.values())
    if len(repositories) > MAX_CODEX_REPOSITORIES or attributed_path_count > MAX_CODEX_ATTRIBUTED_PATHS:
        save_codex_transaction(thread_id, repositories)
        return maybe_continue(
            payload,
            codex_failure_reason(
                "This Codex turn is too large for safe automatic multi-repository finalization.",
                [
                    f"repositories={len(repositories)} (limit {MAX_CODEX_REPOSITORIES}), "
                    f"paths={attributed_path_count} (limit {MAX_CODEX_ATTRIBUTED_PATHS})"
                ],
            ),
            cwd=cwd,
        )

    save_codex_transaction(thread_id, repositories)
    with lock_codex_repositories(list(repositories)):
        failures: list[str] = []
        for item in repositories.values():
            if not is_git_repo(item.root):
                failures.append(f"Repository {item.root}: no longer a Git worktree.")
                continue
            if has_in_progress_ops(item.root):
                failures.append(
                    f"Repository {item.root}: a merge, rebase, cherry-pick, or revert is in progress."
                )
                continue
            if not clear_stale_index_lock(item.root):
                failures.append(f"Repository {item.root}: git index.lock appears active.")
                continue
            current_changes, status_ok = worktree_changed_paths(item.root)
            if not status_ok:
                failures.append(f"Repository {item.root}: could not inspect working-tree changes.")
                continue
            item.paths.update(current_changes)
            existing_unpushed = unpushed_head(item.root)
            if existing_unpushed and not item.commit:
                item.commit = existing_unpushed
            if item.phase == "committed" and current_changes:
                # Preserve item.commit: it still needs to be pushed after the
                # newly consolidated paths are checked and committed.
                item.phase = "pending"
        if failures:
            save_codex_transaction(thread_id, repositories)
            return maybe_continue(
                payload,
                codex_failure_reason("I could not inspect every affected repository.", failures),
                cwd=cwd,
            )
        attributed_path_count = sum(len(item.paths) for item in repositories.values())
        if attributed_path_count > MAX_CODEX_ATTRIBUTED_PATHS:
            save_codex_transaction(thread_id, repositories)
            return maybe_continue(
                payload,
                codex_failure_reason(
                    "The consolidated Codex transaction is too large for safe automatic finalization.",
                    [
                        f"paths={attributed_path_count} "
                        f"(limit {MAX_CODEX_ATTRIBUTED_PATHS})"
                    ],
                ),
                cwd=cwd,
            )
        pending_items = [item for item in repositories.values() if item.phase == "pending"]
        staged_pending_items: list[RepoFinalization] = []
        for item in pending_items:
            current_staged, staged_result = staged_paths(item.root)
            if staged_result.returncode != 0:
                failures.append(
                    command_failure_reason(
                        item.root,
                        "inspect staged paths",
                        ["git", "--literal-pathspecs", "diff", "--cached", "--name-only", "-z"],
                        staged_result,
                    )
                )
                continue
            item.paths.update(current_staged)
            if not item.paths:
                if item.commit:
                    item.phase = "committed"
                else:
                    repositories.pop(item.root, None)
                continue
            add_cmd = ["git", "--literal-pathspecs", "add", "-A", "--", *sorted(item.paths)]
            add = run(add_cmd, item.root, timeout=GIT_ADD_TIMEOUT_SEC)
            if add.returncode != 0:
                failures.append(command_failure_reason(item.root, "git add attributed paths", add_cmd, add))
                continue
            final_staged, final_staged_result = staged_paths(item.root)
            if final_staged_result.returncode != 0:
                failures.append(
                    command_failure_reason(
                        item.root,
                        "inspect attributed staging result",
                        ["git", "--literal-pathspecs", "diff", "--cached", "--name-only", "-z"],
                        final_staged_result,
                    )
                )
                continue
            if final_staged:
                staged_pending_items.append(item)
            elif item.commit:
                item.phase = "committed"
            else:
                repositories.pop(item.root, None)

        if failures:
            save_codex_transaction(thread_id, repositories)
            return maybe_continue(
                payload,
                codex_failure_reason("I could not stage the complete Codex turn safely.", failures),
                cwd=cwd,
            )

        pending_items = staged_pending_items
        save_codex_transaction(thread_id, repositories)

        stable = False
        for pass_index in range(MAX_CONSOLIDATION_PASSES):
            check_failures: list[str] = []
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, min(CODEX_CHECK_WORKERS, len(pending_items) or 1))
            ) as executor:
                for root, result in executor.map(preflight_repo_check, pending_items):
                    if result is not None and result.returncode != 0:
                        check_failures.append(
                            command_failure_reason(
                                root,
                                "scripts/check-fast.sh preflight",
                                ["bash", "scripts/check-fast.sh"],
                                result,
                            )
                        )
            if check_failures:
                save_codex_transaction(thread_id, repositories)
                return maybe_continue(
                    payload,
                    codex_failure_reason("Fast checks failed in one or more repositories.", check_failures),
                    cwd=cwd,
                )

            restage_failures: list[str] = []
            changed_during_checks = False
            for item in pending_items:
                staged, staged_result = staged_paths(item.root)
                unstaged, unstaged_results = unstaged_paths(item.root)
                if staged_result.returncode != 0 or any(
                    result.returncode != 0 for result in unstaged_results
                ):
                    restage_failures.append(
                        f"Repository {item.root}: could not re-read changes after checks."
                    )
                    continue
                additions = (staged | unstaged) - item.paths
                if additions or unstaged:
                    item.paths.update(staged | unstaged)
                    changed_during_checks = True
                    add_cmd = [
                        "git",
                        "--literal-pathspecs",
                        "add",
                        "-A",
                        "--",
                        *sorted(item.paths),
                    ]
                    add = run(add_cmd, item.root, timeout=GIT_ADD_TIMEOUT_SEC)
                    if add.returncode != 0:
                        restage_failures.append(
                            command_failure_reason(
                                item.root,
                                "restage concurrent changes",
                                add_cmd,
                                add,
                            )
                        )
            if restage_failures:
                save_codex_transaction(thread_id, repositories)
                return maybe_continue(
                    payload,
                    codex_failure_reason(
                        "I could not consolidate files that changed during checks.",
                        restage_failures,
                    ),
                    cwd=cwd,
                )
            if sum(len(item.paths) for item in repositories.values()) > MAX_CODEX_ATTRIBUTED_PATHS:
                save_codex_transaction(thread_id, repositories)
                return maybe_continue(
                    payload,
                    codex_failure_reason(
                        "Concurrent changes made the consolidated transaction too large.",
                        [f"path limit={MAX_CODEX_ATTRIBUTED_PATHS}"],
                    ),
                    cwd=cwd,
                )
            save_codex_transaction(thread_id, repositories)
            if not changed_during_checks:
                stable = True
                break
            log(
                "codex",
                f"restage concurrent-edits thread={thread_id} pass={pass_index + 1}",
            )

        if not stable:
            return maybe_continue(
                payload,
                codex_failure_reason(
                    "Affected repositories kept changing while checks were running.",
                    [
                        f"Retried consolidation {MAX_CONSOLIDATION_PASSES} times without "
                        "discarding any staged or working-tree changes."
                    ],
                ),
                cwd=cwd,
            )

        message = build_commit_message(payload)
        for item in pending_items:
            staged, staged_result = staged_paths(item.root)
            if staged_result.returncode != 0:
                failures.append(f"Repository {item.root}: could not inspect the final staged paths.")
                break
            if not staged:
                repositories.pop(item.root, None)
                save_codex_transaction(thread_id, repositories)
                continue
            unexpected_staged = staged - item.paths
            if unexpected_staged:
                failures.append(
                    f"Repository {item.root}: new staged files arrived after the final check: "
                    + ", ".join(sorted(unexpected_staged))
                    + ". Left them intact for the next consolidation pass."
                )
                break
            final_unstaged, final_unstaged_results = unstaged_paths(item.root)
            if final_unstaged or any(
                result.returncode != 0 for result in final_unstaged_results
            ):
                failures.append(
                    f"Repository {item.root}: new edits arrived after the final check; "
                    "left them intact for the next consolidation pass."
                )
                break
            commit_cmd = ["git", "commit", "--no-verify", "-m", message]
            commit = run(commit_cmd, item.root, timeout=GIT_COMMIT_TIMEOUT_SEC)
            if commit.returncode != 0:
                non_actionable, label = is_non_actionable_failure(commit_cmd, commit)
                if non_actionable and label == "nothing to commit":
                    item.phase = "committed"
                    item.commit = unpushed_head(item.root) or head_commit(item.root)
                    save_codex_transaction(thread_id, repositories)
                    continue
                failures.append(
                    command_failure_reason(
                        item.root,
                        "git commit / pre-commit checks",
                        commit_cmd,
                        commit,
                    )
                )
                break
            item.phase = "committed"
            item.commit = head_commit(item.root)
            save_codex_transaction(thread_id, repositories)

        if failures:
            return maybe_continue(
                payload,
                codex_failure_reason("A repository commit failed during Codex finalization.", failures),
                cwd=cwd,
            )

        for root in sorted(list(repositories)):
            item = repositories[root]
            if item.phase != "committed":
                continue
            current_head = head_commit(root)
            if item.commit != current_head:
                log(
                    "codex",
                    f"adopt rewritten-head repo={root} pending={item.commit or '<missing>'} "
                    f"current={current_head or '<missing>'}",
                )
                item.commit = current_head
                save_codex_transaction(thread_id, repositories)
            push, command, failure_title = push_committed_repo(root)
            if push is None:
                failures.append(f"Repository {root}: {failure_title}.")
                break
            if push.returncode != 0:
                non_actionable, label = is_non_actionable_failure(command, push)
                reason = command_failure_reason(
                    root,
                    f"{failure_title} ({label})" if non_actionable else failure_title,
                    command,
                    push,
                    retryable=not non_actionable,
                )
                failures.append(reason)
                break
            repositories.pop(root, None)
            save_codex_transaction(thread_id, repositories)
            log("codex", f"ok turn-repo-pushed thread={thread_id} repo={root} commit={item.commit}")

        if failures:
            return maybe_continue(
                payload,
                codex_failure_reason("A repository publish failed during Codex finalization.", failures),
                cwd=cwd,
            )

    save_codex_transaction(thread_id, {})
    return None


def process_repo(cwd: str, payload: dict[str, Any], *, runtime: str) -> dict[str, Any] | None:
    total_started_at = time.monotonic()
    timings: list[tuple[str, float]] = []
    log_repo = cwd

    def finish(outcome: str, output: dict[str, Any] | None) -> dict[str, Any] | None:
        log_timing(
            runtime,
            repo=log_repo,
            outcome=outcome,
            total_started_at=total_started_at,
            timings=timings,
        )
        return output

    started_at = time.monotonic()
    is_repo = is_git_repo(cwd)
    record_timing(timings, "is_git_repo", started_at)
    if not is_repo:
        log(runtime, f"skip not-git cwd={cwd}")
        return finish("not_git", None)

    started_at = time.monotonic()
    root = repo_root(cwd) or cwd
    record_timing(timings, "repo_root", started_at)
    log_repo = root

    started_at = time.monotonic()
    in_progress = has_in_progress_ops(root)
    lock_clear = clear_stale_index_lock(root) if not in_progress else True
    record_timing(timings, "state", started_at)
    if in_progress:
        log(runtime, f"block in-progress-git-op repo={root}")
        return finish(
            "block_in_progress_git_op",
            maybe_continue(
                payload,
                state_failure_reason(root, "a merge, rebase, cherry-pick, or revert is in progress"),
                cwd=root,
            ),
        )
    if not lock_clear:
        log(runtime, f"block active-index-lock repo={root}")
        return finish(
            "block_active_index_lock",
            maybe_continue(payload, state_failure_reason(root, "git index.lock appears active"), cwd=root),
        )

    started_at = time.monotonic()
    changed = has_changes(root)
    record_timing(timings, "status", started_at)
    if not changed:
        if runtime == "codex":
            pending_head = unpushed_head(root)
            if pending_head:
                push, command, failure_title = push_committed_repo(root)
                if push is None:
                    return finish(
                        "warn_no_remote",
                        warning(f"Local commits in {root} could not be pushed: {failure_title}."),
                    )
                if push.returncode != 0:
                    return finish(
                        "block_existing_commit_push",
                        maybe_continue(
                            payload,
                            command_failure_reason(root, failure_title, command, push),
                            cwd=root,
                        ),
                    )
                log("codex", f"ok pushed-existing-commits repo={root} head={pending_head}")
                return finish("pushed_existing_commits", None)
        log(runtime, f"skip clean repo={root}")
        return finish("clean", None)

    message = build_commit_message(payload)
    started_at = time.monotonic()
    add = run(["git", "add", "-A"], root, timeout=GIT_ADD_TIMEOUT_SEC)
    if add.returncode != 0:
        if "index.lock" in f"{add.stdout}\n{add.stderr}".lower() and clear_stale_index_lock(root):
            add = run(["git", "add", "-A"], root, timeout=GIT_ADD_TIMEOUT_SEC)
        if add.returncode != 0:
            record_timing(timings, "add", started_at)
            log(runtime, f"block git-add repo={root} exit={add.returncode}")
            return finish(
                "block_git_add",
                maybe_continue(
                    payload,
                    command_failure_reason(root, "git add", ["git", "add", "-A"], add),
                    cwd=root,
                ),
            )
    record_timing(timings, "add", started_at)

    started_at = time.monotonic()
    pre_commit_status = run(
        ["git", "status", "--porcelain"],
        root,
        timeout=GIT_STATUS_TIMEOUT_SEC,
    )
    pre_commit_snapshot = pre_commit_status.stdout if pre_commit_status.returncode == 0 else ""
    commit, _retried = commit_with_retry(root, message, pre_commit_snapshot)
    record_timing(timings, "commit_check", started_at)
    if commit.returncode != 0:
        skip, skip_reason = is_non_actionable_failure(["git", "commit", "-m", message], commit)
        if skip and skip_reason == "nothing to commit":
            log(runtime, f"skip nothing-to-commit repo={root}")
            return finish("nothing_to_commit", None)
        if skip:
            log(runtime, f"warn git-commit repo={root} reason={skip_reason} exit={commit.returncode}")
            return finish(
                "warn_git_commit",
                warning(
                    command_failure_reason(
                        root,
                        f"git commit ({skip_reason})",
                        ["git", "commit", "-m", message],
                        commit,
                        retryable=False,
                    )
                ),
            )
        log(runtime, f"block git-commit repo={root} exit={commit.returncode}")
        return finish(
            "block_git_commit",
            maybe_continue(
                payload,
                command_failure_reason(root, "git commit / pre-commit checks", ["git", "commit", "-m", message], commit),
                cwd=root,
            ),
        )

    started_at = time.monotonic()
    remote = resolve_push_remote(root)
    tracked_branch = has_tracking_upstream(root) if remote else False
    record_timing(timings, "remote", started_at)
    if not remote:
        log(runtime, f"warn no-remote repo={root}")
        return finish(
            "warn_no_remote",
            warning(f"Committed changes in {root}, but no push remote could be resolved."),
        )

    if tracked_branch:
        push_cmd = ["git", "push", remote, "HEAD"]
    else:
        log(runtime, f"initial-push repo={root} remote={remote} branch={current_branch_name(root)}")
        push_cmd = ["git", "push", "-u", remote, "HEAD"]

    started_at = time.monotonic()
    push = run(push_cmd, root, timeout=GIT_PUSH_TIMEOUT_SEC)
    record_timing(timings, "push", started_at)
    if push.returncode != 0 and tracked_branch and push_needs_rebase(push):
        pull_cmd = ["git", "pull", "--rebase"]
        started_at = time.monotonic()
        pull = run(pull_cmd, root, timeout=GIT_PULL_TIMEOUT_SEC)
        record_timing(timings, "pull_rebase", started_at)
        if pull.returncode != 0:
            log(runtime, f"block git-pull-rebase repo={root} exit={pull.returncode}")
            return finish(
                "block_git_pull_rebase",
                maybe_continue(
                    payload,
                    command_failure_reason(root, "git pull --rebase", pull_cmd, pull),
                    cwd=root,
                ),
            )
        started_at = time.monotonic()
        push = run(push_cmd, root, timeout=GIT_PUSH_TIMEOUT_SEC)
        record_timing(timings, "push_retry", started_at)

    if push.returncode != 0:
        skip, skip_reason = is_non_actionable_failure(push_cmd, push)
        if skip:
            log(runtime, f"warn git-push repo={root} reason={skip_reason} exit={push.returncode}")
            return finish(
                "warn_git_push",
                warning(
                    command_failure_reason(root, f"git push ({skip_reason})", push_cmd, push, retryable=False)
                ),
            )
        log(runtime, f"block git-push repo={root} exit={push.returncode}")
        return finish(
            "block_git_push",
            maybe_continue(payload, command_failure_reason(root, "git push", push_cmd, push), cwd=root),
        )

    log(runtime, f"ok committed-and-pushed repo={root} branch={current_branch_name(root)} remote={remote}")
    return finish("committed_pushed", None)


def main() -> int:
    args = parse_args()
    payload = read_payload(args.debug) or {}
    if payload.get("hook_event_name") not in {None, "Stop"}:
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())

    try:
        if args.runtime == "codex":
            output = process_codex_repositories(cwd, payload)
        else:
            output = process_repo(cwd, payload, runtime=args.runtime)
    except subprocess.TimeoutExpired as exc:
        cmd = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        timeout = exc.timeout if exc.timeout is not None else "unknown"
        output = maybe_continue(
            payload,
            state_failure_reason(cwd, f"command timed out after {timeout}s: {cmd}"),
            cwd=cwd,
        )
    except RuntimeError as exc:
        log(args.runtime, f"runtime-error cwd={cwd} error={exc}")
        output = maybe_continue(
            payload,
            state_failure_reason(cwd, str(exc)),
            cwd=cwd,
        )
    except Exception as exc:
        log(args.runtime, f"unexpected-error cwd={cwd} error={exc}")
        output = warning(f"Stop hook failed unexpectedly at {utc_now_iso_z()}: {exc}")

    if output:
        return emit_json(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
