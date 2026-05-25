#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import queue
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMAND = "codex-sidebar-project-prune"
DEFAULT_DAYS = 2.0
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_PAGE_LIMIT = 200
DEFAULT_LOCK = Path.home() / ".local/state/codex-control-plane/sidebar-project-prune.lock"
DEFAULT_BACKUP_ROOT = Path.home() / ".local/state/codex-control-plane/sidebar-project-prune/backups"

REQUIRED_GLOBAL_KEYS = {
    "active-workspace-roots",
    "electron-persisted-atom-state",
    "electron-saved-workspace-roots",
    "project-order",
    "remote-projects",
}

REQUIRED_THREAD_COLUMNS = {
    "id",
    "cwd",
    "created_at",
    "updated_at",
    "archived",
    "archived_at",
}


class ToolError(RuntimeError):
    code = "E_TOOL"
    exit_code = 1
    retryable = False
    hint = "Inspect the command inputs and retry after fixing the reported problem."


class UsageError(ToolError):
    code = "E_USAGE"
    exit_code = 2
    hint = "Run with --help and provide a valid non-interactive command."


class SchemaError(ToolError):
    code = "E_SCHEMA"
    exit_code = 2
    hint = "Codex local state or app-server response shape changed; no cleanup was applied."


class DependencyError(ToolError):
    code = "E_DEPENDENCY"
    exit_code = 4
    retryable = True
    hint = "Check that Codex and any selected SSH remote are available, then retry."


class TimeoutToolError(ToolError):
    code = "E_TIMEOUT"
    exit_code = 5
    retryable = True
    hint = "Increase --timeout-seconds or retry when Codex app-server is responsive."


@dataclass(frozen=True)
class ThreadRef:
    thread_id: str
    cwd: str
    created_at: int
    updated_at: int
    archived: bool
    host_id: str | None
    status: Any


@dataclass(frozen=True)
class ProjectActivity:
    root: str
    host_id: str | None
    last_updated: int | None
    thread_ids: tuple[str, ...]


@dataclass(frozen=True)
class AppServerTarget:
    host_id: str | None
    command: list[str]
    env: dict[str, str] | None = None

    @property
    def label(self) -> str:
        return self.host_id or "local"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_utc(epoch: int | float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def one_line(value: str, *, max_chars: int = 120) -> str:
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "..."


def emit_plain(payload: dict[str, Any]) -> None:
    if payload["status"] != "ok":
        error = payload["error"] or {}
        print(f"error {error.get('code')}: {error.get('message')}", file=sys.stderr)
        if error.get("hint"):
            print(error["hint"], file=sys.stderr)
        return

    data = payload["data"]
    mode = "apply" if data["applied"] else "dry-run"
    print(
        f"ok mode={mode} activity={data['activity_source']}:{data['activity_timestamp']} "
        f"cutoff={data['cutoff_utc']} "
        f"stale={data['stale_project_count']} pruned_remote={data['pruned_remote_project_count']} "
        f"pruned_saved={data['pruned_saved_root_count']} "
        f"pruned_trusted={data['pruned_trusted_project_count']}"
    )
    for item in data["projects"]:
        if item["decision"] != "stale":
            continue
        print(
            f"stale host={item.get('host_id') or 'local'} last={item.get('last_updated_utc') or 'never'} "
            f"threads={item['thread_count']} root={item['root']} actions={','.join(item['actions'])}"
        )


def finish(
    *,
    status: str,
    started_at: float,
    request_id: str,
    plain: bool,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    exit_code: int,
) -> int:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "status": status,
        "data": data or {},
        "error": error,
        "meta": {
            "request_id": request_id,
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
    def __init__(self, target: AppServerTarget, timeout_seconds: float) -> None:
        self.target = target
        self.timeout_seconds = timeout_seconds
        self.proc: subprocess.Popen[str] | None = None
        self.stdout_queue: queue.Queue[str] = queue.Queue()
        self.stderr_lines: list[str] = []
        self.next_id = 1

    def __enter__(self) -> "AppServerClient":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def start(self) -> None:
        try:
            self.proc = subprocess.Popen(
                self.target.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=self.target.env,
            )
        except OSError as exc:
            raise DependencyError(f"failed to start app-server target {self.target.label}: {exc}") from exc

        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        threading.Thread(target=self._read_stdout, args=(self.proc.stdout,), daemon=True).start()
        threading.Thread(target=self._read_stderr, args=(self.proc.stderr,), daemon=True).start()
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "agents_prune_sidebar_projects",
                    "title": "Agents Codex Sidebar Project Pruner",
                    "version": SCHEMA_VERSION,
                },
                "capabilities": {"experimentalApi": False},
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
            self.stdout_queue.put(line)

    def _read_stderr(self, stream: Any) -> None:
        for line in stream:
            text = line.rstrip("\n")
            if text:
                self.stderr_lines.append(text)
                del self.stderr_lines[:-80]

    def _write(self, message: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise DependencyError(f"app-server target {self.target.label} is not running")
        if self.proc.poll() is not None:
            raise DependencyError(
                f"app-server target {self.target.label} exited with code {self.proc.returncode}"
            )
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        message: dict[str, Any] = {"method": method, "id": request_id}
        if params is not None:
            message["params"] = params
        self._write(message)
        return self._read_response(method, request_id)

    def _read_response(self, method: str, request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stderr_tail = "\n".join(self.stderr_lines[-20:])
                raise TimeoutToolError(
                    f"timed out waiting for {self.target.label} app-server {method}"
                    + (f"; stderr: {one_line(stderr_tail, max_chars=500)}" if stderr_tail else "")
                )
            try:
                line = self.stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutToolError(
                    f"timed out waiting for {self.target.label} app-server {method}"
                ) from exc
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SchemaError(
                    f"{self.target.label} app-server emitted non-JSONL output: {one_line(line)}"
                ) from exc
            if not isinstance(payload, dict):
                raise SchemaError(f"{self.target.label} app-server emitted non-object JSON")

            if payload.get("id") == request_id:
                if "error" in payload:
                    error = payload["error"]
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise DependencyError(f"{self.target.label} app-server {method} failed: {message}")
                result = payload.get("result")
                if result is None:
                    return {}
                if not isinstance(result, dict):
                    raise SchemaError(f"{self.target.label} app-server {method} returned non-object result")
                return result

            if isinstance(payload.get("id"), int) and isinstance(payload.get("method"), str):
                self._write({"id": payload["id"], "result": {"decision": "decline"}})


def require_list(value: Any, key: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"expected {key} to be a list")
    return value


def require_string_list(value: Any, key: str) -> list[str]:
    items = require_list(value, key)
    if any(not isinstance(item, str) for item in items):
        raise SchemaError(f"expected {key} to be a list of strings")
    return list(items)


def read_global_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaError(f"missing Codex global state file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaError(f"Codex global state is not valid JSON: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SchemaError("Codex global state is not a JSON object")

    missing = REQUIRED_GLOBAL_KEYS - set(raw)
    if missing:
        raise SchemaError(f"Codex global state missing key(s): {', '.join(sorted(missing))}")

    require_string_list(raw["active-workspace-roots"], "active-workspace-roots")
    require_string_list(raw["electron-saved-workspace-roots"], "electron-saved-workspace-roots")
    require_string_list(raw["project-order"], "project-order")

    persisted = raw["electron-persisted-atom-state"]
    if not isinstance(persisted, dict):
        raise SchemaError("expected electron-persisted-atom-state to be an object")
    collapsed = persisted.get("sidebar-collapsed-groups")
    if collapsed is not None and not isinstance(collapsed, dict):
        raise SchemaError("expected sidebar-collapsed-groups to be an object when present")

    remote_projects = require_list(raw["remote-projects"], "remote-projects")
    for item in remote_projects:
        validate_remote_project(item)
    return raw


def validate_remote_project(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise SchemaError("expected remote-projects entries to be objects")
    required = ("hostId", "id", "label", "remotePath")
    for key in required:
        if not isinstance(item.get(key), str) or not item.get(key):
            raise SchemaError(f"expected remote-projects entry key {key!r} to be a non-empty string")
    return {key: item[key] for key in required}


def direct_project_root(cwd: str) -> str | None:
    home = str(Path.home())
    github = f"{home}/GitHub"
    if cwd == f"{home}/.agents" or cwd.startswith(f"{home}/.agents/"):
        return f"{home}/.agents"
    if cwd == github:
        return None
    prefix = f"{github}/"
    if cwd.startswith(prefix):
        first = cwd[len(prefix) :].split("/", 1)[0]
        return f"{prefix}{first}" if first else None
    return None


def direct_remote_project_root(cwd: str) -> str | None:
    if "/GitHub/" not in cwd and not cwd.endswith("/.agents") and "/.agents/" not in cwd:
        return None
    marker = "/GitHub/"
    if marker in cwd:
        before, after = cwd.split(marker, 1)
        first = after.split("/", 1)[0]
        return f"{before}{marker}{first}" if first else None
    if cwd.endswith("/.agents"):
        return cwd
    prefix = cwd.split("/.agents/", 1)[0]
    return f"{prefix}/.agents"


def project_root_for_cwd(cwd: str, host_id: str | None) -> str | None:
    if host_id is None:
        return direct_project_root(cwd)
    return direct_remote_project_root(cwd)


def list_threads_for_archived_state(
    client: AppServerClient,
    *,
    archived: bool,
    page_limit: int,
    use_state_db_only: bool,
    activity_timestamp: str,
) -> list[ThreadRef]:
    threads: list[ThreadRef] = []
    cursor: str | None = None
    while True:
        if activity_timestamp == "updated_at":
            sort_key = "updated_at"
        elif activity_timestamp == "created_or_unarchived_updated" and not archived:
            sort_key = "updated_at"
        else:
            sort_key = "created_at"
        params: dict[str, Any] = {
            "archived": archived,
            "cursor": cursor,
            "limit": page_limit,
            "sortKey": sort_key,
            "sortDirection": "desc",
            "useStateDbOnly": use_state_db_only,
        }
        result = client.request("thread/list", params)
        data = result.get("data")
        if not isinstance(data, list):
            raise SchemaError(f"{client.target.label} thread/list returned malformed data")
        for item in data:
            if not isinstance(item, dict):
                raise SchemaError(f"{client.target.label} thread/list returned a non-object thread")
            thread_id = item.get("id")
            cwd = item.get("cwd")
            created_at = item.get("createdAt")
            updated_at = item.get("updatedAt")
            if (
                not isinstance(thread_id, str)
                or not isinstance(cwd, str)
                or not isinstance(created_at, int)
                or not isinstance(updated_at, int)
            ):
                raise SchemaError(
                    f"{client.target.label} thread/list thread missing id/cwd/createdAt/updatedAt with expected types"
                )
            threads.append(
                ThreadRef(
                    thread_id=thread_id,
                    cwd=cwd,
                    created_at=created_at,
                    updated_at=updated_at,
                    archived=archived,
                    host_id=client.target.host_id,
                    status=item.get("status"),
                )
            )
        cursor_value = result.get("nextCursor")
        if cursor_value is None:
            return threads
        if not isinstance(cursor_value, str):
            raise SchemaError(f"{client.target.label} thread/list nextCursor was not a string/null")
        cursor = cursor_value


def list_threads(
    client: AppServerClient,
    *,
    page_limit: int,
    use_state_db_only: bool,
    activity_timestamp: str,
    include_archived_activity: bool,
) -> list[ThreadRef]:
    threads = list_threads_for_archived_state(
        client,
        archived=False,
        page_limit=page_limit,
        use_state_db_only=use_state_db_only,
        activity_timestamp=activity_timestamp,
    )
    if include_archived_activity:
        threads.extend(
            list_threads_for_archived_state(
                client,
                archived=True,
                page_limit=page_limit,
                use_state_db_only=use_state_db_only,
                activity_timestamp=activity_timestamp,
            )
        )
    return threads


def activity_by_root(
    threads: list[ThreadRef],
    *,
    activity_timestamp: str,
) -> dict[tuple[str | None, str], ProjectActivity]:
    ids: dict[tuple[str | None, str], list[str]] = {}
    last: dict[tuple[str | None, str], int] = {}
    for thread in threads:
        root = project_root_for_cwd(thread.cwd, thread.host_id)
        if root is None:
            continue
        key = (thread.host_id, root)
        ids.setdefault(key, [])
        if not thread.archived:
            ids[key].append(thread.thread_id)
        if activity_timestamp == "created_at":
            timestamp = thread.created_at
        elif activity_timestamp == "updated_at":
            timestamp = thread.updated_at
        elif thread.archived:
            timestamp = thread.created_at
        else:
            timestamp = max(thread.created_at, thread.updated_at)
        last[key] = max(last.get(key, 0), timestamp)
    return {
        key: ProjectActivity(
            root=key[1],
            host_id=key[0],
            last_updated=last[key],
            thread_ids=tuple(value),
        )
        for key, value in ids.items()
    }


def selected_remote_host_ids(remote_host_args: list[str]) -> set[str]:
    selected: set[str] = set()
    for raw in remote_host_args:
        host = raw.strip()
        if not host:
            continue
        selected.add(host if host.startswith("remote-ssh-discovered:") else f"remote-ssh-discovered:{host}")
    return selected


def ssh_alias_for_host_id(host_id: str) -> str | None:
    prefix = "remote-ssh-discovered:"
    if not host_id.startswith(prefix):
        return None
    alias = host_id[len(prefix) :]
    return alias or None


def make_local_target(codex_bin: str, codex_home: Path) -> AppServerTarget:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return AppServerTarget(host_id=None, command=[codex_bin, "app-server"], env=env)


def make_remote_target(ssh_bin: str, host_id: str, codex_bin: str) -> AppServerTarget:
    alias = ssh_alias_for_host_id(host_id)
    if alias is None:
        raise UsageError(f"remote host id is not SSH-discovered and cannot be queried safely: {host_id}")
    return AppServerTarget(host_id=host_id, command=[ssh_bin, "-T", alias, f"{codex_bin} app-server"])


def validate_sqlite_schema(conn: sqlite3.Connection, label: str) -> None:
    rows = conn.execute("PRAGMA table_info(threads)").fetchall()
    columns = {str(row[1]) for row in rows}
    missing = REQUIRED_THREAD_COLUMNS - columns
    if missing:
        raise SchemaError(f"{label} Codex thread DB schema missing column(s): {', '.join(sorted(missing))}")


def read_sqlite_threads(
    sqlite_path: Path,
    host_id: str | None,
    *,
    include_archived_activity: bool,
) -> list[ThreadRef]:
    if not sqlite_path.exists():
        raise SchemaError(f"missing Codex thread database: {sqlite_path}")
    label = host_id or "local"
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True, timeout=10)
    try:
        validate_sqlite_schema(conn, label)
        where = "" if include_archived_activity else "WHERE archived = 0"
        rows = conn.execute(
            f"""
            SELECT id, cwd, created_at, updated_at, archived
            FROM threads
            {where}
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    threads: list[ThreadRef] = []
    for thread_id, cwd, created_at, updated_at, archived in rows:
        if (
            not isinstance(thread_id, str)
            or not isinstance(cwd, str)
            or not isinstance(created_at, int)
            or not isinstance(updated_at, int)
            or not isinstance(archived, int)
        ):
            raise SchemaError(f"{label} Codex thread DB returned unexpected id/cwd/created_at/updated_at/archived types")
        threads.append(
            ThreadRef(
                thread_id=thread_id,
                cwd=cwd,
                created_at=created_at,
                updated_at=updated_at,
                archived=bool(archived),
                host_id=host_id,
                status={"type": "unknown"},
            )
        )
    return threads


REMOTE_SQLITE_READER = r"""
import json
import sqlite3
import sys
from pathlib import Path
include_archived = sys.argv[1] == "1"
path = Path.home() / ".codex/state_5.sqlite"
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
try:
    rows = conn.execute("PRAGMA table_info(threads)").fetchall()
    columns = {str(row[1]) for row in rows}
    required = {"id", "cwd", "created_at", "updated_at", "archived", "archived_at"}
    missing = sorted(required - columns)
    if missing:
        print(json.dumps({"status": "error", "code": "schema", "message": ",".join(missing)}))
        raise SystemExit(2)
    where = "" if include_archived else "WHERE archived = 0"
    data = conn.execute(
        f"SELECT id, cwd, created_at, updated_at, archived FROM threads {where} ORDER BY updated_at DESC, id DESC"
    ).fetchall()
finally:
    conn.close()
print(json.dumps({"status": "ok", "data": data}, separators=(",", ":")))
"""


def read_remote_sqlite_threads(
    ssh_bin: str,
    host_id: str,
    *,
    include_archived_activity: bool,
) -> list[ThreadRef]:
    alias = ssh_alias_for_host_id(host_id)
    if alias is None:
        raise UsageError(f"remote host id is not SSH-discovered and cannot be queried safely: {host_id}")
    try:
        proc = subprocess.run(
            [ssh_bin, "-T", alias, "python3 -", "1" if include_archived_activity else "0"],
            check=False,
            text=True,
            input=REMOTE_SQLITE_READER,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutToolError(f"timed out reading remote Codex activity from {host_id}") from exc
    except OSError as exc:
        raise DependencyError(f"failed to read remote Codex activity from {host_id}: {exc}") from exc
    if proc.returncode != 0:
        raise DependencyError(
            f"remote Codex activity read failed for {host_id}: {one_line(proc.stderr or proc.stdout)}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"remote Codex activity read from {host_id} returned non-JSON output") from exc
    if not isinstance(payload, dict) or payload.get("status") != "ok" or not isinstance(payload.get("data"), list):
        raise SchemaError(f"remote Codex activity read from {host_id} returned unexpected shape")
    threads: list[ThreadRef] = []
    for row in payload["data"]:
        if (
            not isinstance(row, list)
            or len(row) != 5
            or not isinstance(row[0], str)
            or not isinstance(row[1], str)
            or not isinstance(row[2], int)
            or not isinstance(row[3], int)
            or not isinstance(row[4], int)
        ):
            raise SchemaError(f"remote Codex activity read from {host_id} returned unexpected row shape")
        threads.append(
            ThreadRef(
                thread_id=row[0],
                cwd=row[1],
                created_at=row[2],
                updated_at=row[3],
                archived=bool(row[4]),
                host_id=host_id,
                status={"type": "unknown"},
            )
        )
    return threads


def load_sqlite_activity(
    codex_home: Path,
    ssh_bin: str,
    remote_host_ids: set[str],
    *,
    activity_timestamp: str,
    include_archived_activity: bool,
) -> dict[tuple[str | None, str], ProjectActivity]:
    threads = read_sqlite_threads(
        codex_home / "state_5.sqlite",
        None,
        include_archived_activity=include_archived_activity,
    )
    for host_id in sorted(remote_host_ids):
        threads.extend(
            read_remote_sqlite_threads(
                ssh_bin,
                host_id,
                include_archived_activity=include_archived_activity,
            )
        )
    return activity_by_root(threads, activity_timestamp=activity_timestamp)


def load_threads_for_targets(
    targets: list[AppServerTarget],
    *,
    timeout_seconds: float,
    page_limit: int,
    use_state_db_only: bool,
    activity_timestamp: str,
    include_archived_activity: bool,
) -> tuple[dict[tuple[str | None, str], ProjectActivity], dict[str | None, AppServerClient]]:
    clients: dict[str | None, AppServerClient] = {}
    all_threads: list[ThreadRef] = []
    try:
        for target in targets:
            client = AppServerClient(target, timeout_seconds)
            client.start()
            clients[target.host_id] = client
            all_threads.extend(
                list_threads(
                    client,
                    page_limit=page_limit,
                    use_state_db_only=use_state_db_only,
                    activity_timestamp=activity_timestamp,
                    include_archived_activity=include_archived_activity,
                )
            )
        return activity_by_root(all_threads, activity_timestamp=activity_timestamp), clients
    except Exception:
        for client in clients.values():
            client.close()
        raise


def write_global_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def backup_state(codex_home: Path, backup_root: Path) -> Path:
    backup_dir = backup_root / time.strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(codex_home / ".codex-global-state.json", backup_dir / ".codex-global-state.json")
    config_path = codex_home / "config.toml"
    if config_path.is_file():
        shutil.copy2(config_path, backup_dir / "config.toml")
    for path in codex_home.glob("state_5.sqlite*"):
        if path.is_file():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def load_slack_webhook(slack_webhook_file: Path) -> str | None:
    try:
        lines = slack_webhook_file.expanduser().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line.startswith("HEALTH_SLACK_WEBHOOK_URL="):
            continue
        _, value = line.split("=", 1)
        return value.strip().strip("'\"") or None
    return None


def send_schema_failure_slack(message: str, *, codex_home: Path, slack_webhook_file: Path) -> None:
    webhook = load_slack_webhook(slack_webhook_file)
    if webhook is None:
        return
    payload = {
        "text": (
            ":warning: Codex sidebar project prune skipped on "
            f"`{os.uname().nodename}` because the Codex state/API schema was not recognized.\n"
            f"Codex home: `{codex_home}`\n"
            f"Reason: `{message}`"
        )
    }
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
    except (OSError, urllib.error.URLError) as exc:
        print(f"warning: failed to send Slack schema alert: {exc}", file=sys.stderr)


def acquire_lock(lock_path: Path) -> Any:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise DependencyError(f"another sidebar prune run already holds {lock_path}") from exc
    lock_file.write(f"{os.getpid()}\n")
    lock_file.flush()
    return lock_file


def is_codex_app_running(app_name: str) -> bool:
    proc = subprocess.run(
        ["pgrep", "-x", app_name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def quit_codex_app(app_name: str, timeout_seconds: float) -> bool:
    was_running = is_codex_app_running(app_name)
    if not was_running:
        return False
    subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to quit'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not is_codex_app_running(app_name):
            return True
        time.sleep(0.5)
    raise TimeoutToolError(f"timed out waiting for {app_name} to quit")


def reopen_codex_app(app_name: str) -> None:
    subprocess.run(
        ["open", "-a", app_name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def close_app_server_clients(clients: dict[str | None, AppServerClient]) -> None:
    for client in clients.values():
        client.close()
    clients.clear()


def project_output(
    *,
    root: str,
    host_id: str | None,
    activity: ProjectActivity | None,
    decision: str,
    reason: str,
    actions: list[str],
) -> dict[str, Any]:
    last_updated = activity.last_updated if activity else None
    return {
        "root": root,
        "host_id": host_id,
        "last_activity": last_updated,
        "last_activity_utc": format_utc(last_updated),
        "last_updated": last_updated,
        "last_updated_utc": format_utc(last_updated),
        "thread_count": len(activity.thread_ids) if activity else 0,
        "decision": decision,
        "reason": reason,
        "actions": actions,
    }


def prune_global_state(
    state: dict[str, Any],
    *,
    stale_local_roots: set[str],
    stale_remote_ids: set[str],
) -> None:
    saved = require_string_list(state["electron-saved-workspace-roots"], "electron-saved-workspace-roots")
    order = require_string_list(state["project-order"], "project-order")
    state["electron-saved-workspace-roots"] = [root for root in saved if root not in stale_local_roots]
    state["project-order"] = [
        value for value in order if value not in stale_local_roots and value not in stale_remote_ids
    ]
    state["remote-projects"] = [
        item for item in state["remote-projects"] if validate_remote_project(item)["id"] not in stale_remote_ids
    ]

    persisted = state["electron-persisted-atom-state"]
    collapsed = persisted.get("sidebar-collapsed-groups")
    if isinstance(collapsed, dict):
        for root in stale_local_roots:
            collapsed.pop(root, None)
        for remote_id in stale_remote_ids:
            collapsed.pop(remote_id, None)


def unescape_toml_basic_string(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value
    return decoded if isinstance(decoded, str) else value


def prune_global_config_project_sections(codex_home: Path, stale_local_roots: set[str]) -> int:
    if not stale_local_roots:
        return 0
    config_path = codex_home / "config.toml"
    if not config_path.is_file():
        return 0

    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    project_re = re.compile(r'^\s*\[projects\."((?:[^"\\]|\\.)*)"\]\s*$')
    any_section_re = re.compile(r"^\s*\[")
    output: list[str] = []
    removed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        match = project_re.match(line.strip())
        if not match:
            output.append(line)
            i += 1
            continue

        root = unescape_toml_basic_string(match.group(1))
        j = i + 1
        while j < len(lines) and not any_section_re.match(lines[j].strip()):
            j += 1

        if root in stale_local_roots:
            removed += 1
        else:
            output.extend(lines[i:j])
        i = j

    if removed:
        config_path.write_text("".join(output), encoding="utf-8")
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prune stale Codex Desktop sidebar projects using app-server for threads and guarded local state edits.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write Codex sidebar state.")
    mode.add_argument("--dry-run", action="store_true", help="Report planned changes only.")
    age = parser.add_mutually_exclusive_group()
    age.add_argument("--older-than-days", type=float, default=DEFAULT_DAYS)
    age.add_argument("--older-than-hours", type=float)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--ssh-bin", default="ssh")
    parser.add_argument(
        "--remote-host",
        action="append",
        default=[],
        help="SSH-discovered remote host to prune remote-projects for, e.g. macmini. Repeatable.",
    )
    parser.add_argument("--keep-root", action="append", default=[], help="Local or remote project root to always keep.")
    parser.add_argument("--allow-active", action="store_true", help="Allow pruning active-workspace-roots.")
    parser.add_argument("--no-unsaved-thread-projects", action="store_true")
    parser.add_argument("--state-db-only", action="store_true")
    parser.add_argument(
        "--activity-timestamp",
        choices=("created_or_unarchived_updated", "created_at", "updated_at"),
        default="created_or_unarchived_updated",
        help=(
            "Timestamp used to decide recent project activity. Default keeps projects with "
            "recently created threads, plus unarchived threads updated recently."
        ),
    )
    parser.add_argument(
        "--activity-source",
        choices=("sqlite", "app-server"),
        default="app-server",
        help="Read thread activity from app-server thread/list or SQLite read-only. Default: app-server.",
    )
    parser.add_argument("--page-limit", type=int, default=DEFAULT_PAGE_LIMIT)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--slack-webhook-file", type=Path, default=Path.home() / ".secrets/slack/env")
    parser.add_argument("--no-slack", action="store_true")
    parser.add_argument("--quit-codex-app", action="store_true", help="Quit the local Codex app before applying.")
    parser.add_argument("--reopen-codex-app", action="store_true", help="Reopen the local Codex app after the run.")
    parser.add_argument("--codex-app-name", default="Codex", help="macOS app name for quit/reopen. Default: Codex.")
    parser.add_argument("--quit-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--no-input", action="store_true", help="Accepted for agent callers; this command never prompts.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON (default).")
    parser.add_argument("--plain", action="store_true", help="Emit compact plain text.")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.older_than_hours is not None:
        older_than_hours = args.older_than_hours
    else:
        older_than_hours = args.older_than_days * 24
    if older_than_hours <= 0:
        raise UsageError("--older-than-days/--older-than-hours must be positive")
    if args.page_limit <= 0:
        raise UsageError("--page-limit must be positive")
    if args.timeout_seconds <= 0:
        raise UsageError("--timeout-seconds must be positive")
    if args.quit_timeout_seconds <= 0:
        raise UsageError("--quit-timeout-seconds must be positive")
    include_archived_activity = True

    codex_home = args.codex_home.expanduser()
    global_state_path = codex_home / ".codex-global-state.json"
    remote_host_ids = selected_remote_host_ids(args.remote_host)
    keep_roots = {str(Path(root).expanduser()) if root.startswith("~") else root for root in args.keep_root}

    codex_app_was_running = False
    if args.apply and args.quit_codex_app:
        codex_app_was_running = quit_codex_app(args.codex_app_name, args.quit_timeout_seconds)

    lock_file = acquire_lock(args.lock.expanduser())
    clients: dict[str | None, AppServerClient] = {}
    try:
        state = read_global_state(global_state_path)
        remote_projects = [validate_remote_project(item) for item in state["remote-projects"]]
        selected_remote_projects = [
            item for item in remote_projects if item["hostId"] in remote_host_ids
        ]

        targets = [make_local_target(args.codex_bin, codex_home)]
        for host_id in sorted({item["hostId"] for item in selected_remote_projects}):
            targets.append(make_remote_target(args.ssh_bin, host_id, args.codex_bin))

        if args.activity_source == "sqlite":
            activity = load_sqlite_activity(
                codex_home,
                args.ssh_bin,
                {item["hostId"] for item in selected_remote_projects},
                activity_timestamp=args.activity_timestamp,
                include_archived_activity=include_archived_activity,
            )
        else:
            activity, clients = load_threads_for_targets(
                targets,
                timeout_seconds=args.timeout_seconds,
                page_limit=args.page_limit,
                use_state_db_only=bool(args.state_db_only),
                activity_timestamp=args.activity_timestamp,
                include_archived_activity=include_archived_activity,
            )

        now = int(time.time())
        cutoff = int(now - older_than_hours * 3600)
        active_roots = set(require_string_list(state["active-workspace-roots"], "active-workspace-roots"))
        saved_roots = set(require_string_list(state["electron-saved-workspace-roots"], "electron-saved-workspace-roots"))
        order_values = set(require_string_list(state["project-order"], "project-order"))

        roots: set[tuple[str | None, str]] = {(None, root) for root in saved_roots}
        roots |= {(None, value) for value in order_values if value.startswith("/")}
        if not args.no_unsaved_thread_projects:
            roots |= set(activity)

        remote_by_key = {(item["hostId"], item["remotePath"]): item for item in selected_remote_projects}
        roots |= set(remote_by_key)

        stale_local_roots: set[str] = set()
        stale_remote_ids: set[str] = set()
        project_items: list[dict[str, Any]] = []

        for host_id, root in sorted(roots, key=lambda item: (item[0] or "", item[1])):
            item_activity = activity.get((host_id, root))
            remote_item = remote_by_key.get((host_id, root))
            is_recent = item_activity is not None and item_activity.last_updated is not None and item_activity.last_updated >= cutoff
            is_active = host_id is None and root in active_roots
            is_kept = root in keep_roots
            actions: list[str] = []

            if is_recent:
                project_items.append(
                    project_output(
                        root=root,
                        host_id=host_id,
                        activity=item_activity,
                        decision="keep",
                        reason="recent",
                        actions=[],
                    )
                )
                continue
            if is_kept:
                project_items.append(
                    project_output(
                        root=root,
                        host_id=host_id,
                        activity=item_activity,
                        decision="keep",
                        reason="keep_root",
                        actions=[],
                    )
                )
                continue
            if is_active and not args.allow_active:
                project_items.append(
                    project_output(
                        root=root,
                        host_id=host_id,
                        activity=item_activity,
                        decision="keep",
                        reason="active_workspace",
                        actions=[],
                    )
                )
                continue

            if host_id is None and root in saved_roots:
                stale_local_roots.add(root)
                actions.append("prune_saved_root")
            if host_id is None and root in order_values:
                stale_local_roots.add(root)
                actions.append("prune_project_order_root")
            if remote_item is not None:
                stale_remote_ids.add(remote_item["id"])
                actions.append("prune_remote_project")
            if not actions:
                actions.append("no_sidebar_state")
            project_items.append(
                project_output(
                    root=root,
                    host_id=host_id,
                    activity=item_activity,
                    decision="stale",
                    reason="older_than_cutoff_or_no_recent_activity",
                    actions=actions,
                )
            )

        backup_dir: str | None = None
        if args.apply:
            close_app_server_clients(clients)
            backup_dir = str(backup_state(codex_home, args.backup_root.expanduser()))
            prune_global_state(
                state,
                stale_local_roots=stale_local_roots,
                stale_remote_ids=stale_remote_ids,
            )
            write_global_state(global_state_path, state)
            pruned_trusted_project_count = prune_global_config_project_sections(codex_home, stale_local_roots)
        else:
            pruned_trusted_project_count = len(stale_local_roots)

        return {
            "applied": bool(args.apply),
            "codex_home": str(codex_home),
            "older_than_hours": older_than_hours,
            "activity_source": args.activity_source,
            "activity_timestamp": args.activity_timestamp,
            "include_archived_activity": include_archived_activity,
            "cutoff_epoch": cutoff,
            "cutoff_utc": format_utc(cutoff),
            "selected_remote_host_ids": sorted(remote_host_ids),
            "stale_project_count": sum(1 for item in project_items if item["decision"] == "stale"),
            "pruned_saved_root_count": len(stale_local_roots),
            "pruned_remote_project_count": len(stale_remote_ids),
            "pruned_trusted_project_count": pruned_trusted_project_count,
            "backup_dir": backup_dir,
            "codex_app_quit": bool(args.apply and args.quit_codex_app),
            "codex_app_was_running": codex_app_was_running,
            "codex_app_reopened": bool(args.apply and args.reopen_codex_app),
            "projects": project_items,
        }
    finally:
        close_app_server_clients(clients)
        lock_file.close()
        if args.apply and args.reopen_codex_app:
            reopen_codex_app(args.codex_app_name)


def main() -> int:
    started_at = time.time()
    request_id = f"{int(started_at)}-{os.getpid()}"
    args = parse_args()
    plain = bool(args.plain and not args.json)
    try:
        data = run(args)
        return finish(
            status="ok",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            data=data,
            error=None,
            exit_code=0,
        )
    except ToolError as exc:
        if isinstance(exc, SchemaError) and not args.no_slack:
            send_schema_failure_slack(
                str(exc),
                codex_home=args.codex_home.expanduser(),
                slack_webhook_file=args.slack_webhook_file,
            )
        return finish(
            status="error",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            error={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "hint": exc.hint,
            },
            exit_code=exc.exit_code,
        )
    except KeyboardInterrupt:
        exc = TimeoutToolError("interrupted")
        return finish(
            status="error",
            started_at=started_at,
            request_id=request_id,
            plain=plain,
            error={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "hint": exc.hint,
            },
            exit_code=exc.exit_code,
        )


if __name__ == "__main__":
    raise SystemExit(main())
