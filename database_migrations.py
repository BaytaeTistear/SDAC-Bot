from datetime import datetime, timezone
import sqlite3


DATABASE_SCHEMA_VERSION = 9


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def table_exists(connection, table_name):
    row = connection.execute("""
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
    """, (table_name,)).fetchone()
    return row is not None


def ensure_column(connection, table_name, column_name, definition):
    if not table_exists(connection, table_name):
        return
    existing = {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }
    if column_name not in existing:
        try:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).casefold():
                raise


def ensure_schema_version_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


def current_schema_version(connection):
    ensure_schema_version_table(connection)
    row = connection.execute("""
        SELECT version
        FROM schema_version
        WHERE id = 1
    """).fetchone()
    return int(row["version"]) if row else 0


def set_schema_version(connection, version):
    connection.execute("""
        INSERT INTO schema_version (id, version, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            version = excluded.version,
            updated_at = excluded.updated_at
    """, (version, utc_now_iso()))


def migration_3_media_metadata_and_rate_limits(connection):
    ensure_column(connection, "submissions", "media_sizes", "TEXT")
    ensure_column(connection, "submissions", "media_metadata_json", "TEXT")
    ensure_column(connection, "monthly_submission_top", "media_sizes", "TEXT")
    ensure_column(
        connection,
        "monthly_submission_top",
        "media_metadata_json",
        "TEXT",
    )
    ensure_column(connection, "guess_games", "media_size", "INTEGER DEFAULT 0")
    ensure_column(connection, "guess_games", "media_metadata_json", "TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            username TEXT,
            bucket TEXT,
            action TEXT,
            retry_after_seconds INTEGER DEFAULT 0,
            details TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_created
        ON rate_limit_events (created_at, id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_bucket
        ON rate_limit_events (guild_id, bucket, created_at)
    """)


def migration_4_restore_test_runs(connection):
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
        CREATE INDEX IF NOT EXISTS idx_restore_test_runs_created
        ON restore_test_runs (created_at)
    """)


def migration_5_reports_aliases_and_hints(connection):
    ensure_column(connection, "guess_games", "answer_aliases_json", "TEXT")
    ensure_column(connection, "guess_games", "hints_json", "TEXT")
    ensure_column(connection, "guess_games", "hint_level", "INTEGER DEFAULT 0")
    ensure_column(connection, "guess_games", "next_hint_at", "TEXT")
    ensure_column(connection, "guess_games", "auto_hint_minutes", "INTEGER DEFAULT 0")
    ensure_column(connection, "guess_games", "hint_category", "TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS submission_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER,
            guild_id TEXT,
            reporter_name TEXT,
            reason TEXT,
            status TEXT DEFAULT 'open',
            admin_notes TEXT,
            created_at TEXT,
            resolved_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_submission_reports_status
        ON submission_reports (status, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_submission_reports_submission
        ON submission_reports (submission_id)
    """)


def migration_6_guess_library(connection):
    ensure_column(connection, "guess_games", "library_item_id", "INTEGER")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS guess_library_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            title TEXT,
            answer TEXT,
            answer_display TEXT,
            answer_aliases_json TEXT,
            prompt_text TEXT,
            category TEXT,
            hint_text TEXT,
            auto_hint_minutes INTEGER DEFAULT 0,
            media_path TEXT,
            media_name TEXT,
            media_type TEXT,
            media_size INTEGER DEFAULT 0,
            media_metadata_json TEXT,
            status TEXT DEFAULT 'active',
            times_used INTEGER DEFAULT 0,
            last_used_at TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_library_items_guild_status
        ON guess_library_items (guild_id, status, id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_library_items_last_used
        ON guess_library_items (guild_id, status, last_used_at)
    """)


def migration_7_operations_tables(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_admin_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'moderator',
            disabled INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            last_login_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_role
        ON dashboard_admin_users (role, disabled)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS setup_test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            actor_user_id TEXT,
            actor_username TEXT,
            status TEXT,
            summary TEXT,
            details_json TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_setup_test_runs_guild_created
        ON setup_test_runs (guild_id, created_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            event_key TEXT,
            channel_id TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE (guild_id, event_key)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_admin_notifications_guild_event
        ON admin_notifications (guild_id, event_key, enabled)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS game_seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            name TEXT,
            starts_at TEXT,
            ends_at TEXT,
            status TEXT DEFAULT 'active',
            winner_user_id TEXT,
            winner_username TEXT,
            winner_points INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_seasons_guild_status
        ON game_seasons (guild_id, status, starts_at, ends_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS backup_integrity (
            backup_name TEXT PRIMARY KEY,
            sha256 TEXT,
            size_bytes INTEGER DEFAULT 0,
            restore_status TEXT,
            restore_details TEXT,
            checked_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_backup_integrity_checked
        ON backup_integrity (checked_at)
    """)


def migration_8_multi_server_and_answer_history(connection):
    ensure_column(connection, "dashboard_admin_users", "guild_ids_json", "TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS guess_answer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            game_id INTEGER,
            library_item_id INTEGER,
            answer TEXT,
            answer_display TEXT,
            category TEXT,
            source TEXT,
            started_by TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_answer_history_guild_answer
        ON guess_answer_history (guild_id, answer, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_guess_answer_history_library
        ON guess_answer_history (library_item_id, created_at)
    """)


def migration_9_production_operations(connection):
    ensure_column(connection, "guess_library_items", "difficulty", "TEXT")
    ensure_column(
        connection,
        "guess_library_items",
        "reuse_cooldown_days",
        "INTEGER DEFAULT 0",
    )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS support_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            actor_user_id TEXT,
            actor_username TEXT,
            summary TEXT,
            details_json TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_bundles_created
        ON support_bundles (created_at, guild_id)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS content_moderation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            username TEXT,
            category TEXT,
            reason TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_moderation_events_guild_created
        ON content_moderation_events (guild_id, created_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS offsite_backup_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT,
            destination TEXT,
            status TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_offsite_backup_runs_created
        ON offsite_backup_runs (created_at, status)
    """)


MIGRATIONS = (
    (3, migration_3_media_metadata_and_rate_limits),
    (4, migration_4_restore_test_runs),
    (5, migration_5_reports_aliases_and_hints),
    (6, migration_6_guess_library),
    (7, migration_7_operations_tables),
    (8, migration_8_multi_server_and_answer_history),
    (9, migration_9_production_operations),
)


def apply_database_migrations(connection):
    version = current_schema_version(connection)
    for target_version, migration in MIGRATIONS:
        if version >= target_version:
            continue
        migration(connection)
        set_schema_version(connection, target_version)
        version = target_version
    if version < DATABASE_SCHEMA_VERSION:
        set_schema_version(connection, DATABASE_SCHEMA_VERSION)
    return DATABASE_SCHEMA_VERSION
