from datetime import datetime, timezone
import sqlite3


DATABASE_SCHEMA_VERSION = 5


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


MIGRATIONS = (
    (3, migration_3_media_metadata_and_rate_limits),
    (4, migration_4_restore_test_runs),
    (5, migration_5_reports_aliases_and_hints),
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
