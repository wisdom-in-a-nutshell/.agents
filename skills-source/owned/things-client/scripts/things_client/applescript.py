from __future__ import annotations

import re
import subprocess

from .config import JXA_READ_TIMEOUT
from .errors import ThingsError

def run_applescript(script: str, *, timeout: int = JXA_READ_TIMEOUT) -> str:
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ThingsError("E_TIMEOUT", f"AppleScript timed out after {timeout}s.", retryable=True) from exc
    except FileNotFoundError as exc:
        raise ThingsError("E_DEPENDENCY", "osascript is not available.") from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "not running" in stderr or "Connection is invalid" in stderr:
            raise ThingsError("E_DEPENDENCY", "Things 3 is not running.", hint="Open Things 3 and retry.")
        raise ThingsError("E_RUNTIME", f"AppleScript failed: {stderr}")
    return proc.stdout.strip()


def escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def looks_like_things_id(target: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9]{15,}$", target))


def applescript_todo_ref(target: str) -> str:
    if looks_like_things_id(target):
        return f'to do id "{escape_applescript(target)}"'
    return f'to do named "{escape_applescript(target)}"'


