import inspect
import sqlite3
import unittest

from database_migrations import (
    migration_16_dashboard_access_and_bot_owners,
    migration_30_myanimelist_account_connections,
    migration_31_anilist_account_connections,
    migration_32_distinct_anime_profile_statuses,
)


class DatabaseMigrationTests(unittest.TestCase):
    def test_anime_profile_statuses_are_stored_separately(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE anime_profiles (guild_id TEXT, user_id TEXT)")
        migration_32_distinct_anime_profile_statuses(connection)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(anime_profiles)")}
        self.assertTrue({
            "anime_completed", "anime_planned", "anime_on_hold",
            "manga_completed", "manga_planned", "manga_on_hold",
        }.issubset(columns))

    def test_anilist_connection_schema_encrypts_tokens_and_adds_profile_url(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE anime_profiles (guild_id TEXT, user_id TEXT)")
        migration_31_anilist_account_connections(connection)
        connection_columns = {row["name"] for row in connection.execute("PRAGMA table_info(dashboard_anilist_connections)")}
        profile_columns = {row["name"] for row in connection.execute("PRAGMA table_info(anime_profiles)")}
        self.assertIn("access_token_encrypted", connection_columns)
        self.assertNotIn("access_token", connection_columns)
        self.assertIn("anilist_profile_url", profile_columns)

    def test_myanimelist_connection_schema_keeps_tokens_out_of_account_rows(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        migration_30_myanimelist_account_connections(connection)

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(dashboard_mal_connections)")
        }
        self.assertIn("access_token_encrypted", columns)
        self.assertIn("refresh_token_encrypted", columns)
        self.assertIn("last_sync_status", columns)
        self.assertNotIn("access_token", columns)

    def test_dashboard_access_backfill_is_portable_and_preserves_legacy_scopes(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("""
            CREATE TABLE dashboard_admin_users (
                username TEXT PRIMARY KEY,
                role TEXT,
                guild_ids_json TEXT,
                updated_at TEXT
            )
        """)
        connection.executemany("""
            INSERT INTO dashboard_admin_users (
                username, role, guild_ids_json, updated_at
            ) VALUES (?, ?, ?, ?)
        """, (
            ("baytae", "admin", '["100", "200"]', "2026-09-22T00:00:00+00:00"),
            ("helper", "moderator", '["300"]', "2026-09-22T00:00:00+00:00"),
            ("broken", "user", "not-json", "2026-09-22T00:00:00+00:00"),
        ))

        migration_16_dashboard_access_and_bot_owners(connection)

        rows = connection.execute("""
            SELECT username, guild_id, role
            FROM dashboard_user_server_access
            ORDER BY username, guild_id
        """).fetchall()
        self.assertEqual(
            [tuple(row) for row in rows],
            [
                ("baytae", "100", "bot_owner"),
                ("baytae", "200", "bot_owner"),
                ("helper", "300", "moderator"),
            ],
        )
        self.assertNotIn(
            "json_each",
            inspect.getsource(migration_16_dashboard_access_and_bot_owners),
        )


if __name__ == "__main__":
    unittest.main()
