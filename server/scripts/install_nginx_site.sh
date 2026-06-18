#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
DOMAIN="${1:-${SDAC_DOMAIN:-}}"
UPSTREAM="${SDAC_DASHBOARD_UPSTREAM:-127.0.0.1:5000}"
CLIENT_MAX_BODY_SIZE="${SDAC_CLIENT_MAX_BODY_SIZE:-100M}"
SITE_NAME="${SDAC_NGINX_SITE_NAME:-sdac-dashboard}"
TEMPLATE="${SDAC_NGINX_TEMPLATE:-$APP_DIR/nginx/sdac-dashboard.conf.template}"
AVAILABLE="/etc/nginx/sites-available/$SITE_NAME"
ENABLED="/etc/nginx/sites-enabled/$SITE_NAME"

if [[ -z "$DOMAIN" ]]; then
    read -r -p "Domain name for the dashboard: " DOMAIN
fi

if [[ -z "$DOMAIN" ]]; then
    echo "Domain name cannot be blank." >&2
    exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
    echo "Nginx template not found: $TEMPLATE" >&2
    exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx is required. Install it first: sudo apt install nginx" >&2
    exit 1
fi

echo "Installing Nginx site $SITE_NAME for $DOMAIN"
echo "Proxy upstream: $UPSTREAM"
echo "Upload limit: $CLIENT_MAX_BODY_SIZE"

TMP_FILE="$(mktemp)"
cleanup() {
    rm -f "$TMP_FILE"
}
trap cleanup EXIT

sed \
    -e "s#__DOMAIN__#$DOMAIN#g" \
    -e "s#__DASHBOARD_UPSTREAM__#$UPSTREAM#g" \
    -e "s#__CLIENT_MAX_BODY_SIZE__#$CLIENT_MAX_BODY_SIZE#g" \
    "$TEMPLATE" > "$TMP_FILE"

sudo install -m 644 -o root -g root "$TMP_FILE" "$AVAILABLE"
sudo ln -sfn "$AVAILABLE" "$ENABLED"

if sudo grep -R "server_name[[:space:]]\\+$DOMAIN" /etc/nginx/sites-enabled 2>/dev/null | grep -v "$ENABLED" >/dev/null 2>&1; then
    echo "Warning: another enabled Nginx site also references $DOMAIN." >&2
    echo "If nginx reports a conflicting server name, remove the duplicate site." >&2
fi

sudo nginx -t
sudo systemctl reload nginx

echo "Nginx site installed."
echo "Next HTTPS command:"
echo "  sudo certbot --nginx -d $DOMAIN --cert-name $DOMAIN --key-type rsa"
