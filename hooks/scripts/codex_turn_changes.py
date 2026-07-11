"""Read parent and subagent Codex turn file changes from App Server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from hooks.scripts.stop_feedback_turn import AppServerClient, FeedbackTurnError
except ModuleNotFoundError:  # Direct script execution adds this directory to sys.path.
    from stop_feedback_turn import AppServerClient, FeedbackTurnError


MAX_THREAD_LIST_PAGES = 5
THREAD_LIST_PAGE_SIZE = 100
MAX_SAME_SESSION_READS = 48


class CodexTurnChangesError(RuntimeError):
    """Raised when Codex turn attribution cannot be read safely."""


@dataclass(frozen=True)
class CodexTurnChanges:
    """Attributed file changes for one Codex turn and its subagent tree."""

    thread_id: str
    session_id: str
    parent_thread_id: str
    turn_id: str
    turn_started_at: int
    touched_paths: tuple[str, ...]


def collect_codex_turn_changes(
    thread_id: str,
    *,
    timeout_seconds: float = 8.0,
) -> CodexTurnChanges:
    """Return file changes from the latest parent turn and its subagent tree."""
    normalized_thread_id = str(thread_id or "").strip()
    if not normalized_thread_id:
        raise CodexTurnChangesError("Codex Stop payload is missing session_id.")

    try:
        with AppServerClient(timeout_seconds=timeout_seconds) as client:
            owner = _read_thread(client, normalized_thread_id)
            owner_turn = _latest_turn(owner)
            owner_session_id = _text(owner.get("sessionId")) or normalized_thread_id
            turn_started_at = _integer(owner_turn.get("startedAt"))
            touched_paths = set(_file_change_paths(owner_turn))

            listed_threads = _list_threads(
                client,
                min_updated_at=turn_started_at,
            )
            same_session_threads = [
                thread
                for thread in listed_threads
                if _text(thread.get("id")) != normalized_thread_id
                and (_text(thread.get("sessionId")) or _text(thread.get("id")))
                == owner_session_id
                and (
                    _integer(thread.get("updatedAt")) == 0
                    or _integer(thread.get("updatedAt")) >= turn_started_at
                )
            ]
            if len(same_session_threads) > MAX_SAME_SESSION_READS:
                raise CodexTurnChangesError(
                    "Too many same-session Codex threads to attribute safely "
                    f"({len(same_session_threads)})."
                )
            for thread in same_session_threads:
                child_id = _text(thread.get("id"))
                if not child_id:
                    continue
                child = _read_thread(client, child_id)
                touched_paths.update(
                    _file_change_paths_since(child, started_at=turn_started_at)
                )
    except FeedbackTurnError as exc:
        raise CodexTurnChangesError(str(exc)) from exc

    return CodexTurnChanges(
        thread_id=normalized_thread_id,
        session_id=owner_session_id,
        parent_thread_id=_text(owner.get("parentThreadId")),
        turn_id=_text(owner_turn.get("id")),
        turn_started_at=turn_started_at,
        touched_paths=tuple(sorted(touched_paths)),
    )


def _read_thread(client: AppServerClient, thread_id: str) -> dict[str, Any]:
    result = client.request(
        "thread/read",
        {"threadId": thread_id, "includeTurns": True},
    )
    thread = result.get("thread")
    if not isinstance(thread, dict):
        raise CodexTurnChangesError(
            f"thread/read returned no thread for {thread_id}."
        )
    return thread


def _list_threads(
    client: AppServerClient,
    *,
    min_updated_at: int,
) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    for _page in range(MAX_THREAD_LIST_PAGES):
        params: dict[str, Any] = {
            "archived": False,
            "limit": THREAD_LIST_PAGE_SIZE,
            "sortDirection": "desc",
        }
        if cursor:
            params["cursor"] = cursor
        result = client.request("thread/list", params)
        page = result.get("data")
        if not isinstance(page, list):
            raise CodexTurnChangesError("thread/list returned malformed data.")
        page_threads = [item for item in page if isinstance(item, dict)]
        threads.extend(page_threads)
        cursor = _text(result.get("nextCursor")) or None
        if not cursor:
            return threads
        page_updates = [_integer(item.get("updatedAt")) for item in page_threads]
        if page_updates and all(value > 0 for value in page_updates):
            if min(page_updates) < min_updated_at:
                return threads
    if cursor:
        raise CodexTurnChangesError(
            "Codex thread listing exceeded the safety pagination limit."
        )
    return threads


def _latest_turn(thread: dict[str, Any]) -> dict[str, Any]:
    turns = thread.get("turns")
    if not isinstance(turns, list):
        raise CodexTurnChangesError("thread/read did not include turns.")
    candidates = [turn for turn in turns if isinstance(turn, dict)]
    if not candidates:
        raise CodexTurnChangesError("Codex thread has no turn to attribute.")
    return max(
        candidates,
        key=lambda turn: (
            _integer(turn.get("startedAt")),
            _text(turn.get("id")),
        ),
    )


def _file_change_paths_since(
    thread: dict[str, Any],
    *,
    started_at: int,
) -> set[str]:
    turns = thread.get("turns")
    if not isinstance(turns, list):
        return set()
    paths: set[str] = set()
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if _integer(turn.get("startedAt")) < started_at:
            continue
        paths.update(_file_change_paths(turn))
    return paths


def _file_change_paths(turn: dict[str, Any]) -> set[str]:
    items = turn.get("items")
    if not isinstance(items, list):
        return set()
    paths: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "fileChange":
            continue
        if item.get("status") not in {None, "completed"}:
            continue
        changes = item.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            path = _text(change.get("path"))
            if path:
                paths.add(path)
            kind = change.get("kind")
            if isinstance(kind, dict):
                move_path = _text(kind.get("move_path"))
                if move_path:
                    paths.add(move_path)
    return paths


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


__all__ = [
    "CodexTurnChanges",
    "CodexTurnChangesError",
    "collect_codex_turn_changes",
]
