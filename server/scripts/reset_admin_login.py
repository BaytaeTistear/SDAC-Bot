#!/usr/bin/env python3
"""Manage SDAC dashboard accounts from the server shell."""

import argparse
import getpass
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash


ROLE_LEVELS = {
    "user": 0,
    "trusted": 0,
    "moderator": 1,
    "admin": 2,
    "owner": 3,
}
LEGACY_DEFAULT_USERS = ("owner", "admin", "web-admin")


def app_dir():
    return Path(os.getenv("SDAC_APP_DIR", Path(__file__).resolve().parents[1])).resolve()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create, update, list, disable, enable, or delete SDAC dashboard accounts."
    )
    parser.add_argument(
        "--username",
        default="",
        help="Dashboard username. Required unless --list or --delete-defaults is used.",
    )
    parser.add_argument(
        "--email",
        default="",
        help="Optional account email address.",
    )
    parser.add_argument(
        "--display-name",
        default="",
        help="Optional display name shown in the dashboard.",
    )
    parser.add_argument(
        "--discord-user-id",
        default="",
        help="Optional Discord user ID to link with My Submissions.",
    )
    parser.add_argument(
        "--role",
        default="owner",
        choices=tuple(ROLE_LEVELS.keys()),
        help="Dashboard role. Default: owner",
    )
    parser.add_argument(
        "--password",
        default="",
        help="New password. Omit this to be prompted securely when creating/updating.",
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
    parser.add_argument(
        "--list",
        action="store_true",
        help="List dashboard accounts.",
    )
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable the named account.",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable the named account.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the named account.",
    )
    parser.add_argument(
        "--delete-defaults",
        action="store_true",
        help="Delete legacy default usernames: owner, admin, and web-admin.",
    )
    parser.add_argument(
        "--no-password",
        action="store_true",
        help="Update role/email/scope without changing the password.",
    )
    return parser.parse_args()


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def prompt_password():
    password = getpass.getpass("New dashboard password: ")
    confirm = getpass.getpass("Confirm dashboard password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 10:
        raise SystemExit("Use at least 10 characters for the dashboard password.")
    return password


def normalize_email(email):
    value = str(email or "").strip().casefold()
    if not value:
        return ""
    if len(value) > 254 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        raise SystemExit("Enter a valid email address.")
    return value


def normalize_username(username, email=""):
    value = str(username or "").strip().casefold()
    if not value and email:
        value = email.split("@", 1)[0].casefold()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value).strip("-._")
    if not value:
        raise SystemExit("A username is required when it cannot be derived from email.")
    if not re.match(r"^[a-z0-9_.-]{3,40}$", value):
        raise SystemExit(
            "Username must be 3-40 letters, numbers, dots, dashes, or underscores."
        )
    return value


def normalize_discord_user_id(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if not value.isdigit() or len(value) < 15 or len(value) > 25:
        raise SystemExit("Discord user ID must be numeric.")
    return value


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


def print_accounts(connection):
    rows = connection.execute("""
        SELECT username, email, display_name, discord_user_id, role, disabled,
               guild_ids_json, created_at, updated_at, last_login_at
        FROM dashboard_admin_users
        ORDER BY disabled ASC, role DESC, username ASC
    """).fetchall()
    if not rows:
        print("No dashboard accounts exist yet.")
        return
    for row in rows:
        scope = json.loads(row["guild_ids_json"] or "[]")
        scope_label = "all servers" if not scope else ", ".join(scope)
        status = "disabled" if int(row["disabled"] or 0) else "active"
        email = row["email"] or "-"
        display = row["display_name"] or "-"
        discord_user_id = row["discord_user_id"] or "-"
        last_login = row["last_login_at"] or "never"
        print(
            f"{row['username']:24} {row['role']:10} {status:8} "
            f"{email:32} {display:24} discord={discord_user_id} "
            f"{scope_label} last={last_login}"
        )


def audit(connection, action, username, details):
    connection.execute("""
        INSERT INTO admin_audit_log (
            guild_id, action, actor_user_id, actor_username,
            target_type, target_id, details, created_at
        )
        VALUES ('', ?, 'system', 'server shell',
                'dashboard_user', ?, ?, ?)
    """, (action, username, details, utc_now_iso()))


def main():
    args = parse_args()
    root = app_dir()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from database_backend import connect_database
    from database_migrations import apply_database_migrations

    db_path = Path(args.db) if args.db else root / "sdac.db"
    connection = connect_database(db_path, timeout=30)
    try:
        apply_database_migrations(connection)
        connection.commit()

        if args.list:
            print_accounts(connection)
            return

        if args.delete_defaults:
            placeholders = ",".join("?" for _ in LEGACY_DEFAULT_USERS)
            connection.execute(
                f"DELETE FROM dashboard_admin_users WHERE username IN ({placeholders})",
                LEGACY_DEFAULT_USERS,
            )
            audit(
                connection,
                "cli_delete_legacy_dashboard_defaults",
                ",".join(LEGACY_DEFAULT_USERS),
                "Deleted legacy default dashboard usernames.",
            )
            connection.commit()
            print("Deleted legacy default dashboard usernames: owner, admin, web-admin.")
            return

        email = normalize_email(args.email)
        discord_user_id = normalize_discord_user_id(args.discord_user_id)
        username = normalize_username(args.username, email)
        now = utc_now_iso()

        if args.delete:
            connection.execute(
                "DELETE FROM dashboard_admin_users WHERE username = ?",
                (username,),
            )
            audit(connection, "cli_delete_dashboard_account", username, "Deleted account.")
            connection.commit()
            print(f"Deleted dashboard account '{username}'.")
            return

        if args.disable or args.enable:
            disabled = 0 if args.enable else 1
            connection.execute("""
                UPDATE dashboard_admin_users
                SET disabled = ?, updated_at = ?
                WHERE username = ?
            """, (disabled, now, username))
            action = "enabled" if args.enable else "disabled"
            audit(
                connection,
                f"cli_{action}_dashboard_account",
                username,
                f"{action.title()} account.",
            )
            connection.commit()
            print(f"{action.title()} dashboard account '{username}'.")
            return

        existing = connection.execute("""
            SELECT username
            FROM dashboard_admin_users
            WHERE username = ?
        """, (username,)).fetchone()
        password_hash = None
        if not args.no_password:
            password = args.password or prompt_password()
            password_hash = generate_password_hash(password)
        elif not existing:
            raise SystemExit("--no-password can only be used for existing accounts.")

        guild_scope = parse_guild_scope(args.guild_ids)
        guild_scope_json = json.dumps(guild_scope, separators=(",", ":"))
        if discord_user_id:
            existing_discord_id = connection.execute("""
                SELECT username
                FROM dashboard_admin_users
                WHERE discord_user_id = ?
                  AND username != ?
                LIMIT 1
            """, (discord_user_id, username)).fetchone()
            if existing_discord_id:
                raise SystemExit("That Discord user ID is already linked.")
        if password_hash:
            connection.execute("""
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, discord_user_id,
                    password_hash, role, disabled, created_at, updated_at, guild_ids_json,
                    approved_by, approved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'server shell', ?)
                ON CONFLICT(username) DO UPDATE SET
                    email = excluded.email,
                    display_name = excluded.display_name,
                    discord_user_id = excluded.discord_user_id,
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    disabled = 0,
                    guild_ids_json = excluded.guild_ids_json,
                    approved_by = 'server shell',
                    approved_at = excluded.approved_at,
                    updated_at = excluded.updated_at
            """, (
                username,
                email,
                args.display_name.strip()[:120],
                discord_user_id,
                password_hash,
                args.role,
                now,
                now,
                guild_scope_json,
                now,
            ))
        else:
            connection.execute("""
                UPDATE dashboard_admin_users
                SET email = ?, display_name = ?, discord_user_id = ?,
                    role = ?, disabled = 0, guild_ids_json = ?,
                    approved_by = COALESCE(approved_by, 'server shell'),
                    approved_at = COALESCE(approved_at, ?), updated_at = ?
                WHERE username = ?
            """, (
                email,
                args.display_name.strip()[:120],
                discord_user_id,
                args.role,
                guild_scope_json,
                now,
                now,
                username,
            ))
        audit(
            connection,
            "cli_save_dashboard_account",
            username,
            f"Saved dashboard login for {username} as {args.role}.",
        )
        connection.commit()
    finally:
        connection.close()

    scope_label = "all servers" if not parse_guild_scope(args.guild_ids) else args.guild_ids
    print(f"Dashboard account '{username}' saved as {args.role} for {scope_label}.")


if __name__ == "__main__":
    main()
