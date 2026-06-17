#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:-${SDAC_DOMAIN:-}}"
DASHBOARD_LOCAL_URL="${SDAC_DASHBOARD_LOCAL_URL:-http://127.0.0.1:5000/health}"
RUN_CERTBOT_DRY_RUN="${SDAC_RUN_CERTBOT_DRY_RUN:-0}"

check() {
    local label="$1"
    shift
    printf 'Checking %-34s' "$label"
    if "$@" >/dev/null 2>&1; then
        echo " ok"
    else
        echo " failed"
        return 1
    fi
}

check "sdac-bot service" systemctl is-active --quiet sdac-bot
check "sdac-dashboard service" systemctl is-active --quiet sdac-dashboard

if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
    check "nginx service" systemctl is-active --quiet nginx
    check "nginx config" sudo nginx -t
fi

if command -v curl >/dev/null 2>&1; then
    check "local dashboard health" curl -fsS "$DASHBOARD_LOCAL_URL"
    if [[ -n "$DOMAIN" ]]; then
        check "public HTTPS health" curl -fsS "https://$DOMAIN/health"
    fi
fi

if [[ "$RUN_CERTBOT_DRY_RUN" == "1" ]]; then
    check "certbot renew dry-run" sudo certbot renew --dry-run
else
    echo "Skipping certbot dry-run. Set SDAC_RUN_CERTBOT_DRY_RUN=1 to include it."
fi

echo "Production check complete."
