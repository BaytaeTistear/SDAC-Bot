import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

import database_migrations


class CommunityQuoteMigrationTests(unittest.TestCase):
    def test_quote_tables_are_created_by_latest_migration(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            database_migrations.apply_database_migrations(connection)
            version = connection.execute(
                "SELECT version FROM schema_version WHERE id = 1"
            ).fetchone()["version"]
            self.assertEqual(version, 24)
            quote_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(community_quotes)"
                ).fetchall()
            }
            self.assertTrue(
                {
                    "guild_id",
                    "quote_text",
                    "speaker",
                    "status",
                    "reviewed_by",
                    "last_posted_at",
                }.issubset(quote_columns)
            )
            run_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(community_quote_daily_runs)"
                ).fetchall()
            }
            self.assertEqual(
                run_columns,
                {"guild_id", "run_date", "quote_id", "channel_id", "created_at"},
            )
        finally:
            connection.close()

    def test_daily_quote_posts_only_once_per_server_day(self):
        import bot

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        original_db_file = bot.DB_FILE
        original_get_channel = bot.bot.get_channel
        sent_messages = []

        class TestChannel:
            async def send(self, content):
                sent_messages.append(content)

        try:
            bot.DB_FILE = Path(temp_file.name)
            with bot.database() as connection:
                database_migrations.apply_database_migrations(connection)
                now = bot.utc_now_iso()
                connection.execute(
                    """
                    INSERT INTO community_quotes (
                        guild_id, quote_text, speaker, status,
                        submitter_user_id, submitter_name, created_at, updated_at
                    )
                    VALUES ('111', 'A useful test quote.', 'Test Speaker', 'approved',
                            '222', 'tester', ?, ?)
                    """,
                    (now, now),
                )
            bot.bot.get_channel = lambda channel_id: TestChannel()
            guild_config = {
                "quote_channel": 333,
                "quote_time_local": "09:00",
                "timezone": "UTC",
            }
            run_time = datetime(2026, 9, 13, 9, 0, tzinfo=timezone.utc)
            first = asyncio.run(bot.post_daily_quote("111", guild_config, run_time))
            second = asyncio.run(bot.post_daily_quote("111", guild_config, run_time))
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(len(sent_messages), 1)
            self.assertIn("A useful test quote.", sent_messages[0])
            self.assertIn("Test Speaker", sent_messages[0])
        finally:
            bot.DB_FILE = original_db_file
            bot.bot.get_channel = original_get_channel
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
