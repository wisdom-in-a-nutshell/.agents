#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

DB="$TMP_DIR/things.sqlite"
AUTO_DB="$TMP_DIR/home/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-LIVE/Things Database.thingsdatabase/main.sqlite"
BACKUP_DB="$TMP_DIR/home/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-LIVE.bak-123/Things Database.thingsdatabase/main.sqlite"
export THINGS_CLIENT_SQLITE_PATH="$DB"

python3 - "$DB" <<'PY'
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1])
conn = sqlite3.connect(db)
conn.executescript(
    """
    CREATE TABLE TMTask (
        uuid TEXT PRIMARY KEY,
        title TEXT,
        notes TEXT,
        status INTEGER,
        type INTEGER,
        trashed INTEGER,
        start INTEGER,
        startDate INTEGER,
        deadline INTEGER,
        deadlineSuppressionDate INTEGER,
        creationDate REAL,
        userModificationDate REAL,
        stopDate REAL,
        project TEXT,
        area TEXT,
        heading TEXT,
        "index" INTEGER,
        todayIndex INTEGER
    );
    CREATE TABLE TMTaskTag (tasks TEXT, tags TEXT);
    CREATE TABLE TMTag (uuid TEXT PRIMARY KEY, title TEXT, "index" INTEGER);
    CREATE TABLE TMArea (uuid TEXT PRIMARY KEY, title TEXT);
    CREATE TABLE TMAreaTag (areas TEXT, tags TEXT);
    INSERT INTO TMTag VALUES ('tag-agent', 'agent', 0);
    INSERT INTO TMTag VALUES ('tag-other', 'other', 1);
    INSERT INTO TMArea VALUES ('area-builder', 'Builder');
    INSERT INTO TMTask VALUES (
        'project-builder',
        'Builder Project',
        'Project notes.',
        0, 1, 0, 1, NULL, NULL, NULL, 900, 2100, NULL, NULL, 'area-builder', NULL, 0, 0
    );
    INSERT INTO TMTask VALUES (
        'task-1234567890abcdef',
        'Implement intake',
        'repo:codexclaw\n\nBuild the bridge.',
        0, 0, 0, 1, NULL, NULL, NULL, 1000, 2000, NULL, 'project-builder', NULL, NULL, 1, 1
    );
    INSERT INTO TMTask VALUES (
        'task-ignored',
        'Other task',
        'No repo marker.',
        0, 0, 0, 1, NULL, NULL, NULL, 1000, 1000, NULL, NULL, NULL, NULL, 2, 2
    );
    INSERT INTO TMTask VALUES (
        'task-inbox',
        'Inbox task',
        '',
        0, 0, 0, 0, NULL, NULL, NULL, 1000, 1900, NULL, NULL, NULL, NULL, 3, 3
    );
    INSERT INTO TMTask VALUES (
        'task-overdue',
        'Overdue task',
        '',
        0, 0, 0, 1, NULL, 132780160, NULL, 1000, 1800, NULL, NULL, NULL, NULL, 4, 4
    );
    INSERT INTO TMTaskTag VALUES ('task-1234567890abcdef', 'tag-agent');
    INSERT INTO TMTaskTag VALUES ('task-ignored', 'tag-other');
    """
)
conn.commit()
conn.close()
PY

mkdir -p "$(dirname "$AUTO_DB")" "$(dirname "$BACKUP_DB")"
cp "$DB" "$AUTO_DB"
cp "$DB" "$BACKUP_DB"

list_json="$("$ROOT/scripts/things-client" list --tag agent --verbose)"
python3 - "$list_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
assert payload["command"] == "things-client.list", payload
assert payload["data"]["count"] == 1, payload
task = payload["data"]["tasks"][0]
assert task["name"] == "Implement intake", task
assert "repo:codexclaw" in task["notes"], task
PY

snapshot_json="$("$ROOT/scripts/things-client" snapshot --minimal --limit 2)"
python3 - "$snapshot_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
assert payload["data"]["views"]["inbox"]["count"] == 1, payload
assert payload["data"]["views"]["overdue"]["count"] == 1, payload
assert payload["data"]["backend"]["name"] == "sqlite", payload
PY

projects_json="$("$ROOT/scripts/things-client" projects)"
python3 - "$projects_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
assert payload["data"]["count"] == 1, payload
assert payload["data"]["projects"][0]["name"] == "Builder Project", payload
PY

areas_json="$("$ROOT/scripts/things-client" areas)"
python3 - "$areas_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
assert payload["data"]["count"] == 1, payload
assert payload["data"]["areas"][0]["name"] == "Builder", payload
PY

auto_json="$(env -u THINGS_CLIENT_SQLITE_PATH -u THINGS_SQLITE_PATH HOME="$TMP_DIR/home" "$ROOT/scripts/things-client" list --tag agent --verbose)"
python3 - "$auto_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
backend = payload["data"]["backend"]
assert backend["name"] == "sqlite", backend
assert "ThingsData-LIVE" in backend["path"], backend
assert ".bak" not in backend["path"], backend
PY

inspect_json="$("$ROOT/scripts/things-client" inspect task-1234567890abcdef)"
python3 - "$inspect_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "ok", payload
assert payload["data"]["result"]["task"]["area"] == "Builder", payload
PY

error_json="$("$ROOT/scripts/things-client" list --limit -1 || true)"
python3 - "$error_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["status"] == "error", payload
assert payload["error"]["code"] == "E_VALIDATION", payload
PY

printf 'things-client sqlite tests passed\n'
