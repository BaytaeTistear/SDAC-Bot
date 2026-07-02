#!/usr/bin/env bash
set -Eeuo pipefail

ENV_DIR="${SDAC_ENV_DIR:-/etc/sdac-bot}"
ENV_FILE="${SDAC_ENV_FILE:-$ENV_DIR/sdac.env}"
LEGACY_ENV_FILE="${SDAC_LEGACY_ENV_FILE:-/etc/sdac.env}"
SERVICES="${SDAC_SERVICES:-sdac-bot sdac-dashboard}"

if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$LEGACY_ENV_FILE" ]]; then
        echo "Copying legacy environment file $LEGACY_ENV_FILE to $ENV_FILE"
        sudo mkdir -p "$ENV_DIR"
        sudo install -m 600 -o root -g root "$LEGACY_ENV_FILE" "$ENV_FILE"
    else
        echo "Environment file not found: $ENV_FILE" >&2
        echo "Legacy environment file not found: $LEGACY_ENV_FILE" >&2
        echo "Run scripts/install_ubuntu.sh to create $ENV_FILE." >&2
        exit 1
    fi
else
    echo "Found canonical environment file: $ENV_FILE"
fi

sudo chown root:root "$ENV_FILE"
sudo chmod 600 "$ENV_FILE"

for service in $SERVICES; do
    DROPIN_DIR="/etc/systemd/system/$service.service.d"
    DROPIN_FILE="$DROPIN_DIR/10-sdac-env.conf"
    TMP_FILE="$(mktemp)"
    cat > "$TMP_FILE" <<EOF
[Service]
EnvironmentFile=
EnvironmentFile=$ENV_FILE
EOF
    sudo mkdir -p "$DROPIN_DIR"
    sudo install -m 644 -o root -g root "$TMP_FILE" "$DROPIN_FILE"
    rm -f "$TMP_FILE"
    echo "Installed $DROPIN_FILE"
done

sudo systemctl daemon-reload

for service in $SERVICES; do
    if systemctl list-unit-files "$service.service" >/dev/null 2>&1; then
        sudo systemctl restart "$service"
        sudo systemctl is-active --quiet "$service"
        echo "$service is active"
    fi
done

echo "Environment standardization complete."
