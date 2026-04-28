# Things Client Architecture

`scripts/things-client` is a stable executable wrapper. It imports the Python
package in `scripts/things_client/`.

## Modules

- `cli.py` / `commands.py` — argparse surface and command handlers.
- `envelope.py` / `errors.py` — stable JSON envelope and error contract.
- `config.py` — environment variables, timeouts, token lookup.
- `sqlite_backend.py` — read-only SQLite discovery and queries.
- `jxa_backend.py` — bounded JXA fallback reads.
- `url_scheme.py` — Things URL-scheme writes.
- `applescript.py` — operations not exposed by the URL scheme.
- `formatting.py` — `--plain` output helpers.

## Tests

- `tests/contract.sh` checks imports, wrapper help, and token path policy.
- `tests/sqlite.sh` builds a temporary SQLite fixture and verifies read behavior.
- `tests/live.sh` is opt-in and performs real Things 3 writes before cleanup.
