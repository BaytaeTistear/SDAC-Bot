#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
CONFIG_FILE="${SDAC_CONFIG_FILE:-$APP_DIR/config.json}"
DB_FILE="${SDAC_DB_FILE:-$APP_DIR/sdac.db}"
MEDIA_DIR="${SDAC_MEDIA_DIR:-$APP_DIR/media}"
BACKUP_ROOT="${SDAC_GUILD_BACKUP_ROOT:-$APP_DIR/backups/guild-offsite}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
PYTHON="$APP_DIR/venv/bin/python"

if [[ -n "${SDAC_GUILD_ID:-}" ]]; then
    GUILD_ID="$SDAC_GUILD_ID"
    REMOTE="${1:-${SDAC_GUILD_RCLONE_REMOTE:-}}"
else
    GUILD_ID="${1:-}"
    REMOTE="${2:-${SDAC_GUILD_RCLONE_REMOTE:-}}"
fi

if [[ ! "$GUILD_ID" =~ ^[0-9]+$ ]]; then
    echo "Set SDAC_GUILD_ID or pass a numeric guild ID." >&2
    echo "Example: SDAC_GUILD_ID=123456789 bash scripts/backup_guild_offsite.sh" >&2
    echo "Example: bash scripts/backup_guild_offsite.sh 123456789 drive:sdac/123456789" >&2
    exit 1
fi

ARCHIVE_DIR="${SDAC_GUILD_BACKUP_ARCHIVE_DIR:-$BACKUP_ROOT/$GUILD_ID/archives}"
ARCHIVE_PATH="$ARCHIVE_DIR/sdac-guild-$GUILD_ID-$STAMP.zip"

if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is required for per-server offsite backups." >&2
    echo "Install backup prerequisites with: sudo bash scripts/install_backup_prereqs.sh" >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

RUN_DIR="$BACKUP_ROOT/$GUILD_ID/$STAMP"
mkdir -p "$RUN_DIR"

eval "$(
    SDAC_CONFIG_FILE="$CONFIG_FILE" \
    SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
    "$PYTHON" - <<'PY'
import json
import os
import shlex
from pathlib import Path

config_path = Path(os.environ["SDAC_CONFIG_FILE"])
guild_id = os.environ["SDAC_BACKUP_GUILD_ID"]
backup = {}
if config_path.is_file():
    data = json.loads(config_path.read_text(encoding="utf-8"))
    guild_config = (data.get("guilds") or {}).get(str(guild_id)) or {}
    backup = guild_config.get("external_backup") or {}

defaults = {
    "enabled": False,
    "remote": "",
    "include_media": True,
    "include_database_export": True,
    "zip_backups": True,
    "delete_local_media_after_success": False,
}
settings = {**defaults, **backup}

def emit(name, value):
    print(f"{name}={shlex.quote(str(value))}")

emit("CONFIG_BACKUP_ENABLED", "1" if settings.get("enabled") else "0")
emit("CONFIG_REMOTE", settings.get("remote") or "")
emit("CONFIG_INCLUDE_MEDIA", "1" if settings.get("include_media") else "0")
emit("CONFIG_INCLUDE_DB_EXPORT", "1" if settings.get("include_database_export") else "0")
emit("CONFIG_ZIP_BACKUPS", "1" if settings.get("zip_backups", True) else "0")
emit("CONFIG_DELETE_LOCAL_MEDIA", "1" if settings.get("delete_local_media_after_success") else "0")
PY
)"

REMOTE="${REMOTE:-$CONFIG_REMOTE}"
INCLUDE_MEDIA="${SDAC_GUILD_BACKUP_INCLUDE_MEDIA:-$CONFIG_INCLUDE_MEDIA}"
INCLUDE_DB_EXPORT="${SDAC_GUILD_BACKUP_INCLUDE_DB_EXPORT:-$CONFIG_INCLUDE_DB_EXPORT}"
ZIP_BACKUPS="${SDAC_GUILD_BACKUP_ZIP:-$CONFIG_ZIP_BACKUPS}"
DELETE_LOCAL_MEDIA="${SDAC_GUILD_BACKUP_DELETE_LOCAL_MEDIA_AFTER_SUCCESS:-$CONFIG_DELETE_LOCAL_MEDIA}"

enabled() {
    case "${1:-}" in
        1|true|TRUE|yes|YES|on|ON|enabled|ENABLED) return 0 ;;
        *) return 1 ;;
    esac
}

record_status() {
    local status="$1"
    local details="$2"
    if [[ ! -f "$CONFIG_FILE" ]]; then
        return 0
    fi
    SDAC_BACKUP_STATUS="$status" \
    SDAC_BACKUP_DETAILS="$details" \
    SDAC_BACKUP_REMOTE="${REMOTE%/}" \
    SDAC_BACKUP_ARCHIVE_PATH="$ARCHIVE_PATH" \
    SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
    SDAC_APP_DIR="$APP_DIR" \
    SDAC_CONFIG_FILE="$CONFIG_FILE" \
    SDAC_DB_FILE="$DB_FILE" \
    "$PYTHON" - <<'PY' || true
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

app_dir = Path(os.environ.get("SDAC_APP_DIR", ".")).resolve()
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

guild_id = str(os.environ["SDAC_BACKUP_GUILD_ID"])
status = os.environ["SDAC_BACKUP_STATUS"]
details = os.environ["SDAC_BACKUP_DETAILS"]
remote = os.environ.get("SDAC_BACKUP_REMOTE", "")
now = datetime.now(timezone.utc).isoformat()
config_path = Path(os.environ["SDAC_CONFIG_FILE"])
data = json.loads(config_path.read_text(encoding="utf-8"))
guild_config = data.setdefault("guilds", {}).setdefault(guild_id, {})
backup = guild_config.setdefault("external_backup", {})
backup["provider"] = "rclone"
backup["remote"] = remote or backup.get("remote", "")
backup["last_status"] = status
backup["last_details"] = details
archive_path = Path(os.environ.get("SDAC_BACKUP_ARCHIVE_PATH", ""))
if archive_path.is_file():
    backup["last_archive_path"] = str(archive_path)
if status == "success":
    backup["last_success_at"] = now
config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

try:
    from database_backend import connect_database
    connection = connect_database(Path(os.environ["SDAC_DB_FILE"]), timeout=30)
    try:
        connection.execute(
            """
            INSERT INTO offsite_backup_runs (
                provider, destination, status, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("rclone", f"guild:{guild_id}:{remote}", status, details, now),
        )
        connection.commit()
    finally:
        connection.close()
except Exception:
    pass
PY
}

trap 'line=$LINENO; record_status failed "Per-server backup failed at line $line."; exit 1' ERR

if [[ -z "$REMOTE" ]]; then
    echo "No per-server backup remote configured for guild $GUILD_ID." >&2
    echo "Use /setserverbackup in Discord or pass an rclone destination." >&2
    exit 1
fi

if [[ "$CONFIG_BACKUP_ENABLED" != "1" && "${SDAC_GUILD_BACKUP_RUN_DISABLED:-0}" != "1" ]]; then
    echo "Per-server backups are disabled for guild $GUILD_ID." >&2
    echo "Enable them with /setserverbackup or set SDAC_GUILD_BACKUP_RUN_DISABLED=1 for a one-off run." >&2
    exit 1
fi

if enabled "$DELETE_LOCAL_MEDIA" && ! enabled "$INCLUDE_MEDIA"; then
    echo "Refusing to delete local media when media backup is disabled." >&2
    exit 1
fi

echo "Exporting per-server metadata for guild $GUILD_ID."
SDAC_APP_DIR="$APP_DIR" \
SDAC_CONFIG_FILE="$CONFIG_FILE" \
SDAC_DB_FILE="$DB_FILE" \
SDAC_BACKUP_RUN_DIR="$RUN_DIR" \
SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
SDAC_INCLUDE_DB_EXPORT="$INCLUDE_DB_EXPORT" \
"$PYTHON" - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

app_dir = Path(os.environ["SDAC_APP_DIR"]).resolve()
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from database_backend import connect_database, using_postgres

config_path = Path(os.environ["SDAC_CONFIG_FILE"])
db_path = Path(os.environ["SDAC_DB_FILE"])
run_dir = Path(os.environ["SDAC_BACKUP_RUN_DIR"])
guild_id = str(os.environ["SDAC_BACKUP_GUILD_ID"])
include_db = os.environ.get("SDAC_INCLUDE_DB_EXPORT", "1") not in {"0", "false", "False"}
run_dir.mkdir(parents=True, exist_ok=True)

metadata = {
    "guild_id": guild_id,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "database_backend": "postgresql" if using_postgres() else "sqlite",
    "tables": {},
}

if config_path.is_file():
    data = json.loads(config_path.read_text(encoding="utf-8"))
    guild_config = (data.get("guilds") or {}).get(guild_id) or {}
    (run_dir / "guild-config.json").write_text(
        json.dumps({
            "guild_id": guild_id,
            "guild_config": guild_config,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

tables = (
    "submissions",
    "monthly_submission_top",
    "category_history",
    "moderation_history",
    "admin_audit_log",
    "admin_notifications",
    "game_seasons",
    "guess_games",
    "guess_library_items",
    "guess_answer_history",
    "guess_points",
    "guess_correct_guesses",
    "guess_cooldowns",
    "monthly_guess_runs",
    "daily_guess_runs",
    "rate_limit_events",
    "submission_reports",
    "setup_test_runs",
    "support_bundles",
    "content_moderation_events",
)

if include_db and (db_path.is_file() or using_postgres()):
    connection = connect_database(db_path, timeout=30)
    try:
        export = {}
        for table in tables:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            columns = [
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table})")
            ]
            if "guild_id" not in columns:
                continue
            order_column = "id" if "id" in columns else columns[0]
            rows = [
                {key: row[key] for key in row.keys()}
                for row in connection.execute(
                    f'SELECT * FROM "{table}" WHERE guild_id = ? ORDER BY "{order_column}"',
                    (guild_id,),
                )
            ]
            export[table] = rows
            metadata["tables"][table] = len(rows)
        (run_dir / "database-guild-export.json").write_text(
            json.dumps(export, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    finally:
        connection.close()
elif include_db:
    metadata["database_warning"] = f"Database file was not found: {db_path}"
else:
    metadata["database_export"] = "disabled"

(run_dir / "manifest.json").write_text(
    json.dumps(metadata, indent=2) + "\n",
    encoding="utf-8",
)
PY

(
    cd "$RUN_DIR"
    find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "Copying metadata to ${REMOTE%/}/metadata/$STAMP."
rclone copy "$RUN_DIR" "${REMOTE%/}/metadata/$STAMP" \
    --copy-links \
    --fast-list \
    --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
    --checkers "${SDAC_RCLONE_CHECKERS:-8}"

GUILD_MEDIA_DIR="$MEDIA_DIR/$GUILD_ID"
if enabled "$INCLUDE_MEDIA"; then
    if [[ -d "$GUILD_MEDIA_DIR" ]]; then
        echo "Copying guild media to ${REMOTE%/}/media."
        rclone copy "$GUILD_MEDIA_DIR" "${REMOTE%/}/media" \
            --copy-links \
            --fast-list \
            --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
            --checkers "${SDAC_RCLONE_CHECKERS:-8}"
    else
        echo "No local media folder found for guild $GUILD_ID; skipping media copy."
    fi
fi

if enabled "$ZIP_BACKUPS"; then
    mkdir -p "$ARCHIVE_DIR"
    echo "Creating zip archive at $ARCHIVE_PATH."
    SDAC_BACKUP_RUN_DIR="$RUN_DIR" \
    SDAC_BACKUP_ARCHIVE_PATH="$ARCHIVE_PATH" \
    SDAC_MEDIA_DIR="$MEDIA_DIR" \
    SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
    SDAC_INCLUDE_MEDIA="$INCLUDE_MEDIA" \
    "$PYTHON" - <<'PY'
import hashlib
import os
import zipfile
from pathlib import Path

run_dir = Path(os.environ["SDAC_BACKUP_RUN_DIR"]).resolve()
archive_path = Path(os.environ["SDAC_BACKUP_ARCHIVE_PATH"]).resolve()
media_root = Path(os.environ["SDAC_MEDIA_DIR"]).resolve()
guild_id = str(os.environ["SDAC_BACKUP_GUILD_ID"])
include_media = os.environ.get("SDAC_INCLUDE_MEDIA", "1").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
archive_path.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(
    archive_path,
    "w",
    compression=zipfile.ZIP_DEFLATED,
    compresslevel=6,
) as archive:
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            archive.write(path, f"metadata/{path.relative_to(run_dir).as_posix()}")
    if include_media:
        guild_media_dir = (media_root / guild_id).resolve()
        try:
            guild_media_dir.relative_to(media_root)
        except ValueError:
            guild_media_dir = media_root / "__invalid__"
        if guild_media_dir.is_dir():
            for path in sorted(guild_media_dir.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        f"media/{path.relative_to(media_root).as_posix()}",
                    )

digest = hashlib.sha256()
with archive_path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
sha256 = digest.hexdigest()
archive_path.with_suffix(archive_path.suffix + ".sha256").write_text(
    f"{sha256}  {archive_path.name}\n",
    encoding="utf-8",
)
print(f"Created {archive_path} ({archive_path.stat().st_size} bytes, sha256 {sha256})")
PY
    echo "Copying zip archive to ${REMOTE%/}/archives."
    rclone copy "$ARCHIVE_PATH" "${REMOTE%/}/archives" \
        --copy-links \
        --fast-list \
        --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
        --checkers "${SDAC_RCLONE_CHECKERS:-8}"
    if [[ -f "$ARCHIVE_PATH.sha256" ]]; then
        rclone copy "$ARCHIVE_PATH.sha256" "${REMOTE%/}/archives" \
            --copy-links \
            --fast-list \
            --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
            --checkers "${SDAC_RCLONE_CHECKERS:-8}"
    fi
fi

if enabled "$DELETE_LOCAL_MEDIA"; then
    echo "Deleting local media for guild $GUILD_ID after successful backup."
    SDAC_MEDIA_DIR="$MEDIA_DIR" \
    SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
    "$PYTHON" - <<'PY'
import os
import shutil
from pathlib import Path

media_root = Path(os.environ["SDAC_MEDIA_DIR"]).resolve()
guild_id = str(os.environ["SDAC_BACKUP_GUILD_ID"])
target = (media_root / guild_id).resolve()
target.relative_to(media_root)
if target.name != guild_id:
    raise RuntimeError(f"Refusing to delete unexpected path: {target}")
if target.is_dir():
    for child in target.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
PY
fi

trap - ERR
if enabled "$ZIP_BACKUPS"; then
    record_status success "Per-server backup complete: ${REMOTE%/}/metadata/$STAMP and ${REMOTE%/}/archives/$(basename "$ARCHIVE_PATH")"
else
    record_status success "Per-server backup complete: ${REMOTE%/}/metadata/$STAMP"
fi
echo "Per-server backup complete for guild $GUILD_ID: ${REMOTE%/}"
