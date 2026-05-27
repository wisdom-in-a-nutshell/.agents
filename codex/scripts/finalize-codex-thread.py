#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "finalize-codex-thread"
HOOK_EVENT = "FinalizeCodexThread"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_FINALIZATION_TIMEOUT_SECONDS = 900.0
MAX_OUTPUT_CHARS = 12_000
REPO_FINALIZER = Path("scripts/hooks/finalize_codex_thread.py")


class AppServerError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinalizeResult:
    thread_id: str
    cwd: str | None
    repo_root: str | None
    finalizer_path: str | None
    finalizer_status: str
    finalization_turn_id: str | None
    finalization_turn_status: str | None
    archived: bool
    skipped_reason: str | None
    error: str | None


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def truncate_text(value: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    suffix = "\n...[truncated]"
    return text[: max(0, limit - len(suffix))] + suffix


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_plain(payload: dict[str, Any]) -> None:
    status = payload["status"]
    data = payload.get("data") or {}
    result = data.get("result") or {}
    if status == "ok":
        action = "archived" if result.get("archived") else "resolved"
        print(
            f"ok {action} id={result.get('thread_id')} "
            f"cwd={result.get('cwd') or 'unknown'} "
            f"repo_hook={result.get('finalizer_status')} "
            f"turn={result.get('finalization_turn_status') or 'none'}"
        )
        return

    error = payload.get("error") or {}
    print(f"error {error.get('code', 'error')}: {error.get('message', status)}", file=sys.stderr)
    if error.get("hint"):
        print(error["hint"], file=sys.stderr)


def finish(
    *,
    status: str,
    started_at: float,
    plain: bool,
    result: FinalizeResult | None = None,
    error: dict[str, Any] | None = None,
    exit_code: int,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": status,
        "data": {"result": asdict(result) if result else None},
        "error": error,
        "meta": {
            "timestamp_utc": utc_now(),
            "duration_ms": int((time.time() - started_at) * 1000),
        },
    }
    if plain:
        emit_plain(payload)
    else:
        emit_json(payload)
    return exit_code


class AppServerClient:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.proc: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr_lines: list[str] = []
        self.next_id = 1

    def __enter__(self) -> "AppServerClient":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def start(self) -> None:
        self.proc = subprocess.Popen(
            ["codex", "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        threading.Thread(target=self._read_stdout, args=(self.proc.stdout,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(self.proc.stderr,), daemon=True).start()

        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "agents_finalize_codex_thread",
                    "title": "Agents Codex Thread Finalizer",
                    "version": SCHEMA_VERSION,
                }
            },
        )
        self.notify("initialized", {})

    def close(self) -> None:
        if self.proc is None:
            return
        proc = self.proc
        self.proc = None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    def _read_stdout(self, stream: Any) -> None:
        for line in stream:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                self.messages.put(payload)

    def _read_stderr(self, stream: Any) -> None:
        for line in stream:
            text = line.rstrip("\n")
            if text:
                self.stderr_lines.append(text)
                del self.stderr_lines[:-80]

    def _write(self, message: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise AppServerError("app-server is not running")
        if self.proc.poll() is not None:
            raise AppServerError(f"app-server exited with code {self.proc.returncode}")
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        message: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        self._write(message)
        return self._read_response(request_id, method=method, timeout_seconds=timeout_seconds or self.timeout_seconds)

    def _next_message(self, *, timeout_seconds: float) -> dict[str, Any]:
        if self.proc is not None and self.proc.poll() is not None and self.messages.empty():
            stderr_tail = "\n".join(self.stderr_lines[-20:])
            raise AppServerError(
                f"app-server exited with code {self.proc.returncode}"
                + (f"\nstderr:\n{stderr_tail}" if stderr_tail else "")
            )
        try:
            return self.messages.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            stderr_tail = "\n".join(self.stderr_lines[-20:])
            raise AppServerError(
                "timed out waiting for app-server message"
                + (f"\nstderr:\n{stderr_tail}" if stderr_tail else "")
            ) from exc

    def _read_response(self, request_id: int, *, method: str, timeout_seconds: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stderr_tail = "\n".join(self.stderr_lines[-20:])
                raise AppServerError(
                    f"timed out waiting for {method} response id={request_id}"
                    + (f"\nstderr:\n{stderr_tail}" if stderr_tail else "")
                )
            payload = self._next_message(timeout_seconds=remaining)
            if "id" in payload and "method" in payload:
                self._handle_server_request(payload)
                continue
            if payload.get("id") != request_id:
                continue
            if "error" in payload:
                error = payload["error"]
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise AppServerError(f"{method} failed: {message}")
            result = payload.get("result")
            if not isinstance(result, dict):
                return {}
            return result

    def _handle_server_request(self, msg: dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if req_id is None:
            return
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            self._write({"id": req_id, "result": {"decision": "acceptForSession"}})
            return
        if method == "applyPatchApproval":
            self._write({"id": req_id, "result": {"decision": "approved_for_session"}})
            return
        if method == "execCommandApproval":
            self._write({"id": req_id, "result": {"decision": "approved_for_session"}})
            return
        if isinstance(method, str) and method.startswith("item/") and method.endswith("/requestApproval"):
            self._write({"id": req_id, "result": {"decision": "decline"}})
            return
        self._write({"id": req_id, "result": {}})


def thread_read(client: AppServerClient, thread_id: str) -> dict[str, Any]:
    result = client.request("thread/read", {"threadId": thread_id, "includeTurns": False})
    thread = result.get("thread")
    if not isinstance(thread, dict):
        raise AppServerError("thread/read returned malformed response")
    return thread


def archive_thread(client: AppServerClient, thread_id: str) -> None:
    client.request("thread/archive", {"threadId": thread_id})


def is_nonfatal_archive_error(exc: Exception) -> bool:
    return "no rollout found for thread id" in str(exc)


def repo_root_for_cwd(cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return str(Path(cwd).expanduser().resolve())
    if result.returncode != 0 or not result.stdout.strip():
        return str(Path(cwd).expanduser().resolve())
    return str(Path(result.stdout.strip()).expanduser().resolve())


def run_repo_finalizer(
    *,
    finalizer_path: Path,
    repo_root: str,
    thread: dict[str, Any],
    reason: str,
    timeout_seconds: float,
    finalization_timeout_seconds: float,
) -> tuple[bool, str | None, str | None]:
    thread_id = str(thread.get("id") or "")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "hook_event_name": HOOK_EVENT,
        "thread_id": thread_id,
        "reason": reason,
    }
    env = os.environ.copy()
    try:
        result = subprocess.run(
            [sys.executable, str(finalizer_path)],
            cwd=repo_root,
            env=env,
            input=json.dumps(payload, sort_keys=True),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds + finalization_timeout_seconds + 30,
        )
    except subprocess.TimeoutExpired as exc:
        return False, None, f"repo finalizer timed out after {exc.timeout}s"
    except OSError as exc:
        return False, None, f"repo finalizer failed to start: {exc}"

    if result.returncode == 0:
        return True, result.stdout.strip() or None, None
    output = "\n".join(part for part in [result.stderr, result.stdout] if part.strip())
    message = output.strip() or f"repo finalizer exited {result.returncode}"
    return False, None, truncate_text(message)


def finalize_thread(
    *,
    thread_id: str,
    reason: str,
    dry_run: bool,
    timeout_seconds: float,
    finalization_timeout_seconds: float,
    client_factory: Any = AppServerClient,
) -> FinalizeResult:
    with client_factory(timeout_seconds) as client:
        thread = thread_read(client, thread_id)
    cwd = thread.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return FinalizeResult(
            thread_id=thread_id,
            cwd=None,
            repo_root=None,
            finalizer_path=None,
            finalizer_status="not_run",
            finalization_turn_id=None,
            finalization_turn_status=None,
            archived=False,
            skipped_reason="missing_thread_cwd",
            error="thread/read did not return a usable cwd",
        )

    repo_root = repo_root_for_cwd(cwd)
    finalizer_path = Path(repo_root) / REPO_FINALIZER
    finalizer_path_str = str(finalizer_path) if finalizer_path.is_file() else None

    if dry_run:
        return FinalizeResult(
            thread_id=thread_id,
            cwd=cwd,
            repo_root=repo_root,
            finalizer_path=finalizer_path_str,
            finalizer_status="would_run" if finalizer_path_str else "not_found",
            finalization_turn_id=None,
            finalization_turn_status=None,
            archived=False,
            skipped_reason="dry_run",
            error=None,
        )

    finalizer_status = "not_found"
    if finalizer_path_str:
        ok, output, error = run_repo_finalizer(
            finalizer_path=finalizer_path,
            repo_root=repo_root,
            thread=thread,
            reason=reason,
            timeout_seconds=timeout_seconds,
            finalization_timeout_seconds=finalization_timeout_seconds,
        )
        if not ok:
            return FinalizeResult(
                thread_id=thread_id,
                cwd=cwd,
                repo_root=repo_root,
                finalizer_path=finalizer_path_str,
                finalizer_status="failed",
                finalization_turn_id=None,
                finalization_turn_status=None,
                archived=False,
                skipped_reason="finalizer_failed",
                error=error,
            )
        finalizer_status = "completed"
        if output:
            print(
                f"[finalize-codex-thread] repo finalizer output: {truncate_text(output, 1000)}",
                file=sys.stderr,
            )

    with client_factory(timeout_seconds) as client:
        try:
            archive_thread(client, thread_id)
        except Exception as exc:
            if is_nonfatal_archive_error(exc):
                return FinalizeResult(
                    thread_id=thread_id,
                    cwd=cwd,
                    repo_root=repo_root,
                    finalizer_path=finalizer_path_str,
                    finalizer_status=finalizer_status,
                    finalization_turn_id=None,
                    finalization_turn_status=None,
                    archived=False,
                    skipped_reason="archive_unavailable",
                    error=None,
                )
            return FinalizeResult(
                thread_id=thread_id,
                cwd=cwd,
                repo_root=repo_root,
                finalizer_path=finalizer_path_str,
                finalizer_status=finalizer_status,
                finalization_turn_id=None,
                finalization_turn_status=None,
                archived=False,
                skipped_reason="archive_failed",
                error=str(exc),
            )

    return FinalizeResult(
        thread_id=thread_id,
        cwd=cwd,
        repo_root=repo_root,
        finalizer_path=finalizer_path_str,
        finalizer_status=finalizer_status,
        finalization_turn_id=None,
        finalization_turn_status=None,
        archived=True,
        skipped_reason=None,
        error=None,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize a Codex thread by deriving repo policy from thread/read, running an optional repo finalizer, then archiving the thread."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Run finalization and archive the thread.")
    mode.add_argument("--dry-run", action="store_true", help="Resolve repo policy without running finalization or archive (default).")
    parser.add_argument("--thread-id", required=True, help="Codex/App Server thread id to finalize.")
    parser.add_argument("--reason", default="manual", help="Reason label passed to repo finalizers.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--finalization-timeout-seconds", type=float, default=DEFAULT_FINALIZATION_TIMEOUT_SECONDS)
    parser.add_argument("--no-input", action="store_true", help="Accepted for non-interactive callers; this command never prompts.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    parser.add_argument("--plain", action="store_true", help="Emit compact plain text for operator inspection.")
    return parser.parse_args()


def main() -> int:
    started_at = time.time()
    args = parse_args()
    plain = bool(args.plain)
    dry_run = not bool(args.apply)

    try:
        if args.timeout_seconds <= 0:
            raise ValueError("--timeout-seconds must be positive")
        if args.finalization_timeout_seconds <= 0:
            raise ValueError("--finalization-timeout-seconds must be positive")
        result = finalize_thread(
            thread_id=args.thread_id,
            reason=args.reason,
            dry_run=dry_run,
            timeout_seconds=args.timeout_seconds,
            finalization_timeout_seconds=args.finalization_timeout_seconds,
        )
        status = "ok" if result.error is None and (dry_run or result.archived) else "error"
        if result.error is None and result.skipped_reason == "archive_unavailable":
            status = "ok"
        exit_code = 0
        if status != "ok":
            exit_code = 5 if "timed out" in (result.error or "") else 4
        return finish(
            status=status,
            started_at=started_at,
            plain=plain,
            result=result,
            error=None
            if status == "ok"
            else {
                "code": "FinalizeFailed",
                "message": result.error or result.skipped_reason or "thread finalization failed",
                "hint": "Check the repo finalizer, Codex app-server availability, and thread/archive behavior.",
            },
            exit_code=exit_code,
        )
    except ValueError as exc:
        return finish(
            status="error",
            started_at=started_at,
            plain=plain,
            error={
                "code": "InvalidUsage",
                "message": str(exc),
                "retryable": False,
                "hint": "Fix the command arguments and retry.",
            },
            exit_code=2,
        )
    except Exception as exc:
        return finish(
            status="error",
            started_at=started_at,
            plain=plain,
            error={
                "code": exc.__class__.__name__,
                "message": str(exc),
                "retryable": True,
                "hint": "Run with --dry-run --json, then check Codex app-server availability.",
            },
            exit_code=4,
        )


if __name__ == "__main__":
    raise SystemExit(main())
