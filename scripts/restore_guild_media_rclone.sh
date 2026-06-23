#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
CONFIG_FILE="${SDAC_CONFIG_FILE:-$APP_DIR/config.json}"
MEDIA_DIR="${SDAC_MEDIA_DIR:-$APP_DIR/media}"
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
    echo "Example: SDAC_GUILD_ID=123456789 bash scripts/restore_guild_media_rclone.sh" >&2
    exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is required for media restore." >&2
    echo "Install it with: sudo apt install rclone" >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

if [[ -z "$REMOTE" ]]; then
    REMOTE="$(
        SDAC_CONFIG_FILE="$CONFIG_FILE" \
        SDAC_BACKUP_GUILD_ID="$GUILD_ID" \
        "$PYTHON" - <<'PY'
import json
import os
from pathlib import Path

config_path = Path(os.environ["SDAC_CONFIG_FILE"])
guild_id = os.environ["SDAC_BACKUP_GUILD_ID"]
remote = ""
if config_path.is_file():
    data = json.loads(config_path.read_text(encoding="utf-8"))
    guild_config = (data.get("guilds") or {}).get(str(guild_id)) or {}
    remote = ((guild_config.get("external_backup") or {}).get("remote") or "").strip()
print(remote)
PY
    )"
fi

if [[ -z "$REMOTE" ]]; then
    echo "No restore remote configured for guild $GUILD_ID." >&2
    exit 1
fi

DESTINATION="$MEDIA_DIR/$GUILD_ID"
mkdir -p "$DESTINATION"

rclone copy "${REMOTE%/}/media" "$DESTINATION" \
    --copy-links \
    --fast-list \
    --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
    --checkers "${SDAC_RCLONE_CHECKERS:-8}"

echo "Restored guild media for $GUILD_ID from ${REMOTE%/}/media"
