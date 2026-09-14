import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dashboard
from database_migrations import apply_database_migrations


class QuoteWebsiteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sdac-quotes-")
        root = Path(self.temp_dir.name)
        self.original_db_file = dashboard.DB_FILE
        self.original_config_file = dashboard.CONFIG_FILE
        dashboard.DB_FILE = root / "quotes.db"
        dashboard.CONFIG_FILE = root / "config.json"
        dashboard.CONFIG_FILE.write_text(json.dumps({
            "guilds": {
                "111": {
                    "guild_name": "Quote Test Server",
                    "features": {"public_gallery": True},
                }
            }
        }), encoding="utf-8")
        with dashboard.database() as connection:
            apply_database_migrations(connection)
            dashboard.upsert_user_server_access(
                connection,
                "quote-user",
                ["111"],
                role="user",
                source="test",
                preserve_existing_roles=False,
            )
        self.notification_patcher = patch.object(
            dashboard,
            "send_quote_submitter_notifications",
            return_value=(1, 1, []),
        )
        self.notification_mock = self.notification_patcher.start()

    def tearDown(self):
        self.notification_patcher.stop()
        dashboard.DB_FILE = self.original_db_file
        dashboard.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def test_submit_duplicate_status_and_moderation_flow(self):
        client = dashboard.app.test_client()
        page = client.get("/quotes?guild_id=111")
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn("Source", body)
        self.assertIn("My Quote Status", body)
        with client.session_transaction() as session:
            csrf = session["csrf_token"]
            session["sdac_account_username"] = "quote-user"
            session["sdac_account_role"] = "user"
            session["sdac_discord_user_id"] = "123456789012345678"
        quote_form = {
            "csrf_token": csrf,
            "guild_id": "111",
            "quote_text": "A memorable quote.",
            "speaker": "Sana",
            "category": "Inspirational",
            "source_text": "Test episode",
            "context_text": "Regression test context",
            "submitter_email": "quote-user@example.com",
        }
        response = client.post("/quotes", data=quote_form)
        self.assertEqual(response.status_code, 302)
        duplicate = client.post("/quotes", data={
            **quote_form,
            "quote_text": "  a   memorable quote. ",
            "speaker": "SANA",
        }, follow_redirects=True)
        self.assertIn("already in the pending queue", duplicate.get_data(as_text=True))

        with dashboard.database() as connection:
            row = connection.execute(
                "SELECT * FROM community_quotes WHERE guild_id = '111'"
            ).fetchone()
        self.assertEqual(row["submitter_email"], "quote-user@example.com")
        with client.session_transaction() as session:
            session["sdac_admin"] = True
            session["sdac_admin_username"] = "baytae"
            session["sdac_admin_role"] = "bot_owner"
            session["sdac_admin_auth"] = "test"
            session["sdac_admin_guild_ids"] = []
            csrf = session["csrf_token"]
        reviewed = client.post("/admin/quotes?status=pending", data={
            "csrf_token": csrf,
            "quote_id": row["id"],
            "action": "approve",
            "quote_text": row["quote_text"],
            "speaker": row["speaker"],
            "category": row["category"],
            "source_text": row["source_text"],
            "context_text": row["context_text"],
            "review_notes": "Looks good.",
        })
        self.assertEqual(reviewed.status_code, 302)
        with dashboard.database() as connection:
            approved = connection.execute(
                "SELECT status, review_notes FROM community_quotes WHERE id = ?",
                (row["id"],),
            ).fetchone()
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["review_notes"], "Looks good.")
        self.assertEqual(self.notification_mock.call_count, 2)

        with client.session_transaction() as session:
            session.pop("sdac_admin", None)
            session["sdac_account_username"] = "quote-user"
            session["sdac_account_role"] = "user"
            session["sdac_discord_user_id"] = "123456789012345678"
        status_page = client.get("/quotes?guild_id=111")
        status_body = status_page.get_data(as_text=True)
        self.assertIn("Status: Approved", status_body)
        self.assertIn("Looks good.", status_body)


if __name__ == "__main__":
    unittest.main()
