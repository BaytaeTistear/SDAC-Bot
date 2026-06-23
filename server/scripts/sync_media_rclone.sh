#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
REMOTE="${1:-${SDAC_MEDIA_RCLONE_REMOTE:-}}"
MEDIA_DIR="${SDAC_MEDIA_DIR:-$APP_DIR/media}"

if [[ -z "$REMOTE" ]]; then
    echo "Set SDAC_MEDIA_RCLONE_REMOTE or pass an rclone remote destination." >&2
    echo "Example: SDAC_MEDIA_RCLONE_REMOTE=drive:sdac-media bash scripts/sync_media_rclone.sh" >&2
    exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "rclone is required for media mirroring." >&2
    echo "Install it with: sudo apt install rclone" >&2
    exit 1
fi

if [[ ! -d "$MEDIA_DIR" ]]; then
    echo "Media folder does not exist yet: $MEDIA_DIR"
    exit 0
fi

rclone sync "$MEDIA_DIR" "$REMOTE" \
    --copy-links \
    --fast-list \
    --transfers "${SDAC_RCLONE_TRANSFERS:-4}" \
    --checkers "${SDAC_RCLONE_CHECKERS:-8}"

echo "Media mirror complete: $REMOTE"
