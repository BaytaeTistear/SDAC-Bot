#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
APP_USER="${SDAC_APP_USER:-$(id -un)}"
DASHBOARD_BIND="${SDAC_DASHBOARD_BIND:-127.0.0.1:5000}"
ENV_FILE="${SDAC_ENV_FILE:-/etc/sdac-bot/sdac.env}"
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

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Environment file not found: $ENV_FILE" >&2
    echo "Run scripts/install_ubuntu.sh or scripts/standardize_env_file.sh first." >&2
    exit 1
fi

echo "Restoring app files from $BACKUP_DIR"
cp -a "$BACKUP_DIR/." "$APP_DIR/"

"$PYTHON" -m py_compile \
    "$APP_DIR/bot.py" \
    "$APP_DIR/dashboard.py" \
    "$APP_DIR/config.py"

render_service() {
    local template="$1"
    local target="$2"
    sed \
        -e "s#__APP_DIR__#$APP_DIR#g" \
        -e "s#__APP_USER__#$APP_USER#g" \
        -e "s#__ENV_FILE__#$ENV_FILE#g" \
        -e "s#__DASHBOARD_BIND__#$DASHBOARD_BIND#g" \
        "$template" | sudo tee "$target" >/dev/null
}

render_service \
    "$APP_DIR/systemd/sdac-bot.service.template" \
    "/etc/systemd/system/sdac-bot.service"
render_service \
    "$APP_DIR/systemd/sdac-dashboard.service.template" \
    "/etc/systemd/system/sdac-dashboard.service"

sudo systemctl daemon-reload
sudo systemctl restart sdac-bot sdac-dashboard
sudo systemctl is-active --quiet sdac-bot
sudo systemctl is-active --quiet sdac-dashboard

echo "Rollback complete."
echo "Environment file: $ENV_FILE"
echo "Dashboard bind: $DASHBOARD_BIND"
echo "Service status:"
sudo systemctl status sdac-bot --no-pager -l
sudo systemctl status sdac-dashboard --no-pager -l
