from datetime import datetime, timezone
import sqlite3



DATABASE_SCHEMA_VERSION = 18
GOOGLE_PLAY_REVIEW_PASSWORD_HASH = "scrypt:32768:8:1$tpr2C1Lx7O3szQ0T$0f9b5ee8f0d5caaecaf4d69667ea93aff95365decc7108fd955590df4ef07c17680a64610805821aef23fcb86171de70c4bc0f577501ca920bb6b5bb80a4426b"


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
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_events_guild_created
        ON rate_limit_events (guild_id, created_at, id)
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


def migration_10_jobs_duplicates_and_privacy(connection):
    ensure_column(connection, "submissions", "media_hashes", "TEXT")
    ensure_column(connection, "submissions", "spam_score", "INTEGER DEFAULT 0")
    ensure_column(connection, "submissions", "spam_reasons_json", "TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS background_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT,
            guild_id TEXT,
            status TEXT DEFAULT 'queued',
            requested_by TEXT,
            requested_by_name TEXT,
            payload_json TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT,
            started_at TEXT,
            finished_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_background_jobs_status_created
        ON background_jobs (status, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_background_jobs_guild_created
        ON background_jobs (guild_id, created_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS media_fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_hash TEXT,
            guild_id TEXT,
            submission_id INTEGER,
            media_path TEXT,
            media_name TEXT,
            size_bytes INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_fingerprints_guild_hash
        ON media_fingerprints (guild_id, media_hash)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS privacy_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            action TEXT,
            actor_user_id TEXT,
            actor_username TEXT,
            details_json TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_privacy_actions_guild_user_created
        ON privacy_actions (guild_id, user_id, created_at)
    """)


def migration_11_operations_safety_tables(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS pending_admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            action_type TEXT,
            target_type TEXT,
            target_id TEXT,
            payload_json TEXT,
            requested_by TEXT,
            requested_by_name TEXT,
            approved_by TEXT,
            approved_by_name TEXT,
            status TEXT DEFAULT 'pending',
            result_text TEXT,
            created_at TEXT,
            approved_at TEXT,
            completed_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_admin_actions_status_created
        ON pending_admin_actions (status, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_admin_actions_guild_status
        ON pending_admin_actions (guild_id, status, created_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS media_quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            submission_id INTEGER,
            original_path TEXT,
            quarantine_path TEXT,
            media_name TEXT,
            reason TEXT,
            status TEXT DEFAULT 'quarantined',
            actor_user_id TEXT,
            actor_username TEXT,
            created_at TEXT,
            resolved_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_quarantine_status_created
        ON media_quarantine (status, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_media_quarantine_submission
        ON media_quarantine (submission_id, status)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS monthly_digest_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            month TEXT,
            status TEXT,
            details_json TEXT,
            posted_at TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_digest_runs_guild_month
        ON monthly_digest_runs (guild_id, month, created_at)
    """)


def migration_12_schedules_achievements_and_archives(connection):
    ensure_column(connection, "guess_library_items", "tags_json", "TEXT")
    ensure_column(connection, "guess_library_items", "pack_name", "TEXT")
    ensure_column(connection, "guess_library_items", "enabled", "INTEGER DEFAULT 1")
    ensure_column(connection, "guess_library_items", "notes", "TEXT")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            library_item_id INTEGER DEFAULT 0,
            category TEXT,
            random_item INTEGER DEFAULT 0,
            starts_at TEXT,
            close_after_minutes INTEGER DEFAULT 0,
            status TEXT DEFAULT 'queued',
            game_id INTEGER,
            created_by TEXT,
            created_by_name TEXT,
            created_at TEXT,
            updated_at TEXT,
            last_error TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduled_games_due
        ON scheduled_games (status, starts_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduled_games_guild_status
        ON scheduled_games (guild_id, status, starts_at)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_streaks (
            guild_id TEXT,
            user_id TEXT,
            username TEXT,
            current_guess_streak INTEGER DEFAULT 0,
            best_guess_streak INTEGER DEFAULT 0,
            last_correct_game_id INTEGER,
            updated_at TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_streaks_best
        ON user_streaks (guild_id, best_guess_streak)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            username TEXT,
            achievement_key TEXT,
            label TEXT,
            details TEXT,
            month TEXT,
            awarded_at TEXT,
            UNIQUE (guild_id, user_id, achievement_key, month)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_achievements_user
        ON user_achievements (guild_id, user_id, awarded_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_achievements_key
        ON user_achievements (guild_id, achievement_key, month)
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS backup_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            archive_type TEXT,
            file_path TEXT,
            size_bytes INTEGER DEFAULT 0,
            sha256 TEXT,
            destination TEXT,
            status TEXT DEFAULT 'created',
            details TEXT,
            created_by TEXT,
            created_by_name TEXT,
            created_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_backup_archives_created
        ON backup_archives (guild_id, created_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_backup_archives_status
        ON backup_archives (status, created_at)
    """)


def migration_13_dashboard_accounts(connection):
    ensure_column(connection, "dashboard_admin_users", "email", "TEXT")
    ensure_column(connection, "dashboard_admin_users", "display_name", "TEXT")
    ensure_column(
        connection,
        "dashboard_admin_users",
        "email_verified",
        "INTEGER DEFAULT 0",
    )
    ensure_column(connection, "dashboard_admin_users", "created_ip", "TEXT")
    ensure_column(connection, "dashboard_admin_users", "approved_by", "TEXT")
    ensure_column(connection, "dashboard_admin_users", "approved_at", "TEXT")
    ensure_column(connection, "dashboard_admin_users", "notes", "TEXT")
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_email
        ON dashboard_admin_users (email, disabled)
    """)


def migration_14_dashboard_account_discord_id(connection):
    ensure_column(connection, "dashboard_admin_users", "discord_user_id", "TEXT")
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_discord_id
        ON dashboard_admin_users (discord_user_id, disabled)
    """)


def migration_15_user_restrictions(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS user_restrictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT DEFAULT '',
            user_id TEXT NOT NULL,
            username TEXT,
            lock_games INTEGER DEFAULT 0,
            lock_submissions INTEGER DEFAULT 0,
            reason TEXT,
            active INTEGER DEFAULT 1,
            created_by TEXT,
            created_by_name TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_restrictions_guild_user
        ON user_restrictions (guild_id, user_id)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_restrictions_active_scope
        ON user_restrictions (active, guild_id, user_id)
    """)


def migration_16_dashboard_access_and_bot_owners(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_user_server_access (
            username TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            source TEXT DEFAULT 'manual',
            verified_at TEXT,
            updated_at TEXT,
            PRIMARY KEY (username, guild_id)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_user_server_access_guild
        ON dashboard_user_server_access (guild_id, role)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_bot_owners (
            username TEXT PRIMARY KEY,
            source TEXT DEFAULT 'manual',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    now = utc_now_iso()
    connection.execute("""
        INSERT OR IGNORE INTO dashboard_bot_owners (
            username, source, created_at, updated_at
        )
        VALUES ('baytae', 'bootstrap', ?, ?)
    """, (now, now))
    connection.execute("""
        INSERT OR IGNORE INTO dashboard_user_server_access (
            username, guild_id, role, source, verified_at, updated_at
        )
        SELECT users.username, json_each.value,
               CASE WHEN owners.username IS NOT NULL THEN 'bot_owner' ELSE users.role END,
               'legacy', users.updated_at, users.updated_at
        FROM dashboard_admin_users AS users
        LEFT JOIN dashboard_bot_owners AS owners
          ON lower(owners.username) = lower(users.username)
        , json_each(COALESCE(NULLIF(users.guild_ids_json, ''), '[]'))
        WHERE json_valid(COALESCE(NULLIF(users.guild_ids_json, ''), '[]'))
    """)


def migration_17_dashboard_auth_codes(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_account_auth_codes (
            code TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_by TEXT,
            created_at TEXT,
            expires_at TEXT,
            used_at TEXT,
            used_by TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_account_auth_codes_user
        ON dashboard_account_auth_codes (username, expires_at, used_at)
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_dashboard_account_auth_codes_guild
        ON dashboard_account_auth_codes (guild_id, expires_at, used_at)
    """)


def migration_18_google_play_test_account(connection):
    now = utc_now_iso()
    connection.execute("""
        INSERT OR IGNORE INTO dashboard_admin_users (
            username, email, display_name, password_hash, role, disabled,
            created_at, updated_at, guild_ids_json, approved_by, approved_at, notes
        )
        VALUES (
            'default', '', 'Default', ?, 'not_added', 0,
            ?, ?, '[]', 'google-play-review-seed', ?,
            'Permanent low-access Google Play review account.'
        )
    """, (GOOGLE_PLAY_REVIEW_PASSWORD_HASH, now, now, now))

MIGRATIONS = (
    (3, migration_3_media_metadata_and_rate_limits),
    (4, migration_4_restore_test_runs),
    (5, migration_5_reports_aliases_and_hints),
    (6, migration_6_guess_library),
    (7, migration_7_operations_tables),
    (8, migration_8_multi_server_and_answer_history),
    (9, migration_9_production_operations),
    (10, migration_10_jobs_duplicates_and_privacy),
    (11, migration_11_operations_safety_tables),
    (12, migration_12_schedules_achievements_and_archives),
    (13, migration_13_dashboard_accounts),
    (14, migration_14_dashboard_account_discord_id),
    (15, migration_15_user_restrictions),
    (16, migration_16_dashboard_access_and_bot_owners),
    (17, migration_17_dashboard_auth_codes),
    (18, migration_18_google_play_test_account),
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
