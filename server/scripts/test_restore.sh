#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
BACKUP_PATH="${1:-}"
PYTHON="${SDAC_PYTHON:-$APP_DIR/venv/bin/python}"

if [[ -z "$BACKUP_PATH" ]]; then
    BACKUP_PATH="$(find "$APP_DIR/backups" -maxdepth 1 -type f -name 'sdac-*.db' 2>/dev/null | sort | tail -n 1)"
fi

if [[ -z "$BACKUP_PATH" || ! -f "$BACKUP_PATH" ]]; then
    echo "Backup file not found. Pass a backup path or create one first." >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

RESTORE_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "$RESTORE_DIR"
}
trap cleanup EXIT

RESTORE_DB="$RESTORE_DIR/sdac.db"
cp "$BACKUP_PATH" "$RESTORE_DB"

"$PYTHON" "$APP_DIR/scripts/migrate_database.py" --db "$RESTORE_DB"

SDAC_RESTORE_DB="$RESTORE_DB" "$PYTHON" - <<'PY'
import os
import sqlite3

db_path = os.environ["SDAC_RESTORE_DB"]
connection = sqlite3.connect(db_path)
try:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"Integrity check failed: {integrity}")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    required = {"submissions", "admin_audit_log", "schema_version"}
    missing = sorted(required - tables)
    if missing:
        raise SystemExit("Missing required table(s): " + ", ".join(missing))
finally:
    connection.close()
print("Restore test passed.")
PY

echo "Backup tested without modifying production: $BACKUP_PATH"
