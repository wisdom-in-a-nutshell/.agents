from __future__ import annotations

import subprocess
import time
import urllib.parse

from .config import URL_SCHEME_OPEN_TIMEOUT, URL_SCHEME_SETTLE_SECS
from .errors import ThingsError

def run_url_scheme(command: str, params: dict[str, str]) -> None:
    clean = {key: value for key, value in params.items() if value is not None}
    url = f"things:///{command}?" + urllib.parse.urlencode(clean, quote_via=urllib.parse.quote)
    try:
        proc = subprocess.run(["open", url], capture_output=True, text=True, timeout=URL_SCHEME_OPEN_TIMEOUT, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ThingsError("E_TIMEOUT", "Things URL scheme timed out.", retryable=True) from exc
    except FileNotFoundError as exc:
        raise ThingsError("E_DEPENDENCY", "`open` command is not available.") from exc
    if proc.returncode != 0:
        raise ThingsError("E_RUNTIME", f"Things URL scheme failed: {proc.stderr.strip()}")
    time.sleep(URL_SCHEME_SETTLE_SECS)

