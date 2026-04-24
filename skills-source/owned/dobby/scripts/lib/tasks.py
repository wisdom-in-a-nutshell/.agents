"""Tasks commands for the Dobby CLI — Things 3 via AppleScript + JXA + URL scheme.

Three access methods, each used where it's strongest:

    JXA (JavaScript for Automation)
        Used for: ALL reads (today, inbox, search, projects, areas, tags, overdue)
        Why: only method that returns structured JSON data

    URL scheme (things:///...)
        Used for: creates and updates that need `when`, checklists, or headings
        Why: AppleScript can't set start dates, create checklists, or use
             natural language dates — the URL scheme can
        Auth: `add` needs no token; `update` needs THINGS3_AUTH_TOKEN from
              the environment or this repo's generated .env

    AppleScript
        Used for: status changes (done, cancel), delete, show, log-completed,
                  empty-trash, and simple creates when URL scheme isn't needed
        Why: two-way IPC, returns confirmation, handles operations the URL
             scheme doesn't support (delete, move to Trash)

All three go through `osascript` or `open` — no external binaries, no
reverse-engineered protocol, no schema mismatch.

Agent contract:
    JSON envelope by default for every command; --plain is inspection.
    No interactive commands are exposed; --no-input is accepted and honored.
    Things URL auth token is read from the workspace .env file, not flags/env.

Requirement: Things 3 must be installed on this Mac. It will be launched
automatically if not already running.

Reference docs:
    AppleScript: https://culturedcode.com/things/support/articles/4562654/
    URL scheme:  https://culturedcode.com/things/support/articles/2803573/
    PDF guide:   https://culturedcode.com/things/download/Things3AppleScriptGuide.pdf
    CLI ref:     docs/references/dobby-cli.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import time
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any

from lib import things_read
from lib.contract import Envelope, emit_json, emit_text, log_stderr
from lib.workspace import workspace_root

THINGS3_BUNDLE = "com.culturedcode.ThingsMac"
AUTH_TOKEN_ENV_VAR = "THINGS3_AUTH_TOKEN"
READ_BACKEND_ENV_VAR = "DOBBY_THINGS_READ_BACKEND"
READ_BACKENDS = ("auto", "sqlite", "jxa")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


OSASCRIPT_TIMEOUT = _int_env("DOBBY_THINGS_OSASCRIPT_TIMEOUT_SECS", 15)
JXA_READ_TIMEOUT = _int_env("DOBBY_THINGS_JXA_READ_TIMEOUT_SECS", 5)
JXA_PROBE_TIMEOUT = _int_env("DOBBY_THINGS_JXA_PROBE_TIMEOUT_SECS", 3)
URL_SCHEME_OPEN_TIMEOUT = _int_env("DOBBY_THINGS_OPEN_TIMEOUT_SECS", 10)
URL_SCHEME_SETTLE_SECS = _float_env("DOBBY_THINGS_URL_SETTLE_SECS", 0.5)  # let Things 3 process the URL before reading back

_REPO_ROOT: Path | None = None


def repo_root() -> Path:
    """Return the active Dobby workspace root, resolving lazily.

    Keeping this lazy lets help/argument parsing work even when an agent runs
    the skill script outside the workspace and has not set DOBBY_WORKSPACE.
    """
    global _REPO_ROOT
    if _REPO_ROOT is None:
        _REPO_ROOT = workspace_root()
    return _REPO_ROOT


def repo_env_path() -> Path:
    return repo_root() / ".env"


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def add_subparsers(parent: argparse.ArgumentParser) -> None:
    sub = parent.add_subparsers(dest="tasks_cmd", required=True)

    # --- read commands (JXA) ---
    for name, help_text in [
        ("today", "Today view"),
        ("inbox", "Inbox"),
        ("upcoming", "Upcoming (scheduled for the future)"),
        ("anytime", "Anytime view"),
        ("someday", "Someday view"),
        ("logbook", "Logbook (completed tasks)"),
    ]:
        p = sub.add_parser(name, help=help_text)
        _read_fmt(p)
        p.set_defaults(handler=lambda a, _n=name: cmd_list(a, _n))

    p = sub.add_parser("snapshot", help="One-call boot snapshot: today + overdue + inbox")
    p.add_argument(
        "--minimal",
        action="store_true",
        help="Return only exact counts plus lightweight task titles (intended for session boot hooks)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max tasks returned per view; counts remain exact. 0 means no limit (default)",
    )
    _read_fmt(p)
    p.set_defaults(handler=cmd_snapshot)

    p = sub.add_parser("overdue", help="Tasks with deadline before today")
    _read_fmt(p)
    p.set_defaults(handler=cmd_overdue)

    p = sub.add_parser("search", help="Search tasks by name")
    p.add_argument("query")
    p.add_argument("--include-completed", action="store_true")
    _read_fmt(p)
    p.set_defaults(handler=cmd_search)

    p = sub.add_parser("inspect", help="Inspect a task/project by exact title or ID prefix")
    p.add_argument("target")
    p.add_argument("--include-completed", action="store_true", help="Include completed/canceled project items")
    _read_fmt(p)
    p.set_defaults(handler=cmd_inspect)

    p = sub.add_parser("projects", help="List projects")
    _fmt(p)
    _backend_arg(p)
    p.set_defaults(handler=cmd_projects)

    p = sub.add_parser("areas", help="List areas")
    _fmt(p)
    _backend_arg(p)
    p.set_defaults(handler=cmd_areas)

    p = sub.add_parser("tags", help="List tags")
    _fmt(p)
    _backend_arg(p)
    p.set_defaults(handler=cmd_tags)

    # --- create commands (URL scheme) ---
    p = sub.add_parser(
        "add",
        help="Create a task. Examples:\n"
        "  dobby-tasks add 'Buy milk' --when today\n"
        "  dobby-tasks add 'Plan trip' --when 'next monday' --project 'Travel'\n"
        "  dobby-tasks add 'Pack' --checklist 'Passport,Charger,Clothes'\n",
    )
    p.add_argument("title")
    p.add_argument("--when", help="today | tomorrow | evening | anytime | someday | YYYY-MM-DD | natural language")
    p.add_argument("--deadline", help="Deadline: YYYY-MM-DD")
    p.add_argument("--notes")
    p.add_argument("--tags", help="Comma-separated tag names")
    p.add_argument("--project", help="Project name to add into")
    p.add_argument("--area", help="Area name (used if no --project)")
    p.add_argument("--heading", help="Heading title within the project")
    p.add_argument("--checklist", help="Comma-separated checklist items")
    p.add_argument("--resolve", action="store_true", help="After creating, do a slower read-back to resolve full task data")
    _fmt(p)
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("project-new", help="Create a project")
    p.add_argument("title")
    p.add_argument("--area")
    p.add_argument("--notes")
    p.add_argument("--when", help="today | someday | YYYY-MM-DD")
    p.add_argument("--deadline")
    p.add_argument("--resolve", action="store_true", help="After creating, do a slower read-back to resolve full project data")
    _fmt(p)
    p.set_defaults(handler=cmd_project_new)

    p = sub.add_parser("area-new", help="Create an area")
    p.add_argument("title")
    _fmt(p)
    p.set_defaults(handler=cmd_area_new)

    # --- update commands (URL scheme + auth-token) ---
    p = sub.add_parser("edit", help="Edit a task by name or ID")
    p.add_argument("target")
    p.add_argument("--title")
    p.add_argument("--notes")
    p.add_argument("--append-notes")
    p.add_argument("--when", help="today | evening | someday | YYYY-MM-DD | natural language")
    p.add_argument("--deadline")
    p.add_argument("--tags", help="Replace all tags")
    p.add_argument("--add-tags", help="Add tags without removing existing")
    p.add_argument("--checklist", help="Replace checklist (comma-separated)")
    p.add_argument("--append-checklist", help="Append checklist items")
    p.add_argument("--project", help="Move to project")
    p.add_argument("--heading", help="Move under heading in project")
    _fmt(p)
    p.set_defaults(handler=cmd_edit)

    p = sub.add_parser("schedule", help="Reschedule a task")
    p.add_argument("target")
    p.add_argument("--when", help="today | evening | tomorrow | someday | YYYY-MM-DD | natural language")
    p.add_argument("--deadline")
    p.add_argument("--clear-deadline", action="store_true")
    _fmt(p)
    p.set_defaults(handler=cmd_schedule)

    # --- status + cleanup commands (AppleScript) ---
    p = sub.add_parser("done", help="Mark a task as completed")
    p.add_argument("target")
    p.add_argument("--log-now", action="store_true", help="Immediately move completed items to Logbook")
    _fmt(p)
    p.set_defaults(handler=cmd_done)

    p = sub.add_parser("cancel", help="Mark a task as canceled")
    p.add_argument("target")
    _fmt(p)
    p.set_defaults(handler=cmd_cancel)

    p = sub.add_parser("delete", help="Move a task to Trash")
    p.add_argument("target")
    p.add_argument("--yes", action="store_true", help="Required safety gate")
    _fmt(p)
    p.set_defaults(handler=cmd_delete)

    p = sub.add_parser("show", help="Open Things 3 and navigate to a task/project/area")
    p.add_argument("target")
    _fmt(p)
    p.set_defaults(handler=cmd_show)

    p = sub.add_parser("log-completed", help="Immediately log all completed items to Logbook")
    _fmt(p)
    p.set_defaults(handler=cmd_log_completed)

    p = sub.add_parser("empty-trash", help="Empty the Things 3 Trash")
    p.add_argument("--yes", action="store_true", help="Required safety gate")
    _fmt(p)
    p.set_defaults(handler=cmd_empty_trash)

    p = sub.add_parser("doctor", help="Check Things 3 installation and connectivity")
    _fmt(p)
    p.set_defaults(handler=cmd_doctor)


def _fmt(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="Dobby JSON envelope (default)")
    g.add_argument("--plain", action="store_true", help="Compact plain text")
    p.add_argument("--no-input", action="store_true", help="Fail rather than prompt; Dobby task commands never prompt")


def _read_fmt(p: argparse.ArgumentParser) -> None:
    _fmt(p)
    p.add_argument("--verbose", action="store_true", help="Return full task fields; default is a faster summary shape")
    _backend_arg(p)


def _backend_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--backend",
        choices=READ_BACKENDS,
        default=None,
        help=(
            "Read backend for Things data. Default: env "
            f"{READ_BACKEND_ENV_VAR} or auto. auto prefers read-only SQLite and falls back to JXA."
        ),
    )


# ---------------------------------------------------------------------------
# osascript + URL scheme plumbing
# ---------------------------------------------------------------------------

class Things3Error(RuntimeError):
    pass


def _esc_as(s: str) -> str:
    """Escape for AppleScript double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def run_jxa(script: str, *, timeout: int = OSASCRIPT_TIMEOUT) -> Any:
    """Run JXA, return parsed JSON. Raises Things3Error."""
    try:
        r = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise Things3Error(f"JXA timed out after {timeout}s")
    except FileNotFoundError:
        raise Things3Error("osascript not found")
    if r.returncode != 0:
        msg = r.stderr.strip()
        if "not running" in msg or "Connection is invalid" in msg:
            raise Things3Error("Things 3 is not running. Open it first.")
        raise Things3Error(f"JXA error: {msg}")
    out = r.stdout.strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise Things3Error(f"JXA invalid JSON: {e}")


def run_applescript(script: str, *, timeout: int = OSASCRIPT_TIMEOUT) -> str:
    """Run AppleScript, return stdout string. Raises Things3Error."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise Things3Error(f"AppleScript timed out after {timeout}s")
    except FileNotFoundError:
        raise Things3Error("osascript not found")
    if r.returncode != 0:
        msg = r.stderr.strip()
        if "not running" in msg or "Connection is invalid" in msg:
            raise Things3Error("Things 3 is not running. Open it first.")
        raise Things3Error(f"AppleScript error: {msg}")
    return r.stdout.strip()


def run_url_scheme(command: str, params: dict[str, str]) -> None:
    """Fire a things:/// URL. Async — Things 3 processes it in the background.

    Raises Things3Error if the `open` command fails.
    """
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    url = f"things:///{command}?" + urllib.parse.urlencode(clean, quote_via=urllib.parse.quote)
    try:
        r = subprocess.run(["open", url], capture_output=True, text=True, timeout=URL_SCHEME_OPEN_TIMEOUT)
    except Exception as e:
        raise Things3Error(f"URL scheme failed: {e}")
    if r.returncode != 0:
        raise Things3Error(f"open command failed: {r.stderr.strip()}")
    time.sleep(URL_SCHEME_SETTLE_SECS)


def _parse_env_file_value(path: Path, key: str) -> str | None:
    """Return KEY from a simple shell-style env file without exporting it."""
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        try:
            parts = shlex.split(line, comments=False, posix=True)
        except ValueError:
            parts = [line]
        if not parts:
            continue
        env_key, _, value = parts[0].partition("=")
        if env_key == key:
            return value.strip()
    return None


def read_auth_token() -> str:
    """Read the Things 3 URL scheme auth token from the repo-local .env file."""
    env_path = repo_env_path()
    token = (_parse_env_file_value(env_path, AUTH_TOKEN_ENV_VAR) or "").strip()
    if not token:
        raise Things3Error(
            f"{AUTH_TOKEN_ENV_VAR} not found in {env_path}. "
            "Run scripts/local/secrets/bootstrap_local_env_from_keyvault.sh after mapping "
            "THINGS3_AUTH_TOKEN to the repo's Things 3 auth-token secret."
        )
    return token


# ---------------------------------------------------------------------------
# JXA templates
# ---------------------------------------------------------------------------

_TODO_FIELDS = """
    id: t.id(),
    name: t.name(),
    status: t.status(),
    tagNames: t.tagNames() || "",
    notes: t.notes() || "",
    dueDate: (() => { try { const d = t.dueDate(); return d ? d.toISOString() : null; } catch(e) { return null; } })(),
    creationDate: (() => { try { return t.creationDate().toISOString(); } catch(e) { return null; } })(),
    modificationDate: (() => { try { const d = t.modificationDate(); return d ? d.toISOString() : null; } catch(e) { return null; } })(),
    project: (() => { try { const p = t.project(); return p ? p.name() : null; } catch(e) { return null; } })(),
    area: (() => { try { const a = t.area(); return a ? a.name() : null; } catch(e) { return null; } })(),
"""

_TODO_SUMMARY_FIELDS = """
    id: t.id(),
    name: t.name(),
    status: t.status(),
    tagNames: (() => { try { return t.tagNames() || ""; } catch(e) { return ""; } })(),
    project: (() => { try { const p = t.project(); return p ? p.name() : null; } catch(e) { return null; } })(),
    area: (() => { try { const a = t.area(); return a ? a.name() : null; } catch(e) { return null; } })(),
"""

_TODO_DATED_SUMMARY_FIELDS = """
    id: t.id(),
    name: t.name(),
    status: t.status(),
    tagNames: (() => { try { return t.tagNames() || ""; } catch(e) { return ""; } })(),
    dueDate: (() => { try { const d = t.dueDate(); return d ? d.toISOString() : null; } catch(e) { return null; } })(),
    project: (() => { try { const p = t.project(); return p ? p.name() : null; } catch(e) { return null; } })(),
    area: (() => { try { const a = t.area(); return a ? a.name() : null; } catch(e) { return null; } })(),
"""


def _task_fields(verbose: bool, *, dated: bool = False) -> str:
    if verbose:
        return _TODO_FIELDS
    return _TODO_DATED_SUMMARY_FIELDS if dated else _TODO_SUMMARY_FIELDS


def _jxa_list(name: str, *, verbose: bool = False, open_only: bool = True) -> str:
    """List tasks, filtering active views before serializing task fields."""
    fields = _task_fields(verbose)
    open_guard = 'if (t.status() !== "open") continue;' if open_only else ""
    return f"""
const things = Application("Things3");
const todos = things.lists.byName({json.dumps(name)}).toDos();
const out = [];
for (const t of todos) {{
  {open_guard}
  out.push({{ {fields} }});
}}
JSON.stringify(out);
"""


def _jxa_all(*, verbose: bool = False) -> str:
    return f'const things = Application("Things3");\nconst todos = things.toDos();\nJSON.stringify(todos.map(t => ({{ {_task_fields(verbose)} }})));'


def _jxa_search(query: str, *, include_completed: bool = False, verbose: bool = False) -> str:
    """Search in JXA before serializing task objects.

    This avoids fetching full fields for every task in Python. Project/area and
    other heavier properties are only fetched for tasks whose names match.
    """
    q = json.dumps(query.lower())
    fields = _task_fields(verbose)
    if not include_completed:
        return f"""
const things = Application("Things3");
const q = {q};
const matches = [];

function taskObject(t) {{
  return {{ {fields} }};
}}

for (const t of things.toDos()) {{
  const name = t.name();
  const status = t.status();
  if (status === "open" && name.toLowerCase().includes(q)) {{
    matches.push(taskObject(t));
  }}
}}
JSON.stringify(matches);
"""

    include = "true"
    return f"""
const things = Application("Things3");
const q = {q};
const includeCompleted = {include};
const matches = [];
const seen = {{}};

function taskObject(t) {{
  return {{ {fields} }};
}}

function scan(todos) {{
  for (const t of todos) {{
    const id = t.id();
    if (seen[id]) continue;
    seen[id] = true;
    const name = t.name();
    const status = t.status();
    if (!includeCompleted && status !== "open") continue;
    if (name.toLowerCase().includes(q)) {{
      matches.push(taskObject(t));
    }}
  }}
}}

scan(things.toDos());
if (includeCompleted) {{
  try {{ scan(things.lists.byName("Logbook").toDos()); }} catch(e) {{}}
}}
JSON.stringify(matches);
"""


def _jxa_overdue(today_iso: str, *, verbose: bool = False) -> str:
    fields = _task_fields(verbose, dated=True)
    return f"""
const things = Application("Things3");
const today = {json.dumps(today_iso)};
const todos = things.toDos();
const overdue = [];
for (const t of todos) {{
  const status = t.status();
  if (status !== "open") continue;
  let due = null;
  try {{
    const d = t.dueDate();
    due = d ? d.toISOString() : null;
  }} catch(e) {{}}
  if (due && due.slice(0, 10) < today) {{
    overdue.push({{ {fields} }});
  }}
}}
JSON.stringify(overdue);
"""


def _jxa_snapshot(today_iso: str, *, verbose: bool = False, minimal: bool = False, limit: int = 0) -> str:
    if minimal:
        return f"""
const things = Application("Things3");
const today = {json.dumps(today_iso)};
const limit = {int(limit)};

function shouldCollect(out) {{
  return limit === 0 || out.length < limit;
}}

function openList(name) {{
  const todos = things.lists.byName(name).toDos();
  const out = [];
  let count = 0;
  for (const t of todos) {{
    if (t.status() !== "open") continue;
    count += 1;
    if (shouldCollect(out)) out.push({{name: t.name()}});
  }}
  return {{count: count, tasks: out}};
}}

function overdueList() {{
  const todos = things.toDos();
  const out = [];
  let count = 0;
  for (const t of todos) {{
    if (t.status() !== "open") continue;
    let due = null;
    try {{
      const d = t.dueDate();
      due = d ? d.toISOString() : null;
    }} catch(e) {{}}
    if (due && due.slice(0, 10) < today) {{
      count += 1;
      if (shouldCollect(out)) out.push({{name: t.name(), dueDate: due}});
    }}
  }}
  return {{count: count, tasks: out}};
}}

JSON.stringify({{
  today: openList("Today"),
  overdue: overdueList(),
  inbox: openList("Inbox")
}});
"""

    fields = _task_fields(verbose)
    overdue_fields = _task_fields(verbose, dated=True)
    return f"""
const things = Application("Things3");
const today = {json.dumps(today_iso)};
const limit = {int(limit)};

function shouldCollect(out) {{
  return limit === 0 || out.length < limit;
}}

function taskObject(t) {{
  return {{ {fields} }};
}}

function openList(name) {{
  const todos = things.lists.byName(name).toDos();
  const out = [];
  let count = 0;
  for (const t of todos) {{
    if (t.status() !== "open") continue;
    count += 1;
    if (shouldCollect(out)) out.push(taskObject(t));
  }}
  return {{count: count, tasks: out}};
}}

function overdueList() {{
  const todos = things.toDos();
  const out = [];
  let count = 0;
  for (const t of todos) {{
    if (t.status() !== "open") continue;
    let due = null;
    try {{
      const d = t.dueDate();
      due = d ? d.toISOString() : null;
    }} catch(e) {{}}
    if (due && due.slice(0, 10) < today) {{
      count += 1;
      if (shouldCollect(out)) out.push({{ {overdue_fields} }});
    }}
  }}
  return {{count: count, tasks: out}};
}}

JSON.stringify({{
  today: openList("Today"),
  overdue: overdueList(),
  inbox: openList("Inbox")
}});
"""


def _jxa_projects() -> str:
    return """
const things = Application("Things3");
JSON.stringify(things.projects().map(p => {
    const r = {id: p.id(), name: p.name(), status: p.status()};
    try { r.area = p.area() ? p.area().name() : null; } catch(e) { r.area = null; }
    try { r.notes = p.notes() || ""; } catch(e) { r.notes = ""; }
    try { r.tagNames = p.tagNames() || ""; } catch(e) { r.tagNames = ""; }
    return r;
}));
"""


def _jxa_areas() -> str:
    return 'const things = Application("Things3");\nJSON.stringify(things.areas().map(a => ({id: a.id(), name: a.name(), tagNames: a.tagNames() || ""})));'


def _jxa_tags() -> str:
    return 'const things = Application("Things3");\nJSON.stringify(things.tags().map(t => ({id: t.id(), name: t.name()})));'


# ---------------------------------------------------------------------------
# AppleScript target resolution
# ---------------------------------------------------------------------------

def _as_ref(target: str) -> str:
    """Build an AppleScript to-do reference by name or ID."""
    if re.match(r"^[A-Za-z0-9]{15,}$", target):
        return f'to do id "{_esc_as(target)}"'
    return f'to do named "{_esc_as(target)}"'


def _looks_like_things_id(target: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9]{15,}$", target))


def _resolve_id(target: str) -> str:
    """Resolve a target (name or ID) to a Things 3 task ID."""
    if re.match(r"^[A-Za-z0-9]{15,}$", target):
        return target
    try:
        return things_read.resolve_id(target)
    except things_read.ThingsReadError:
        # Keep AppleScript as a fallback because Things can sometimes know
        # about very recent writes before the SQLite file has settled.
        pass
    # Look up by name via AppleScript (simpler than JXA for single-value returns)
    try:
        return run_applescript(
            f'tell application "Things3" to return id of (to do named "{_esc_as(target)}")'
        )
    except Things3Error:
        raise Things3Error(f"Task not found: {target}")


# ---------------------------------------------------------------------------
# plain-text rendering
# ---------------------------------------------------------------------------

def _task_line(t: dict) -> str:
    name = t.get("name", "")
    proj = t.get("project") or ""
    tags = t.get("tagNames") or ""
    mark = "✓" if t.get("status") == "completed" else " "
    parts = [f"  [{mark}] {name}"]
    if proj:
        parts.append(f" · {proj}")
    if tags:
        parts.append(f" [{tags}]")
    return "".join(parts)


def _proj_line(p: dict) -> str:
    area = p.get("area") or ""
    return f"  {p.get('name','')}" + (f" · {area}" if area else "")


def _snapshot_text(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, title in [("overdue", "Overdue"), ("today", "Today"), ("inbox", "Inbox")]:
        section = snapshot.get(key, {})
        tasks = section.get("tasks", [])
        parts.append(f"{title} ({section.get('count', len(tasks))})")
        parts.append("\n".join(_task_line(t) for t in tasks) if tasks else "  (empty)")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# error classification
# ---------------------------------------------------------------------------

def _err_code(e: Things3Error) -> str:
    m = str(e).lower()
    if "not running" in m or "connection" in m:
        return "E_DEPENDENCY"
    if "invalid" in m and READ_BACKEND_ENV_VAR.lower() in m:
        return "E_VALIDATION"
    if "timed out" in m:
        return "E_TIMEOUT"
    if "not found" in m or "can't get" in m:
        return "E_NOT_FOUND"
    if "auth" in m or "token" in m:
        return "E_AUTH"
    return "E_RUNTIME"


# ---------------------------------------------------------------------------
# read backend abstraction
# ---------------------------------------------------------------------------

def _selected_read_backend(args: argparse.Namespace) -> str:
    raw = (getattr(args, "backend", None) or os.environ.get(READ_BACKEND_ENV_VAR) or "auto").strip().lower()
    if raw not in READ_BACKENDS:
        raise Things3Error(f"invalid {READ_BACKEND_ENV_VAR}: {raw!r}; expected one of {', '.join(READ_BACKENDS)}")
    return raw


def _sqlite_backend_meta(*, fallback_from: str | None = None, fallback_reason: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": "sqlite"}
    if fallback_from:
        meta["fallback_from"] = fallback_from
    if fallback_reason:
        meta["fallback_reason"] = fallback_reason
    return meta


def _jxa_backend_meta(*, fallback_from: str | None = None, fallback_reason: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": "jxa"}
    if fallback_from:
        meta["fallback_from"] = fallback_from
    if fallback_reason:
        meta["fallback_reason"] = fallback_reason
    return meta


def _read_backend(
    args: argparse.Namespace,
    *,
    sqlite_call,
    jxa_script: str,
) -> tuple[Any, dict[str, Any]]:
    """Run a read through the selected backend.

    Default `auto` avoids the fragile Apple automation path for normal reads.
    If the local database is unavailable, it falls back to the old JXA path.
    """
    selected = _selected_read_backend(args)

    if selected in ("auto", "sqlite"):
        try:
            return sqlite_call(), _sqlite_backend_meta()
        except things_read.ThingsReadError as sqlite_error:
            if selected == "sqlite":
                raise Things3Error(str(sqlite_error)) from sqlite_error
            try:
                return run_jxa(jxa_script, timeout=JXA_READ_TIMEOUT), _jxa_backend_meta(
                    fallback_from="sqlite",
                    fallback_reason=str(sqlite_error),
                )
            except Things3Error as jxa_error:
                raise Things3Error(
                    f"SQLite read failed: {sqlite_error}; JXA fallback failed: {jxa_error}"
                ) from jxa_error

    return run_jxa(jxa_script, timeout=JXA_READ_TIMEOUT), _jxa_backend_meta()


# ---------------------------------------------------------------------------
# read commands (SQLite/JXA abstraction)
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace, name: str) -> int:
    env = Envelope(f"tasks.{name}")
    try:
        list_name = name.capitalize() if name != "logbook" else "Logbook"
        tasks, backend = _read_backend(
            args,
            sqlite_call=lambda: things_read.list_view(name, verbose=args.verbose),
            jxa_script=_jxa_list(
                list_name,
                verbose=args.verbose,
                open_only=name != "logbook",
            ),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    # Defensive fallback: active lists are already filtered inside JXA before
    # fields are serialized, but keep this guard for backend quirks.
    if name != "logbook":
        tasks = [t for t in tasks if t.get("status") == "open"]
    if not args.plain:
        return emit_json(env.ok({"count": len(tasks), "tasks": tasks, "verbose": args.verbose, "backend": backend}))
    return emit_text("\n".join(_task_line(t) for t in tasks) if tasks else "(empty)")


def cmd_snapshot(args: argparse.Namespace) -> int:
    env = Envelope("tasks.snapshot")
    if args.limit < 0:
        return emit_json(env.err("E_VALIDATION", "--limit must be >= 0"))
    try:
        today_iso = date.today().isoformat()
        snapshot, backend = _read_backend(
            args,
            sqlite_call=lambda: things_read.snapshot(
                today_iso=today_iso,
                verbose=args.verbose,
                minimal=args.minimal,
                limit=args.limit,
            ),
            jxa_script=_jxa_snapshot(
                today_iso,
                verbose=args.verbose,
                minimal=args.minimal,
                limit=args.limit,
            ),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    payload = {
        "views": snapshot,
        "verbose": args.verbose,
        "minimal": args.minimal,
        "limit": args.limit,
        "backend": backend,
    }
    if not args.plain:
        return emit_json(env.ok(payload))
    return emit_text(_snapshot_text(snapshot))


def cmd_overdue(args: argparse.Namespace) -> int:
    env = Envelope("tasks.overdue")
    try:
        today_iso = date.today().isoformat()
        overdue, backend = _read_backend(
            args,
            sqlite_call=lambda: things_read.overdue(today_iso=today_iso, verbose=args.verbose),
            jxa_script=_jxa_overdue(today_iso, verbose=args.verbose),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"count": len(overdue), "tasks": overdue, "verbose": args.verbose, "backend": backend}))
    return emit_text("\n".join(_task_line(t) for t in overdue) if overdue else "(no overdue tasks)")


def cmd_search(args: argparse.Namespace) -> int:
    env = Envelope("tasks.search")
    try:
        matches, backend = _read_backend(
            args,
            sqlite_call=lambda: things_read.search(
                args.query,
                include_completed=args.include_completed,
                verbose=args.verbose,
            ),
            jxa_script=_jxa_search(
                args.query,
                include_completed=args.include_completed,
                verbose=args.verbose,
            ),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({
            "count": len(matches),
            "tasks": matches,
            "query": args.query,
            "include_completed": args.include_completed,
            "verbose": args.verbose,
            "backend": backend,
        }))
    return emit_text("\n".join(_task_line(t) for t in matches) if matches else "(no matches)")


def cmd_inspect(args: argparse.Namespace) -> int:
    env = Envelope("tasks.inspect")
    try:
        data, backend = _read_backend(
            args,
            sqlite_call=lambda: things_read.inspect(
                args.target,
                include_completed=args.include_completed,
                verbose=args.verbose,
            ),
            jxa_script=_jxa_search(
                args.target,
                include_completed=args.include_completed,
                verbose=True,
            ),
        )
        if backend.get("name") == "jxa":
            # JXA fallback cannot reliably expand project children. Preserve a
            # deterministic inspection shape rather than leaking raw search
            # results as if they were a fully resolved project.
            data = {
                "type": "search-results",
                "target": args.target,
                "count": len(data),
                "items": data,
                "note": "JXA fallback cannot expand project children; retry with SQLite backend available.",
            }
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))

    if not args.plain:
        return emit_json(env.ok({"target": args.target, "result": data, "backend": backend}))

    result_type = data.get("type")
    if result_type == "project":
        project = data.get("project", {})
        lines = [f"Project: {project.get('name', args.target)}", f"Open items ({data.get('count', 0)}):"]
        lines.extend(_task_line(t) for t in data.get("items", []))
        return emit_text("\n".join(lines))
    if result_type in ("to-do", "heading"):
        return emit_text(_task_line(data.get("task", {})))
    return emit_text("\n".join(_task_line(t) for t in data.get("items", [])) if data.get("items") else "(empty)")


def cmd_projects(args: argparse.Namespace) -> int:
    env = Envelope("tasks.projects")
    try:
        projects, backend = _read_backend(
            args,
            sqlite_call=things_read.projects,
            jxa_script=_jxa_projects(),
        )
        projects = [p for p in projects if p.get("status") == "open"]
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"count": len(projects), "projects": projects, "backend": backend}))
    return emit_text("\n".join(_proj_line(p) for p in projects) if projects else "(no projects)")


def cmd_areas(args: argparse.Namespace) -> int:
    env = Envelope("tasks.areas")
    try:
        areas, backend = _read_backend(
            args,
            sqlite_call=things_read.areas,
            jxa_script=_jxa_areas(),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"count": len(areas), "areas": areas, "backend": backend}))
    return emit_text("\n".join(f"  {a.get('name','')}" for a in areas) if areas else "(no areas)")


def cmd_tags(args: argparse.Namespace) -> int:
    env = Envelope("tasks.tags")
    try:
        tags, backend = _read_backend(
            args,
            sqlite_call=things_read.tags,
            jxa_script=_jxa_tags(),
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"count": len(tags), "tags": tags, "backend": backend}))
    return emit_text("\n".join(t.get("name", "") for t in tags) if tags else "(no tags)")


# ---------------------------------------------------------------------------
# create commands (URL scheme)
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> int:
    env = Envelope("tasks.add")
    if not args.title.strip():
        return emit_json(env.err("E_VALIDATION", "title cannot be empty"))

    params: dict[str, str] = {"title": args.title}
    if args.when:
        params["when"] = args.when
    if args.deadline:
        params["deadline"] = args.deadline
    if args.notes:
        params["notes"] = args.notes
    if args.tags:
        params["tags"] = args.tags
    if args.project:
        params["list"] = args.project
    elif args.area:
        params["list"] = args.area
    if args.heading:
        params["heading"] = args.heading
    if args.checklist:
        params["checklist-items"] = args.checklist.replace(",", "\n")

    try:
        run_url_scheme("add", params)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))

    if not args.plain:
        task_data: dict[str, Any] = {"name": args.title, "resolved": False}
        if args.resolve:
            try:
                time.sleep(0.3)  # extra settle time for JSON response
                try:
                    matches = things_read.search(args.title, verbose=True)
                except things_read.ThingsReadError:
                    matches = run_jxa(_jxa_search(args.title, verbose=True), timeout=JXA_READ_TIMEOUT)
                exact = [t for t in matches if t.get("name") == args.title]
                task_data = (exact[-1] if exact else {"name": args.title}) | {"resolved": bool(exact)}
            except Things3Error:
                task_data = {"name": args.title, "resolved": False}
        return emit_json(env.ok({"task": task_data, "title": args.title, "resolved": args.resolve and task_data.get("resolved") is True}))
    return emit_text(f"created: {args.title}")


def cmd_project_new(args: argparse.Namespace) -> int:
    env = Envelope("tasks.project-new")
    if not args.title.strip():
        return emit_json(env.err("E_VALIDATION", "title cannot be empty"))

    params: dict[str, str] = {"title": args.title}
    if args.area:
        params["area"] = args.area
    if args.notes:
        params["notes"] = args.notes
    if args.when:
        params["when"] = args.when
    if args.deadline:
        params["deadline"] = args.deadline

    try:
        run_url_scheme("add-project", params)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))

    if not args.plain:
        proj_data: dict[str, Any] = {"name": args.title, "resolved": False}
        if args.resolve:
            try:
                time.sleep(0.3)
                try:
                    projects = things_read.projects()
                except things_read.ThingsReadError:
                    projects = run_jxa(_jxa_projects(), timeout=JXA_READ_TIMEOUT)
                match = [p for p in projects if p.get("name") == args.title]
                proj_data = (match[-1] if match else {"name": args.title}) | {"resolved": bool(match)}
            except Things3Error:
                proj_data = {"name": args.title, "resolved": False}
        return emit_json(env.ok({"project": proj_data, "title": args.title, "resolved": args.resolve and proj_data.get("resolved") is True}))
    return emit_text(f"project created: {args.title}")


def cmd_area_new(args: argparse.Namespace) -> int:
    """Areas can only be created via AppleScript (no URL scheme for areas)."""
    env = Envelope("tasks.area-new")
    if not args.title.strip():
        return emit_json(env.err("E_VALIDATION", "title cannot be empty"))
    try:
        area_id = run_applescript(
            f'tell application "Things3" to return id of (make new area with properties {{name:"{_esc_as(args.title)}"}})'
        )
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"id": area_id, "title": args.title}))
    return emit_text(f"area created: {args.title} ({area_id})")


# ---------------------------------------------------------------------------
# update commands (URL scheme + auth-token)
# ---------------------------------------------------------------------------

def cmd_edit(args: argparse.Namespace) -> int:
    env = Envelope("tasks.edit")
    changes = [args.title, args.notes, args.append_notes, args.when, args.deadline,
               args.tags, args.add_tags, args.checklist, args.append_checklist,
               args.project, args.heading]
    if all(c is None for c in changes):
        return emit_json(env.err("E_VALIDATION", "edit requires at least one change flag"))

    try:
        token = read_auth_token()
        task_id = _resolve_id(args.target)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))

    params: dict[str, str] = {"auth-token": token, "id": task_id}
    if args.title is not None:
        params["title"] = args.title
    if args.notes is not None:
        params["notes"] = args.notes
    if args.append_notes:
        params["append-notes"] = args.append_notes
    if args.when:
        params["when"] = args.when
    if args.deadline:
        params["deadline"] = args.deadline
    if args.tags is not None:
        params["tags"] = args.tags
    if args.add_tags:
        params["add-tags"] = args.add_tags
    if args.checklist is not None:
        params["checklist-items"] = args.checklist.replace(",", "\n")
    if args.append_checklist:
        params["append-checklist-items"] = args.append_checklist.replace(",", "\n")
    if args.project:
        params["list"] = args.project
    if args.heading:
        params["heading"] = args.heading

    try:
        run_url_scheme("update", params)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"target": args.target, "id": task_id}))
    return emit_text(f"edited: {args.target}")


def cmd_schedule(args: argparse.Namespace) -> int:
    env = Envelope("tasks.schedule")
    if not (args.when or args.deadline or args.clear_deadline):
        return emit_json(env.err("E_VALIDATION", "must pass --when, --deadline, or --clear-deadline"))

    try:
        token = read_auth_token()
        task_id = _resolve_id(args.target)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))

    params: dict[str, str] = {"auth-token": token, "id": task_id}
    if args.when:
        params["when"] = args.when
    if args.deadline:
        params["deadline"] = args.deadline
    if args.clear_deadline:
        params["deadline"] = ""

    try:
        run_url_scheme("update", params)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"target": args.target, "id": task_id}))
    return emit_text(f"scheduled: {args.target}")


# ---------------------------------------------------------------------------
# status + cleanup commands (AppleScript)
# ---------------------------------------------------------------------------

def cmd_done(args: argparse.Namespace) -> int:
    env = Envelope("tasks.done")
    ref = _as_ref(args.target)
    script = f'''tell application "Things3"
    set t to {ref}
    set status of t to completed'''
    if args.log_now:
        script += "\n    log completed now"
    script += '''
    return name of t
end tell'''
    try:
        name = run_applescript(script)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"target": args.target, "name": name, "status": "completed", "logged": bool(args.log_now)}))
    suffix = " (logged)" if args.log_now else ""
    return emit_text(f"done: {name}{suffix}")


def cmd_cancel(args: argparse.Namespace) -> int:
    env = Envelope("tasks.cancel")
    ref = _as_ref(args.target)
    try:
        name = run_applescript(f'''tell application "Things3"
    set t to {ref}
    set status of t to canceled
    return name of t
end tell''')
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"target": args.target, "name": name, "status": "canceled"}))
    return emit_text(f"canceled: {name}")


def cmd_delete(args: argparse.Namespace) -> int:
    env = Envelope("tasks.delete")
    if not args.yes:
        return emit_json(env.err("E_VALIDATION", "delete is destructive; pass --yes to confirm", hint="Deliberate safety gate"))
    ref = _as_ref(args.target)
    script = f'''tell application "Things3"
    set t to {ref}
    set n to name of t
    delete t
    return n
end tell'''
    try:
        name = run_applescript(script)
    except Things3Error as e:
        if not _looks_like_things_id(args.target):
            return emit_json(env.err(_err_code(e), str(e)))
        logbook_ref = f'to do id "{_esc_as(args.target)}" of list "Logbook"'
        logbook_script = f'''tell application "Things3"
    set n to name of ({logbook_ref})
    delete ({logbook_ref})
    return n
end tell'''
        try:
            name = run_applescript(logbook_script)
        except Things3Error:
            return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"target": args.target, "name": name}))
    return emit_text(f"deleted: {name}")


def cmd_show(args: argparse.Namespace) -> int:
    """Open Things 3 and navigate to a task, project, or area."""
    env = Envelope("tasks.show")
    target = _esc_as(args.target)
    # Try task first, then project, then area
    script = f'''tell application "Things3"
    try
        show to do named "{target}"
        return "to-do: {target}"
    on error
        try
            show project "{target}"
            return "project: {target}"
        on error
            try
                show area "{target}"
                return "area: {target}"
            on error
                error "Not found: {target}"
            end try
        end try
    end try
end tell'''
    try:
        result = run_applescript(script)
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"shown": result}))
    return emit_text(f"showing: {result}")


def cmd_log_completed(args: argparse.Namespace) -> int:
    env = Envelope("tasks.log-completed")
    try:
        run_applescript('tell application "Things3" to log completed now')
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"action": "log-completed"}))
    return emit_text("logged all completed items")


def cmd_empty_trash(args: argparse.Namespace) -> int:
    env = Envelope("tasks.empty-trash")
    if not args.yes:
        return emit_json(env.err("E_VALIDATION", "empty-trash is destructive; pass --yes to confirm", hint="Deliberate safety gate"))
    try:
        run_applescript('tell application "Things3" to empty trash')
    except Things3Error as e:
        return emit_json(env.err(_err_code(e), str(e)))
    if not args.plain:
        return emit_json(env.ok({"action": "empty-trash"}))
    return emit_text("trash emptied")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    env = Envelope("tasks.doctor")
    checks: list[dict[str, Any]] = []

    from shutil import which
    osa = which("osascript")
    checks.append({"name": "osascript", "ok": osa is not None, "detail": osa or "not found"})

    things_installed = False
    running_pid = ""
    try:
        running_pid = subprocess.run(["pgrep", "-x", "Things3"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        running_pid = ""
    try:
        r = subprocess.run(["mdfind", f"kMDItemCFBundleIdentifier == '{THINGS3_BUNDLE}'"], capture_output=True, text=True, timeout=5)
        things_installed = bool(r.stdout.strip())
        if things_installed:
            installed_detail = r.stdout.strip().split("\n")[0]
        elif running_pid:
            # Spotlight/mdfind can be unavailable or stale. A running app is
            # sufficient proof for this health check and avoids a false
            # degraded state.
            things_installed = True
            installed_detail = f"running process pid {running_pid.splitlines()[0]}"
        else:
            installed_detail = "not found"
        checks.append({"name": "things3_installed", "ok": things_installed, "detail": installed_detail})
    except Exception as e:
        if running_pid:
            things_installed = True
            checks.append({"name": "things3_installed", "ok": True, "detail": f"running process pid {running_pid.splitlines()[0]}"})
        else:
            checks.append({"name": "things3_installed", "ok": False, "detail": str(e)})

    things_running = False
    things_running = bool(running_pid)
    checks.append({"name": "things3_running", "ok": things_running, "detail": "running" if things_running else "not running"})

    sqlite_ok = False
    sqlite_detail = ""
    try:
        db_info = things_read.find_database()
        # Run a tiny query through the read backend to prove the chosen file is
        # readable and schema-compatible.
        _ = things_read.areas()
        sqlite_ok = True
        sqlite_detail = str(db_info.path)
    except things_read.ThingsReadError as e:
        sqlite_detail = str(e)
    checks.append({"name": "sqlite_read_backend", "ok": sqlite_ok, "detail": sqlite_detail})

    jxa_ok = False
    jxa_detail = "skipped"
    if things_running:
        try:
            result = run_jxa(
                'JSON.stringify({ok: true, app: Application("Things3").name()});',
                timeout=JXA_PROBE_TIMEOUT,
            )
            jxa_ok = isinstance(result, dict) and result.get("ok") is True
            jxa_detail = f"connected to {result.get('app', '?')}" if jxa_ok else f"unexpected: {result}"
        except Things3Error as e:
            jxa_detail = str(e)
    checks.append({"name": "jxa_roundtrip", "ok": jxa_ok, "detail": jxa_detail})

    env_path = repo_env_path()
    token_source = str(env_path)
    token_value = (_parse_env_file_value(env_path, AUTH_TOKEN_ENV_VAR) or "").strip()
    token_ok = bool(token_value)
    checks.append({
        "name": "auth_token_file",
        "ok": token_ok,
        "detail": f"{AUTH_TOKEN_ENV_VAR} present via {token_source}" if token_ok else (
            f"missing: {AUTH_TOKEN_ENV_VAR} in {env_path}"
        ),
    })

    all_ok = all(c["ok"] for c in checks)
    report = {
        "ok": all_ok,
        "checks": checks,
        "timeouts": {
            "osascript_secs": OSASCRIPT_TIMEOUT,
            "jxa_read_secs": JXA_READ_TIMEOUT,
            "jxa_probe_secs": JXA_PROBE_TIMEOUT,
            "url_open_secs": URL_SCHEME_OPEN_TIMEOUT,
            "url_settle_secs": URL_SCHEME_SETTLE_SECS,
        },
        "read_backend": os.environ.get(READ_BACKEND_ENV_VAR, "auto"),
    }

    if not args.plain:
        if all_ok:
            return emit_json(env.ok(report))
        err = env.err("E_DEPENDENCY", "one or more checks failed")
        err["data"] = report
        return emit_json(err)

    lines = []
    for c in checks:
        mark = "✔" if c["ok"] else "✘"
        lines.append(f"{mark}  {c['name']}: {c['detail']}")
    lines.append("")
    lines.append("status: OK" if all_ok else "status: DEGRADED")
    emit_text("\n".join(lines))
    return 0 if all_ok else 4
