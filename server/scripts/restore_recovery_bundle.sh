#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 /path/to/sana-recovery-YYYYMMDD-HHMMSS.tar.gz.enc" >&2
    exit 2
fi

APP_DIR="${SANA_APP_DIR:-${SDAC_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"
ENV_FILE="${SANA_ENV_FILE:-${SDAC_ENV_FILE:-/etc/sana-bot/sana.env}}"
BUNDLE_FILE="$1"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

for command_name in python3 tar openssl; do
    command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required."
done
[[ -f "$BUNDLE_FILE" ]] || fail "Recovery bundle not found: $BUNDLE_FILE"
[[ -d "$APP_DIR" ]] || fail "Application directory not found: $APP_DIR"

if [[ -e "$APP_DIR/config.json" || -e "$APP_DIR/sdac.db" || -e "$APP_DIR/.sdac_secret_key" || -e "$ENV_FILE" ]] || \
   { [[ -d "$APP_DIR/media" ]] && [[ -n "$(find "$APP_DIR/media" -mindepth 1 -print -quit)" ]]; }; then
    fail "The target already contains config, database, environment, or media data. Move it aside before restoring; this command will not overwrite it."
fi

WORK_DIR="$(mktemp -d)"
chmod 700 "$WORK_DIR"
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

read -r -s -p "Recovery bundle passphrase: " PASSPHRASE
echo
PASSPHRASE_FILE="$WORK_DIR/passphrase"
printf '%s\n' "$PASSPHRASE" > "$PASSPHRASE_FILE"
chmod 600 "$PASSPHRASE_FILE"
if ! openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 250000 -md sha256 \
    -pass "file:$PASSPHRASE_FILE" -in "$BUNDLE_FILE" -out "$WORK_DIR/sana-recovery.tar.gz"; then
    unset PASSPHRASE
    fail "Unable to decrypt the bundle. Check the passphrase and try again."
fi
unset PASSPHRASE
rm -f "$PASSPHRASE_FILE"

python3 - "$WORK_DIR/sana-recovery.tar.gz" "$WORK_DIR/restore" <<'PY'
import json
import sqlite3
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
required = {"config.json", "sdac.db", "metadata.json", "secrets/sana.env"}
allowed_extra = {".", "./", "secrets", "secrets/sdac_secret_key"}
seen = set()
with tarfile.open(archive_path, "r:gz") as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Unsafe archive path: {member.name}")
        if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
            raise SystemExit(f"Unsupported archive entry: {member.name}")
        if member.name not in required and member.name not in allowed_extra and member.name != "media" and not member.name.startswith("media/"):
            raise SystemExit(f"Unexpected archive entry: {member.name}")
        seen.add(member.name)
    if not required.issubset(seen):
        raise SystemExit("The recovery bundle is missing required files.")
    metadata = json.load(archive.extractfile("metadata.json"))
    if metadata.get("format") != "sana-recovery-v1" or metadata.get("database") != "sqlite":
        raise SystemExit("Unsupported or invalid Sana recovery bundle format.")
    config = json.load(archive.extractfile("config.json"))
    if not isinstance(config, dict):
        raise SystemExit("Configuration must be a JSON object.")
    env_data = archive.extractfile("secrets/sana.env").read()
    if b"DISCORD_TOKEN=" not in env_data and b"SANA_DISCORD_TOKEN=" not in env_data and b"SDAC_DISCORD_TOKEN=" not in env_data:
        raise SystemExit("The recovery bundle does not include a Discord token.")
    secret_file = "secrets/sdac_secret_key" in seen
    if b"SANA_SECRET_KEY=" not in env_data and b"SDAC_SECRET_KEY=" not in env_data and not secret_file:
        raise SystemExit("The recovery bundle does not include the encryption key.")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive.extractall(destination)

database = sqlite3.connect(f"file:{destination / 'sdac.db'}?mode=ro", uri=True)
try:
    if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Database integrity check failed.")
finally:
    database.close()
PY

STAGE_DIR="$WORK_DIR/restore"
install -m 600 "$STAGE_DIR/config.json" "$APP_DIR/config.json"
install -m 600 "$STAGE_DIR/sdac.db" "$APP_DIR/sdac.db"
mkdir -p "$APP_DIR/media"
cp -a "$STAGE_DIR/media/." "$APP_DIR/media/"
sudo mkdir -p "$(dirname "$ENV_FILE")"
sudo install -m 600 -o root -g root "$STAGE_DIR/secrets/sana.env" "$ENV_FILE"
if [[ -f "$STAGE_DIR/secrets/sdac_secret_key" ]]; then
    install -m 600 "$STAGE_DIR/secrets/sdac_secret_key" "$APP_DIR/.sdac_secret_key"
fi

echo "Recovery data restored into $APP_DIR"
echo "Environment secrets restored to $ENV_FILE with mode 600."
echo "The installer will next install the current Sana-Chan application code and services."
