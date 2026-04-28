from __future__ import annotations

import json
import subprocess
from typing import Any

from .config import JXA_READ_TIMEOUT
from .errors import ThingsError

def run_jxa(script: str) -> Any:
    try:
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=JXA_READ_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ThingsError("E_TIMEOUT", f"JXA timed out after {JXA_READ_TIMEOUT}s.", retryable=True) from exc
    except FileNotFoundError as exc:
        raise ThingsError("E_DEPENDENCY", "osascript is not available.") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "not running" in stderr or "Connection is invalid" in stderr:
            raise ThingsError("E_DEPENDENCY", "Things 3 is not running.", hint="Open Things 3 and retry.")
        raise ThingsError("E_RUNTIME", f"JXA failed: {stderr}")
    stdout = proc.stdout.strip()
    if not stdout:
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ThingsError("E_RUNTIME", f"JXA returned invalid JSON: {exc}") from exc


def jxa_task_fields(*, verbose: bool) -> str:
    base = """
        id: t.id(),
        name: t.name(),
        status: t.status(),
        tagNames: (() => { try { return t.tagNames() || ""; } catch(e) { return ""; } })(),
        project: (() => { try { const p = t.project(); return p ? p.name() : null; } catch(e) { return null; } })(),
        area: (() => { try { const a = t.area(); return a ? a.name() : null; } catch(e) { return null; } })(),
    """
    if not verbose:
        return base
    return base + """
        notes: (() => { try { return t.notes() || ""; } catch(e) { return ""; } })(),
        dueDate: (() => { try { const d = t.dueDate(); return d ? d.toISOString().slice(0, 10) : null; } catch(e) { return null; } })(),
        creationDate: (() => { try { return t.creationDate().toISOString(); } catch(e) { return null; } })(),
        modificationDate: (() => { try { const d = t.modificationDate(); return d ? d.toISOString() : null; } catch(e) { return null; } })(),
    """


def jxa_list_tasks(*, tag: str | None, verbose: bool, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tag_json = json.dumps((tag or "").lower())
    script = f"""
const things = Application("Things3");
const tag = {tag_json};
const limit = {int(limit)};
const out = [];
function hasTag(t) {{
  if (!tag) return true;
  let names = "";
  try {{ names = t.tagNames() || ""; }} catch(e) {{ names = ""; }}
  return names.split(",").map(s => s.trim().toLowerCase()).includes(tag);
}}
for (const t of things.toDos()) {{
  if (t.status() !== "open") continue;
  if (!hasTag(t)) continue;
  out.push({{ {jxa_task_fields(verbose=verbose)} }});
  if (limit > 0 && out.length >= limit) break;
}}
JSON.stringify(out);
"""
    return run_jxa(script), {"name": "jxa"}


def jxa_search_tasks(query: str, *, tag: str | None, include_completed: bool, verbose: bool, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query_json = json.dumps(query.lower())
    tag_json = json.dumps((tag or "").lower())
    include_json = "true" if include_completed else "false"
    script = f"""
const things = Application("Things3");
const query = {query_json};
const tag = {tag_json};
const includeCompleted = {include_json};
const limit = {int(limit)};
const out = [];
function hasTag(t) {{
  if (!tag) return true;
  let names = "";
  try {{ names = t.tagNames() || ""; }} catch(e) {{ names = ""; }}
  return names.split(",").map(s => s.trim().toLowerCase()).includes(tag);
}}
function matches(t) {{
  let notes = "";
  try {{ notes = t.notes() || ""; }} catch(e) {{ notes = ""; }}
  return t.name().toLowerCase().includes(query) || notes.toLowerCase().includes(query);
}}
function scan(todos) {{
  for (const t of todos) {{
    if (!includeCompleted && t.status() !== "open") continue;
    if (!hasTag(t) || !matches(t)) continue;
    out.push({{ {jxa_task_fields(verbose=verbose)} }});
    if (limit > 0 && out.length >= limit) return;
  }}
}}
scan(things.toDos());
if (includeCompleted && (limit === 0 || out.length < limit)) {{
  try {{ scan(things.lists.byName("Logbook").toDos()); }} catch(e) {{}}
}}
JSON.stringify(out);
"""
    return run_jxa(script), {"name": "jxa"}


def jxa_inspect_task(target: str, *, include_completed: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    target_json = json.dumps(target)
    include_json = "true" if include_completed else "false"
    script = f"""
const things = Application("Things3");
const target = {target_json};
const includeCompleted = {include_json};
const matches = [];
function scan(todos) {{
  for (const t of todos) {{
    if (!includeCompleted && t.status() !== "open") continue;
    const id = t.id();
    const name = t.name();
    if (id === target || id.startsWith(target) || name === target) {{
      matches.push({{ {jxa_task_fields(verbose=True)} }});
    }}
  }}
}}
scan(things.toDos());
if (includeCompleted) {{
  try {{ scan(things.lists.byName("Logbook").toDos()); }} catch(e) {{}}
}}
JSON.stringify(matches);
"""
    matches = run_jxa(script)
    if not matches:
        raise ThingsError("E_NOT_FOUND", f"not found: {target}")
    if len(matches) > 1 and not (matches[0].get("id") == target or matches[0].get("name") == target):
        raise ThingsError("E_VALIDATION", f"ambiguous target prefix: {target}")
    return {"type": "to-do", "task": matches[0]}, {"name": "jxa"}


def jxa_view_tasks(name: str, *, verbose: bool, limit: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    list_name = "Logbook" if name == "logbook" else name.capitalize()
    open_guard = "" if name == "logbook" else 'if (t.status() !== "open") continue;'
    script = f"""
const things = Application("Things3");
const limit = {int(limit)};
const out = [];
for (const t of things.lists.byName({json.dumps(list_name)}).toDos()) {{
  {open_guard}
  out.push({{ {jxa_task_fields(verbose=verbose)} }});
  if (limit > 0 && out.length >= limit) break;
}}
JSON.stringify(out);
"""
    return run_jxa(script), {"name": "jxa"}


def jxa_overdue_tasks(today_iso: str, *, verbose: bool, limit: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    script = f"""
const things = Application("Things3");
const today = {json.dumps(today_iso)};
const limit = {int(limit)};
const out = [];
for (const t of things.toDos()) {{
  if (t.status() !== "open") continue;
  let due = null;
  try {{
    const d = t.dueDate();
    due = d ? d.toISOString().slice(0, 10) : null;
  }} catch(e) {{}}
  if (due && due < today) {{
    out.push({{ {jxa_task_fields(verbose=verbose)} }});
    if (limit > 0 && out.length >= limit) break;
  }}
}}
JSON.stringify(out);
"""
    return run_jxa(script), {"name": "jxa"}


def jxa_snapshot_tasks(today_iso: str, *, verbose: bool, minimal: bool, limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
    today, _ = jxa_view_tasks("today", verbose=verbose, limit=0)
    overdue, _ = jxa_overdue_tasks(today_iso, verbose=True if minimal else verbose, limit=0)
    inbox, backend = jxa_view_tasks("inbox", verbose=verbose, limit=0)
    views = {"today": today, "overdue": overdue, "inbox": inbox}
    out: dict[str, Any] = {}
    for name, tasks in views.items():
        selected = tasks[:limit] if limit else tasks
        if minimal:
            if name == "overdue":
                selected = [{"name": task.get("name", ""), "dueDate": task.get("dueDate")} for task in selected]
            else:
                selected = [{"name": task.get("name", "")} for task in selected]
        out[name] = {"count": len(tasks), "tasks": selected}
    return out, backend


def jxa_projects() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    script = """
const things = Application("Things3");
JSON.stringify(things.projects().map(p => {
  const r = {id: p.id(), name: p.name(), status: p.status()};
  try { r.area = p.area() ? p.area().name() : null; } catch(e) { r.area = null; }
  try { r.notes = p.notes() || ""; } catch(e) { r.notes = ""; }
  try { r.tagNames = p.tagNames() || ""; } catch(e) { r.tagNames = ""; }
  return r;
}));
"""
    return run_jxa(script), {"name": "jxa"}


def jxa_areas() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    script = 'const things = Application("Things3");\nJSON.stringify(things.areas().map(a => ({id: a.id(), name: a.name(), tagNames: a.tagNames() || ""})));'
    return run_jxa(script), {"name": "jxa"}


def jxa_tags() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    script = 'const things = Application("Things3");\nJSON.stringify(things.tags().map(t => ({id: t.id(), name: t.name()})));'
    return run_jxa(script), {"name": "jxa"}
