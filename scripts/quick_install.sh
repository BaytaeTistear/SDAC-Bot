#!/usr/bin/env bash
set -Eeuo pipefail

# Public one-line installer bootstrap. The full installer is downloaded to a
# temporary file so its interactive setup can continue reading from the user's
# terminal instead of from a curl pipe.

REPO="${SANA_GITHUB_REPO:-BaytaeTistear/SDAC-Bot}"
RELEASE_TAG="${SANA_RELEASE_TAG:-latest-experimental}"
INSTALLER_NAME="Sana-Chan-Linux-Installer.sh"
BASE_URL="https://github.com/${REPO}/releases/download/${RELEASE_TAG}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl is required. On Ubuntu run: sudo apt-get update && sudo apt-get install -y curl"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required (normally provided by coreutils)."
command -v mktemp >/dev/null 2>&1 || fail "mktemp is required."

if [[ "$(uname -s)" != "Linux" ]]; then
    fail "The one-line installer is for Linux servers. Use the Windows installer on Windows."
fi

if [[ -z "${SANA_APP_USER:-}" ]]; then
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        SANA_APP_USER="$SUDO_USER"
    elif id ubuntu >/dev/null 2>&1; then
        SANA_APP_USER="ubuntu"
    else
        SANA_APP_USER="$(id -un)"
    fi
fi

if [[ -z "${SANA_APP_DIR:-}" ]]; then
    APP_HOME="$(getent passwd "$SANA_APP_USER" 2>/dev/null | cut -d: -f6 || true)"
    if [[ -z "$APP_HOME" || "$APP_HOME" == "/" ]]; then
        APP_HOME="/opt"
    fi
    SANA_APP_DIR="${APP_HOME%/}/discord-screenshot-bot"
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Downloading Sana-Chan ${RELEASE_TAG} from ${REPO}"
curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
    --retry 3 \
    "$BASE_URL/$INSTALLER_NAME" -o "$TMP_DIR/$INSTALLER_NAME"
curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
    --retry 3 \
    "$BASE_URL/$INSTALLER_NAME.sha256" -o "$TMP_DIR/$INSTALLER_NAME.sha256"

(
    cd "$TMP_DIR"
    sha256sum --check "$INSTALLER_NAME.sha256"
)

chmod 700 "$TMP_DIR/$INSTALLER_NAME"
export SANA_APP_USER SANA_APP_DIR

echo "Installing into $SANA_APP_DIR as $SANA_APP_USER"
echo "Existing configuration, database, media, and environment files are preserved."
bash "$TMP_DIR/$INSTALLER_NAME" "$@"
