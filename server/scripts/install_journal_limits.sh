#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_DIR="/etc/systemd/journald.conf.d"
CONFIG_FILE="$CONFIG_DIR/sdac.conf"

sudo mkdir -p "$CONFIG_DIR"
sudo tee "$CONFIG_FILE" >/dev/null <<'EOF'
[Journal]
SystemMaxUse=500M
RuntimeMaxUse=100M
MaxRetentionSec=30day
EOF

sudo systemctl restart systemd-journald

echo "Installed journald limits at $CONFIG_FILE"
echo "Current journal disk usage:"
journalctl --disk-usage
