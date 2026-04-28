from __future__ import annotations

import os
import shlex
from pathlib import Path

from .errors import ThingsError

AUTH_TOKEN_ENV = "THINGS3_AUTH_TOKEN"
SQLITE_PATH_ENVS = ("THINGS_CLIENT_SQLITE_PATH", "THINGS_SQLITE_PATH")
THINGS_BUNDLE_ID = "com.culturedcode.ThingsMac"
JXA_READ_TIMEOUT = int(os.environ.get("THINGS_CLIENT_JXA_TIMEOUT_SECS", "10"))
JXA_PROBE_TIMEOUT = int(os.environ.get("THINGS_CLIENT_JXA_PROBE_TIMEOUT_SECS", "3"))
URL_SCHEME_OPEN_TIMEOUT = int(os.environ.get("THINGS_CLIENT_OPEN_TIMEOUT_SECS", "10"))
URL_SCHEME_SETTLE_SECS = float(os.environ.get("THINGS_CLIENT_URL_SETTLE_SECS", "0.5"))
READ_BACKEND_ENV = "THINGS_CLIENT_READ_BACKEND"
READ_BACKENDS = ("auto", "sqlite", "jxa")
DEFAULT_DATABASE_GLOBS = (
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-*/Things Database.thingsdatabase/main.sqlite",
    "~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingsdatabase/main.sqlite",
)


def parse_env_file(path: Path, key: str) -> str | None:
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


def token_search_paths() -> list[Path]:
    paths: list[Path] = []
    explicit_env_file = os.environ.get("THINGS_CLIENT_ENV_FILE")
    if explicit_env_file:
        paths.append(Path(explicit_env_file).expanduser())
    workspace = os.environ.get("DOBBY_WORKSPACE")
    if workspace:
        paths.append(Path(workspace).expanduser() / ".env")
    paths.append(Path.cwd() / ".env")
    return paths


def read_auth_token() -> str:
    token = os.environ.get(AUTH_TOKEN_ENV, "").strip()
    if token:
        return token
    for path in token_search_paths():
        token = (parse_env_file(path, AUTH_TOKEN_ENV) or "").strip()
        if token:
            return token
    raise ThingsError(
        "E_AUTH",
        f"{AUTH_TOKEN_ENV} is not configured.",
        hint="Set THINGS3_AUTH_TOKEN, THINGS_CLIENT_ENV_FILE, DOBBY_WORKSPACE, or run from a repo with .env before using write commands.",
    )
