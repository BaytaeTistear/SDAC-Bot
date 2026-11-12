#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${SANA_APP_DIR:-${SDAC_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"
CONFIG_FILE="${SANA_CONFIG_FILE:-${SDAC_CONFIG_FILE:-$APP_DIR/config.json}}"
DB_FILE="${SANA_DB_FILE:-${SDAC_DB_FILE:-$APP_DIR/sdac.db}}"
MEDIA_DIR="${SANA_MEDIA_DIR:-${SDAC_MEDIA_DIR:-$APP_DIR/media}}"
ENV_FILE="${SANA_ENV_FILE:-${SDAC_ENV_FILE:-/etc/sana-bot/sana.env}}"
OUTPUT_OWNER="${SUDO_USER:-$(id -un)}"
OUTPUT_HOME="$(getent passwd "$OUTPUT_OWNER" 2>/dev/null | cut -d: -f6 || true)"
OUTPUT_HOME="${OUTPUT_HOME:-$HOME}"
OUTPUT_FILE="${1:-$OUTPUT_HOME/sana-recovery-$(date -u +%Y%m%d-%H%M%S).tar.gz.enc}"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

for command_name in python3 tar openssl; do
    command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required."
done

[[ -f "$CONFIG_FILE" ]] || fail "Configuration file not found: $CONFIG_FILE"
[[ -f "$DB_FILE" ]] || fail "SQLite database not found: $DB_FILE"
[[ -d "$MEDIA_DIR" ]] || fail "Media directory not found: $MEDIA_DIR"
[[ -r "$ENV_FILE" ]] || fail "Cannot read $ENV_FILE. Run with sudo or set SANA_ENV_FILE to the bot's environment file."

if [[ "${SDAC_DATABASE_URL:-}" =~ ^postgres(ql)?:// ]] || python3 - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path

for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if line.startswith("export "):
        line = line[7:].lstrip()
    key, separator, value = line.partition("=")
    if separator and key.strip() == "SDAC_DATABASE_URL":
        value = value.strip().strip("\"'")
        if value.casefold().startswith(("postgres://", "postgresql://")):
            raise SystemExit(0)
raise SystemExit(1)
PY
then
    fail "This recovery bundle currently supports SQLite. Create a PostgreSQL dump with pg_dump before migrating this server."
fi

if ! grep -Eq '^[[:space:]]*(export[[:space:]]+)?(DISCORD_TOKEN|SANA_DISCORD_TOKEN|SDAC_DISCORD_TOKEN)=' "$ENV_FILE"; then
    fail "The environment file does not contain a Discord bot token; refusing to create an incomplete recovery bundle."
fi
INCLUDE_SECRET_FILE=0
if ! grep -Eq '^[[:space:]]*(export[[:space:]]+)?(SANA_SECRET_KEY|SDAC_SECRET_KEY)=.+[^[:space:]]' "$ENV_FILE"; then
    [[ -s "$APP_DIR/.sdac_secret_key" ]] || fail "No Sana encryption key was found in the environment file or $APP_DIR/.sdac_secret_key."
    INCLUDE_SECRET_FILE=1
fi

if [[ -n "$(find "$MEDIA_DIR" ! -type d ! -type f -print -quit)" ]]; then
    fail "Media contains a symbolic link or special file. Resolve it before creating a portable recovery bundle."
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"
OUTPUT_FILE="$(cd "$(dirname "$OUTPUT_FILE")" && pwd)/$(basename "$OUTPUT_FILE")"
[[ ! -e "$OUTPUT_FILE" ]] || fail "Output already exists: $OUTPUT_FILE"

WORK_DIR="$(mktemp -d)"
chmod 700 "$WORK_DIR"
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

STAGE_DIR="$WORK_DIR/bundle"
mkdir -p "$STAGE_DIR/secrets"
chmod 700 "$STAGE_DIR/secrets"
cp "$CONFIG_FILE" "$STAGE_DIR/config.json"
cp "$ENV_FILE" "$STAGE_DIR/secrets/sana.env"
chmod 600 "$STAGE_DIR/secrets/sana.env"
if [[ "$INCLUDE_SECRET_FILE" == "1" ]]; then
    cp "$APP_DIR/.sdac_secret_key" "$STAGE_DIR/secrets/sdac_secret_key"
    chmod 600 "$STAGE_DIR/secrets/sdac_secret_key"
fi
SDAC_SOURCE_DB="$DB_FILE" SDAC_TARGET_DB="$STAGE_DIR/sdac.db" python3 - <<'PY'
import os
import sqlite3
import sys

source = sqlite3.connect(f"file:{os.environ['SDAC_SOURCE_DB']}?mode=ro", uri=True, timeout=30)
target = sqlite3.connect(os.environ["SDAC_TARGET_DB"])
try:
    source.backup(target)
    result = target.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Database integrity check failed: {result}")
finally:
    target.close()
    source.close()
PY

python3 - "$STAGE_DIR/metadata.json" "$APP_DIR/RELEASE.md" <<'PY'
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

release_path = Path(sys.argv[2])
release = release_path.read_text(encoding="utf-8").splitlines()[0] if release_path.is_file() else "unknown"
Path(sys.argv[1]).write_text(
    json.dumps({
        "format": "sana-recovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_host": socket.gethostname(),
        "source_release": release,
        "database": "sqlite",
    }, indent=2) + "\n",
    encoding="utf-8",
)
PY

python3 - "$STAGE_DIR/config.json" "$STAGE_DIR/sdac.db" <<'PY'
import json
import sqlite3
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    if not isinstance(json.load(stream), dict):
        raise SystemExit("Configuration must be a JSON object.")
connection = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
try:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Database integrity check failed: {result}")
finally:
    connection.close()
PY

read -r -s -p "Choose a recovery bundle passphrase (12+ characters): " PASSPHRASE
echo
[[ ${#PASSPHRASE} -ge 12 ]] || fail "Use a passphrase with at least 12 characters."
read -r -s -p "Enter it again: " PASSPHRASE_CONFIRM
echo
[[ "$PASSPHRASE" == "$PASSPHRASE_CONFIRM" ]] || fail "Passphrases do not match."
PASSPHRASE_FILE="$WORK_DIR/passphrase"
printf '%s\n' "$PASSPHRASE" > "$PASSPHRASE_FILE"
chmod 600 "$PASSPHRASE_FILE"

tar -czf - -C "$STAGE_DIR" config.json sdac.db metadata.json secrets \
    -C "$MEDIA_DIR" --transform='s,^\./,media/,' . |
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 250000 -md sha256 \
        -pass "file:$PASSPHRASE_FILE" -out "$OUTPUT_FILE"
chmod 600 "$OUTPUT_FILE"
if ! openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 250000 -md sha256 \
    -pass "file:$PASSPHRASE_FILE" -in "$OUTPUT_FILE" | tar -tzf - >/dev/null; then
    rm -f "$OUTPUT_FILE"
    fail "The encrypted recovery bundle did not pass its archive check."
fi
if [[ "$(id -u)" == "0" && "$OUTPUT_OWNER" != "root" ]]; then
    chown "$OUTPUT_OWNER" "$OUTPUT_FILE"
fi
unset PASSPHRASE PASSPHRASE_CONFIRM
rm -f "$PASSPHRASE_FILE"

echo "Recovery bundle created: $OUTPUT_FILE"
echo "The bundle contains configuration, a consistent SQLite snapshot, media, and the environment secrets."
echo "Keep the passphrase separately. The bundle is needed to recover the Discord token and encryption key."
