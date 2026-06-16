#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"

if [[ ! -f "$APP_DIR/bot.py" || ! -f "$APP_DIR/dashboard.py" ]]; then
    echo "Run this script from the SDAC bot folder, or set SDAC_APP_DIR." >&2
    exit 1
fi

if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
    echo "Virtualenv missing. Run scripts/install_ubuntu.sh first." >&2
    exit 1
fi

if [[ -f "$APP_DIR/requirements.txt" ]]; then
    "$APP_DIR/venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
else
    "$APP_DIR/venv/bin/python" -m pip install "discord.py>=2.3.2" "Flask>=3.0.0" "gunicorn>=22.0.0"
fi
"$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/bot.py" "$APP_DIR/dashboard.py"

sudo systemctl restart sdac-bot sdac-dashboard

echo "Update complete."
echo "Bot logs:"
echo "  journalctl -u sdac-bot -n 80 --no-pager"
echo "Dashboard logs:"
echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
