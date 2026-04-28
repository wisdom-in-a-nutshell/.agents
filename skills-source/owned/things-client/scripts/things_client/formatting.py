from __future__ import annotations

from typing import Any

def task_line(task: dict[str, Any]) -> str:
    tags = f" [{task.get('tagNames')}]" if task.get("tagNames") else ""
    project = f" - {task.get('project')}" if task.get("project") else ""
    return f"{task.get('id', '')[:8]}  {task.get('name', '')}{project}{tags}"


def project_line(project: dict[str, Any]) -> str:
    area = f" - {project.get('area')}" if project.get("area") else ""
    return f"{project.get('id', '')[:8]}  {project.get('name', '')}{area}"


def snapshot_text(snapshot: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, title in [("overdue", "Overdue"), ("today", "Today"), ("inbox", "Inbox")]:
        section = snapshot.get(key, {})
        tasks = section.get("tasks", [])
        parts.append(f"{title} ({section.get('count', len(tasks))})")
        parts.append("\n".join(task_line(task) for task in tasks) if tasks else "  (empty)")
    return "\n\n".join(parts)

