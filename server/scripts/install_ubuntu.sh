#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
APP_USER="${SDAC_APP_USER:-$(id -un)}"
DASHBOARD_BIND="${SDAC_DASHBOARD_BIND:-127.0.0.1:5000}"
ENV_DIR="${SDAC_ENV_DIR:-/etc/sdac-bot}"
ENV_FILE="${SDAC_ENV_FILE:-$ENV_DIR/sdac.env}"

if [[ ! -f "$APP_DIR/bot.py" || ! -f "$APP_DIR/dashboard.py" ]]; then
    echo "Run this script from the SDAC bot folder, or set SDAC_APP_DIR." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required. Install it first: sudo apt install python3 python3-venv" >&2
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "python3-venv is required. Install it first: sudo apt install python3-venv" >&2
    exit 1
fi

echo "Setting up SDAC in $APP_DIR as user $APP_USER"
echo "Using environment file $ENV_FILE"

mkdir -p "$APP_DIR/media" "$APP_DIR/backups"

if [[ ! -f "$APP_DIR/config.json" ]]; then
    cat > "$APP_DIR/config.json" <<'JSON'
{
    "guilds": {},
    "limits": {
        "max_file_bytes": 26214400,
        "max_total_bytes": 52428800,
        "max_text_length": 1500,
        "wrong_guess_timeout_seconds": 600,
        "orphan_media_cleanup_enabled": true,
        "audit_retention_days": 365,
        "pending_submission_retention_hours": 48
    }
}
JSON
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Creating $ENV_FILE"
    DISCORD_TOKEN_INPUT="${SDAC_DISCORD_TOKEN:-}"
    ADMIN_KEY_INPUT="${SDAC_ADMIN_KEY_INPUT:-}"
    ADMIN_PASSWORD_INPUT="${SDAC_ADMIN_PASSWORD_INPUT:-}"
    SECRET_KEY_INPUT="${SDAC_SECRET_KEY_INPUT:-}"

    if [[ -z "$DISCORD_TOKEN_INPUT" ]]; then
        read -r -p "Discord bot token: " DISCORD_TOKEN_INPUT
    fi
    if [[ -z "$DISCORD_TOKEN_INPUT" ]]; then
        echo "Discord bot token cannot be blank." >&2
        exit 1
    fi

    if [[ -z "$ADMIN_KEY_INPUT" ]]; then
        read -r -p "Dashboard admin key [ImTheBestAdmin]: " ADMIN_KEY_INPUT
    fi
    ADMIN_KEY_INPUT="${ADMIN_KEY_INPUT:-ImTheBestAdmin}"

    if [[ -z "$ADMIN_PASSWORD_INPUT" ]]; then
        read -r -s -p "Dashboard admin password: " ADMIN_PASSWORD_INPUT
        echo
    fi
    if [[ -z "$ADMIN_PASSWORD_INPUT" ]]; then
        echo "Admin password cannot be blank." >&2
        exit 1
    fi
    if [[ -z "$SECRET_KEY_INPUT" ]]; then
        SECRET_KEY_INPUT="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
    fi

    ENV_TMP="$(mktemp)"
    cat > "$ENV_TMP" <<EOF
DISCORD_TOKEN=$DISCORD_TOKEN_INPUT
SDAC_ADMIN_KEY=$ADMIN_KEY_INPUT
SDAC_ADMIN_PASSWORD=$ADMIN_PASSWORD_INPUT
SDAC_SECRET_KEY=$SECRET_KEY_INPUT
PYTHONUNBUFFERED=1
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0
SDAC_RELEASE=
SDAC_SERVER_NAME=
EOF
    sudo mkdir -p "$ENV_DIR"
    sudo install -m 600 -o root -g root "$ENV_TMP" "$ENV_FILE"
    rm -f "$ENV_TMP"
else
    echo "Keeping existing $ENV_FILE"
fi

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/python" -m pip install --upgrade pip
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    "$APP_DIR/venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
else
    "$APP_DIR/venv/bin/python" -m pip install "discord.py>=2.3.2" "Flask>=3.0.0" "gunicorn>=22.0.0"
fi
"$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/bot.py" "$APP_DIR/dashboard.py"
"$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/config.py" "$APP_DIR/database_migrations.py" "$APP_DIR/observability.py"

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
sudo systemctl enable --now sdac-bot sdac-dashboard

echo
echo "SDAC install complete."
echo "Environment file: $ENV_FILE"
echo "Dashboard bind: $DASHBOARD_BIND"
echo "Check status:"
echo "  sudo systemctl status sdac-bot --no-pager"
echo "  sudo systemctl status sdac-dashboard --no-pager"
echo
echo "View logs:"
echo "  journalctl -u sdac-bot -n 80 --no-pager"
echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
