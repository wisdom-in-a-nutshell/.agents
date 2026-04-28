#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THINGS="$ROOT/scripts/things-client"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

python3 -m compileall -q "$ROOT/scripts/things_client" "$THINGS"

"$THINGS" --help >/dev/null
"$THINGS" list --help >/dev/null
"$THINGS" doctor --help >/dev/null
THINGS_CLIENT_JXA_TIMEOUT_SECS=bad THINGS_CLIENT_URL_SETTLE_SECS=bad "$THINGS" doctor >/dev/null

python3 - <<'PY'
import os
import tempfile
from pathlib import Path

from things_client.config import read_auth_token, token_search_paths

old_env = dict(os.environ)
try:
    os.environ.clear()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        explicit = root / "explicit.env"
        workspace = root / "workspace"
        cwd = root / "cwd"
        workspace.mkdir()
        cwd.mkdir()

        os.environ["THINGS_CLIENT_ENV_FILE"] = str(explicit)
        os.environ["DOBBY_WORKSPACE"] = str(workspace)
        os.environ["THINGS3_AUTH_TOKEN"] = "ignored-direct-env-secret"
        os.chdir(cwd)

        paths = token_search_paths()
        resolved_paths = [path.resolve() for path in paths]
        assert resolved_paths == [explicit.resolve(), (workspace / ".env").resolve(), (cwd / ".env").resolve()], paths
        assert all("GitHub/adi" not in str(path) for path in paths), paths

        try:
            read_auth_token()
        except Exception as exc:
            assert getattr(exc, "code", None) == "E_AUTH", exc
        else:
            raise AssertionError("direct THINGS3_AUTH_TOKEN env secret should not be accepted")

        explicit.write_text("THINGS3_AUTH_TOKEN=file-secret\n", encoding="utf-8")
        assert read_auth_token() == "file-secret"
finally:
    os.environ.clear()
    os.environ.update(old_env)
PY

if find "$ROOT" -type f \
    ! -path "$ROOT/tests/contract.sh" \
    ! -path '*/__pycache__/*' \
    -exec grep -H "THINGS3_ENV_FILE\\|/Users/dobby/GitHub/adi/.env" {} + >/dev/null; then
    echo "unexpected legacy token fallback in things-client skill" >&2
    exit 1
fi

printf 'things-client contract tests passed\n'
