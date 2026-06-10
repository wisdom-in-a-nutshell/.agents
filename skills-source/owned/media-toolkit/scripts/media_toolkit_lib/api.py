"""HTTP client for backend media endpoints."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from media_toolkit_lib.errors import CliError

TERMINAL_JOB_STATUSES = {"completed", "failed", "canceled"}
DEFAULT_PROGRESS_HEARTBEAT_SECONDS = 60.0
DEFAULT_API_KEY_FILE = Path.home() / ".secrets/aipodcasting/env"


def _strip_shell_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
        return stripped[1:-1]
    return stripped


def _read_secret_file(path: Path, names: tuple[str, ...]) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError:
        return ""

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        name, separator, value = line.partition("=")
        if separator == "=" and name.strip() in names:
            return _strip_shell_quotes(value)

    return content.strip()


def get_backend_api_key() -> str:
    """Read the WIN backend API key from local secret file or environment."""
    api_key_file = Path(
        os.getenv("AIPODCASTING_WIN_API_KEY_FILE", str(DEFAULT_API_KEY_FILE))
    ).expanduser()
    file_key = _read_secret_file(
        api_key_file,
        ("WIN_API_KEY", "AIP_API_KEY", "WIN_API_KEYS", "AIP_API_KEYS"),
    )
    if file_key:
        return file_key

    for env_var in ("WIN_API_KEY", "AIP_API_KEY"):
        key = os.getenv(env_var, "").strip()
        if key:
            return key

    for env_var in ("WIN_API_KEYS", "AIP_API_KEYS"):
        for key in os.getenv(env_var, "").split(","):
            stripped = key.strip()
            if stripped:
                return stripped

    return ""


class MediaToolkitApiClient:
    """Thin HTTP client for backend media endpoints."""

    def __init__(
        self,
        *,
        api_base_url: str,
        request_timeout_seconds: float,
        poll_interval_seconds: float,
        poll_timeout_seconds: float,
        progress_heartbeat_seconds: float = DEFAULT_PROGRESS_HEARTBEAT_SECONDS,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.progress_heartbeat_seconds = progress_heartbeat_seconds
        self.session = session or requests.Session()

    def submit_job(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", endpoint, json_body=payload)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/jobs/{job_id}")

    def fetch_text(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=self.request_timeout_seconds)
        except requests.Timeout as exc:
            raise CliError(
                code="E_TIMEOUT",
                message=f"Timed out while fetching artifact {url}.",
                exit_code=5,
                retryable=True,
                hint="Retry the command or increase --request-timeout-seconds.",
            ) from exc
        except requests.RequestException as exc:
            raise CliError(
                code="E_NETWORK",
                message=f"Failed to fetch artifact {url}.",
                exit_code=4,
                retryable=True,
                hint="Check network connectivity and artifact URL accessibility.",
            ) from exc

        if response.status_code >= 400:
            raise CliError(
                code="E_API",
                message=f"Artifact fetch failed with HTTP {response.status_code}.",
                exit_code=4 if response.status_code < 500 else 5,
                retryable=response.status_code >= 500,
                hint="Inspect the artifact URL returned by the job.",
                detail={"url": url, "status_code": response.status_code},
            )
        return response.text

    def wait_for_job(
        self,
        job_id: str,
        *,
        progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout_seconds
        started_at = time.monotonic()
        last_status: str | None = None
        last_updated_at: str | None = None
        last_queue_dequeue_count: int | None = None
        last_emit_at = 0.0
        heartbeat_seconds = max(self.progress_heartbeat_seconds, self.poll_interval_seconds)
        while True:
            now = time.monotonic()
            elapsed_seconds = now - started_at
            try:
                job = self.get_job(job_id)
            except CliError as exc:
                if not exc.retryable:
                    raise

                heartbeat_due = now - last_emit_at >= heartbeat_seconds
                if progress_callback is not None and heartbeat_due:
                    progress_callback(
                        {
                            "event": "poll_retry",
                            "job_id": job_id,
                            "status": last_status or "unknown",
                            "elapsed_seconds": elapsed_seconds,
                            "updated_at": last_updated_at,
                            "queue_dequeue_count": last_queue_dequeue_count,
                            "error_code": exc.code,
                        }
                    )
                    last_emit_at = now

                if now >= deadline:
                    raise CliError(
                        code=exc.code,
                        message=f"Timed out while waiting for job {job_id} after repeated poll errors.",
                        exit_code=5,
                        retryable=True,
                        hint="Retry the command or inspect the job directly with status --job-id.",
                        detail={"job_id": job_id, "last_error": exc.detail},
                    ) from exc

                time.sleep(self.poll_interval_seconds)
                continue

            job_status = str(job.get("status", "")).strip().lower()
            if job_status in TERMINAL_JOB_STATUSES:
                if progress_callback is not None:
                    progress_callback(
                        {
                            "event": job_status,
                            "job_id": job_id,
                            "status": job_status,
                            "elapsed_seconds": elapsed_seconds,
                            "updated_at": job.get("updated_at"),
                            "queue_dequeue_count": job.get("queue_dequeue_count"),
                        }
                    )
                if job_status == "completed":
                    return job

                error_payload = job.get("error") or {}
                message = error_payload.get("message") or f"Job {job_id} {job_status}."
                raise CliError(
                    code="E_JOB_FAILED",
                    message=message,
                    exit_code=1,
                    retryable=bool(job.get("should_retry")),
                    hint="Inspect the job payload or job events for failure details.",
                    detail=job,
                )

            updated_at = job.get("updated_at")
            queue_dequeue_count = job.get("queue_dequeue_count")
            state_changed = (
                last_status != job_status
                or last_queue_dequeue_count != queue_dequeue_count
            )
            heartbeat_due = now - last_emit_at >= heartbeat_seconds
            should_emit_progress = state_changed or heartbeat_due
            if progress_callback is not None and should_emit_progress:
                progress_callback(
                    {
                        "event": "wait" if state_changed else "heartbeat",
                        "job_id": job_id,
                        "status": job_status or "unknown",
                        "elapsed_seconds": elapsed_seconds,
                        "updated_at": updated_at,
                        "queue_dequeue_count": queue_dequeue_count,
                    }
                )
                last_emit_at = now
            last_status = job_status
            last_updated_at = updated_at
            last_queue_dequeue_count = queue_dequeue_count

            if time.monotonic() >= deadline:
                raise CliError(
                    code="E_TIMEOUT",
                    message=f"Timed out while waiting for job {job_id}.",
                    exit_code=5,
                    retryable=True,
                    hint="Increase --poll-timeout-seconds or rerun with --no-wait.",
                    detail={"job_id": job_id},
                )

            time.sleep(self.poll_interval_seconds)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base_url}{path}"
        headers: dict[str, str] = {}
        api_key = get_backend_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
                timeout=self.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise CliError(
                code="E_TIMEOUT",
                message=f"Timed out while calling {url}.",
                exit_code=5,
                retryable=True,
                hint="Retry the command or increase --request-timeout-seconds.",
            ) from exc
        except requests.RequestException as exc:
            raise CliError(
                code="E_NETWORK",
                message=f"Failed to reach {url}.",
                exit_code=4,
                retryable=True,
                hint="Check network connectivity and API base URL configuration.",
            ) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if response.status_code >= 400:
            error_hint = "Inspect the server response for more detail."
            error_code = "E_API"
            exit_code = 4
            retryable = response.status_code >= 500

            if response.status_code in {400, 422}:
                error_code = "E_VALIDATION"
                exit_code = 2
                retryable = False
                error_hint = "Fix the request payload and rerun the command."
            elif response.status_code in {401, 403}:
                error_code = "E_AUTH"
                exit_code = 3
                retryable = False
                error_hint = "Check API authentication or access configuration."

            if isinstance(payload, dict):
                message = (
                    payload.get("detail")
                    or payload.get("error")
                    or response.text
                    or f"API request failed with HTTP {response.status_code}."
                )
            else:
                message = (
                    response.text
                    or f"API request failed with HTTP {response.status_code}."
                )

            raise CliError(
                code=error_code,
                message=str(message),
                exit_code=exit_code,
                retryable=retryable,
                hint=error_hint,
                detail=payload,
            )

        if not isinstance(payload, dict):
            raise CliError(
                code="E_API",
                message=f"Expected JSON object response from {url}.",
                exit_code=4,
                retryable=False,
                hint="Check whether the API endpoint returned a valid JSON payload.",
            )
        return payload
