import asyncio
import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from werkzeug.exceptions import HTTPException

import bot
import dashboard


class SubmissionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "sdac.db"
        self.media_dir = self.root / "media"
        self.media_dir.mkdir()

        self.originals = {
            "bot_db": bot.DB_FILE,
            "bot_media": bot.MEDIA_DIR,
            "bot_config": copy.deepcopy(bot.config),
            "dashboard_db": dashboard.DB_FILE,
            "dashboard_media": dashboard.MEDIA_DIR,
        }
        bot.DB_FILE = self.db_path
        bot.MEDIA_DIR = self.media_dir
        dashboard.DB_FILE = self.db_path
        dashboard.MEDIA_DIR = self.media_dir
        bot.initialize_database()
        dashboard.initialize_database()

    def tearDown(self):
        bot.DB_FILE = self.originals["bot_db"]
        bot.MEDIA_DIR = self.originals["bot_media"]
        bot.config.clear()
        bot.config.update(self.originals["bot_config"])
        dashboard.DB_FILE = self.originals["dashboard_db"]
        dashboard.MEDIA_DIR = self.originals["dashboard_media"]
        self.temp_dir.cleanup()

    def insert_submission(self, status="posted", guild_id="111", media_path=""):
        created_at = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with bot.database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_message_id,
                    repost_channel_id, approval_message_id,
                    approval_channel_id, user_id, username, category,
                    media_paths, file_paths, media_names, media_types,
                    media_sizes, media_metadata_json, status,
                    submitted_at, created_at
                )
                VALUES (?, '10', '20', '30', '40', '50', '60',
                        'tester', 'art', ?, ?, 'image.png', 'image',
                        '4', '[]', ?, ?, ?)
                """,
                (
                    guild_id,
                    media_path,
                    media_path,
                    status,
                    created_at,
                    created_at,
                ),
            )
            submission_id = cursor.lastrowid
            connection.execute(
                """
                INSERT INTO media_fingerprints (
                    media_hash, guild_id, submission_id, media_path,
                    media_name, size_bytes, created_at
                )
                VALUES ('hash', ?, ?, ?, 'image.png', 4, ?)
                """,
                (guild_id, submission_id, media_path, created_at),
            )
            connection.execute(
                """
                INSERT INTO submission_reports (
                    submission_id, guild_id, reporter_name,
                    reason, status, created_at
                )
                VALUES (?, ?, 'reporter', 'reason', 'open', ?)
                """,
                (submission_id, guild_id, created_at),
            )
        return submission_id

    def related_counts(self, submission_id):
        with bot.database() as connection:
            return tuple(
                connection.execute(query, (submission_id,)).fetchone()[0]
                for query in (
                    "SELECT COUNT(*) FROM submissions WHERE id = ?",
                    "SELECT COUNT(*) FROM media_fingerprints WHERE submission_id = ?",
                    "SELECT COUNT(*) FROM submission_reports WHERE submission_id = ?",
                )
            )

    def test_category_names_are_filesystem_safe(self):
        self.assertEqual(bot.clean_category_name("  Fan Art  "), "fanart")
        self.assertEqual(bot.clean_category_name("../../outside"), "outside")
        self.assertEqual(bot.clean_category_name("clips_and-memes"), "clips_and-memes")
        self.assertEqual(bot.clean_category_name("..."), "")

    def test_bot_removal_deletes_discord_messages_and_related_rows(self):
        media_path = self.media_dir / "111" / "art" / "image.png"
        media_path.parent.mkdir(parents=True)
        media_path.write_bytes(b"data")
        submission_id = self.insert_submission(media_path=str(media_path))

        with mock.patch.object(
            bot,
            "delete_discord_message",
            new=mock.AsyncMock(return_value=(True, "")),
        ) as delete_message:
            ok, _message = asyncio.run(
                bot.remove_submission_record(submission_id, "1", "admin", "test")
            )

        self.assertTrue(ok)
        self.assertEqual(delete_message.await_count, 2)
        self.assertEqual(self.related_counts(submission_id), (0, 0, 0))
        self.assertFalse(media_path.exists())

    def test_stale_pending_cleanup_keeps_record_when_discord_delete_fails(self):
        submission_id = self.insert_submission(status="pending")
        bot.config.setdefault("limits", {})["pending_submission_retention_hours"] = 1

        with mock.patch.object(
            bot,
            "delete_discord_message",
            new=mock.AsyncMock(return_value=(False, "permission denied")),
        ), mock.patch.object(
            bot,
            "send_error_notification",
            new=mock.AsyncMock(),
        ):
            asyncio.run(bot.cleanup_background_data())

        self.assertEqual(self.related_counts(submission_id), (1, 1, 1))

    def test_stale_pending_cleanup_removes_related_rows_after_discord_delete(self):
        media_path = self.media_dir / "111" / "art" / "pending.png"
        media_path.parent.mkdir(parents=True)
        media_path.write_bytes(b"data")
        submission_id = self.insert_submission(
            status="pending",
            media_path=str(media_path),
        )
        bot.config.setdefault("limits", {})["pending_submission_retention_hours"] = 1

        with mock.patch.object(
            bot,
            "delete_discord_message",
            new=mock.AsyncMock(return_value=(True, "")),
        ):
            asyncio.run(bot.cleanup_background_data())

        self.assertEqual(self.related_counts(submission_id), (0, 0, 0))
        self.assertFalse(media_path.exists())

    def test_dashboard_removal_enforces_server_scope(self):
        submission_id = self.insert_submission(guild_id="222")
        with dashboard.app.test_request_context("/delete"):
            with mock.patch.object(
                dashboard,
                "can_admin_access_guild",
                return_value=False,
            ):
                with self.assertRaises(HTTPException) as raised:
                    dashboard.remove_submission_from_dashboard(
                        submission_id,
                        "admin",
                        "Admin",
                    )

        self.assertEqual(raised.exception.code, 403)
        self.assertEqual(self.related_counts(submission_id), (1, 1, 1))

    def test_dashboard_removal_deletes_related_rows(self):
        submission_id = self.insert_submission()
        with dashboard.app.test_request_context("/delete"):
            with mock.patch.object(
                dashboard,
                "can_admin_access_guild",
                return_value=True,
            ), mock.patch.object(
                dashboard,
                "delete_discord_message",
                return_value=(True, ""),
            ):
                ok, _message = dashboard.remove_submission_from_dashboard(
                    submission_id,
                    "admin",
                    "Admin",
                )

        self.assertTrue(ok)
        self.assertEqual(self.related_counts(submission_id), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
