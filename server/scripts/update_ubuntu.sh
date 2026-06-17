#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEPLOY_BACKUP_ROOT="$APP_DIR/deploy-backups"
DEPLOY_BACKUP_DIR="$DEPLOY_BACKUP_ROOT/$STAMP"
DB_BACKUP_DIR="$APP_DIR/backups"
PYTHON="$APP_DIR/venv/bin/python"

if [[ ! -f "$APP_DIR/bot.py" || ! -f "$APP_DIR/dashboard.py" ]]; then
    echo "Run this script from the SDAC bot folder, or set SDAC_APP_DIR." >&2
    exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "Virtualenv missing. Run scripts/install_ubuntu.sh first." >&2
    exit 1
fi

mkdir -p "$DEPLOY_BACKUP_DIR" "$DB_BACKUP_DIR"

previous_backup=""
if [[ -d "$DEPLOY_BACKUP_ROOT" ]]; then
    previous_backup="$(
        find "$DEPLOY_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
            ! -path "$DEPLOY_BACKUP_DIR" | sort | tail -n 1
    )"
fi

echo "Creating deploy snapshot: $DEPLOY_BACKUP_DIR"
for file in \
    bot.py \
    dashboard.py \
    config.py \
    requirements.txt \
    HOSTING.md \
    DEPLOY.md \
    PRODUCTION_NEXT.md \
    DISCORD_PERMISSIONS.md
do
    if [[ -e "$APP_DIR/$file" ]]; then
        cp -a "$APP_DIR/$file" "$DEPLOY_BACKUP_DIR/"
    fi
done

for directory in scripts systemd; do
    if [[ -d "$APP_DIR/$directory" ]]; then
        mkdir -p "$DEPLOY_BACKUP_DIR/$directory"
        cp -a "$APP_DIR/$directory/." "$DEPLOY_BACKUP_DIR/$directory/"
    fi
done

if [[ -f "$APP_DIR/sdac.db" ]]; then
    echo "Creating database backup with SQLite backup API."
    SDAC_DB_FILE="$APP_DIR/sdac.db" \
    SDAC_DB_BACKUP="$DB_BACKUP_DIR/sdac-pre-update-$STAMP.db" \
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
fi

if [[ -f "$APP_DIR/requirements.txt" ]]; then
    "$PYTHON" -m pip install -r "$APP_DIR/requirements.txt"
else
    "$PYTHON" -m pip install "discord.py>=2.3.2" "Flask>=3.0.0" "gunicorn>=22.0.0"
fi

"$PYTHON" -m py_compile \
    "$APP_DIR/bot.py" \
    "$APP_DIR/dashboard.py" \
    "$APP_DIR/config.py"

sudo systemctl restart sdac-bot sdac-dashboard
sudo systemctl is-active --quiet sdac-bot
sudo systemctl is-active --quiet sdac-dashboard

echo "Update complete."
echo "Service status:"
sudo systemctl status sdac-bot --no-pager -l
sudo systemctl status sdac-dashboard --no-pager -l

if [[ -n "$previous_backup" ]]; then
    echo
    echo "Rollback to the previous deploy snapshot with:"
    echo "  cd $APP_DIR"
    echo "  bash scripts/rollback_ubuntu.sh \"$previous_backup\""
else
    echo
    echo "No previous deploy snapshot was found for rollback yet."
fi

echo
echo "Useful logs:"
echo "  journalctl -u sdac-bot -n 80 --no-pager"
echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
