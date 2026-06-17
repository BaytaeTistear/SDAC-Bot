#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
DEPLOY_BACKUP_ROOT="$APP_DIR/deploy-backups"
BACKUP_DIR="${1:-}"
PYTHON="$APP_DIR/venv/bin/python"

if [[ ! -d "$DEPLOY_BACKUP_ROOT" ]]; then
    echo "No deploy-backups folder exists yet." >&2
    exit 1
fi

if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="$(find "$DEPLOY_BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
fi

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
    echo "Backup snapshot not found: ${BACKUP_DIR:-none}" >&2
    exit 1
fi

BACKUP_DIR="$(realpath "$BACKUP_DIR")"
DEPLOY_BACKUP_ROOT="$(realpath "$DEPLOY_BACKUP_ROOT")"
case "$BACKUP_DIR" in
    "$DEPLOY_BACKUP_ROOT"/*) ;;
    *)
        echo "Refusing to restore from outside $DEPLOY_BACKUP_ROOT" >&2
        exit 1
        ;;
esac

if [[ ! -x "$PYTHON" ]]; then
    echo "Virtualenv missing. Run scripts/install_ubuntu.sh first." >&2
    exit 1
fi

echo "Restoring app files from $BACKUP_DIR"
cp -a "$BACKUP_DIR/." "$APP_DIR/"

"$PYTHON" -m py_compile \
    "$APP_DIR/bot.py" \
    "$APP_DIR/dashboard.py" \
    "$APP_DIR/config.py"

sudo systemctl restart sdac-bot sdac-dashboard
sudo systemctl is-active --quiet sdac-bot
sudo systemctl is-active --quiet sdac-dashboard

echo "Rollback complete."
echo "Service status:"
sudo systemctl status sdac-bot --no-pager -l
sudo systemctl status sdac-dashboard --no-pager -l
