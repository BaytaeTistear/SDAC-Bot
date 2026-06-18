import asyncio
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import TOKEN
from database_migrations import DATABASE_SCHEMA_VERSION, apply_database_migrations
from observability import capture_exception, init_sentry


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE = BASE_DIR / "sdac.db"
MEDIA_DIR = BASE_DIR / "media"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_KEEP_COUNT = 30
SCHEMA_VERSION = DATABASE_SCHEMA_VERSION

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".mov", ".webm", ".mkv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a",
}

USER_COOLDOWN_SECONDS = 30
CATEGORY_COOLDOWN_SECONDS = 5
PUBLIC_CACHE_SECONDS = 45
WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
WEEKDAY_CHOICES = [
    app_commands.Choice(name=name.title(), value=name)
    for name in WEEKDAY_NAMES
]

init_sentry("sdac-bot")

DEFAULT_CONFIG = {
    "guilds": {},
    "limits": {
        "max_file_bytes": 25 * 1024 * 1024,
        "max_total_bytes": 50 * 1024 * 1024,
        "max_text_length": 1500,
        "wrong_guess_timeout_seconds": 600,
        "submission_user_cooldown_seconds": 30,
        "submission_category_cooldown_seconds": 5,
        "guess_command_cooldown_seconds": 2,
        "admin_action_cooldown_seconds": 1,
        "rate_limit_retention_days": 30,
        "orphan_media_cleanup_enabled": True,
        "audit_retention_days": 365,
        "pending_submission_retention_hours": 48,
        "media_warning_bytes": 5 * 1024 * 1024 * 1024,
        "database_warning_bytes": 512 * 1024 * 1024,
        "restore_test_enabled": True,
        "restore_test_weekday": "sunday",
        "restore_test_time_utc": "03:30",
    },
}

DEFAULT_GUILD_CONFIG = {
    "guild_name": "",
    "admin_role_ids": [],
    "submit_channel": None,
    "daily_top_channel": None,
    "daily_top_time_utc": "00:00",
    "weekly_top_day": "sunday",
    "game_summary_channel": None,
    "error_channel": None,
    "timezone": "UTC",
    "approval_enabled": False,
    "approval_channel": None,
    "categories": {},
}

REQUIRED_TABLES = {
    "submissions",
    "category_history",
    "moderation_history",
    "admin_audit_log",
    "daily_runs",
    "guess_games",
    "guess_points",
    "guess_correct_guesses",
    "guess_cooldowns",
    "monthly_guess_runs",
    "daily_guess_runs",
    "monthly_submission_top",
    "schema_version",
    "rate_limit_events",
    "restore_test_runs",
}


def save_config(data):
    with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=4)
        file.write("\n")


def load_config():
    if not CONFIG_FILE.exists():
        data = json.loads(json.dumps(DEFAULT_CONFIG))
        save_config(data)
        return data

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    changed = False
    if "guilds" not in data:
        legacy_config = {
            "submit_channel": data.get("submit_channel"),
            "daily_top_channel": data.get("daily_top_channel"),
            "daily_top_time_utc": data.get(
                "daily_top_time_utc",
                "00:00",
            ),
            "guild_name": data.get("guild_name", ""),
            "admin_role_ids": data.get("admin_role_ids") or [],
            "weekly_top_day": data.get("weekly_top_day", "sunday"),
            "game_summary_channel": data.get("game_summary_channel"),
            "error_channel": data.get("error_channel"),
            "approval_enabled": data.get("approval_enabled", False),
            "approval_channel": data.get("approval_channel"),
            "categories": data.get("categories") or {},
        }
        if any([
            legacy_config["submit_channel"],
            legacy_config["daily_top_channel"],
            legacy_config["approval_channel"],
            legacy_config["categories"],
        ]):
            data["legacy_guild_config"] = legacy_config
        data["guilds"] = {}
        changed = True
    if "limits" not in data:
        data["limits"] = dict(DEFAULT_CONFIG["limits"])
        changed = True

    for key, value in DEFAULT_CONFIG["limits"].items():
        if key not in data["limits"]:
            data["limits"][key] = value
            changed = True

    if changed:
        save_config(data)
    return data


config = load_config()


def migrate_legacy_config():
    legacy_config = config.get("legacy_guild_config")
    if not legacy_config:
        return
    if len(bot.guilds) != 1:
        print(
            "Legacy configuration needs exactly one connected guild "
            "before it can be migrated."
        )
        return

    guild = bot.guilds[0]
    guild_config = get_guild_config(guild.id)
    guild_config.update(legacy_config)
    config.pop("legacy_guild_config", None)
    for key in (
        "guild_name",
        "admin_role_ids",
        "submit_channel",
        "daily_top_channel",
        "daily_top_time_utc",
        "weekly_top_day",
        "game_summary_channel",
        "error_channel",
        "timezone",
        "approval_enabled",
        "approval_channel",
        "categories",
    ):
        config.pop(key, None)
    save_config(config)

    with database() as connection:
        connection.execute("""
            UPDATE submissions
            SET guild_id = ?
            WHERE guild_id IS NULL OR guild_id = ''
        """, (str(guild.id),))
        connection.execute("""
            UPDATE category_history
            SET guild_id = ?
            WHERE guild_id IS NULL OR guild_id = ''
        """, (str(guild.id),))
    print(f"Migrated legacy configuration to guild {guild.id}.")


def get_guild_config(guild_id, create=True):
    if guild_id is None:
        return None

    guilds = config.setdefault("guilds", {})
    key = str(guild_id)
    if key not in guilds:
        if not create:
            return dict(DEFAULT_GUILD_CONFIG)
        guilds[key] = json.loads(json.dumps(DEFAULT_GUILD_CONFIG))
        save_config(config)

    guild_config = guilds[key]
    changed = False
    for setting, default in DEFAULT_GUILD_CONFIG.items():
        if setting not in guild_config:
            guild_config[setting] = json.loads(json.dumps(default))
            changed = True
    if changed:
        save_config(config)
    return guild_config


def connect_db():
    connection = sqlite3.connect(DB_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = connect_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_column(connection, table, column, definition):
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def initialize_database():
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                original_message_id TEXT,
                repost_message_id TEXT,
                repost_channel_id TEXT,
                approval_message_id TEXT,
                approval_channel_id TEXT,
                user_id TEXT,
                username TEXT,
                category TEXT,
                message_text TEXT,
                file_paths TEXT,
                media_paths TEXT,
                media_names TEXT,
                media_types TEXT,
                media_sizes TEXT,
                media_metadata_json TEXT,
                stars INTEGER DEFAULT 0,
                voters TEXT DEFAULT '',
                status TEXT DEFAULT 'posted',
                submitted_at TEXT,
                created_at TEXT,
                approved_at TEXT,
                daily_posted_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS category_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                category TEXT,
                channel_id TEXT,
                admin_user_id TEXT,
                admin_username TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS moderation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                submission_id INTEGER,
                action TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                details TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_runs (
                guild_id TEXT,
                run_date TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, run_date)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS restore_test_runs (
                run_key TEXT PRIMARY KEY,
                backup_name TEXT,
                status TEXT,
                details TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                message_id TEXT,
                starter_user_id TEXT,
                starter_username TEXT,
                answer TEXT,
                answer_display TEXT,
                prompt_text TEXT,
                media_path TEXT,
                media_name TEXT,
                media_type TEXT,
                media_size INTEGER DEFAULT 0,
                media_metadata_json TEXT,
                hint_text TEXT,
                hint_revealed_at TEXT,
                status TEXT DEFAULT 'active',
                winner_user_id TEXT,
                winner_username TEXT,
                started_at TEXT,
                solved_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                username TEXT,
                month TEXT,
                points INTEGER DEFAULT 0,
                updated_at TEXT,
                UNIQUE (guild_id, channel_id, user_id, month)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_correct_guesses (
                game_id INTEGER,
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                username TEXT,
                guessed_at TEXT,
                PRIMARY KEY (game_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_cooldowns (
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                timeout_until TEXT,
                PRIMARY KEY (guild_id, channel_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_guess_runs (
                guild_id TEXT,
                channel_id TEXT,
                month TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, channel_id, month)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_guess_runs (
                guild_id TEXT,
                channel_id TEXT,
                run_date TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, channel_id, run_date)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_submission_top (
                month TEXT,
                category TEXT,
                rank INTEGER,
                submission_id INTEGER,
                guild_id TEXT,
                original_message_id TEXT,
                repost_message_id TEXT,
                repost_channel_id TEXT,
                user_id TEXT,
                username TEXT,
                message_text TEXT,
                file_paths TEXT,
                media_paths TEXT,
                media_names TEXT,
                media_types TEXT,
                media_sizes TEXT,
                media_metadata_json TEXT,
                stars INTEGER DEFAULT 0,
                voters TEXT DEFAULT '',
                submitted_at TEXT,
                created_at TEXT,
                captured_at TEXT,
                PRIMARY KEY (month, category, rank)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        submission_columns = {
            "guild_id": "TEXT",
            "original_message_id": "TEXT",
            "repost_message_id": "TEXT",
            "repost_channel_id": "TEXT",
            "approval_message_id": "TEXT",
            "approval_channel_id": "TEXT",
            "user_id": "TEXT",
            "username": "TEXT",
            "category": "TEXT",
            "message_text": "TEXT",
            "file_paths": "TEXT",
            "media_paths": "TEXT",
            "media_names": "TEXT",
            "media_types": "TEXT",
            "media_sizes": "TEXT",
            "media_metadata_json": "TEXT",
            "stars": "INTEGER DEFAULT 0",
            "voters": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'posted'",
            "submitted_at": "TEXT",
            "created_at": "TEXT",
            "approved_at": "TEXT",
            "daily_posted_at": "TEXT",
        }
        for column, definition in submission_columns.items():
            ensure_column(
                connection, "submissions", column, definition
            )

        for column, definition in {
            "guild_id": "TEXT",
            "action": "TEXT",
            "category": "TEXT",
            "channel_id": "TEXT",
            "admin_user_id": "TEXT",
            "admin_username": "TEXT",
            "created_at": "TEXT",
        }.items():
            ensure_column(
                connection, "category_history", column, definition
            )

        for column, definition in {
            "guild_id": "TEXT",
            "channel_id": "TEXT",
            "message_id": "TEXT",
            "starter_user_id": "TEXT",
            "starter_username": "TEXT",
            "answer": "TEXT",
            "answer_display": "TEXT",
            "prompt_text": "TEXT",
            "media_path": "TEXT",
            "media_name": "TEXT",
            "media_type": "TEXT",
            "media_size": "INTEGER DEFAULT 0",
            "media_metadata_json": "TEXT",
            "hint_text": "TEXT",
            "hint_revealed_at": "TEXT",
            "status": "TEXT DEFAULT 'active'",
            "winner_user_id": "TEXT",
            "winner_username": "TEXT",
            "started_at": "TEXT",
            "solved_at": "TEXT",
        }.items():
            ensure_column(
                connection, "guess_games", column, definition
            )

        connection.execute("""
            UPDATE submissions
            SET status = 'posted'
            WHERE status IS NULL OR status = ''
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_guild_category
            ON submissions (guild_id, category, status)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_gallery
            ON submissions (guild_id, status, category, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_search
            ON submissions (guild_id, status, username, message_text, category)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_repost
            ON submissions (repost_message_id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_games_active
            ON guess_games (guild_id, channel_id, status)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_points_month
            ON guess_points (guild_id, channel_id, month, points)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_points_global_month
            ON guess_points (month, user_id, points)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_cooldowns_timeout
            ON guess_cooldowns (timeout_until)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_submission_top_month
            ON monthly_submission_top (month, category, rank)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
            ON admin_audit_log (created_at, id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action
            ON admin_audit_log (action, guild_id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_restore_test_runs_created
            ON restore_test_runs (created_at)
        """)
        apply_database_migrations(connection)


initialize_database()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def ensure_directory_writable(path):
    path.mkdir(parents=True, exist_ok=True)
    probe_path = path / ".sdac-write-test"
    probe_path.write_text("ok", encoding="utf-8")
    try:
        probe_path.unlink()
    except OSError:
        pass


def startup_health_check():
    issues = []

    if not TOKEN:
        issues.append("DISCORD_TOKEN is missing.")
    if not CONFIG_FILE.is_file():
        issues.append(f"{CONFIG_FILE} is missing.")

    for directory in (MEDIA_DIR, BACKUP_DIR):
        try:
            ensure_directory_writable(directory)
        except OSError as error:
            issues.append(f"{directory} is not writable: {error}")

    try:
        with database() as connection:
            table_names = {
                row["name"]
                for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
            }
            missing_tables = sorted(REQUIRED_TABLES - table_names)
            if missing_tables:
                issues.append(
                    "Database is missing tables: "
                    + ", ".join(missing_tables)
                )
            version_row = connection.execute("""
                SELECT version
                FROM schema_version
                WHERE id = 1
            """).fetchone()
            if not version_row or version_row["version"] < SCHEMA_VERSION:
                issues.append(
                    f"Database schema version is below {SCHEMA_VERSION}."
                )
    except sqlite3.Error as error:
        issues.append(f"Database check failed: {error}")

    if issues:
        raise RuntimeError(
            "Startup health check failed: " + " ".join(issues)
        )

    print(
        "Startup health check passed: "
        f"schema v{SCHEMA_VERSION}, database={DB_FILE}, media={MEDIA_DIR}",
        flush=True,
    )


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_now_display():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def clean_category_name(category):
    return category.lower().strip().replace(" ", "")


def normalize_guess(value):
    cleaned = re.sub(r"[^\w\s]", " ", value.casefold())
    cleaned = re.sub(r"[_\s]+", " ", cleaned)
    return cleaned.strip()


def get_guild_timezone(guild_config):
    timezone_name = (
        (guild_config or {}).get("timezone")
        or DEFAULT_GUILD_CONFIG["timezone"]
    )
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_GUILD_CONFIG["timezone"])


def guild_now(guild_config):
    return datetime.now(get_guild_timezone(guild_config))


def parse_database_datetime(value):
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def current_month_key(guild_config=None):
    return guild_now(guild_config).strftime("%Y-%m")


def previous_month_key(now=None):
    now = now or datetime.now(timezone.utc)
    first_of_month = now.replace(day=1)
    previous_month = first_of_month - timedelta(days=1)
    return previous_month.strftime("%Y-%m")


def normalize_weekday(value):
    value = (value or "").casefold().strip()
    if value in WEEKDAY_NAMES:
        return value
    return None


def weekly_top_day_index(guild_config):
    day = normalize_weekday(guild_config.get("weekly_top_day"))
    if day is None:
        day = DEFAULT_GUILD_CONFIG["weekly_top_day"]
    return WEEKDAY_NAMES.index(day)


def weekly_run_key(now):
    return f"weekly:{now.strftime('%G-W%V')}"


def safe_backup_label(label):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "backup"


def cleanup_old_database_backups():
    if not BACKUP_DIR.exists():
        return
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup_path in backups[BACKUP_KEEP_COUNT:]:
        try:
            backup_path.unlink()
        except OSError:
            pass


def latest_database_backup():
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def create_database_backup(label):
    if not DB_FILE.exists():
        return None, False, "Database file does not exist."

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"sdac-{safe_backup_label(label)}.db"
    if backup_path.exists():
        return backup_path, False, "Backup already exists."

    source = sqlite3.connect(DB_FILE)
    destination = sqlite3.connect(backup_path)
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()

    cleanup_old_database_backups()
    return backup_path, True, "Backup created."


def validate_database_backup(backup_path):
    backup_path = Path(backup_path) if backup_path else None
    if backup_path is None or not backup_path.is_file():
        return False, "Backup file was not found."

    with tempfile.TemporaryDirectory(prefix="sdac-restore-test-") as temp_dir:
        restore_path = Path(temp_dir) / "sdac.db"
        shutil.copy2(backup_path, restore_path)
        connection = sqlite3.connect(restore_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA foreign_keys = ON")
            apply_database_migrations(connection)
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                return False, f"Integrity check failed: {integrity}"
            tables = {
                row["name"]
                for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
            }
            required = {
                "submissions",
                "admin_audit_log",
                "schema_version",
            }
            missing = sorted(required - tables)
            if missing:
                return (
                    False,
                    "Missing required table(s): " + ", ".join(missing),
                )
            connection.commit()
        finally:
            connection.close()
    return True, f"Restore test passed for {backup_path.name}."


def record_restore_test_run(run_key, backup_path, status, details):
    with database() as connection:
        connection.execute("""
            INSERT INTO restore_test_runs (
                run_key, backup_name, status, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_key) DO UPDATE SET
                backup_name = excluded.backup_name,
                status = excluded.status,
                details = excluded.details,
                created_at = excluded.created_at
        """, (
            run_key,
            backup_path.name if backup_path else "",
            status,
            details,
            utc_now_iso(),
        ))


def restore_test_has_run(run_key):
    with database() as connection:
        row = connection.execute("""
            SELECT 1
            FROM restore_test_runs
            WHERE run_key = ?
            LIMIT 1
        """, (run_key,)).fetchone()
    return row is not None


def run_restore_test(run_key):
    backup_path = latest_database_backup()
    passed, details = validate_database_backup(backup_path)
    status = "passed" if passed else "failed"
    record_restore_test_run(run_key, backup_path, status, details)
    return passed, backup_path, details


def create_daily_database_backup():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        backup_path, created, message = create_database_backup(f"daily-{today}")
    except (OSError, sqlite3.Error) as error:
        print(f"Daily database backup failed: {error}", flush=True)
        return None, False, str(error)
    if created:
        with database() as connection:
            add_admin_audit_log(
                connection,
                None,
                "database_backup_daily",
                "system",
                "system",
                "backup",
                backup_path.name,
                message,
            )
    return backup_path, created, message


def referenced_media_paths(connection):
    paths = set()
    for row in connection.execute("""
        SELECT media_paths, file_paths
        FROM submissions
    """):
        for value in split_values(row["media_paths"] or row["file_paths"]):
            try:
                paths.add(Path(value).resolve())
            except OSError:
                pass
    for row in connection.execute("""
        SELECT media_path
        FROM guess_games
        WHERE media_path IS NOT NULL AND media_path != ''
    """):
        try:
            paths.add(Path(row["media_path"]).resolve())
        except OSError:
            pass
    return paths


def cleanup_orphaned_media(connection):
    if not config["limits"].get("orphan_media_cleanup_enabled", True):
        return 0
    if not MEDIA_DIR.exists():
        return 0
    media_root = MEDIA_DIR.resolve()
    referenced = referenced_media_paths(connection)
    removed = 0
    for file_path in media_root.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            resolved = file_path.resolve()
            resolved.relative_to(media_root)
        except (OSError, ValueError):
            continue
        if resolved in referenced:
            continue
        try:
            resolved.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def cleanup_background_data():
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    pending_hours = config["limits"].get(
        "pending_submission_retention_hours",
        48,
    )
    audit_days = config["limits"].get("audit_retention_days", 365)
    rate_limit_days = config["limits"].get("rate_limit_retention_days", 30)
    pending_cutoff = (now - timedelta(hours=pending_hours)).isoformat()
    audit_cutoff = (now - timedelta(days=audit_days)).isoformat()
    rate_limit_cutoff = (now - timedelta(days=rate_limit_days)).isoformat()

    with database() as connection:
        pending_rows = connection.execute("""
            SELECT *
            FROM submissions
            WHERE status = 'pending'
              AND COALESCE(created_at, submitted_at, '') < ?
        """, (pending_cutoff,)).fetchall()
        for row in pending_rows:
            cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
            connection.execute(
                "DELETE FROM submissions WHERE id = ?",
                (row["id"],),
            )
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE timeout_until IS NOT NULL AND timeout_until < ?
        """, (now_iso,))
        if audit_days:
            connection.execute("""
                DELETE FROM admin_audit_log
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (audit_cutoff,))
            connection.execute("""
                DELETE FROM moderation_history
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (audit_cutoff,))
        if rate_limit_days:
            connection.execute("""
                DELETE FROM rate_limit_events
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (rate_limit_cutoff,))
        removed_media = cleanup_orphaned_media(connection)
        if pending_rows or removed_media:
            add_admin_audit_log(
                connection,
                None,
                "background_cleanup",
                "system",
                "system",
                "cleanup",
                "",
                (
                    f"Removed {len(pending_rows)} stale pending submission(s) "
                    f"and {removed_media} orphan media file(s)."
                ),
            )


def preserve_monthly_submission_top(connection, month):
    existing = connection.execute("""
        SELECT 1
        FROM monthly_submission_top
        WHERE month = ?
        LIMIT 1
    """, (month,)).fetchone()
    if existing:
        return

    rows = connection.execute("""
        SELECT *
        FROM submissions
        WHERE status = 'posted'
          AND substr(COALESCE(created_at, submitted_at), 1, 7) = ?
        ORDER BY category ASC, stars DESC, created_at DESC, id DESC
    """, (month,)).fetchall()

    ranks_by_category = {}
    captured_at = utc_now_iso()
    for row in rows:
        category = row["category"] or "Uncategorized"
        rank = ranks_by_category.get(category, 0) + 1
        if rank > 10:
            continue
        ranks_by_category[category] = rank
        connection.execute("""
            INSERT OR IGNORE INTO monthly_submission_top (
                month, category, rank, submission_id, guild_id,
                original_message_id, repost_message_id, repost_channel_id,
                user_id, username, message_text, file_paths, media_paths,
                media_names, media_types, media_sizes, media_metadata_json,
                stars, voters, submitted_at, created_at, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month,
            category,
            rank,
            row["id"],
            row["guild_id"],
            row["original_message_id"],
            row["repost_message_id"],
            row["repost_channel_id"],
            row["user_id"],
            row["username"],
            row["message_text"],
            row["file_paths"],
            row["media_paths"],
            row["media_names"],
            row["media_types"],
            row["media_sizes"],
            row["media_metadata_json"],
            row["stars"] or 0,
            row["voters"],
            row["submitted_at"],
            row["created_at"],
            captured_at,
        ))


def is_allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_media_type(filename):
    extension = Path(filename).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if extension in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if extension in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
        return "audio"
    return "unknown"


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def directory_size(path):
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        try:
            total += item.stat().st_size
        except OSError:
            pass
    return total


def storage_warning_lines():
    lines = []
    media_limit = configured_limit("media_warning_bytes", 0)
    database_limit = configured_limit("database_warning_bytes", 0)
    media_size = directory_size(MEDIA_DIR)
    database_size = DB_FILE.stat().st_size if DB_FILE.exists() else 0

    if media_limit and media_size >= media_limit:
        lines.append(
            f"Media folder is {format_bytes(media_size)} "
            f"(warning at {format_bytes(media_limit)})."
        )
    if database_limit and database_size >= database_limit:
        lines.append(
            f"Database is {format_bytes(database_size)} "
            f"(warning at {format_bytes(database_limit)})."
        )
    return lines


def probe_media_duration(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    if duration <= 0:
        return None
    return round(duration, 2)


def attachment_metadata(attachment, path):
    media_type = get_media_type(attachment.filename)
    metadata = {
        "filename": attachment.filename,
        "media_type": media_type,
        "size": int(attachment.size or 0),
        "size_label": format_bytes(int(attachment.size or 0)),
        "content_type": getattr(attachment, "content_type", "") or "",
        "duration_seconds": None,
    }
    if media_type in {"audio", "video"}:
        metadata["duration_seconds"] = probe_media_duration(path)
    return metadata


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


def get_voters(raw_value):
    if not raw_value:
        return set()
    return {value for value in raw_value.split(",") if value}


def save_voters(voters):
    return ",".join(sorted(voters))


def cleanup_files(paths):
    for raw_path in paths:
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            resolved.relative_to(MEDIA_DIR.resolve())
            if resolved.is_file():
                resolved.unlink()
        except (OSError, ValueError):
            continue


def make_discord_files(row):
    paths = split_values(row["media_paths"] or row["file_paths"])
    names = split_values(row["media_names"])
    files = []
    for index, raw_path in enumerate(paths):
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"Missing media file: {path.name}")
        filename = names[index] if index < len(names) else path.name
        files.append(discord.File(path, filename=filename))
    return files


async def send_submission_message(channel, content, row, view):
    files = make_discord_files(row)
    try:
        return await channel.send(
            content=content,
            files=files,
            view=view,
        )
    finally:
        for file in files:
            file.close()


def add_admin_audit_log(
    connection,
    guild_id,
    action,
    actor_user_id,
    actor_username,
    target_type="",
    target_id="",
    details="",
):
    connection.execute("""
        INSERT INTO admin_audit_log (
            guild_id, action, actor_user_id, actor_username,
            target_type, target_id, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(guild_id) if guild_id is not None else None,
        action,
        str(actor_user_id) if actor_user_id is not None else "",
        str(actor_username) if actor_username is not None else "",
        target_type,
        str(target_id) if target_id is not None else "",
        details,
        utc_now_iso(),
    ))


def log_admin_action(
    guild_id,
    action,
    actor_user_id,
    actor_username,
    target_type="",
    target_id="",
    details="",
):
    with database() as connection:
        add_admin_audit_log(
            connection,
            guild_id,
            action,
            actor_user_id,
            actor_username,
            target_type,
            target_id,
            details,
        )


def audit_interaction(
    interaction,
    action,
    target_type="",
    target_id="",
    details="",
):
    log_admin_action(
        interaction.guild_id,
        action,
        interaction.user.id,
        interaction.user,
        target_type,
        target_id,
        details,
    )


def record_rate_limit_event(
    guild_id,
    user_id,
    username,
    bucket,
    action,
    retry_after_seconds,
    details="",
):
    with database() as connection:
        connection.execute("""
            INSERT INTO rate_limit_events (
                guild_id, user_id, username, bucket, action,
                retry_after_seconds, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(guild_id) if guild_id is not None else "",
            str(user_id) if user_id is not None else "",
            str(username) if username is not None else "",
            bucket,
            action,
            int(retry_after_seconds),
            details,
            utc_now_iso(),
        ))


def configured_limit(name, default):
    try:
        value = int(config["limits"].get(name, default))
    except (TypeError, ValueError):
        return default
    return max(0, value)


def command_cooldown_message(bucket, guild_id, user_id, seconds):
    if seconds <= 0:
        return None, 0
    now = time.time()
    key = f"{bucket}:{guild_id}:{user_id}"
    last_seen = command_cooldowns.get(key, 0)
    elapsed = now - last_seen
    if elapsed < seconds:
        remaining = max(1, int(seconds - elapsed))
        return f"Slow down a little. Try again in {remaining}s.", remaining
    command_cooldowns[key] = now
    return None, 0


def add_moderation_history(
    connection,
    row,
    action,
    actor_user_id,
    actor_username,
    details="",
):
    connection.execute("""
        INSERT INTO moderation_history (
            guild_id, submission_id, action, actor_user_id,
            actor_username, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        row["guild_id"],
        row["id"],
        action,
        str(actor_user_id),
        str(actor_username),
        details,
        utc_now_iso(),
    ))


def admin_only(interaction):
    if not interaction.guild:
        return False
    if interaction.user.guild_permissions.administrator:
        return True

    guild_config = get_guild_config(interaction.guild_id, create=False)
    allowed_role_ids = {
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id).strip()
    }
    if not allowed_role_ids:
        return False
    return any(str(role.id) in allowed_role_ids for role in interaction.user.roles)


async def require_admin(interaction):
    if admin_only(interaction):
        seconds = configured_limit("admin_action_cooldown_seconds", 1)
        message, remaining = command_cooldown_message(
            "admin_action",
            interaction.guild_id,
            interaction.user.id,
            seconds,
        )
        if message:
            record_rate_limit_event(
                interaction.guild_id,
                interaction.user.id,
                interaction.user,
                "admin_action",
                (
                    interaction.command.name
                    if getattr(interaction, "command", None)
                    else "unknown"
                ),
                remaining,
                "Admin command cooldown.",
            )
            await interaction.response.send_message(message, ephemeral=True)
            return False
        return True
    command_name = (
        interaction.command.name
        if getattr(interaction, "command", None)
        else "unknown"
    )
    log_admin_action(
        interaction.guild_id,
        "admin_command_denied",
        interaction.user.id,
        interaction.user,
        "command",
        command_name,
        "Non-admin attempted an admin-only command.",
    )
    await interaction.response.send_message(
        "Only admins can use this command.",
        ephemeral=True,
    )
    return False


async def category_autocomplete(interaction, current):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    categories = guild_config.get("categories", {}) if guild_config else {}
    current = clean_category_name(current)
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(categories)
        if current in name
    ][:25]


def channel_display(channel_id):
    return f"<#{channel_id}>" if channel_id else "Not set"


def settings_lines(guild_config):
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    timeout_seconds = config["limits"].get("wrong_guess_timeout_seconds", 600)
    timeout_minutes = max(1, round(timeout_seconds / 60))
    weekly_day = guild_config.get(
        "weekly_top_day",
        DEFAULT_GUILD_CONFIG["weekly_top_day"],
    ).title()
    lines = [
        "**SDAC Settings**",
        f"Submit channel: {channel_display(guild_config.get('submit_channel'))}",
        f"Weekly top channel: {channel_display(guild_config.get('daily_top_channel'))}",
        f"Weekly top day: `{weekly_day}`",
        f"Weekly top time: `{guild_config['daily_top_time_utc']}` `{timezone_name}`",
        f"Timezone: `{timezone_name}`",
        f"Approval: {'Enabled' if guild_config['approval_enabled'] else 'Disabled'}",
        f"Approval channel: {channel_display(guild_config.get('approval_channel'))}",
        f"Game summary channel: {channel_display(guild_config.get('game_summary_channel'))}",
        f"Error channel: {channel_display(guild_config.get('error_channel'))}",
        f"Admin roles: `{len(guild_config.get('admin_role_ids', []))}`",
        f"Wrong guess timeout: `{timeout_minutes}` minute(s)",
        f"Categories: `{len(guild_config.get('categories', {}))}`",
        "",
    ]
    categories = guild_config.get("categories", {})
    if not categories:
        lines.append("No categories are set.")
    else:
        lines.append("**Categories:**")
        for category, channel_id in sorted(categories.items()):
            lines.append(f"- `{category}` -> {channel_display(channel_id)}")
    return lines


def submission_content(row):
    return (
        f"Category: **{row['category'].upper()}**\n"
        f"Submitted by: <@{row['user_id']}>\n"
        f"Submitted: {utc_now_display()}\n\n"
        f"{row['message_text'] or ''}"
    )


REQUIRED_BOT_PERMISSIONS = (
    ("view_channel", "View Channel"),
    ("send_messages", "Send Messages"),
    ("attach_files", "Attach Files"),
    ("read_message_history", "Read Message History"),
)
OPTIONAL_BOT_PERMISSIONS = (
    ("manage_messages", "Manage Messages"),
)


def configured_channel_ids(guild_config):
    channel_ids = []
    for key in (
        "submit_channel",
        "daily_top_channel",
        "game_summary_channel",
        "error_channel",
        "approval_channel",
    ):
        channel_id = guild_config.get(key)
        if channel_id:
            channel_ids.append(channel_id)
    channel_ids.extend((guild_config.get("categories") or {}).values())

    deduped = []
    seen = set()
    for channel_id in channel_ids:
        if str(channel_id) in seen:
            continue
        seen.add(str(channel_id))
        deduped.append(channel_id)
    return deduped


async def resolve_guild_channel(guild, channel_id):
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None
    channel = guild.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        channel = await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        return None
    if getattr(channel, "guild", None) and channel.guild.id == guild.id:
        return channel
    return None


def bot_permission_summary(guild, channel):
    bot_member = guild.me
    if bot_member is None and bot.user is not None:
        bot_member = guild.get_member(bot.user.id)
    if bot_member is None:
        return "Bot member was not found in this server."

    permissions = channel.permissions_for(bot_member)
    missing_required = [
        label
        for attribute, label in REQUIRED_BOT_PERMISSIONS
        if not getattr(permissions, attribute, False)
    ]
    missing_optional = [
        label
        for attribute, label in OPTIONAL_BOT_PERMISSIONS
        if not getattr(permissions, attribute, False)
    ]
    if missing_required:
        return "Missing required: " + ", ".join(missing_required)
    if missing_optional:
        return "Usable, recommended: " + ", ".join(missing_optional)
    return "OK"


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!sdac ", intents=intents)
tree = bot.tree
user_cooldowns = {}
category_cooldowns = {}
command_cooldowns = {}
active_submission_sessions = set()
slash_commands_synced = False
persistent_views_registered = False
last_backup_date = None
last_storage_warning_date = None


def refresh_known_guilds():
    changed = False
    for guild in bot.guilds:
        guild_config = get_guild_config(guild.id)
        if guild_config.get("guild_name") != guild.name:
            guild_config["guild_name"] = guild.name
            changed = True
    if changed:
        save_config(config)


async def delete_discord_message(channel_id, message_id):
    if not channel_id or not message_id:
        return True, ""
    try:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            channel = await bot.fetch_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        await message.delete()
        return True, ""
    except discord.NotFound:
        return True, ""
    except discord.Forbidden:
        return False, "The bot does not have permission to delete the Discord message."
    except discord.HTTPException as error:
        return False, f"Discord deletion failed: {error}"


async def delete_guess_game_message(row):
    deleted, message = await delete_discord_message(
        row["channel_id"],
        row["message_id"],
    )
    if not deleted:
        print(f"Could not delete old guessing game message: {message}", flush=True)
    cleanup_files([row["media_path"]])


async def close_active_guess_game(guild_id, channel_id, status):
    with database() as connection:
        row = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(guild_id), str(channel_id))).fetchone()
        if row:
            connection.execute("""
                UPDATE guess_games
                SET status = ?,
                    solved_at = COALESCE(solved_at, ?)
                WHERE id = ?
            """, (status, utc_now_iso(), row["id"]))
            connection.execute("""
                DELETE FROM guess_cooldowns
                WHERE guild_id = ? AND channel_id = ?
            """, (str(guild_id), str(channel_id)))

    if row:
        await delete_guess_game_message(row)
    return row


def guess_leaderboard_lines(connection, guild_id, channel_id, month, limit=10):
    rows = connection.execute("""
        SELECT username, points
        FROM guess_points
        WHERE guild_id = ?
          AND channel_id = ?
          AND month = ?
        ORDER BY points DESC, username ASC
        LIMIT ?
    """, (str(guild_id), str(channel_id), month, limit)).fetchall()

    if not rows:
        return ["No points yet."]

    return [
        f"{index}. {row['username']} - {row['points']} point(s)"
        for index, row in enumerate(rows, start=1)
    ]


async def configured_summary_channel(game, fallback_channel):
    guild_config = get_guild_config(game["guild_id"], create=False)
    channel_id = guild_config.get("game_summary_channel")
    if not channel_id:
        return fallback_channel
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            channel = None
    return channel or fallback_channel


async def send_error_notification(guild_id, message):
    guild_config = get_guild_config(guild_id, create=False)
    channel_id = guild_config.get("error_channel")
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            channel = None
    if channel is not None:
        try:
            await channel.send(f"**SDAC Error**\n{message}")
        except discord.HTTPException:
            pass


async def send_system_error_notification(message):
    sent_guilds = set()
    for guild_id in config.get("guilds", {}):
        if guild_id in sent_guilds:
            continue
        sent_guilds.add(guild_id)
        await send_error_notification(guild_id, message)


async def report_background_error(name, error):
    capture_exception(error)
    print(f"{name} failed: {error}", flush=True)
    await send_system_error_notification(
        f"`{name}` failed: `{error}`"
    )


async def announce_guess_summary(channel, game, reason):
    guild_config = get_guild_config(game["guild_id"], create=False)
    target_channel = await configured_summary_channel(game, channel)
    if target_channel is None:
        return
    with database() as connection:
        correct_rows = connection.execute("""
            SELECT username
            FROM guess_correct_guesses
            WHERE game_id = ?
            ORDER BY guessed_at ASC
        """, (game["id"],)).fetchall()
        leaderboard = guess_leaderboard_lines(
            connection,
            game["guild_id"],
            game["channel_id"],
            current_month_key(guild_config),
            limit=10,
        )

    correct_names = (
        ", ".join(row["username"] for row in correct_rows)
        if correct_rows
        else "Nobody"
    )
    await target_channel.send(
        f"**Guessing Game Summary ({reason})**\n"
        f"Answer: **{game['answer_display']}**\n"
        f"Correct guessers: {correct_names}\n\n"
        "**Top 10 This Month**\n"
        + "\n".join(leaderboard)
    )


async def remove_submission_record(
    submission_id,
    actor_user_id,
    actor_username,
    reason,
):
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    if not row:
        return False, "Submission not found."

    deleted, message = await delete_discord_message(
        row["repost_channel_id"],
        row["repost_message_id"],
    )
    if not deleted:
        return False, message

    await delete_discord_message(
        row["approval_channel_id"],
        row["approval_message_id"],
    )

    with database() as connection:
        add_moderation_history(
            connection,
            row,
            "remove",
            actor_user_id,
            actor_username,
            reason,
        )
        add_admin_audit_log(
            connection,
            row["guild_id"],
            "remove_submission",
            actor_user_id,
            actor_username,
            "submission",
            row["id"],
            reason,
        )
        connection.execute(
            "DELETE FROM submissions WHERE id = ?",
            (submission_id,),
        )

    cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
    return True, "Submission removed from Discord and the database."


class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Vote",
        style=discord.ButtonStyle.secondary,
        custom_id="sdac_star_vote",
    )
    async def star_vote(self, interaction, button):
        repost_message_id = str(interaction.message.id)
        user_id = str(interaction.user.id)

        with database() as connection:
            row = connection.execute("""
                SELECT id, voters
                FROM submissions
                WHERE repost_message_id = ? AND status = 'posted'
            """, (repost_message_id,)).fetchone()

            if not row:
                await interaction.response.send_message(
                    "This post is not registered in the SDAC database.",
                    ephemeral=True,
                )
                return

            voters = get_voters(row["voters"])
            if user_id in voters:
                await interaction.response.send_message(
                    "You already voted for this post.",
                    ephemeral=True,
                )
                return

            voters.add(user_id)
            connection.execute("""
                UPDATE submissions
                SET stars = stars + 1, voters = ?
                WHERE id = ?
            """, (save_voters(voters), row["id"]))

        await interaction.response.send_message(
            "Vote added.",
            ephemeral=True,
        )


class ApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_pending_row(self, interaction):
        with database() as connection:
            return connection.execute("""
                SELECT *
                FROM submissions
                WHERE approval_message_id = ? AND status = 'pending'
            """, (str(interaction.message.id),)).fetchone()

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="sdac_approve_submission",
    )
    async def approve(self, interaction, button):
        if not admin_only(interaction):
            log_admin_action(
                interaction.guild_id,
                "admin_button_denied",
                interaction.user.id,
                interaction.user,
                "button",
                "approve_submission",
                "Non-admin attempted to approve a submission.",
            )
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        row = await self.get_pending_row(interaction)
        if not row:
            await interaction.followup.send(
                "This submission is no longer pending.",
                ephemeral=True,
            )
            return

        target_channel = bot.get_channel(int(row["repost_channel_id"]))
        if target_channel is None:
            try:
                target_channel = await bot.fetch_channel(
                    int(row["repost_channel_id"])
                )
            except discord.HTTPException:
                target_channel = None
        if target_channel is None:
            await interaction.followup.send(
                "The target category channel could not be found.",
                ephemeral=True,
            )
            return

        try:
            repost = await send_submission_message(
                target_channel,
                submission_content(row),
                row,
                VoteView(),
            )
        except (discord.HTTPException, OSError) as error:
            await interaction.followup.send(
                f"Approval failed: `{error}`",
                ephemeral=True,
            )
            return

        with database() as connection:
            connection.execute("""
                UPDATE submissions
                SET status = 'posted',
                    repost_message_id = ?,
                    repost_channel_id = ?,
                    approved_at = ?
                WHERE id = ? AND status = 'pending'
            """, (
                str(repost.id),
                str(target_channel.id),
                utc_now_iso(),
                row["id"],
            ))
            add_moderation_history(
                connection,
                row,
                "approve",
                interaction.user.id,
                interaction.user,
            )
            add_admin_audit_log(
                connection,
                row["guild_id"],
                "approve_submission",
                interaction.user.id,
                interaction.user,
                "submission",
                row["id"],
                f"Posted to channel {target_channel.id}.",
            )

        await interaction.message.edit(
            content=interaction.message.content + "\n\nApproved.",
            view=None,
        )
        await interaction.followup.send(
            f"Submission `{row['id']}` approved.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="sdac_reject_submission",
    )
    async def reject(self, interaction, button):
        if not admin_only(interaction):
            log_admin_action(
                interaction.guild_id,
                "admin_button_denied",
                interaction.user.id,
                interaction.user,
                "button",
                "reject_submission",
                "Non-admin attempted to reject a submission.",
            )
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return

        row = await self.get_pending_row(interaction)
        if not row:
            await interaction.response.send_message(
                "This submission is no longer pending.",
                ephemeral=True,
            )
            return

        with database() as connection:
            add_moderation_history(
                connection,
                row,
                "reject",
                interaction.user.id,
                interaction.user,
            )
            add_admin_audit_log(
                connection,
                row["guild_id"],
                "reject_submission",
                interaction.user.id,
                interaction.user,
                "submission",
                row["id"],
                "Rejected from approval queue.",
            )
            connection.execute(
                "DELETE FROM submissions WHERE id = ?",
                (row["id"],),
            )

        cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
        await interaction.message.edit(
            content=interaction.message.content + "\n\nRejected.",
            attachments=[],
            view=None,
        )
        await interaction.response.send_message(
            f"Submission `{row['id']}` rejected.",
            ephemeral=True,
        )


@tree.command(name="setsubmit", description="Set the SDAC submission channel")
@app_commands.guild_only()
@app_commands.describe(channel="Channel where users can submit")
async def setsubmit(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["submit_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_submit_channel",
        "channel",
        channel.id,
        f"Submit channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Submit channel set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearsubmit", description="Clear the SDAC submission channel")
@app_commands.guild_only()
async def clearsubmit(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["submit_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_submit_channel",
        "channel",
        "",
        "Submit channel cleared.",
    )
    await interaction.response.send_message(
        "Submit channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setcategory", description="Create or update an SDAC category")
@app_commands.guild_only()
@app_commands.describe(category="Category name", channel="Category repost channel")
async def setcategory(
    interaction,
    category: str,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return
    category = clean_category_name(category)
    if not category:
        await interaction.response.send_message(
            "Category name cannot be empty.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["categories"][category] = channel.id
    save_config(config)

    with database() as connection:
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            "set",
            category,
            str(channel.id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "set_category",
            interaction.user.id,
            interaction.user,
            "category",
            category,
            f"Channel {channel.id}.",
        )

    await interaction.response.send_message(
        f"Category `{category}` set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="editcategory", description="Rename or move an SDAC category")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
@app_commands.describe(
    category="Existing category",
    new_name="New category name",
    channel="Optional new repost channel",
)
async def editcategory(
    interaction,
    category: str,
    new_name: str,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return

    category = clean_category_name(category)
    new_name = clean_category_name(new_name)
    guild_config = get_guild_config(interaction.guild_id)
    categories = guild_config["categories"]
    if category not in categories:
        await interaction.response.send_message(
            f"Category `{category}` does not exist.",
            ephemeral=True,
        )
        return
    if not new_name:
        await interaction.response.send_message(
            "New category name cannot be empty.",
            ephemeral=True,
        )
        return
    if new_name != category and new_name in categories:
        await interaction.response.send_message(
            f"Category `{new_name}` already exists.",
            ephemeral=True,
        )
        return

    channel_id = channel.id if channel else categories[category]
    categories.pop(category)
    categories[new_name] = channel_id
    save_config(config)

    with database() as connection:
        connection.execute("""
            UPDATE submissions
            SET category = ?
            WHERE guild_id = ? AND category = ?
        """, (new_name, str(interaction.guild_id), category))
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            f"edit:{category}",
            new_name,
            str(channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "edit_category",
            interaction.user.id,
            interaction.user,
            "category",
            new_name,
            f"Renamed from {category}; channel {channel_id}.",
        )

    await interaction.response.send_message(
        f"Category `{category}` changed to `{new_name}`.",
        ephemeral=True,
    )


@tree.command(name="deletecategory", description="Delete an SDAC category")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
async def deletecategory(interaction, category: str):
    if not await require_admin(interaction):
        return
    category = clean_category_name(category)
    guild_config = get_guild_config(interaction.guild_id)
    if category not in guild_config["categories"]:
        await interaction.response.send_message(
            f"Category `{category}` does not exist.",
            ephemeral=True,
        )
        return

    old_channel_id = guild_config["categories"].pop(category)
    save_config(config)
    with database() as connection:
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            "delete",
            category,
            str(old_channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "delete_category",
            interaction.user.id,
            interaction.user,
            "category",
            category,
            f"Removed channel {old_channel_id}.",
        )

    await interaction.response.send_message(
        f"Deleted category `{category}`. Existing submissions remain.",
        ephemeral=True,
    )


@tree.command(name="categories", description="List SDAC configuration")
@app_commands.guild_only()
async def categories(interaction):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    submit_channel_id = guild_config.get("submit_channel")
    submit_channel = (
        bot.get_channel(submit_channel_id) if submit_channel_id else None
    )
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    lines = [
        "**SDAC Configuration**",
        f"Submit channel: {submit_channel.mention if submit_channel else 'Not set'}",
        f"Timezone: `{timezone_name}`",
        f"Weekly day: {guild_config.get('weekly_top_day', 'sunday').title()}",
        f"Weekly time: {guild_config['daily_top_time_utc']} {timezone_name}",
        f"Approval: {'Enabled' if guild_config['approval_enabled'] else 'Disabled'}",
        "",
    ]
    if not guild_config["categories"]:
        lines.append("No categories are set.")
    else:
        lines.append("**Categories:**")
        for category, channel_id in sorted(
            guild_config["categories"].items()
        ):
            channel = bot.get_channel(channel_id)
            destination = (
                channel.mention
                if channel
                else f"Unknown channel `{channel_id}`"
            )
            lines.append(f"- `{category}` -> {destination}")
    await interaction.response.send_message(
        "\n".join(lines),
        ephemeral=True,
    )


@tree.command(name="settings", description="Show SDAC bot settings")
@app_commands.guild_only()
async def settings(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    await interaction.response.send_message(
        "\n".join(settings_lines(guild_config)),
        ephemeral=True,
    )


@tree.command(name="checkpermissions", description="Check SDAC bot channel permissions")
@app_commands.guild_only()
@app_commands.describe(channel="Optional channel to check")
async def checkpermissions(
    interaction,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id, create=False)
    channel_ids = configured_channel_ids(guild_config)
    if channel is not None:
        channel_ids.insert(0, channel.id)
    if not channel_ids and isinstance(interaction.channel, discord.TextChannel):
        channel_ids.append(interaction.channel.id)

    lines = ["**SDAC Permission Check**"]
    if not channel_ids:
        lines.append("No configured text channels were found.")

    seen = set()
    for channel_id in channel_ids:
        if str(channel_id) in seen:
            continue
        seen.add(str(channel_id))
        guild_channel = await resolve_guild_channel(
            interaction.guild,
            channel_id,
        )
        if guild_channel is None:
            lines.append(
                f"- `{channel_id}`: channel was not found or is not visible."
            )
            continue
        summary = bot_permission_summary(interaction.guild, guild_channel)
        lines.append(f"- {guild_channel.mention}: {summary}")

    audit_interaction(
        interaction,
        "check_permissions",
        "guild",
        interaction.guild_id,
        f"Checked {len(seen)} channel(s).",
    )
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="setweeklychannel", description="Set weekly top channel")
@app_commands.guild_only()
async def setweeklychannel(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_weekly_channel",
        "channel",
        channel.id,
        f"Weekly top channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Weekly top channel set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearweeklychannel", description="Clear weekly top channel")
@app_commands.guild_only()
async def clearweeklychannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_weekly_channel",
        "channel",
        "",
        "Weekly top channel cleared.",
    )
    await interaction.response.send_message(
        "Weekly top channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setweeklytime", description="Set weekly top posting time")
@app_commands.guild_only()
@app_commands.describe(
    hour="Hour from 0 to 23 in the configured timezone",
    minute="Minute from 0 to 59 in the configured timezone",
)
async def setweeklytime(interaction, hour: app_commands.Range[int, 0, 23], minute: app_commands.Range[int, 0, 59] = 0):
    if not await require_admin(interaction):
        return
    value = f"{hour:02d}:{minute:02d}"
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_time_utc"] = value
    save_config(config)
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    audit_interaction(
        interaction,
        "set_weekly_time",
        "schedule",
        value,
        f"Weekly top time set in {timezone_name}.",
    )
    await interaction.response.send_message(
        f"Weekly top time set to `{value}` in `{timezone_name}`.",
        ephemeral=True,
    )


@tree.command(name="setweeklyday", description="Set weekly top posting day")
@app_commands.guild_only()
@app_commands.choices(day=WEEKDAY_CHOICES)
@app_commands.describe(day="Day of the week for weekly top posts")
async def setweeklyday(interaction, day: str):
    if not await require_admin(interaction):
        return
    day = normalize_weekday(day)
    if day is None:
        await interaction.response.send_message(
            "Choose a valid weekday.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["weekly_top_day"] = day
    save_config(config)
    audit_interaction(
        interaction,
        "set_weekly_day",
        "schedule",
        day,
        f"Weekly top day set to {day}.",
    )
    await interaction.response.send_message(
        f"Weekly top day set to `{day.title()}`.",
        ephemeral=True,
    )


@tree.command(name="settimezone", description="Set the SDAC server timezone")
@app_commands.guild_only()
@app_commands.describe(
    timezone_name="IANA timezone name, for example America/New_York",
)
async def settimezone(interaction, timezone_name: str):
    if not await require_admin(interaction):
        return

    timezone_name = timezone_name.strip()
    try:
        selected_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        await interaction.response.send_message(
            "That timezone was not found. Use an IANA name like "
            "`America/Los_Angeles`, `America/New_York`, or `UTC`.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["timezone"] = timezone_name
    save_config(config)
    current_time = datetime.now(selected_timezone).strftime("%Y-%m-%d %H:%M")
    audit_interaction(
        interaction,
        "set_timezone",
        "timezone",
        timezone_name,
        f"Current configured local time was {current_time}.",
    )
    await interaction.response.send_message(
        f"Timezone set to `{timezone_name}`. Current server time there is "
        f"`{current_time}`.",
        ephemeral=True,
    )


@tree.command(name="setguesstimeout", description="Set wrong-guess cooldown")
@app_commands.guild_only()
@app_commands.describe(minutes="Cooldown minutes after a wrong guess")
async def setguesstimeout(
    interaction,
    minutes: app_commands.Range[int, 1, 1440],
):
    if not await require_admin(interaction):
        return
    seconds = int(minutes) * 60
    config["limits"]["wrong_guess_timeout_seconds"] = seconds
    save_config(config)
    audit_interaction(
        interaction,
        "set_guess_timeout",
        "limit",
        "wrong_guess_timeout_seconds",
        f"Set to {minutes} minute(s).",
    )
    await interaction.response.send_message(
        f"Wrong-guess cooldown set to `{minutes}` minute(s).",
        ephemeral=True,
    )


@tree.command(name="setadminrole", description="Allow a role to manage SDAC")
@app_commands.guild_only()
@app_commands.describe(role="Role that can manage SDAC without Administrator")
async def setadminrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    role_ids = {
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id).strip()
    }
    role_ids.add(str(role.id))
    guild_config["admin_role_ids"] = sorted(role_ids)
    save_config(config)
    audit_interaction(
        interaction,
        "set_admin_role",
        "role",
        role.id,
        f"Added SDAC admin role {role.name}.",
    )
    await interaction.response.send_message(
        f"{role.mention} can now manage SDAC.",
        ephemeral=True,
    )


@tree.command(name="removeadminrole", description="Remove an SDAC admin role")
@app_commands.guild_only()
@app_commands.describe(role="Role to remove from SDAC admin access")
async def removeadminrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    role_ids = [
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id) != str(role.id)
    ]
    guild_config["admin_role_ids"] = role_ids
    save_config(config)
    audit_interaction(
        interaction,
        "remove_admin_role",
        "role",
        role.id,
        f"Removed SDAC admin role {role.name}.",
    )
    await interaction.response.send_message(
        f"{role.mention} can no longer manage SDAC through its role.",
        ephemeral=True,
    )


@tree.command(name="setgamesummarychannel", description="Set guessing game summary channel")
@app_commands.guild_only()
async def setgamesummarychannel(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["game_summary_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_game_summary_channel",
        "channel",
        channel.id,
        f"Game summaries set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Guessing game summaries will post in {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="cleargamesummarychannel", description="Use game channel for summaries")
@app_commands.guild_only()
async def cleargamesummarychannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["game_summary_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_game_summary_channel",
        "channel",
        "",
        "Game summaries will post in the game channel.",
    )
    await interaction.response.send_message(
        "Guessing game summaries will post in the game channel.",
        ephemeral=True,
    )


@tree.command(name="seterrorchannel", description="Set SDAC error notification channel")
@app_commands.guild_only()
async def seterrorchannel(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["error_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_error_channel",
        "channel",
        channel.id,
        f"Error channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"SDAC error notifications will use {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearerrorchannel", description="Clear SDAC error notification channel")
@app_commands.guild_only()
async def clearerrorchannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["error_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_error_channel",
        "channel",
        "",
        "Error channel cleared.",
    )
    await interaction.response.send_message(
        "SDAC error channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setapproval", description="Configure approval-before-repost")
@app_commands.guild_only()
@app_commands.describe(
    enabled="Whether submissions require admin approval",
    channel="Channel where pending submissions are reviewed",
)
async def setapproval(
    interaction,
    enabled: bool,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    if enabled and channel is None and not guild_config["approval_channel"]:
        await interaction.response.send_message(
            "Choose an approval channel when enabling approval.",
            ephemeral=True,
        )
        return
    guild_config["approval_enabled"] = enabled
    if channel is not None:
        guild_config["approval_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_approval",
        "approval",
        "enabled" if enabled else "disabled",
        (
            f"Approval channel {channel.id}."
            if channel is not None
            else "Approval channel unchanged."
        ),
    )
    await interaction.response.send_message(
        f"Approval is now {'enabled' if enabled else 'disabled'}.",
        ephemeral=True,
    )


def submission_cooldown_message(guild_id, user_id, category):
    now = time.time()
    user_key = f"{guild_id}:{user_id}"
    category_key = f"{guild_id}:{category}"
    user_seconds = configured_limit(
        "submission_user_cooldown_seconds",
        USER_COOLDOWN_SECONDS,
    )
    category_seconds = configured_limit(
        "submission_category_cooldown_seconds",
        CATEGORY_COOLDOWN_SECONDS,
    )
    last_user = user_cooldowns.get(user_key, 0)
    if user_seconds and now - last_user < user_seconds:
        remaining = max(1, int(user_seconds - (now - last_user)))
        return f"Wait {remaining}s before submitting again.", remaining, "user"

    last_category = category_cooldowns.get(category_key, 0)
    if category_seconds and now - last_category < category_seconds:
        remaining = max(
            1,
            int(category_seconds - (now - last_category)),
        )
        return (
            f"Category `{category}` is cooling down for {remaining}s.",
            remaining,
            "category",
        )
    return None, 0, ""


def validate_submission_message(message):
    text = message.content.strip()
    attachments = list(message.attachments)
    limits = config["limits"]

    if not attachments:
        return "A submission must include at least one image, audio, or video file."
    if len(text) > limits["max_text_length"]:
        return f"Text is limited to {limits['max_text_length']} characters."
    if len(attachments) > 5:
        return "A submission can contain at most 5 media files."

    bad_files = [
        attachment.filename
        for attachment in attachments
        if not is_allowed_file(attachment.filename)
    ]
    if bad_files:
        return "Unsupported file type: " + ", ".join(bad_files)

    oversized = [
        attachment.filename
        for attachment in attachments
        if attachment.size > limits["max_file_bytes"]
    ]
    if oversized:
        return "Files exceed the per-file limit: " + ", ".join(oversized)

    total_size = sum(attachment.size for attachment in attachments)
    if total_size > limits["max_total_bytes"]:
        return "The combined upload exceeds the total submission limit."
    return None


def submission_preview(category, message):
    text = message.content.strip() or "(no text)"
    file_lines = [
        f"- `{attachment.filename}` ({attachment.size / 1024 / 1024:.2f} MB)"
        for attachment in message.attachments
    ]
    files = "\n".join(file_lines) if file_lines else "(no media)"
    return (
        "**Step 3 of 3: Confirm your submission**\n"
        f"Category: `{category}`\n\n"
        f"Text:\n{text}\n\n"
        f"Media:\n{files}\n\n"
        "Choose **Confirm** to submit or **Cancel** to discard it."
    )


def submission_preview_embeds(message):
    embeds = []
    for attachment in message.attachments:
        if get_media_type(attachment.filename) != "image":
            continue
        embed = discord.Embed(title=attachment.filename)
        embed.set_image(url=attachment.url)
        embeds.append(embed)
    return embeds


async def delete_source_message(message):
    try:
        await message.delete()
        return True, ""
    except discord.NotFound:
        return True, ""
    except discord.Forbidden:
        return (
            False,
            "The bot needs the **Manage Messages** permission in the submit channel.",
        )
    except discord.HTTPException:
        try:
            fresh_message = await message.channel.fetch_message(message.id)
            await fresh_message.delete()
            return True, ""
        except discord.NotFound:
            return True, ""
        except discord.Forbidden:
            return (
                False,
                "The bot needs the **Manage Messages** permission in the submit channel.",
            )
        except discord.HTTPException as error:
            return False, f"The source message could not be deleted: {error}"


async def create_submission(source_message, category):
    guild_config = get_guild_config(source_message.guild.id, create=False)
    categories_config = guild_config.get("categories", {})
    target_channel = bot.get_channel(categories_config.get(category))
    if target_channel is None:
        return False, "The category channel could not be found."

    approval_channel = None
    if guild_config["approval_enabled"]:
        approval_channel_id = guild_config.get("approval_channel")
        approval_channel = (
            bot.get_channel(approval_channel_id)
            if approval_channel_id
            else None
        )
        if approval_channel is None:
            return False, "Approval is enabled, but its channel is unavailable."

    cooldown_message, retry_after, bucket = submission_cooldown_message(
        source_message.guild.id,
        source_message.author.id,
        category,
    )
    if cooldown_message:
        record_rate_limit_event(
            source_message.guild.id,
            source_message.author.id,
            source_message.author,
            f"submission_{bucket}",
            "create_submission",
            retry_after,
            f"Category {category}.",
        )
        return False, cooldown_message

    text = source_message.content.strip()
    attachments = list(source_message.attachments)
    user_folder = (
        MEDIA_DIR
        / str(source_message.guild.id)
        / category
        / str(source_message.author.id)
    )
    user_folder.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    media_names = []
    media_types = []
    media_sizes = []
    media_metadata = []
    created_message = None
    submission_id = None

    try:
        for attachment in attachments:
            safe_name = Path(attachment.filename).name.replace("\\", "_")
            filename = (
                f"{int(time.time())}_{source_message.id}_{safe_name}"
            )
            path = user_folder / filename
            await attachment.save(path)
            saved_paths.append(str(path))
            media_names.append(attachment.filename)
            media_types.append(get_media_type(attachment.filename))
            media_sizes.append(str(int(attachment.size or 0)))
            media_metadata.append(attachment_metadata(attachment, path))

        status = "pending" if approval_channel else "posted"
        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_channel_id,
                    user_id, username, category, message_text,
                    file_paths, media_paths, media_names, media_types,
                    media_sizes, media_metadata_json,
                    stars, voters, status, submitted_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?)
            """, (
                str(source_message.guild.id),
                str(source_message.id),
                str(target_channel.id),
                str(source_message.author.id),
                str(source_message.author),
                category,
                text,
                ";".join(saved_paths),
                ";".join(saved_paths),
                ";".join(media_names),
                ";".join(media_types),
                ";".join(media_sizes),
                json.dumps(media_metadata, separators=(",", ":")),
                status,
                utc_now_iso(),
                utc_now_iso(),
            ))
            submission_id = cursor.lastrowid
            row = connection.execute(
                "SELECT * FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()

        if approval_channel:
            created_message = await send_submission_message(
                approval_channel,
                (
                    f"Pending submission `{submission_id}`\n\n"
                    + submission_content(row)
                ),
                row,
                ApprovalView(),
            )
            with database() as connection:
                connection.execute("""
                    UPDATE submissions
                    SET approval_message_id = ?, approval_channel_id = ?
                    WHERE id = ?
                """, (
                    str(created_message.id),
                    str(approval_channel.id),
                    submission_id,
                ))
            response_text = (
                f"Submission `{submission_id}` is awaiting approval."
            )
        else:
            created_message = await send_submission_message(
                target_channel,
                submission_content(row),
                row,
                VoteView(),
            )
            with database() as connection:
                connection.execute("""
                    UPDATE submissions
                    SET repost_message_id = ?, approved_at = ?
                    WHERE id = ?
                """, (
                    str(created_message.id),
                    utc_now_iso(),
                    submission_id,
                ))
            response_text = (
                f"Submitted to `{category}` as `{submission_id}`."
            )

        now = time.time()
        user_cooldowns[
            f"{source_message.guild.id}:{source_message.author.id}"
        ] = now
        category_cooldowns[
            f"{source_message.guild.id}:{category}"
        ] = now
        deleted, delete_error = await delete_source_message(source_message)
        if not deleted:
            raise RuntimeError(delete_error)
        return True, response_text
    except Exception as error:
        capture_exception(error)
        if created_message is not None:
            try:
                await created_message.delete()
            except discord.HTTPException:
                pass
        if submission_id is not None:
            with database() as connection:
                connection.execute(
                    "DELETE FROM submissions WHERE id = ?",
                    (submission_id,),
                )
        cleanup_files(saved_paths)
        return False, f"Submission failed: `{error}`"


class SubmissionConfirmView(discord.ui.View):
    def __init__(self, source_message, category, session_key):
        super().__init__(timeout=300)
        self.source_message = source_message
        self.category = category
        self.session_key = session_key
        self.finished = False
        self.preview_message = None

    async def interaction_check(self, interaction):
        if interaction.user.id == self.source_message.author.id:
            return True
        await interaction.response.send_message(
            "Only the person who started this submission can use these buttons.",
            ephemeral=True,
        )
        return False

    async def finish(self, content):
        active_submission_sessions.discard(self.session_key)
        self.stop()
        if self.preview_message is not None:
            try:
                await self.preview_message.edit(
                    content=content,
                    embeds=[],
                    view=None,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
    )
    async def confirm(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(
                "This submission has already been handled.",
                ephemeral=True,
            )
            return
        self.finished = True
        await interaction.response.defer()
        success, message = await create_submission(
            self.source_message,
            self.category,
        )
        if not success:
            self.finished = False
            await interaction.followup.send(message, ephemeral=True)
            return
        await self.finish(f"**Submission complete**\n{message}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
    )
    async def cancel(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(
                "This submission has already been handled.",
                ephemeral=True,
            )
            return
        self.finished = True
        await interaction.response.defer()
        deleted, delete_error = await delete_source_message(
            self.source_message
        )
        if deleted:
            await self.finish("Submission cancelled.")
        else:
            await self.finish(
                f"Submission cancelled, but {delete_error}"
            )

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        deleted, delete_error = await delete_source_message(
            self.source_message
        )
        message = "Submission timed out. Run `/submit` to start again."
        if not deleted:
            message += f"\n{delete_error}"
        await self.finish(message)


@tree.command(name="submit", description="Start a guided SDAC submission")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
@app_commands.describe(category="Submission category")
async def submit(interaction, category: str):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    submit_channel_id = guild_config.get("submit_channel")
    if not submit_channel_id:
        await interaction.response.send_message(
            "The submit channel is not configured.",
            ephemeral=True,
        )
        return
    if interaction.channel_id != submit_channel_id:
        channel = bot.get_channel(submit_channel_id)
        await interaction.response.send_message(
            f"Please submit in {channel.mention if channel else 'the configured channel'}.",
            ephemeral=True,
        )
        return

    if not interaction.app_permissions.manage_messages:
        await interaction.response.send_message(
            "The bot needs the **Manage Messages** permission in this "
            "channel before guided submissions can be used.",
            ephemeral=True,
        )
        return

    category = clean_category_name(category)
    if category not in guild_config.get("categories", {}):
        await interaction.response.send_message(
            f"Invalid category `{category}`.",
            ephemeral=True,
        )
        return

    cooldown_message, retry_after, bucket = submission_cooldown_message(
        interaction.guild_id,
        interaction.user.id,
        category,
    )
    if cooldown_message:
        record_rate_limit_event(
            interaction.guild_id,
            interaction.user.id,
            interaction.user,
            f"submission_{bucket}",
            "submit",
            retry_after,
            f"Category {category}.",
        )
        await interaction.response.send_message(
            cooldown_message,
            ephemeral=True,
        )
        return

    session_key = f"{interaction.guild_id}:{interaction.user.id}"
    if session_key in active_submission_sessions:
        await interaction.response.send_message(
            "You already have an active submission. Finish or cancel it first.",
            ephemeral=True,
        )
        return

    active_submission_sessions.add(session_key)
    await interaction.response.send_message(
        "**Step 2 of 3: Send your content**\n"
        "Send one normal message in this channel with at least one image, "
        "audio, or video attachment. Text is optional. You can attach up "
        "to 5 files.\n\n"
        "You have 5 minutes.",
        ephemeral=True,
    )

    def message_check(message):
        return (
            message.guild
            and message.guild.id == interaction.guild_id
            and message.channel.id == interaction.channel_id
            and message.author.id == interaction.user.id
            and not message.author.bot
        )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + 300
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            source_message = await bot.wait_for(
                "message",
                timeout=remaining,
                check=message_check,
            )
            validation_error = validate_submission_message(source_message)
            if not validation_error:
                break
            await delete_source_message(source_message)
            await interaction.edit_original_response(
                content=(
                    f"**Step 2 of 3: Try again**\n{validation_error}\n\n"
                    "Send another message with valid text and/or media."
                )
            )
    except asyncio.TimeoutError:
        active_submission_sessions.discard(session_key)
        await interaction.edit_original_response(
            content="Submission timed out. Run `/submit` to start again.",
            view=None,
        )
        return

    view = SubmissionConfirmView(source_message, category, session_key)
    preview_message = await interaction.edit_original_response(
        content=submission_preview(category, source_message),
        embeds=submission_preview_embeds(source_message),
        view=view,
    )
    view.preview_message = preview_message


@tree.command(name="startgame", description="Start a guessing game in a channel")
@app_commands.guild_only()
@app_commands.describe(
    channel="Channel where users will guess",
    answer="Correct answer for the media",
    media="Image, video, or audio to guess",
    text="Optional prompt text",
)
async def startgame(
    interaction,
    channel: discord.TextChannel,
    answer: str,
    media: discord.Attachment,
    text: str = "",
):
    if not await require_admin(interaction):
        return

    answer = answer.strip()
    if not answer:
        await interaction.response.send_message(
            "The answer cannot be empty.",
            ephemeral=True,
        )
        return
    if len(text) > config["limits"]["max_text_length"]:
        await interaction.response.send_message(
            f"Text is limited to {config['limits']['max_text_length']} characters.",
            ephemeral=True,
        )
        return
    if not is_allowed_file(media.filename):
        await interaction.response.send_message(
            "The game media must be an image, video, or audio file.",
            ephemeral=True,
        )
        return
    if media.size > config["limits"]["max_file_bytes"]:
        await interaction.response.send_message(
            "The game media exceeds the per-file size limit.",
            ephemeral=True,
        )
        return

    bot_member = interaction.guild.me
    if bot_member is None and bot.user is not None:
        bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        await interaction.response.send_message(
            "The bot could not verify its permissions in that channel.",
            ephemeral=True,
        )
        return

    permissions = channel.permissions_for(bot_member)
    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.attach_files
    ):
        await interaction.response.send_message(
            "The bot needs View Channel, Send Messages, and Attach Files "
            f"in {channel.mention}.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    replaced_game = await close_active_guess_game(
        interaction.guild_id,
        channel.id,
        "replaced",
    )
    game_folder = (
        MEDIA_DIR
        / str(interaction.guild_id)
        / "guess_games"
        / str(channel.id)
    )
    game_folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(media.filename).name.replace("\\", "_")
    media_path = game_folder / f"{int(time.time())}_{interaction.id}_{safe_name}"
    discord_file = None
    game_message = None
    game_id = None

    try:
        await media.save(media_path)
        media_metadata = attachment_metadata(media, media_path)
        discord_file = discord.File(media_path, filename=media.filename)
        game_message = await channel.send(
            content=(
                "**Guessing Game Started**\n"
                f"{text.strip()}\n\n"
                "Use `/guess <guess>` in this channel."
            ).strip(),
            file=discord_file,
        )

        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO guess_games (
                    guild_id, channel_id, message_id, starter_user_id,
                    starter_username, answer, answer_display, prompt_text,
                    media_path, media_name, media_type, media_size,
                    media_metadata_json, status, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (
                str(interaction.guild_id),
                str(channel.id),
                str(game_message.id),
                str(interaction.user.id),
                str(interaction.user),
                normalize_guess(answer),
                answer,
                text.strip(),
                str(media_path),
                media.filename,
                get_media_type(media.filename),
                int(media.size or 0),
                json.dumps(media_metadata, separators=(",", ":")),
                utc_now_iso(),
            ))
            game_id = cursor.lastrowid
            add_admin_audit_log(
                connection,
                interaction.guild_id,
                "start_guess_game",
                interaction.user.id,
                interaction.user,
                "game",
                game_id,
                (
                    f"Channel {channel.id}; media {media.filename}; "
                    f"replaced={bool(replaced_game)}."
                ),
            )

        await interaction.followup.send(
            (
                f"Guessing game `{game_id}` started in {channel.mention}."
                + (" Previous active game was removed." if replaced_game else "")
            ),
            ephemeral=True,
        )
    except Exception as error:
        capture_exception(error)
        if game_message is not None:
            try:
                await game_message.delete()
            except discord.HTTPException:
                pass
        if game_id is not None:
            with database() as connection:
                connection.execute(
                    "DELETE FROM guess_games WHERE id = ?",
                    (game_id,),
                )
        cleanup_files([str(media_path)])
        await interaction.followup.send(
            f"Game start failed: `{error}`",
            ephemeral=True,
        )
    finally:
        if discord_file is not None:
            discord_file.close()


@tree.command(name="activegame", description="Show this channel's active guessing game")
@app_commands.guild_only()
async def activegame(interaction):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id, create=False)
    timezone_info = get_guild_timezone(guild_config)
    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()
        correct_rows = []
        if game:
            correct_rows = connection.execute("""
                SELECT username, guessed_at
                FROM guess_correct_guesses
                WHERE game_id = ?
                ORDER BY guessed_at ASC
            """, (game["id"],)).fetchall()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    started_at = parse_database_datetime(game["started_at"])
    started_display = started_at.astimezone(timezone_info).strftime(
        "%Y-%m-%d %H:%M"
    )
    correct_names = [row["username"] for row in correct_rows]
    correct_display = ", ".join(correct_names[:20]) if correct_names else "Nobody"
    if len(correct_names) > 20:
        correct_display += f" and {len(correct_names) - 20} more"

    await interaction.response.send_message(
        "\n".join([
            f"**Active Guessing Game {game['id']}**",
            f"Channel: {channel_display(game['channel_id'])}",
            f"Started by: {game['starter_username']}",
            f"Started: `{started_display}` `{guild_config.get('timezone', 'UTC')}`",
            f"Answer: `{game['answer_display']}`",
            f"Prompt: {game['prompt_text'] or '(none)'}",
            f"Hint: {game['hint_text'] or '(none)'}",
            f"Hint revealed: {'Yes' if game['hint_revealed_at'] else 'No'}",
            f"Media: `{game['media_name']}` ({game['media_type']})",
            f"Correct guessers: {correct_display}",
        ]),
        ephemeral=True,
    )


@tree.command(name="cancelgame", description="Cancel this channel's active guessing game")
@app_commands.guild_only()
async def cancelgame(interaction):
    if not await require_admin(interaction):
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    game = await close_active_guess_game(
        interaction.guild_id,
        interaction.channel_id,
        "cancelled",
    )
    if not game:
        await interaction.followup.send(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    audit_interaction(
        interaction,
        "cancel_guess_game",
        "game",
        game["id"],
        f"Cancelled in channel {interaction.channel_id}.",
    )
    await interaction.followup.send(
        f"Cancelled guessing game `{game['id']}` without revealing the answer.",
        ephemeral=True,
    )
    if interaction.channel is not None:
        await interaction.channel.send("The current guessing game was cancelled.")


@tree.command(name="sethint", description="Reveal a hint for this channel's game")
@app_commands.guild_only()
@app_commands.describe(hint="Hint to reveal for the active game")
async def sethint(interaction, hint: str):
    if not await require_admin(interaction):
        return
    hint = hint.strip()
    if not hint:
        await interaction.response.send_message(
            "Hint cannot be empty.",
            ephemeral=True,
        )
        return

    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()
        if not game:
            await interaction.response.send_message(
                "There is no active guessing game in this channel.",
                ephemeral=True,
            )
            return
        connection.execute("""
            UPDATE guess_games
            SET hint_text = ?,
                hint_revealed_at = COALESCE(hint_revealed_at, ?)
            WHERE id = ?
        """, (hint, utc_now_iso(), game["id"]))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "set_guess_hint",
            interaction.user.id,
            interaction.user,
            "game",
            game["id"],
            "Hint revealed for active guessing game.",
        )

    await interaction.response.send_message(
        "Hint revealed.",
        ephemeral=True,
    )
    await interaction.channel.send(
        f"**Guessing Game Hint**\n{hint}\n\n"
        "Correct guesses after a hint do not add leaderboard points."
    )


@tree.command(name="hint", description="Show this channel's game hint")
@app_commands.guild_only()
async def hint(interaction):
    with database() as connection:
        game = connection.execute("""
            SELECT hint_text, hint_revealed_at
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return
    if not game["hint_revealed_at"] or not game["hint_text"]:
        await interaction.response.send_message(
            "No hint has been revealed yet.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"**Hint:** {game['hint_text']}",
        ephemeral=True,
    )


@tree.command(name="guess", description="Guess the answer for this channel's game")
@app_commands.guild_only()
@app_commands.describe(guess="Your guess")
async def guess(interaction, guess: str):
    normalized_guess = normalize_guess(guess)
    if not normalized_guess:
        await interaction.response.send_message(
            "Your guess cannot be empty.",
            ephemeral=True,
        )
        return

    message, retry_after = command_cooldown_message(
        "guess_command",
        interaction.guild_id,
        interaction.user.id,
        configured_limit("guess_command_cooldown_seconds", 2),
    )
    if message:
        record_rate_limit_event(
            interaction.guild_id,
            interaction.user.id,
            interaction.user,
            "guess_command",
            "guess",
            retry_after,
            "Slash command cooldown.",
        )
        await interaction.response.send_message(message, ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    channel = interaction.channel
    guild_config = get_guild_config(interaction.guild_id, create=False)
    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

        if not game:
            await interaction.response.send_message(
                "There is no active guessing game in this channel.",
                ephemeral=True,
            )
            return

        cooldown = connection.execute("""
            SELECT timeout_until
            FROM guess_cooldowns
            WHERE guild_id = ?
              AND channel_id = ?
              AND user_id = ?
        """, (
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
        )).fetchone()

        if cooldown and cooldown["timeout_until"]:
            timeout_until = datetime.fromisoformat(cooldown["timeout_until"])
            if timeout_until > now:
                remaining = int((timeout_until - now).total_seconds()) + 1
                await interaction.response.send_message(
                    f"Wrong guess cooldown: try again in {remaining}s.",
                    ephemeral=True,
                )
                return

        if normalized_guess != game["answer"]:
            seconds = config["limits"].get(
                "wrong_guess_timeout_seconds",
                600,
            )
            timeout_until = now + timedelta(seconds=seconds)
            connection.execute("""
                INSERT INTO guess_cooldowns (
                    guild_id, channel_id, user_id, timeout_until
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT (guild_id, channel_id, user_id)
                DO UPDATE SET timeout_until = excluded.timeout_until
            """, (
                str(interaction.guild_id),
                str(interaction.channel_id),
                str(interaction.user.id),
                timeout_until.isoformat(),
            ))
            connection.execute("""
                INSERT INTO rate_limit_events (
                    guild_id, user_id, username, bucket, action,
                    retry_after_seconds, details, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(interaction.guild_id),
                str(interaction.user.id),
                str(interaction.user),
                "wrong_guess",
                "guess",
                int(seconds),
                f"Game {game['id']}.",
                utc_now_iso(),
            ))
            await interaction.response.send_message(
                f"Incorrect. You can guess again in {seconds}s.",
                ephemeral=True,
            )
            return

        month = current_month_key(guild_config)
        points_awarded = 0 if game["hint_revealed_at"] else 1
        existing_correct = connection.execute("""
            SELECT 1
            FROM guess_correct_guesses
            WHERE game_id = ? AND user_id = ?
        """, (game["id"], str(interaction.user.id))).fetchone()
        if existing_correct:
            await interaction.response.send_message(
                "You already guessed this one correctly.",
                ephemeral=True,
            )
            return

        connection.execute("""
            INSERT INTO guess_correct_guesses (
                game_id, guild_id, channel_id, user_id, username, guessed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            game["id"],
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        connection.execute("""
            UPDATE guess_games
            SET winner_user_id = COALESCE(winner_user_id, ?),
                winner_username = COALESCE(winner_username, ?)
            WHERE id = ? AND status = 'active'
        """, (
            str(interaction.user.id),
            str(interaction.user),
            game["id"],
        ))
        if points_awarded:
            connection.execute("""
                INSERT INTO guess_points (
                    guild_id, channel_id, user_id, username,
                    month, points, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (guild_id, channel_id, user_id, month)
                DO UPDATE SET
                    points = points + excluded.points,
                    username = excluded.username,
                    updated_at = excluded.updated_at
            """, (
                str(interaction.guild_id),
                str(interaction.channel_id),
                str(interaction.user.id),
                str(interaction.user),
                month,
                points_awarded,
                utc_now_iso(),
            ))
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE guild_id = ?
              AND channel_id = ?
              AND user_id = ?
        """, (
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
        ))

    if points_awarded:
        response_text = f"Correct. You gained {points_awarded} point for `{month}`."
    else:
        response_text = (
            "Correct. This game already has a hint revealed, so no "
            "leaderboard point was added."
        )
    await interaction.response.send_message(response_text, ephemeral=True)
    if channel is not None:
        await channel.send(
            f"{interaction.user.mention} guessed correctly."
        )


@tree.command(name="correct", description="Reveal and close this channel's guessing game")
@app_commands.guild_only()
async def correct(interaction):
    if not await require_admin(interaction):
        return

    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    with database() as connection:
        connection.execute("""
            UPDATE guess_games
            SET status = 'closed',
                solved_at = ?
            WHERE id = ? AND status = 'active'
        """, (utc_now_iso(), game["id"]))
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE guild_id = ? AND channel_id = ?
        """, (str(interaction.guild_id), str(interaction.channel_id)))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "correct_guess_game",
            interaction.user.id,
            interaction.user,
            "game",
            game["id"],
            f"Closed and revealed in channel {interaction.channel_id}.",
        )

    await interaction.response.send_message(
        "Closing the current guessing game.",
        ephemeral=True,
    )
    await announce_guess_summary(interaction.channel, game, "manual close")


@tree.command(name="removesubmission", description="Remove a submission")
@app_commands.guild_only()
@app_commands.describe(submission_id="Dashboard submission ID", reason="Audit reason")
async def removesubmission(
    interaction,
    submission_id: int,
    reason: str = "Removed by Discord admin",
):
    if not await require_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    with database() as connection:
        row = connection.execute(
            "SELECT guild_id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if row and row["guild_id"] and row["guild_id"] != str(interaction.guild_id):
        await interaction.followup.send(
            "That submission belongs to another server.",
            ephemeral=True,
        )
        return
    success, message = await remove_submission_record(
        submission_id,
        interaction.user.id,
        interaction.user,
        reason,
    )
    await interaction.followup.send(message, ephemeral=True)


@tree.command(name="submissioninfo", description="Show submission details")
@app_commands.guild_only()
async def submissioninfo(interaction, submission_id: int):
    if not await require_admin(interaction):
        return
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if not row or (
        row["guild_id"]
        and row["guild_id"] != str(interaction.guild_id)
    ):
        await interaction.response.send_message(
            "Submission not found.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        "\n".join([
            f"**Submission {row['id']}**",
            f"Status: `{row['status']}`",
            f"Category: `{row['category']}`",
            f"User: {row['username']} (`{row['user_id']}`)",
            f"Stars: {row['stars'] or 0}",
            f"Created: {row['created_at'] or row['submitted_at']}",
            f"Text: {row['message_text'] or '(none)'}",
        ]),
        ephemeral=True,
    )


async def post_weekly_top(guild_id, guild_config, now):
    channel_id = guild_config.get("daily_top_channel")
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    week_key = weekly_run_key(now)
    with database() as connection:
        already_ran = connection.execute("""
            SELECT 1 FROM daily_runs
            WHERE guild_id = ? AND run_date = ?
        """, (str(guild_id), week_key)).fetchone()
        if already_ran:
            return

        rows = []
        for category in sorted(guild_config.get("categories", {})):
            row = connection.execute("""
                SELECT *
                FROM submissions
                WHERE guild_id = ?
                  AND category = ?
                  AND status = 'posted'
                  AND daily_posted_at IS NULL
                ORDER BY stars DESC, created_at DESC
                LIMIT 1
            """, (str(guild_id), category)).fetchone()
            if row:
                rows.append(row)

    if rows:
        lines = ["**SDAC Weekly Top Posts**"]
        for row in rows:
            link = (
                f"https://discord.com/channels/{guild_id}/"
                f"{row['repost_channel_id']}/{row['repost_message_id']}"
            )
            preview = (row["message_text"] or "").strip()[:100]
            lines.append(
                f"\n**{row['category']}** - {row['username']} - "
                f"{row['stars'] or 0} votes\n{preview}\n{link}"
            )
        await channel.send("\n".join(lines))

    with database() as connection:
        for row in rows:
            connection.execute(
                "UPDATE submissions SET daily_posted_at = ? WHERE id = ?",
                (utc_now_iso(), row["id"]),
            )
        connection.execute("""
            INSERT OR IGNORE INTO daily_runs (guild_id, run_date, created_at)
            VALUES (?, ?, ?)
        """, (str(guild_id), week_key, utc_now_iso()))


async def post_monthly_guess_leaderboards():
    with database() as connection:
        guild_rows = connection.execute("""
            SELECT DISTINCT guild_id
            FROM guess_points
            WHERE guild_id IS NOT NULL AND guild_id != ''
        """).fetchall()

    for guild_row in guild_rows:
        guild_id = guild_row["guild_id"]
        guild_config = get_guild_config(guild_id, create=False)
        now = guild_now(guild_config)
        if now.day != 1:
            continue

        month = previous_month_key(now)
        with database() as connection:
            preserve_monthly_submission_top(connection, month)
            channel_rows = connection.execute("""
                SELECT DISTINCT guild_id, channel_id
                FROM guess_points
                WHERE guild_id = ?
                  AND month = ?
            """, (guild_id, month)).fetchall()

        for channel_row in channel_rows:
            channel_id = channel_row["channel_id"]
            with database() as connection:
                already_posted = connection.execute("""
                    SELECT 1
                    FROM monthly_guess_runs
                    WHERE guild_id = ?
                      AND channel_id = ?
                      AND month = ?
                """, (guild_id, channel_id, month)).fetchone()
                if already_posted:
                    continue
                leaders = connection.execute("""
                    SELECT username, points
                    FROM guess_points
                    WHERE guild_id = ?
                      AND channel_id = ?
                      AND month = ?
                    ORDER BY points DESC, username ASC
                    LIMIT 3
                """, (guild_id, channel_id, month)).fetchall()

            if not leaders:
                continue

            channel = bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except discord.HTTPException:
                    channel = None
            if channel is None:
                continue

            lines = [f"**Guessing Game Top 3 - {month}**"]
            for index, leader in enumerate(leaders, start=1):
                lines.append(
                    f"{index}. {leader['username']} - {leader['points']} point(s)"
                )
            await channel.send("\n".join(lines))

            with database() as connection:
                connection.execute("""
                    INSERT OR IGNORE INTO monthly_guess_runs (
                        guild_id, channel_id, month, created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (guild_id, channel_id, month, utc_now_iso()))


async def post_daily_guess_summaries():
    with database() as connection:
        games = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE status = 'active'
        """).fetchall()

    for game in games:
        guild_config = get_guild_config(game["guild_id"], create=False)
        timezone_info = get_guild_timezone(guild_config)
        now = datetime.now(timezone_info)
        today = now.date().isoformat()
        started_at = parse_database_datetime(game["started_at"])
        if started_at.astimezone(timezone_info).date() >= now.date():
            continue

        with database() as connection:
            already_posted = connection.execute("""
                SELECT 1
                FROM daily_guess_runs
                WHERE guild_id = ?
                  AND channel_id = ?
                  AND run_date = ?
            """, (game["guild_id"], game["channel_id"], today)).fetchone()
            if already_posted:
                continue
            connection.execute("""
                UPDATE guess_games
                SET status = 'closed',
                    solved_at = ?
                WHERE id = ? AND status = 'active'
            """, (utc_now_iso(), game["id"]))
            connection.execute("""
                DELETE FROM guess_cooldowns
                WHERE guild_id = ? AND channel_id = ?
            """, (game["guild_id"], game["channel_id"]))
            connection.execute("""
                INSERT OR IGNORE INTO daily_guess_runs (
                    guild_id, channel_id, run_date, created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                game["guild_id"],
                game["channel_id"],
                today,
                utc_now_iso(),
            ))

        channel = bot.get_channel(int(game["channel_id"]))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(game["channel_id"]))
            except discord.HTTPException:
                channel = None
        if channel is not None:
            await announce_guess_summary(channel, game, "end of day")


@tasks.loop(minutes=1)
async def weekly_top_scheduler():
    try:
        for guild_id, guild_config in config.get("guilds", {}).items():
            now = guild_now(guild_config)
            current_time = now.strftime("%H:%M")
            if now.weekday() != weekly_top_day_index(guild_config):
                continue
            if guild_config.get("daily_top_time_utc", "00:00") == current_time:
                await post_weekly_top(guild_id, guild_config, now)
    except Exception as error:
        await report_background_error("weekly_top_scheduler", error)


@weekly_top_scheduler.before_loop
async def before_weekly_top_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def backup_scheduler():
    global last_backup_date
    try:
        backup_date = datetime.now(timezone.utc).date().isoformat()
        if last_backup_date != backup_date:
            create_daily_database_backup()
            last_backup_date = backup_date
    except Exception as error:
        await report_background_error("backup_scheduler", error)


@backup_scheduler.before_loop
async def before_backup_scheduler():
    await bot.wait_until_ready()


def restore_test_weekday_index():
    day = normalize_weekday(config["limits"].get("restore_test_weekday"))
    if day is None:
        day = DEFAULT_CONFIG["limits"]["restore_test_weekday"]
    return WEEKDAY_NAMES.index(day)


def restore_test_time_minutes():
    raw_value = str(
        config["limits"].get(
            "restore_test_time_utc",
            DEFAULT_CONFIG["limits"]["restore_test_time_utc"],
        )
    )
    if not re.match(r"^\d{2}:\d{2}$", raw_value):
        raw_value = DEFAULT_CONFIG["limits"]["restore_test_time_utc"]
    hour, minute = [int(part) for part in raw_value.split(":")]
    if hour > 23 or minute > 59:
        hour, minute = [int(part) for part in (
            DEFAULT_CONFIG["limits"]["restore_test_time_utc"].split(":")
        )]
    return hour * 60 + minute


@tasks.loop(minutes=30)
async def restore_test_scheduler():
    try:
        if not config["limits"].get("restore_test_enabled", True):
            return
        now = datetime.now(timezone.utc)
        if now.weekday() != restore_test_weekday_index():
            return
        if now.hour * 60 + now.minute < restore_test_time_minutes():
            return
        run_key = f"restore:{now.strftime('%G-W%V')}"
        if restore_test_has_run(run_key):
            return
        passed, backup_path, details = run_restore_test(run_key)
        if passed:
            print(f"Restore test passed: {details}", flush=True)
            return
        target = backup_path.name if backup_path else "no backup"
        await send_system_error_notification(
            f"Weekly restore test failed for `{target}`: `{details}`"
        )
    except Exception as error:
        await report_background_error("restore_test_scheduler", error)


@restore_test_scheduler.before_loop
async def before_restore_test_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=10)
async def guess_summary_scheduler():
    try:
        await post_daily_guess_summaries()
    except Exception as error:
        await report_background_error("guess_summary_scheduler", error)


@guess_summary_scheduler.before_loop
async def before_guess_summary_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def monthly_leaderboard_scheduler():
    try:
        await post_monthly_guess_leaderboards()
    except Exception as error:
        await report_background_error("monthly_leaderboard_scheduler", error)


@monthly_leaderboard_scheduler.before_loop
async def before_monthly_leaderboard_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=60)
async def cleanup_scheduler():
    try:
        cleanup_background_data()
    except Exception as error:
        await report_background_error("cleanup_scheduler", error)


@cleanup_scheduler.before_loop
async def before_cleanup_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=6)
async def storage_warning_scheduler():
    global last_storage_warning_date
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        if last_storage_warning_date == today:
            return
        warnings = storage_warning_lines()
        if not warnings:
            return
        last_storage_warning_date = today
        await send_system_error_notification(
            "Storage warning:\n" + "\n".join(f"- {line}" for line in warnings)
        )
    except Exception as error:
        await report_background_error("storage_warning_scheduler", error)


@storage_warning_scheduler.before_loop
async def before_storage_warning_scheduler():
    await bot.wait_until_ready()


async def sync_slash_commands():
    global slash_commands_synced
    if slash_commands_synced:
        print("Slash commands already synced for this process.", flush=True)
        return

    local_names = ", ".join(sorted(command.name for command in tree.get_commands()))
    print(f"Local slash commands registered: {local_names}", flush=True)

    synced_global = await tree.sync()
    command_names = ", ".join(sorted(command.name for command in synced_global))
    print(
        f"Synced {len(synced_global)} global slash commands: {command_names}",
        flush=True,
    )

    for guild in bot.guilds:
        discord_guild = discord.Object(id=guild.id)
        tree.copy_global_to(guild=discord_guild)
        synced_guild = await tree.sync(guild=discord_guild)
        guild_command_names = ", ".join(
            sorted(command.name for command in synced_guild)
        )
        print(
            f"Synced {len(synced_guild)} slash commands to "
            f"{guild.name} ({guild.id}): {guild_command_names}",
            flush=True,
        )
    slash_commands_synced = True


@bot.event
async def on_ready():
    global persistent_views_registered
    print(f"on_ready fired for {bot.user}. Starting slash command sync.", flush=True)
    if not persistent_views_registered:
        bot.add_view(VoteView())
        bot.add_view(ApprovalView())
        persistent_views_registered = True
    migrate_legacy_config()
    refresh_known_guilds()
    try:
        await sync_slash_commands()
    except Exception as error:
        print(f"Slash command sync failed: {error}", flush=True)
        for guild in bot.guilds:
            await send_error_notification(guild.id, f"Slash command sync failed: `{error}`")
    if not weekly_top_scheduler.is_running():
        weekly_top_scheduler.start()
    if not backup_scheduler.is_running():
        backup_scheduler.start()
    if not restore_test_scheduler.is_running():
        restore_test_scheduler.start()
    if not guess_summary_scheduler.is_running():
        guess_summary_scheduler.start()
    if not monthly_leaderboard_scheduler.is_running():
        monthly_leaderboard_scheduler.start()
    if not cleanup_scheduler.is_running():
        cleanup_scheduler.start()
    if not storage_warning_scheduler.is_running():
        storage_warning_scheduler.start()
    print(f"Logged in as {bot.user}", flush=True)
    print(f"Using database: {DB_FILE}", flush=True)
    print(f"Using config: {CONFIG_FILE}", flush=True)


@bot.event
async def on_error(event_method, *args, **kwargs):
    capture_exception(Exception(f"Unhandled bot event error: {event_method}"))
    formatted = traceback.format_exc().strip()
    message = formatted[-1500:] if formatted else "Unknown bot event error."
    print(f"Unhandled event error in {event_method}: {message}", flush=True)
    await send_system_error_notification(
        f"Unhandled event error in `{event_method}`:\n```{message}```"
    )


@bot.event
async def on_guild_join(guild):
    guild_config = get_guild_config(guild.id)
    guild_config["guild_name"] = guild.name
    save_config(config)


def main():
    startup_health_check()
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
