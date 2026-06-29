#!/usr/bin/env python3
"""Create or reset an SDAC dashboard admin account from the server shell."""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash


def app_dir():
    return Path(os.getenv("SDAC_APP_DIR", Path(__file__).resolve().parents[1])).resolve()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reset or create an SDAC dashboard admin login."
    )
    parser.add_argument(
        "--username",
        default="owner",
        help="Dashboard username to create/update. Default: owner",
    )
    parser.add_argument(
        "--role",
        default="owner",
        choices=("moderator", "admin", "owner"),
        help="Dashboard role. Default: owner",
    )
    parser.add_argument(
        "--password",
        default="",
        help="New password. Omit this to be prompted securely.",
    )
    parser.add_argument(
        "--guild-ids",
        default="",
        help="Optional comma/space-separated guild IDs. Blank means all servers.",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("SDAC_DB_FILE", ""),
        help="Path to sdac.db. Defaults to SDAC_DB_FILE or ./sdac.db.",
    )
    return parser.parse_args()


def prompt_password():
    password = getpass.getpass("New dashboard password: ")
    confirm = getpass.getpass("Confirm dashboard password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 10:
        raise SystemExit("Use at least 10 characters for the dashboard password.")
    return password


def parse_guild_scope(raw_value):
    values = [
        value.strip()
        for value in str(raw_value or "").replace(",", " ").split()
        if value.strip()
    ]
    invalid = [value for value in values if not value.isdigit()]
    if invalid:
        raise SystemExit(f"Guild IDs must be numeric: {', '.join(invalid)}")
    return sorted(set(values))


def main():
    args = parse_args()
    root = app_dir()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from database_backend import connect_database
    from database_migrations import apply_database_migrations

    username = args.username.strip().casefold() or "owner"
    password = args.password or prompt_password()
    guild_scope = parse_guild_scope(args.guild_ids)
    db_path = Path(args.db) if args.db else root / "sdac.db"
    now = datetime.now(timezone.utc).isoformat()

    connection = connect_database(db_path, timeout=30)
    try:
        apply_database_migrations(connection)
        connection.execute("""
            INSERT INTO dashboard_admin_users (
                username, password_hash, role, disabled,
                created_at, updated_at, guild_ids_json
            )
            VALUES (?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role,
                disabled = 0,
                guild_ids_json = excluded.guild_ids_json,
                updated_at = excluded.updated_at
        """, (
            username,
            generate_password_hash(password),
            args.role,
            now,
            now,
            json.dumps(guild_scope, separators=(",", ":")),
        ))
        connection.execute("""
            INSERT INTO admin_audit_log (
                guild_id, action, actor_user_id, actor_username,
                target_type, target_id, details, created_at
            )
            VALUES ('', 'cli_reset_dashboard_admin', 'system', 'server shell',
                    'dashboard_user', ?, ?, ?)
        """, (
            username,
            f"Reset dashboard login for {username} as {args.role}.",
            now,
        ))
        connection.commit()
    finally:
        connection.close()

    scope_label = "all servers" if not guild_scope else ", ".join(guild_scope)
    print(f"Dashboard admin '{username}' saved as {args.role} for {scope_label}.")


if __name__ == "__main__":
    main()
