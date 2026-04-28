from __future__ import annotations

import argparse
import os
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Any

from .applescript import applescript_todo_ref, escape_applescript, looks_like_things_id, run_applescript
from .config import (
    JXA_PROBE_TIMEOUT,
    JXA_READ_TIMEOUT,
    READ_BACKENDS,
    READ_BACKEND_ENV,
    THINGS_BUNDLE_ID,
    URL_SCHEME_OPEN_TIMEOUT,
    URL_SCHEME_SETTLE_SECS,
    read_auth_token,
)
from .envelope import command_from_prog, emit_json, emit_text, envelope, error_envelope, error_payload
from .errors import ERROR_EXIT_CODES, ThingsError
from .formatting import project_line, snapshot_text, task_line
from .jxa_backend import (
    jxa_areas,
    jxa_inspect_task,
    jxa_list_tasks,
    jxa_overdue_tasks,
    jxa_projects,
    jxa_search_tasks,
    jxa_snapshot_tasks,
    jxa_tags,
    jxa_view_tasks,
    run_jxa,
)
from .read_backend import read_with_backend, selected_read_backend, should_fallback_from_sqlite
from .sqlite_backend import (
    connect_readonly,
    find_database,
    inspect_task,
    list_areas,
    list_projects,
    list_tags,
    list_tasks,
    overdue_tasks,
    search_tasks,
    snapshot_tasks,
    view_tasks,
)
from .url_scheme import run_url_scheme


class ThingsArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_json(error_envelope(command_from_prog(self.prog), "E_VALIDATION", message, hint=f"Run `{self.prog} --help`."))
        raise SystemExit(ERROR_EXIT_CODES["E_VALIDATION"])


def resolve_task_id(target: str) -> str:
    try:
        result, _backend = inspect_task(target)
    except ThingsError as exc:
        if not should_fallback_from_sqlite(exc):
            raise
        result, _backend = jxa_inspect_task(target, include_completed=False)
    if "task" not in result:
        raise ThingsError("E_VALIDATION", f"target is not a to-do: {target}")
    return str(result["task"]["id"])

def add_format_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Emit JSON envelope (default).")
    group.add_argument("--plain", action="store_true", help="Emit operator-readable text.")
    parser.add_argument("--no-input", action="store_true", help="Accepted for agent non-interactive callers; commands never prompt.")


def add_read_args(parser: argparse.ArgumentParser) -> None:
    add_format_args(parser)
    parser.add_argument("--tag", help="Only return tasks with this exact tag name.")
    parser.add_argument("--verbose", action="store_true", help="Include notes and date fields.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum returned tasks. 0 means no limit.")
    add_backend_arg(parser)


def add_backend_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=READ_BACKENDS,
        default=None,
        help=f"Read backend. Default: ${READ_BACKEND_ENV} or auto. auto prefers read-only SQLite and falls back to JXA.",
    )


def add_view_args(parser: argparse.ArgumentParser) -> None:
    add_format_args(parser)
    parser.add_argument("--verbose", action="store_true", help="Include notes and date fields.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum returned tasks. 0 means no limit.")
    add_backend_arg(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = ThingsArgumentParser(prog="things-client", description="Reusable Things 3 task client.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=ThingsArgumentParser)

    for name, help_text in [
        ("today", "Today view."),
        ("inbox", "Inbox."),
        ("upcoming", "Upcoming view."),
        ("anytime", "Anytime view."),
        ("someday", "Someday view."),
        ("logbook", "Completed/canceled logbook."),
    ]:
        p = sub.add_parser(name, help=help_text)
        add_view_args(p)
        p.set_defaults(handler=cmd_view, view_name=name)

    p = sub.add_parser("snapshot", help="One-call boot snapshot: today + overdue + inbox.")
    p.add_argument("--minimal", action="store_true", help="Return counts plus lightweight task titles.")
    p.add_argument("--limit", type=int, default=0, help="Maximum returned tasks per view. 0 means no limit.")
    add_format_args(p)
    p.add_argument("--verbose", action="store_true", help="Include notes and date fields.")
    add_backend_arg(p)
    p.set_defaults(handler=cmd_snapshot)

    p = sub.add_parser("overdue", help="Tasks with deadline before today.")
    add_view_args(p)
    p.set_defaults(handler=cmd_overdue)

    p = sub.add_parser("list", help="List open Things tasks.")
    add_read_args(p)
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("search", help="Search open Things tasks by title or notes.")
    p.add_argument("query")
    p.add_argument("--include-completed", action="store_true")
    add_read_args(p)
    p.set_defaults(handler=cmd_search)

    p = sub.add_parser("inspect", help="Inspect one task by exact title, ID, or ID prefix.")
    p.add_argument("target")
    p.add_argument("--include-completed", action="store_true")
    add_format_args(p)
    add_backend_arg(p)
    p.set_defaults(handler=cmd_inspect)

    p = sub.add_parser("projects", help="List projects.")
    add_format_args(p)
    add_backend_arg(p)
    p.set_defaults(handler=cmd_projects)

    p = sub.add_parser("areas", help="List areas.")
    add_format_args(p)
    add_backend_arg(p)
    p.set_defaults(handler=cmd_areas)

    p = sub.add_parser("tags", help="List tags.")
    add_format_args(p)
    add_backend_arg(p)
    p.set_defaults(handler=cmd_tags)

    p = sub.add_parser("add", help="Create a task.")
    p.add_argument("title")
    p.add_argument("--when")
    p.add_argument("--deadline")
    p.add_argument("--notes")
    p.add_argument("--tags")
    p.add_argument("--project")
    p.add_argument("--area")
    p.add_argument("--heading")
    p.add_argument("--checklist", help="Comma-separated checklist items.")
    p.add_argument("--resolve", action="store_true", help="Read back the created task when possible.")
    add_format_args(p)
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("project-new", help="Create a project.")
    p.add_argument("title")
    p.add_argument("--area")
    p.add_argument("--notes")
    p.add_argument("--when")
    p.add_argument("--deadline")
    p.add_argument("--resolve", action="store_true", help="Read back the created project when possible.")
    add_format_args(p)
    p.set_defaults(handler=cmd_project_new)

    p = sub.add_parser("area-new", help="Create an area.")
    p.add_argument("title")
    add_format_args(p)
    p.set_defaults(handler=cmd_area_new)

    p = sub.add_parser("edit", help="Update a task via the Things URL scheme.")
    p.add_argument("target")
    p.add_argument("--title")
    p.add_argument("--notes")
    p.add_argument("--append-notes")
    p.add_argument("--when")
    p.add_argument("--deadline")
    p.add_argument("--tags", help="Replace all tags.")
    p.add_argument("--add-tags")
    p.add_argument("--checklist", help="Replace checklist items.")
    p.add_argument("--append-checklist", help="Append checklist items.")
    p.add_argument("--project")
    p.add_argument("--heading")
    add_format_args(p)
    p.set_defaults(handler=cmd_edit)

    p = sub.add_parser("schedule", help="Reschedule a task.")
    p.add_argument("target")
    p.add_argument("--when")
    p.add_argument("--deadline")
    p.add_argument("--clear-deadline", action="store_true")
    add_format_args(p)
    p.set_defaults(handler=cmd_schedule)

    p = sub.add_parser("done", help="Mark a task as completed.")
    p.add_argument("target")
    p.add_argument("--log-now", action="store_true", help="Immediately move completed items to Logbook.")
    add_format_args(p)
    p.set_defaults(handler=cmd_done)

    p = sub.add_parser("cancel", help="Mark a task as canceled.")
    p.add_argument("target")
    add_format_args(p)
    p.set_defaults(handler=cmd_cancel)

    p = sub.add_parser("delete", help="Move a task to Trash.")
    p.add_argument("target")
    p.add_argument("--yes", action="store_true", help="Required safety gate.")
    add_format_args(p)
    p.set_defaults(handler=cmd_delete)

    p = sub.add_parser("show", help="Open Things 3 and navigate to a task/project/area.")
    p.add_argument("target")
    add_format_args(p)
    p.set_defaults(handler=cmd_show)

    p = sub.add_parser("log-completed", help="Immediately log all completed items to Logbook.")
    add_format_args(p)
    p.set_defaults(handler=cmd_log_completed)

    p = sub.add_parser("empty-trash", help="Empty the Things 3 Trash.")
    p.add_argument("--yes", action="store_true", help="Required safety gate.")
    add_format_args(p)
    p.set_defaults(handler=cmd_empty_trash)

    p = sub.add_parser("complete", help="Complete a Things task via the Things URL scheme.")
    p.add_argument("target")
    p.add_argument("--log-now", action="store_true", help="Immediately move completed items to Logbook.")
    add_format_args(p)
    p.set_defaults(handler=cmd_complete)

    p = sub.add_parser("doctor", help="Check Things client dependencies.")
    add_format_args(p)
    p.set_defaults(handler=cmd_doctor)

    return parser


def validate_limit(limit: int) -> None:
    if limit < 0:
        raise ThingsError("E_VALIDATION", "--limit must be >= 0")


def cmd_list(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        validate_limit(args.limit)
        tasks, backend = read_with_backend(
            args,
            sqlite_call=lambda: list_tasks(tag=args.tag, verbose=args.verbose, limit=args.limit),
            jxa_call=lambda: jxa_list_tasks(tag=args.tag, verbose=args.verbose, limit=args.limit),
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.list", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(task_line(task) for task in tasks) if tasks else "(empty)")
    return emit_json(
        envelope(
            "things-client.list",
            "ok",
            data={"count": len(tasks), "tasks": tasks, "tag": args.tag, "verbose": args.verbose, "limit": args.limit, "backend": backend},
            started=started,
        )
    )


def cmd_view(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    view_name = str(args.view_name)
    try:
        validate_limit(args.limit)
        tasks, backend = read_with_backend(
            args,
            sqlite_call=lambda: view_tasks(view_name, verbose=args.verbose, limit=args.limit),
            jxa_call=lambda: jxa_view_tasks(view_name, verbose=args.verbose, limit=args.limit),
        )
    except ThingsError as exc:
        return emit_json(envelope(f"things-client.{view_name}", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(task_line(task) for task in tasks) if tasks else "(empty)")
    return emit_json(
        envelope(
            f"things-client.{view_name}",
            "ok",
            data={"count": len(tasks), "tasks": tasks, "verbose": args.verbose, "limit": args.limit, "backend": backend},
            started=started,
        )
    )


def cmd_snapshot(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        validate_limit(args.limit)
        today_iso = date.today().isoformat()
        views, backend = read_with_backend(
            args,
            sqlite_call=lambda: snapshot_tasks(today_iso=today_iso, verbose=args.verbose, minimal=args.minimal, limit=args.limit),
            jxa_call=lambda: jxa_snapshot_tasks(today_iso, verbose=args.verbose, minimal=args.minimal, limit=args.limit),
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.snapshot", "error", error=error_payload(exc), started=started))
    data = {"views": views, "verbose": args.verbose, "minimal": args.minimal, "limit": args.limit, "backend": backend}
    if args.plain:
        return emit_text(snapshot_text(views))
    return emit_json(envelope("things-client.snapshot", "ok", data=data, started=started))


def cmd_overdue(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        validate_limit(args.limit)
        today_iso = date.today().isoformat()
        tasks, backend = read_with_backend(
            args,
            sqlite_call=lambda: overdue_tasks(today_iso=today_iso, verbose=args.verbose, limit=args.limit),
            jxa_call=lambda: jxa_overdue_tasks(today_iso, verbose=args.verbose, limit=args.limit),
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.overdue", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(task_line(task) for task in tasks) if tasks else "(no overdue tasks)")
    return emit_json(envelope("things-client.overdue", "ok", data={"count": len(tasks), "tasks": tasks, "verbose": args.verbose, "limit": args.limit, "backend": backend}, started=started))


def cmd_search(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        validate_limit(args.limit)
        tasks, backend = read_with_backend(
            args,
            sqlite_call=lambda: search_tasks(
                args.query,
                tag=args.tag,
                include_completed=args.include_completed,
                verbose=args.verbose,
                limit=args.limit,
            ),
            jxa_call=lambda: jxa_search_tasks(
                args.query,
                tag=args.tag,
                include_completed=args.include_completed,
                verbose=args.verbose,
                limit=args.limit,
            ),
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.search", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(task_line(task) for task in tasks) if tasks else "(no matches)")
    return emit_json(
        envelope(
            "things-client.search",
            "ok",
            data={
                "count": len(tasks),
                "tasks": tasks,
                "query": args.query,
                "tag": args.tag,
                "include_completed": args.include_completed,
                "verbose": args.verbose,
                "limit": args.limit,
                "backend": backend,
            },
            started=started,
        )
    )


def cmd_inspect(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        result, backend = read_with_backend(
            args,
            sqlite_call=lambda: inspect_task(args.target, include_completed=args.include_completed),
            jxa_call=lambda: jxa_inspect_task(args.target, include_completed=args.include_completed),
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.inspect", "error", error=error_payload(exc), started=started))
    if args.plain:
        if result.get("type") == "project":
            lines = [project_line(result.get("project", {}))]
            lines.extend(task_line(task) for task in result.get("items", []))
            return emit_text("\n".join(lines))
        return emit_text(task_line(result["task"]))
    return emit_json(envelope("things-client.inspect", "ok", data={"target": args.target, "result": result, "backend": backend}, started=started))


def cmd_projects(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        projects, backend = read_with_backend(args, sqlite_call=list_projects, jxa_call=jxa_projects)
        projects = [project for project in projects if project.get("status") == "open"]
    except ThingsError as exc:
        return emit_json(envelope("things-client.projects", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(project_line(project) for project in projects) if projects else "(no projects)")
    return emit_json(envelope("things-client.projects", "ok", data={"count": len(projects), "projects": projects, "backend": backend}, started=started))


def cmd_areas(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        areas, backend = read_with_backend(args, sqlite_call=list_areas, jxa_call=jxa_areas)
    except ThingsError as exc:
        return emit_json(envelope("things-client.areas", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(area.get("name", "") for area in areas) if areas else "(no areas)")
    return emit_json(envelope("things-client.areas", "ok", data={"count": len(areas), "areas": areas, "backend": backend}, started=started))


def cmd_tags(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        tags, backend = read_with_backend(args, sqlite_call=list_tags, jxa_call=jxa_tags)
    except ThingsError as exc:
        return emit_json(envelope("things-client.tags", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("\n".join(tag.get("name", "") for tag in tags) if tags else "(no tags)")
    return emit_json(envelope("things-client.tags", "ok", data={"count": len(tags), "tags": tags, "backend": backend}, started=started))


def cmd_add(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not args.title.strip():
        exc = ThingsError("E_VALIDATION", "title cannot be empty")
        return emit_json(envelope("things-client.add", "error", error=error_payload(exc), started=started))
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
    except ThingsError as exc:
        return emit_json(envelope("things-client.add", "error", error=error_payload(exc), started=started))
    task_data: dict[str, Any] = {"name": args.title, "resolved": False}
    if args.resolve:
        try:
            time.sleep(0.3)
            matches, _ = search_tasks(args.title, tag=None, include_completed=False, verbose=True, limit=0)
            exact = [task for task in matches if task.get("name") == args.title]
            task_data = (exact[-1] if exact else {"name": args.title}) | {"resolved": bool(exact)}
        except ThingsError:
            task_data = {"name": args.title, "resolved": False}
    if args.plain:
        return emit_text(f"created: {args.title}")
    return emit_json(envelope("things-client.add", "ok", data={"task": task_data, "title": args.title, "resolved": args.resolve and task_data.get("resolved") is True}, started=started))


def cmd_project_new(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not args.title.strip():
        exc = ThingsError("E_VALIDATION", "title cannot be empty")
        return emit_json(envelope("things-client.project-new", "error", error=error_payload(exc), started=started))
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
    except ThingsError as exc:
        return emit_json(envelope("things-client.project-new", "error", error=error_payload(exc), started=started))
    project_data: dict[str, Any] = {"name": args.title, "resolved": False}
    if args.resolve:
        try:
            time.sleep(0.3)
            projects, _ = list_projects()
            matches = [project for project in projects if project.get("name") == args.title]
            project_data = (matches[-1] if matches else {"name": args.title}) | {"resolved": bool(matches)}
        except ThingsError:
            project_data = {"name": args.title, "resolved": False}
    if args.plain:
        return emit_text(f"project created: {args.title}")
    return emit_json(envelope("things-client.project-new", "ok", data={"project": project_data, "title": args.title, "resolved": args.resolve and project_data.get("resolved") is True}, started=started))


def cmd_area_new(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not args.title.strip():
        exc = ThingsError("E_VALIDATION", "title cannot be empty")
        return emit_json(envelope("things-client.area-new", "error", error=error_payload(exc), started=started))
    try:
        area_id = run_applescript(
            f'tell application "Things3" to return id of (make new area with properties {{name:"{escape_applescript(args.title)}"}})'
        )
    except ThingsError as exc:
        return emit_json(envelope("things-client.area-new", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text(f"area created: {args.title} ({area_id})")
    return emit_json(envelope("things-client.area-new", "ok", data={"id": area_id, "title": args.title}, started=started))


def cmd_edit(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    changes = [
        args.title,
        args.notes,
        args.append_notes,
        args.when,
        args.deadline,
        args.tags,
        args.add_tags,
        args.checklist,
        args.append_checklist,
        args.project,
        args.heading,
    ]
    if all(change is None for change in changes):
        exc = ThingsError("E_VALIDATION", "edit requires at least one change flag")
        return emit_json(envelope("things-client.edit", "error", error=error_payload(exc), started=started))
    try:
        token = read_auth_token()
        task_id = resolve_task_id(args.target)
        params: dict[str, str] = {"auth-token": token, "id": task_id}
        if args.title is not None:
            params["title"] = args.title
        if args.notes is not None:
            params["notes"] = args.notes
        if args.append_notes is not None:
            params["append-notes"] = args.append_notes
        if args.when:
            params["when"] = args.when
        if args.deadline:
            params["deadline"] = args.deadline
        if args.tags is not None:
            params["tags"] = args.tags
        if args.add_tags is not None:
            params["add-tags"] = args.add_tags
        if args.checklist is not None:
            params["checklist-items"] = args.checklist.replace(",", "\n")
        if args.append_checklist:
            params["append-checklist-items"] = args.append_checklist.replace(",", "\n")
        if args.project:
            params["list"] = args.project
        if args.heading:
            params["heading"] = args.heading
        run_url_scheme("update", params)
    except ThingsError as exc:
        return emit_json(envelope("things-client.edit", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text(f"edited: {task_id}")
    return emit_json(envelope("things-client.edit", "ok", data={"target": args.target, "id": task_id}, started=started))


def cmd_schedule(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not (args.when or args.deadline or args.clear_deadline):
        exc = ThingsError("E_VALIDATION", "must pass --when, --deadline, or --clear-deadline")
        return emit_json(envelope("things-client.schedule", "error", error=error_payload(exc), started=started))
    try:
        token = read_auth_token()
        task_id = resolve_task_id(args.target)
        params: dict[str, str] = {"auth-token": token, "id": task_id}
        if args.when:
            params["when"] = args.when
        if args.deadline:
            params["deadline"] = args.deadline
        if args.clear_deadline:
            params["deadline"] = ""
        run_url_scheme("update", params)
    except ThingsError as exc:
        return emit_json(envelope("things-client.schedule", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text(f"scheduled: {args.target}")
    return emit_json(envelope("things-client.schedule", "ok", data={"target": args.target, "id": task_id}, started=started))


def cmd_done(args: argparse.Namespace) -> int:
    return complete_task_command(args, command_name="things-client.done")


def cmd_complete(args: argparse.Namespace) -> int:
    return complete_task_command(args, command_name="things-client.complete")


def complete_task_command(args: argparse.Namespace, *, command_name: str) -> int:
    started = time.perf_counter()
    try:
        token = read_auth_token()
        task_id = resolve_task_id(args.target)
        before: dict[str, Any] = {}
        try:
            result, _ = inspect_task(task_id)
            before = result.get("task", {})
        except ThingsError:
            before = {}
        run_url_scheme("update", {"auth-token": token, "id": task_id, "completed": "true"})
        logged = False
        if getattr(args, "log_now", False):
            try:
                run_applescript('tell application "Things3" to log completed now', timeout=5)
                logged = True
            except ThingsError:
                logged = False
    except ThingsError as exc:
        return emit_json(envelope(command_name, "error", error=error_payload(exc), started=started))
    name = before.get("name") or args.target
    if args.plain:
        suffix = " (logged)" if logged else ""
        return emit_text(f"done: {name}{suffix}")
    return emit_json(envelope(command_name, "ok", data={"target": args.target, "id": task_id, "name": name, "status": "completed", "logged": logged}, started=started))


def cmd_cancel(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        token = read_auth_token()
        task_id = resolve_task_id(args.target)
        before: dict[str, Any] = {}
        try:
            result, _ = inspect_task(task_id)
            before = result.get("task", {})
        except ThingsError:
            before = {}
        run_url_scheme("update", {"auth-token": token, "id": task_id, "canceled": "true"})
    except ThingsError as exc:
        return emit_json(envelope("things-client.cancel", "error", error=error_payload(exc), started=started))
    name = before.get("name") or args.target
    if args.plain:
        return emit_text(f"canceled: {name}")
    return emit_json(envelope("things-client.cancel", "ok", data={"target": args.target, "id": task_id, "name": name, "status": "canceled"}, started=started))


def cmd_delete(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not args.yes:
        exc = ThingsError("E_VALIDATION", "delete is destructive; pass --yes to confirm", hint="Deliberate safety gate")
        return emit_json(envelope("things-client.delete", "error", error=error_payload(exc), started=started))
    try:
        task_id = resolve_task_id(args.target)
    except ThingsError:
        task_id = args.target
    ref = f'to do id "{escape_applescript(task_id)}"' if looks_like_things_id(task_id) else applescript_todo_ref(args.target)
    script = f'''tell application "Things3"
    set t to {ref}
    set n to name of t
    delete t
    return n
end tell'''
    try:
        name = run_applescript(script, timeout=5)
    except ThingsError as exc:
        if exc.code == "E_TIMEOUT":
            exc.hint = "Things AppleScript delete is unavailable. Use `things-client cancel <target>` to remove the task from open lists."
        return emit_json(envelope("things-client.delete", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text(f"deleted: {name}")
    return emit_json(envelope("things-client.delete", "ok", data={"target": args.target, "id": task_id, "name": name}, started=started))


def cmd_show(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        try:
            task_id = resolve_task_id(args.target)
            run_url_scheme("show", {"id": task_id})
            shown = f"id: {task_id}"
        except ThingsError:
            run_url_scheme("show", {"query": args.target})
            shown = f"query: {args.target}"
    except ThingsError as exc:
        return emit_json(envelope("things-client.show", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text(f"showing: {shown}")
    return emit_json(envelope("things-client.show", "ok", data={"shown": shown}, started=started))


def cmd_log_completed(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    try:
        run_applescript('tell application "Things3" to log completed now')
    except ThingsError as exc:
        return emit_json(envelope("things-client.log-completed", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("logged all completed items")
    return emit_json(envelope("things-client.log-completed", "ok", data={"action": "log-completed"}, started=started))


def cmd_empty_trash(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    if not args.yes:
        exc = ThingsError("E_VALIDATION", "empty-trash is destructive; pass --yes to confirm", hint="Deliberate safety gate")
        return emit_json(envelope("things-client.empty-trash", "error", error=error_payload(exc), started=started))
    try:
        run_applescript('tell application "Things3" to empty trash')
    except ThingsError as exc:
        return emit_json(envelope("things-client.empty-trash", "error", error=error_payload(exc), started=started))
    if args.plain:
        return emit_text("trash emptied")
    return emit_json(envelope("things-client.empty-trash", "ok", data={"action": "empty-trash"}, started=started))


def cmd_doctor(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    open_ok = shutil_which("open") is not None
    checks.append({"name": "open_command", "ok": open_ok, "detail": shutil_which("open") or "not found"})

    sqlite_ok = False
    sqlite_detail = ""
    try:
        info = find_database()
        conn, _ = connect_readonly()
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        conn.close()
        sqlite_ok = True
        sqlite_detail = str(info.path)
    except ThingsError as exc:
        sqlite_detail = exc.message
    checks.append({"name": "sqlite_read_backend", "ok": sqlite_ok, "detail": sqlite_detail})

    jxa_ok = False
    jxa_detail = ""
    try:
        _ = run_jxa('const things = Application("Things3"); JSON.stringify({count: things.toDos().length});')
        jxa_ok = True
        jxa_detail = "ok"
    except ThingsError as exc:
        jxa_detail = exc.message
    checks.append({"name": "jxa_read_backend", "ok": jxa_ok, "detail": jxa_detail})

    token_ok = False
    token_detail = "not configured"
    try:
        _ = read_auth_token()
        token_ok = True
        token_detail = "configured"
    except ThingsError:
        token_ok = False
    checks.append({"name": "auth_token_configured", "ok": token_ok, "detail": token_detail})

    installed_detail = ""
    installed_ok = False
    running_detail = ""
    running_ok = False
    try:
        running = subprocess.run(["pgrep", "-x", "Things3"], capture_output=True, text=True, timeout=5)
        running_ok = bool(running.stdout.strip())
        running_detail = "running" if running_ok else "not running"
    except Exception as exc:
        running_detail = str(exc)
    checks.append({"name": "things3_running", "ok": running_ok, "detail": running_detail})

    try:
        proc = subprocess.run(["mdfind", f"kMDItemCFBundleIdentifier == '{THINGS_BUNDLE_ID}'"], capture_output=True, text=True, timeout=5)
        installed_detail = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "not found"
        installed_ok = bool(proc.stdout.strip())
    except Exception as exc:
        installed_detail = str(exc)
    if not installed_ok and running_ok:
        installed_ok = True
        installed_detail = running_detail
    checks.append({"name": "things3_installed", "ok": installed_ok, "detail": installed_detail})

    try:
        read_backend = selected_read_backend(None)
    except ThingsError as exc:
        read_backend = "invalid"
        checks.append({"name": "read_backend_config", "ok": False, "detail": exc.message})

    ok = open_ok and (sqlite_ok or jxa_ok) and read_backend != "invalid"
    data = {
        "ok": ok,
        "read_backend": read_backend,
        "timeouts": {
            "jxa_read_seconds": JXA_READ_TIMEOUT,
            "jxa_probe_seconds": JXA_PROBE_TIMEOUT,
            "url_open_seconds": URL_SCHEME_OPEN_TIMEOUT,
            "url_settle_seconds": URL_SCHEME_SETTLE_SECS,
        },
        "checks": checks,
    }
    if args.plain:
        lines = [f"ok: {str(ok).lower()}"]
        lines.extend(f"{check['name']}: {'ok' if check['ok'] else 'fail'} - {check['detail']}" for check in checks)
        return emit_text("\n".join(lines))
    return emit_json(envelope("things-client.doctor", "ok", data=data, started=started))


def shutil_which(command: str) -> str | None:
    for dirname in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(dirname) / command
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
