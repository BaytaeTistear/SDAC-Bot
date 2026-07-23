#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${SDAC_UPDATE_CONFIG:-/etc/sdac-bot/update.env}"
COMMAND_PATH="${SANA_UPDATE_COMMAND_PATH:-${SDAC_UPDATE_COMMAND_PATH:-/usr/local/bin/sana-update}}"
SCRIPT_PATH="$0"
if command -v readlink >/dev/null 2>&1; then
    SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || printf '%s\n' "$0")"
fi

SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd -P)"
DETECTED_APP_DIR=""
if [[ -z "${SDAC_APP_DIR:-}" ]]; then
    SCRIPT_PARENT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"
    if [[ -f "$SCRIPT_PARENT/docker-compose.yml" && -d "$SCRIPT_PARENT/.git" ]]; then
        DETECTED_APP_DIR="$SCRIPT_PARENT"
    fi
fi

if [[ -f "$CONFIG_FILE" ]]; then
    if [[ ! -r "$CONFIG_FILE" ]]; then
        echo "ERROR: Cannot read updater config: $CONFIG_FILE" >&2
        echo "This file stores updater defaults, not secrets." >&2
        echo "Fix it once with: sudo chmod 644 $CONFIG_FILE" >&2
        exit 1
    fi
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

REPO="${SDAC_GITHUB_REPO:-BaytaeTistear/SDAC-Bot}"
RELEASE_TAG="${SDAC_RELEASE_TAG:-latest-official}"
REQUESTED_RELEASE_TAG="$RELEASE_TAG"
RESOLVED_VERSION="unknown"
UPDATE_FINISHED=0
APP_DIR="${SDAC_APP_DIR:-${DETECTED_APP_DIR:-/home/ubuntu/discord-screenshot-bot}}"
ENV_FILE="${SDAC_ENV_FILE:-/etc/sdac-bot/sdac.env}"
DASHBOARD_BIND="${SDAC_DASHBOARD_BIND:-127.0.0.1:5000}"
INSTALLER_NAME="${SDAC_INSTALLER_NAME:-Sana-Chan-Linux-Installer.sh}"
RUN_RESTORE_TEST="${SDAC_RUN_RESTORE_TEST:-0}"
RUN_PRODUCTION_CHECK="${SDAC_RUN_PRODUCTION_CHECK:-0}"
DOMAIN="${SDAC_DOMAIN:-}"
RELOAD_NGINX="${SDAC_RELOAD_NGINX:-1}"
INSTALL_COMMAND=0
ROLLBACK_MODE=0
ROLLBACK_TARGET=""

print_failure_summary() {
    local exit_code="$1"
    if [[ "$exit_code" == "0" || "$UPDATE_FINISHED" == "1" ]]; then
        return
    fi
    echo
    echo "Update result: FAILED"
    echo "Requested update: $REQUESTED_RELEASE_TAG"
    echo "Resolved release tag: $RELEASE_TAG"
    echo "Resolved version: $RESOLVED_VERSION"
    echo "Exit code: $exit_code"
    echo "Review the lines above, then run:"
    echo "  journalctl -u sdac-bot -n 80 --no-pager"
    echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
}

trap 'exit_code=$?; print_failure_summary "$exit_code"' EXIT

usage() {
    cat <<EOF
Usage:
  $0 [release-tag]
  $0 --install-command
  $0 rollback [snapshot-path-or-name]

Examples:
  sana-update "Version 3"
  sana-update 3
  sana-update 3.0
  sana-update "Version 2"
  sana-update 2
  sana-update 2.6
  sana-update latest-official
  sana-update latest-experimental
  sana-update latest-expirimental
  sana-update rollback
  SDAC_RUN_RESTORE_TEST=1 sana-update latest-official

Environment:
  SDAC_GITHUB_REPO=$REPO
  SDAC_RELEASE_TAG=$RELEASE_TAG
  SDAC_APP_DIR=$APP_DIR
  SDAC_APP_USER=${SDAC_APP_USER:-}
  SDAC_ENV_FILE=$ENV_FILE
  SDAC_DOMAIN=$DOMAIN
EOF
}

normalize_release_tag() {
    local raw="$1"
    local lowered
    lowered="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
    lowered="${lowered// /-}"
    lowered="${lowered//_/-}"
    case "$lowered" in
        ""|latest|stable|official|latest-official|3|v3|version-3)
            printf '%s\n' "latest-official"
            ;;
        2|v2|version-2)
            printf '%s\n' "version-2.8"
            ;;
        experimental|expirimental|latest-experimental|latest-expirimental)
            printf '%s\n' "latest-experimental"
            ;;
        version-[0-9]*.[0-9]*)
            printf '%s\n' "$lowered"
            ;;
        v[0-9]*.[0-9]*)
            printf 'version-%s\n' "${lowered#v}"
            ;;
        [0-9]*.[0-9]*)
            printf 'version-%s\n' "$lowered"
            ;;
        *)
            printf '%s\n' "$raw"
            ;;
    esac
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --install-command)
            INSTALL_COMMAND=1
            shift
            ;;
        rollback|--rollback)
            ROLLBACK_MODE=1
            shift
            if [[ $# -gt 0 && "$1" != -* ]]; then
                ROLLBACK_TARGET="$1"
                shift
            fi
            ;;
        --run-restore-test)
            RUN_RESTORE_TEST=1
            shift
            ;;
        --run-production-check)
            RUN_PRODUCTION_CHECK=1
            shift
            ;;
        --no-nginx-reload)
            RELOAD_NGINX=0
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            RELEASE_TAG="$1"
            shift
            ;;
    esac
done

if [[ "$ROLLBACK_MODE" != "1" ]]; then
    REQUESTED_RELEASE_TAG="$RELEASE_TAG"
    RELEASE_TAG="$(normalize_release_tag "$RELEASE_TAG")"
fi

resolve_release_version() {
    local tag="$1"
    local metadata=""
    if [[ "$tag" == version-* ]]; then
        printf '%s\n' "${tag#version-}"
        return
    fi
    if command -v gh >/dev/null 2>&1; then
        metadata="$(gh release view "$tag" --repo "$REPO" --json tagName,name --jq '.tagName + " " + .name' 2>/dev/null || true)"
    fi
    if [[ "$metadata" =~ ([0-9]+\.[0-9]+(\.[0-9]+)?) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return
    fi
    printf '%s\n' "unknown"
}

if [[ "$ROLLBACK_MODE" != "1" ]]; then
    RESOLVED_VERSION="$(resolve_release_version "$RELEASE_TAG")"
fi

default_app_user() {
    if [[ -n "${SDAC_APP_USER:-}" ]]; then
        printf '%s\n' "$SDAC_APP_USER"
        return
    fi
    if id ubuntu >/dev/null 2>&1; then
        printf '%s\n' "ubuntu"
        return
    fi
    id -un
}

APP_USER="$(default_app_user)"
TMP_DIR="$(mktemp -d)"
INSTALLER_PATH="$TMP_DIR/$INSTALLER_NAME"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

say() {
    printf '\n==> %s\n' "$*"
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

need_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

write_assignment() {
    local key="$1"
    local value="$2"
    printf '%s=%q\n' "$key" "$value"
}

install_update_command() {
    need_command sudo
    need_command install

    say "Installing sana-update and sanachan-update commands"
    sudo install -m 755 "$SCRIPT_PATH" "$COMMAND_PATH"
    sudo install -m 755 "$SCRIPT_PATH" "/usr/local/bin/sanachan-update"
    sudo rm -f "/usr/local/bin/sdac-update"
    if [[ -f "$APP_DIR/scripts/sana-doctor" && -f "$APP_DIR/scripts/sdac-doctor" ]]; then
        say "Installing sana-doctor command"
        sudo install -m 755 "$APP_DIR/scripts/sana-doctor" "/usr/local/bin/sana-doctor"
        sudo install -m 755 "$APP_DIR/scripts/sdac-doctor" "/usr/local/bin/sdac-doctor"
    elif [[ -f "$APP_DIR/scripts/sdac_doctor.py" ]]; then
        say "Installing sana-doctor command"
        local doctor_tmp
        doctor_tmp="$(mktemp)"
        cat > "$doctor_tmp" <<'DOCTOR'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${SDAC_BASE_DIR:-/home/ubuntu/discord-screenshot-bot}"
PYTHON_BIN="${SDAC_PYTHON:-$APP_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi
exec "$PYTHON_BIN" "$APP_DIR/scripts/sdac_doctor.py" "$@"
DOCTOR
        sudo install -m 755 "$doctor_tmp" "/usr/local/bin/sana-doctor"
        sudo install -m 755 "$doctor_tmp" "/usr/local/bin/sdac-doctor"
        rm -f "$doctor_tmp"
    fi
    if [[ -f "/usr/local/bin/sana-doctor" ]]; then
        sudo sed -i 's/\r$//' "/usr/local/bin/sana-doctor"
    fi
    if [[ -f "/usr/local/bin/sdac-doctor" ]]; then
        sudo sed -i 's/\r$//' "/usr/local/bin/sdac-doctor"
    fi

    local config_dir
    config_dir="$(dirname "$CONFIG_FILE")"
    local config_tmp
    config_tmp="$(mktemp)"
    {
        write_assignment SDAC_GITHUB_REPO "$REPO"
        write_assignment SDAC_RELEASE_TAG "$RELEASE_TAG"
        write_assignment SDAC_RELEASE "$RESOLVED_VERSION"
        write_assignment SDAC_APP_DIR "$APP_DIR"
        write_assignment SDAC_APP_USER "$APP_USER"
        write_assignment SDAC_ENV_FILE "$ENV_FILE"
        write_assignment SDAC_DASHBOARD_BIND "$DASHBOARD_BIND"
        write_assignment SDAC_DOMAIN "$DOMAIN"
        write_assignment SDAC_RELOAD_NGINX "$RELOAD_NGINX"
    } > "$config_tmp"
    sudo mkdir -p "$config_dir"
    sudo install -m 644 -o root -g root "$config_tmp" "$CONFIG_FILE"
    rm -f "$config_tmp"

    echo
    echo "Installed: $COMMAND_PATH"
    echo "Config: $CONFIG_FILE"
    echo
    echo "Future updates can be one command:"
    echo "  sana-update latest-official"
    echo "  sana-update latest-experimental"
    echo "  sanachan-update latest-experimental"
}

download_with_gh() {
    gh release download "$RELEASE_TAG" \
        --repo "$REPO" \
        --pattern "$INSTALLER_NAME" \
        --dir "$TMP_DIR"
}

download_with_http() {
    local url
    url="https://github.com/$REPO/releases/download/$RELEASE_TAG/$INSTALLER_NAME"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$INSTALLER_PATH"
        return
    fi
    if command -v wget >/dev/null 2>&1; then
        wget -qO "$INSTALLER_PATH" "$url"
        return
    fi
    fail "Install GitHub CLI, curl, or wget to download the release installer."
}

download_installer() {
    say "Downloading $INSTALLER_NAME from $REPO ($RELEASE_TAG)"
    if command -v gh >/dev/null 2>&1; then
        if ! download_with_gh; then
            echo "GitHub CLI download failed. Falling back to HTTPS download."
            download_with_http
        fi
    else
        download_with_http
    fi

    if [[ ! -f "$INSTALLER_PATH" ]]; then
        fail "Downloaded installer was not found at $INSTALLER_PATH."
    fi
    sed -i 's/\r$//' "$INSTALLER_PATH"
    chmod +x "$INSTALLER_PATH"
}

restart_services() {
    say "Reloading systemd and restarting SDAC services"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed sdac-bot sdac-dashboard >/dev/null 2>&1 || true
    sudo systemctl restart sdac-bot
    sudo systemctl restart sdac-dashboard

    if [[ "$RELOAD_NGINX" == "1" ]] && systemctl list-unit-files nginx.service >/dev/null 2>&1; then
        if systemctl is-active --quiet nginx; then
            say "Reloading Nginx"
            sudo systemctl reload nginx || sudo systemctl restart nginx
        fi
    fi

    sudo systemctl is-active --quiet sdac-bot
    sudo systemctl is-active --quiet sdac-dashboard
}

run_optional_checks() {
    if [[ "$RUN_RESTORE_TEST" == "1" && -x "$APP_DIR/scripts/test_restore.sh" ]]; then
        say "Running restore test"
        SDAC_APP_DIR="$APP_DIR" bash "$APP_DIR/scripts/test_restore.sh"
    fi

    if [[ "$RUN_PRODUCTION_CHECK" == "1" && -x "$APP_DIR/scripts/check_production.sh" ]]; then
        say "Running production check"
        SDAC_DOMAIN="$DOMAIN" bash "$APP_DIR/scripts/check_production.sh"
    fi
}

run_update_health_check() {
    say "Running post-update health check"
    local failed=0

    run_health_check() {
        local label="$1"
        shift
        printf 'Checking %-34s' "$label"
        if "$@" >/dev/null 2>&1; then
            echo " ok"
        else
            echo " failed"
            failed=1
        fi
    }

    run_health_check "sdac-bot service" sudo systemctl is-active --quiet sdac-bot
    run_health_check "sdac-dashboard service" sudo systemctl is-active --quiet sdac-dashboard

    if [[ -x "$APP_DIR/venv/bin/python" && -f "$APP_DIR/scripts/migrate_database.py" && -f "$APP_DIR/sdac.db" ]]; then
        run_health_check "database migration check" "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/migrate_database.py" --db "$APP_DIR/sdac.db"
    fi

    if command -v curl >/dev/null 2>&1; then
        run_health_check "local dashboard health" curl -fsS "http://$DASHBOARD_BIND/health"
        if [[ -n "$DOMAIN" ]]; then
            run_health_check "public HTTPS health" curl -fsS "https://$DOMAIN/health"
        fi
    fi

    if [[ "$RELOAD_NGINX" == "1" ]] && systemctl list-unit-files nginx.service >/dev/null 2>&1; then
        run_health_check "nginx service" systemctl is-active --quiet nginx
        run_health_check "nginx config" sudo nginx -t
    fi

    if [[ "$failed" == "1" ]]; then
        echo "One or more health checks failed. Review the lines above and the service logs."
        return 1
    fi
    echo "All post-update health checks passed."
}


run_git_docker_update() {
    say "Updating Docker checkout in $APP_DIR"
    need_command git
    cd "$APP_DIR"

    if [[ ! -d .git ]]; then
        fail "Docker update mode needs a Git checkout at $APP_DIR."
    fi
    if [[ ! -f docker-compose.yml ]]; then
        fail "Docker update mode needs docker-compose.yml at $APP_DIR."
    fi
    if ! command -v docker >/dev/null 2>&1; then
        fail "Docker update mode needs the docker command."
    fi
    if ! docker compose version >/dev/null 2>&1; then
        fail "Docker Compose v2 is required. Use 'docker compose', not old 'docker-compose'."
    fi

    git fetch --tags --force origin
    if [[ "$RELEASE_TAG" == "latest-official" || "$RELEASE_TAG" == "latest-experimental" || "$RELEASE_TAG" == version-* ]]; then
        git checkout -f "$RELEASE_TAG"
    else
        git checkout -f "$RELEASE_TAG"
    fi

    docker compose up -d --build dashboard bot
    docker compose ps

    if command -v curl >/dev/null 2>&1; then
        say "Checking local dashboard health"
        curl -fsS "http://127.0.0.1:5000/health" >/dev/null
    fi

    UPDATE_FINISHED=1
    say "Update complete"
    echo "Update result: SUCCESS"
    echo "Requested update: $REQUESTED_RELEASE_TAG"
    echo "Resolved release tag: $RELEASE_TAG"
    echo "Resolved version: $RESOLVED_VERSION"
    echo "Repository: $REPO"
    echo "App directory: $APP_DIR"
    echo "Update mode: docker"
}

run_rollback() {
    local rollback_script="$APP_DIR/scripts/rollback_ubuntu.sh"
    if [[ ! -f "$rollback_script" ]]; then
        fail "Rollback script not found: $rollback_script"
    fi
    say "Rolling back SDAC"
    SDAC_APP_DIR="$APP_DIR" \
    SDAC_APP_USER="$APP_USER" \
    SDAC_ENV_FILE="$ENV_FILE" \
    SDAC_DASHBOARD_BIND="$DASHBOARD_BIND" \
    bash "$rollback_script" "$ROLLBACK_TARGET"
    run_update_health_check
    print_summary
}

print_summary() {
    say "Update complete"
    echo "Update result: SUCCESS"
    echo "Requested update: $REQUESTED_RELEASE_TAG"
    echo "Resolved release tag: $RELEASE_TAG"
    echo "Resolved version: $RESOLVED_VERSION"
    echo "Repository: $REPO"
    echo "App directory: $APP_DIR"
    echo "App user: $APP_USER"
    echo "Environment file: $ENV_FILE"
    echo "Dashboard bind: $DASHBOARD_BIND"
    echo
    echo "Service status:"
    printf '  sdac-bot:       %s\n' "$(systemctl is-active sdac-bot 2>/dev/null || echo unknown)"
    printf '  sdac-dashboard: %s\n' "$(systemctl is-active sdac-dashboard 2>/dev/null || echo unknown)"
    if [[ "$RELOAD_NGINX" == "1" ]] && systemctl list-unit-files nginx.service >/dev/null 2>&1; then
        printf '  nginx:          %s\n' "$(systemctl is-active nginx 2>/dev/null || echo unknown)"
    fi
    echo
    echo "Useful commands:"
    echo "  journalctl -u sdac-bot -n 80 --no-pager"
    echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
    echo "  curl http://127.0.0.1:5000/health"
    if [[ -n "$DOMAIN" ]]; then
        echo "  curl -I https://$DOMAIN/health"
    fi
    UPDATE_FINISHED=1
}

if [[ "$(uname -s)" != "Linux" ]]; then
    fail "This updater is intended for Ubuntu/Linux servers."
fi

if [[ "$INSTALL_COMMAND" == "1" ]]; then
    install_update_command
    exit 0
fi

if [[ "${SDAC_UPDATE_MODE:-auto}" != "installer" && -f "$APP_DIR/docker-compose.yml" && -d "$APP_DIR/.git" ]]; then
    if [[ "$ROLLBACK_MODE" == "1" ]]; then
        fail "Rollback is only supported for installer/systemd installs. Use git checkout and docker compose up for Docker rollbacks."
    fi
    run_git_docker_update
    exit 0
fi

need_command sudo
need_command sed
need_command chmod
need_command systemctl

if [[ "$ROLLBACK_MODE" == "1" ]]; then
    run_rollback
    exit 0
fi

download_installer

say "Running release installer"
SDAC_APP_DIR="$APP_DIR" \
SDAC_APP_USER="$APP_USER" \
SDAC_CREATE_APP_USER="${SDAC_CREATE_APP_USER:-0}" \
SDAC_ENV_FILE="$ENV_FILE" \
SDAC_DASHBOARD_BIND="$DASHBOARD_BIND" \
"$INSTALLER_PATH"

restart_services
run_optional_checks
run_update_health_check
print_summary
