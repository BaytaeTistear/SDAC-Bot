#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
REMOTE="${1:-${SDAC_RCLONE_REMOTE:-}}"
ENV_FILE="${SDAC_ENV_FILE:-/etc/sdac-bot/sdac.env}"
BACKUP_ROOT="${SDAC_BACKUP_ROOT:-$APP_DIR/backups/offsite}"
INCLUDE_ENV="${SDAC_BACKUP_INCLUDE_ENV:-0}"
RETENTION_DAYS="${SDAC_LOCAL_BACKUP_RETENTION_DAYS:-0}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="$BACKUP_ROOT/$STAMP"
PYTHON="$APP_DIR/venv/bin/python"

if [[ -z "$REMOTE" ]]; then
    echo "Set SDAC_RCLONE_REMOTE or pass a remote destination." >&2
    echo "Example: SDAC_RCLONE_REMOTE=remote:sdac bash scripts/backup_offsite.sh" >&2
    exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is required for off-server backups." >&2
    echo "Install it with: sudo apt install rclone" >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

mkdir -p "$RUN_DIR"

if [[ -f "$APP_DIR/sdac.db" ]]; then
    echo "Creating SQLite backup."
    SDAC_DB_FILE="$APP_DIR/sdac.db" \
    SDAC_DB_BACKUP="$RUN_DIR/sdac.db" \
    "$PYTHON" - <<'PY'
import os
import sqlite3

source_path = os.environ["SDAC_DB_FILE"]
backup_path = os.environ["SDAC_DB_BACKUP"]
source = sqlite3.connect(source_path)
destination = sqlite3.connect(backup_path)
try:
    with destination:
        source.backup(destination)
finally:
    destination.close()
    source.close()
print(f"Database backup created: {backup_path}")
PY
else
    echo "No sdac.db found; skipping database backup."
fi

if [[ -f "$APP_DIR/config.json" ]]; then
    cp -a "$APP_DIR/config.json" "$RUN_DIR/config.json"
fi

if [[ -d "$APP_DIR/media" ]]; then
    tar -czf "$RUN_DIR/media.tar.gz" -C "$APP_DIR" media
fi

if [[ "$INCLUDE_ENV" == "1" ]]; then
    if [[ -f "$ENV_FILE" ]]; then
        sudo cp "$ENV_FILE" "$RUN_DIR/sdac.env"
        sudo chown "$(id -u):$(id -g)" "$RUN_DIR/sdac.env"
        chmod 600 "$RUN_DIR/sdac.env"
    else
        echo "Environment file not found; skipping env backup: $ENV_FILE" >&2
    fi
fi

(
    cd "$RUN_DIR"
    find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

rclone copy "$RUN_DIR" "${REMOTE%/}/$STAMP"

CONFIG_FILE="${SDAC_CONFIG_FILE:-$APP_DIR/config.json}"
if [[ -f "$CONFIG_FILE" ]]; then
    SDAC_BACKUP_PROVIDER="${SDAC_BACKUP_PROVIDER:-rclone}" \
    SDAC_BACKUP_REMOTE="${REMOTE%/}" \
    SDAC_BACKUP_DETAILS="Off-server backup complete: ${REMOTE%/}/$STAMP" \
    SDAC_BACKUP_STATUS="success" \
    SDAC_CONFIG_FILE="$CONFIG_FILE" \
    "$PYTHON" - <<'PY' || true
import json
import os
from datetime import datetime, timezone
from pathlib import Path

config_path = Path(os.environ["SDAC_CONFIG_FILE"])
data = json.loads(config_path.read_text(encoding="utf-8"))
offsite = data.setdefault("offsite_backup", {})
offsite["provider"] = os.environ.get("SDAC_BACKUP_PROVIDER", "rclone")
offsite["remote"] = os.environ.get("SDAC_BACKUP_REMOTE", "")
offsite["last_status"] = os.environ.get("SDAC_BACKUP_STATUS", "success")
offsite["last_details"] = os.environ.get("SDAC_BACKUP_DETAILS", "")
offsite["last_success_at"] = datetime.now(timezone.utc).isoformat()
config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
fi

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ && "$RETENTION_DAYS" -gt 0 ]]; then
    find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf {} +
fi

echo "Off-server backup complete: ${REMOTE%/}/$STAMP"
