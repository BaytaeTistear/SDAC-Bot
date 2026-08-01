#!/usr/bin/env bash
set -Eeuo pipefail

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    SUDO="sudo"
fi

install_backup_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "Installing Sana-Chan backup prerequisites with apt."
        $SUDO apt-get update
        $SUDO apt-get install -y rclone zip unzip ca-certificates
        return
    fi

    if command -v dnf >/dev/null 2>&1; then
        echo "Installing Sana-Chan backup prerequisites with dnf."
        $SUDO dnf install -y rclone zip unzip ca-certificates
        return
    fi

    if command -v yum >/dev/null 2>&1; then
        echo "Installing Sana-Chan backup prerequisites with yum."
        $SUDO yum install -y rclone zip unzip ca-certificates
        return
    fi

    if command -v apk >/dev/null 2>&1; then
        echo "Installing Sana-Chan backup prerequisites with apk."
        $SUDO apk add --no-cache rclone zip unzip ca-certificates
        return
    fi

    if command -v pacman >/dev/null 2>&1; then
        echo "Installing Sana-Chan backup prerequisites with pacman."
        $SUDO pacman -Sy --needed --noconfirm rclone zip unzip ca-certificates
        return
    fi

    echo "No supported package manager was found." >&2
    echo "Install these packages manually: rclone zip unzip ca-certificates." >&2
    exit 1
}

install_backup_packages

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
