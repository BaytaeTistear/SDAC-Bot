#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
APP_USER="${SDAC_APP_USER:-$(id -un)}"
CREATE_APP_USER="${SDAC_CREATE_APP_USER:-0}"
DASHBOARD_BIND="${SDAC_DASHBOARD_BIND:-127.0.0.1:5000}"
ENV_DIR="${SDAC_ENV_DIR:-/etc/sdac-bot}"
ENV_FILE="${SDAC_ENV_FILE:-$ENV_DIR/sdac.env}"
SKIP_SERVICES="${SDAC_SKIP_SERVICES:-0}"
INSTALL_BACKUP_PREREQS="${SDAC_INSTALL_BACKUP_PREREQS:-0}"

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

if ! id "$APP_USER" >/dev/null 2>&1; then
    if [[ "$CREATE_APP_USER" == "1" ]]; then
        echo "Creating system user $APP_USER"
        sudo useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin --no-create-home "$APP_USER"
    else
        echo "User $APP_USER does not exist." >&2
        echo "Create it first, use SDAC_APP_USER=$(id -un), or set SDAC_CREATE_APP_USER=1." >&2
        exit 1
    fi
fi

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
        "submission_user_cooldown_seconds": 30,
        "submission_category_cooldown_seconds": 5,
        "guess_command_cooldown_seconds": 2,
        "admin_action_cooldown_seconds": 1,
        "rate_limit_retention_days": 30,
        "orphan_media_cleanup_enabled": true,
        "audit_retention_days": 365,
        "pending_submission_retention_hours": 48,
        "media_warning_bytes": 5368709120,
        "database_warning_bytes": 536870912,
        "restore_test_enabled": true,
        "restore_test_weekday": "sunday",
        "restore_test_time_utc": "03:30",
        "restore_drill_enabled": true,
        "monthly_digest_enabled": true,
        "two_admin_approval_enabled": false,
        "monthly_submission_limit_per_guild": 0,
        "active_game_limit_per_guild": 0,
        "guild_storage_limit_bytes": 0,
        "offsite_backup_warning_hours": 72,
        "local_original_retention_days": 30,
        "thumbnail_max_dimension": 640,
        "image_compression_enabled": false,
        "image_compression_quality": 85,
        "archive_full_history_after_months": 18,
        "spam_review_threshold": 40,
        "spam_burst_count": 5,
        "spam_burst_window_minutes": 10
    },
    "offsite_backup": {
        "provider": "",
        "remote": "",
        "last_success_at": "",
        "last_status": "",
        "last_details": ""
    }
}
JSON
fi

write_update_assignment() {
    local key="$1"
    local value="$2"
    printf '%s=%q\n' "$key" "$value"
}

install_update_command() {
    if [[ ! -f "$APP_DIR/scripts/update_from_github.sh" ]]; then
        return
    fi

    echo "Installing sana-update and sanachan-update commands"
    sudo install -m 755 "$APP_DIR/scripts/update_from_github.sh" "/usr/local/bin/sana-update"
    sudo install -m 755 "$APP_DIR/scripts/update_from_github.sh" "/usr/local/bin/sanachan-update"
    sudo rm -f "/usr/local/bin/sdac-update"
    if [[ -f "$APP_DIR/scripts/sdac-doctor" ]]; then
        echo "Installing sdac-doctor command"
        sudo install -m 755 "$APP_DIR/scripts/sdac-doctor" "/usr/local/bin/sdac-doctor"
    elif [[ -f "$APP_DIR/scripts/sdac_doctor.py" ]]; then
        echo "Installing sdac-doctor command"
        DOCTOR_TMP="$(mktemp)"
        cat > "$DOCTOR_TMP" <<'DOCTOR'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${SDAC_BASE_DIR:-/home/ubuntu/discord-screenshot-bot}"
PYTHON_BIN="${SDAC_PYTHON:-$APP_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi
exec "$PYTHON_BIN" "$APP_DIR/scripts/sdac_doctor.py" "$@"
DOCTOR
        sudo install -m 755 "$DOCTOR_TMP" "/usr/local/bin/sdac-doctor"
        rm -f "$DOCTOR_TMP"
    fi
    if [[ -f "/usr/local/bin/sdac-doctor" ]]; then
        sudo sed -i 's/\r$//' "/usr/local/bin/sdac-doctor"
    fi

    UPDATE_CONFIG_TMP="$(mktemp)"
    {
        write_update_assignment SDAC_GITHUB_REPO "BaytaeTistear/SDAC-Bot"
        write_update_assignment SDAC_RELEASE_TAG "latest-official"
        write_update_assignment SDAC_APP_DIR "$APP_DIR"
        write_update_assignment SDAC_APP_USER "$APP_USER"
        write_update_assignment SDAC_ENV_FILE "$ENV_FILE"
        write_update_assignment SDAC_DASHBOARD_BIND "$DASHBOARD_BIND"
        write_update_assignment SDAC_DOMAIN "${SDAC_DOMAIN:-}"
        write_update_assignment SDAC_RELOAD_NGINX "1"
    } > "$UPDATE_CONFIG_TMP"
    sudo mkdir -p "$ENV_DIR"
    sudo install -m 644 -o root -g root "$UPDATE_CONFIG_TMP" "$ENV_DIR/update.env"
    rm -f "$UPDATE_CONFIG_TMP"
}

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Creating $ENV_FILE"
    DISCORD_TOKEN_INPUT="${SDAC_DISCORD_TOKEN:-}"
    ADMIN_KEY_INPUT="${SDAC_ADMIN_KEY_INPUT:-}"
    ADMIN_USERNAME_INPUT="${SDAC_ADMIN_USERNAME_INPUT:-${SDAC_ADMIN_USERNAME:-}}"
    ADMIN_PASSWORD_INPUT="${SDAC_ADMIN_PASSWORD_INPUT:-}"
    SECRET_KEY_INPUT="${SDAC_SECRET_KEY_INPUT:-}"
    PUBLIC_URL_INPUT="${SDAC_PUBLIC_URL_INPUT:-${SDAC_PUBLIC_URL:-}}"
    SERVER_NAME_INPUT="${SDAC_SERVER_NAME_INPUT:-${SDAC_SERVER_NAME:-}}"

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

    if [[ -z "$ADMIN_USERNAME_INPUT" ]]; then
        read -r -p "Initial dashboard owner username [owner]: " ADMIN_USERNAME_INPUT
    fi
    ADMIN_USERNAME_INPUT="${ADMIN_USERNAME_INPUT:-owner}"

    if [[ -z "$ADMIN_PASSWORD_INPUT" ]]; then
        read -r -s -p "Initial dashboard owner password: " ADMIN_PASSWORD_INPUT
        echo
    fi
    if [[ -z "$ADMIN_PASSWORD_INPUT" ]]; then
        echo "Initial dashboard owner password cannot be blank." >&2
        exit 1
    fi
    if [[ -z "$SECRET_KEY_INPUT" ]]; then
        SECRET_KEY_INPUT="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
    fi
    if [[ -z "$PUBLIC_URL_INPUT" ]]; then
        read -r -p "Public dashboard URL or domain (optional): " PUBLIC_URL_INPUT
    fi
    if [[ -z "$SERVER_NAME_INPUT" ]]; then
        read -r -p "Server label for dashboard status [production]: " SERVER_NAME_INPUT
    fi
    SERVER_NAME_INPUT="${SERVER_NAME_INPUT:-production}"

    ENV_TMP="$(mktemp)"
    cat > "$ENV_TMP" <<EOF
DISCORD_TOKEN=$DISCORD_TOKEN_INPUT
SDAC_ADMIN_KEY=$ADMIN_KEY_INPUT
SDAC_SECRET_KEY=$SECRET_KEY_INPUT
PYTHONUNBUFFERED=1
SDAC_PUBLIC_URL=$PUBLIC_URL_INPUT
SDAC_PUBLIC_BOT_NAME=SDAC Bot
SDAC_PUBLIC_TAGLINE=Screenshot, media, and guessing-game management for Discord communities.
SDAC_SUPPORT_URL=
SDAC_PRIVACY_URL=
SDAC_TERMS_URL=
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0
SDAC_RELEASE=
SDAC_SERVER_NAME=$SERVER_NAME_INPUT
EOF
    sudo mkdir -p "$ENV_DIR"
    sudo install -m 600 -o root -g root "$ENV_TMP" "$ENV_FILE"
    rm -f "$ENV_TMP"
else
    echo "Keeping existing $ENV_FILE"
fi

python3 -m venv "$APP_DIR/venv"
export PIP_DISABLE_PIP_VERSION_CHECK=1
"$APP_DIR/venv/bin/python" -m pip install -q --upgrade pip
if [[ -f "$APP_DIR/requirements.txt" ]]; then
    "$APP_DIR/venv/bin/python" -m pip install -q -r "$APP_DIR/requirements.txt"
else
    "$APP_DIR/venv/bin/python" -m pip install -q "discord.py>=2.3.2" "Flask>=3.0.0" "gunicorn>=22.0.0"
fi

if [[ "$INSTALL_BACKUP_PREREQS" == "1" && -f "$APP_DIR/scripts/install_backup_prereqs.sh" ]]; then
    bash "$APP_DIR/scripts/install_backup_prereqs.sh"
fi

"$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/bot.py" "$APP_DIR/dashboard.py" "$APP_DIR/dashboard_account_templates.py" "$APP_DIR/dashboard_admin_roles.py" "$APP_DIR/dashboard_shell_assets.py" "$APP_DIR/dashboard_sidebar.py"
"$APP_DIR/venv/bin/python" -m py_compile "$APP_DIR/config.py" "$APP_DIR/database_backend.py" "$APP_DIR/database_migrations.py" "$APP_DIR/observability.py"

if [[ -f "$APP_DIR/scripts/reset_admin_login.py" ]]; then
    DASHBOARD_ACCOUNT_COUNT="$("$APP_DIR/venv/bin/python" - "$APP_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from database_backend import connect_database
from database_migrations import apply_database_migrations

connection = connect_database(root / "sdac.db", timeout=30)
try:
    apply_database_migrations(connection)
    row = connection.execute("""
        SELECT COUNT(*)
        FROM dashboard_admin_users
        WHERE disabled = 0
          AND role IN ('owner', 'admin')
    """).fetchone()
    print(row[0] if row else 0)
finally:
    connection.close()
PY
)"
    if [[ "${DASHBOARD_ACCOUNT_COUNT:-0}" == "0" ]]; then
        if [[ -z "${ADMIN_USERNAME_INPUT:-}" ]]; then
            read -r -p "Initial dashboard owner username [owner]: " ADMIN_USERNAME_INPUT
            ADMIN_USERNAME_INPUT="${ADMIN_USERNAME_INPUT:-owner}"
        fi
        if [[ -z "${ADMIN_PASSWORD_INPUT:-}" ]]; then
            read -r -s -p "Initial dashboard owner password: " ADMIN_PASSWORD_INPUT
            echo
        fi
        "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/reset_admin_login.py" \
            --username "$ADMIN_USERNAME_INPUT" \
            --password "$ADMIN_PASSWORD_INPUT" \
            --role owner
    fi
fi

sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR" 2>/dev/null || sudo chown -R "$APP_USER" "$APP_DIR"

if [[ "$SKIP_SERVICES" == "1" ]]; then
    echo
    echo "SDAC files compiled. Skipping service installation because SDAC_SKIP_SERVICES=1."
    exit 0
fi

install_update_command

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
echo "Run Discord setup:"
echo "  /setup"
echo "  /setuptest"
echo "Check status:"
echo "  sudo systemctl status sdac-bot --no-pager"
echo "  sudo systemctl status sdac-dashboard --no-pager"
echo
echo "Future GitHub updates:"
echo "  sana-update \"Version 3\""
echo "  sana-update latest-experimental"
echo "  sanachan-update latest-experimental"
echo "  sana-update 2.6"
echo
echo "View logs:"
echo "  journalctl -u sdac-bot -n 80 --no-pager"
echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
