#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SDAC_APP_DIR:-$(pwd)}"
OUT_DIR="${SDAC_SUPPORT_BUNDLE_DIR:-$APP_DIR/backups/support-bundles}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BUNDLE_DIR="$OUT_DIR/$STAMP"
ARCHIVE="$OUT_DIR/sdac-support-$STAMP.tar.gz"

mkdir -p "$BUNDLE_DIR"

run_capture() {
    local name="$1"
    shift
    {
        echo "\$ $*"
        "$@"
    } >"$BUNDLE_DIR/$name.txt" 2>&1 || true
}

run_capture "system" uname -a
run_capture "disk" df -h "$APP_DIR"
run_capture "files" find "$APP_DIR" -maxdepth 2 -type f
run_capture "git" git -C "$APP_DIR" status --short

if command -v systemctl >/dev/null 2>&1; then
    run_capture "sdac-bot-service" systemctl status sdac-bot --no-pager
    run_capture "sdac-dashboard-service" systemctl status sdac-dashboard --no-pager
fi

if command -v journalctl >/dev/null 2>&1; then
    run_capture "sdac-bot-journal" journalctl -u sdac-bot -n 120 --no-pager
    run_capture "sdac-dashboard-journal" journalctl -u sdac-dashboard -n 120 --no-pager
fi

if [[ -f "$APP_DIR/config.json" ]]; then
    cp "$APP_DIR/config.json" "$BUNDLE_DIR/config.json"
fi

if [[ -f "$APP_DIR/bot_status.json" ]]; then
    cp "$APP_DIR/bot_status.json" "$BUNDLE_DIR/bot_status.json"
fi

if [[ -f "$APP_DIR/sdac.db" ]]; then
    run_capture "sqlite-tables" sqlite3 "$APP_DIR/sdac.db" ".tables"
    run_capture "sqlite-schema-version" sqlite3 "$APP_DIR/sdac.db" "SELECT * FROM schema_version;"
fi

tar -czf "$ARCHIVE" -C "$OUT_DIR" "$STAMP"
echo "Support bundle created: $ARCHIVE"
