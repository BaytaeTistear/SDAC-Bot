#!/usr/bin/env bash
set -Eeuo pipefail

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    SUDO="sudo"
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This helper currently supports Ubuntu/Debian servers with apt-get." >&2
    echo "Install these packages manually: rclone zip unzip ca-certificates." >&2
    exit 1
fi

echo "Installing SDAC backup prerequisites."
$SUDO apt-get update
$SUDO apt-get install -y rclone zip unzip ca-certificates

echo
echo "Installed versions:"
rclone version | sed -n '1,3p' || true
zip -v | sed -n '1p' || true
unzip -v | sed -n '1p' || true

echo
echo "Next steps:"
echo "  1. Run: rclone config"
echo "  2. Add Google Drive, OneDrive, Dropbox, Mega, S3, B2, Box, or SFTP."
echo "  3. In Discord, run: /backupguide provider"
echo "  4. In Discord, run: /backupsetup provider remote"
echo "  5. Test it with: /backupnow upload:true"
