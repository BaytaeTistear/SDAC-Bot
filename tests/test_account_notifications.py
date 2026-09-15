import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import dashboard


class AccountNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sdac-account-notifications-")
        root = Path(self.temp_dir.name)
        self.original_db_file = dashboard.DB_FILE
        self.original_config_file = dashboard.CONFIG_FILE
        dashboard.DB_FILE = root / "account.db"
        dashboard.CONFIG_FILE = root / "config.json"
        dashboard.CONFIG_FILE.write_text(json.dumps({
            "guilds": {
                "111": {
                    "guild_name": "Account Test Server",
                    "features": {"public_gallery": True},
                }
            }
        }), encoding="utf-8")
        dashboard.initialize_database()
        with dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, discord_user_id,
                    password_hash, role, disabled, email_verified,
                    notify_email, notify_discord, created_at, updated_at,
                    guild_ids_json
                ) VALUES (
                    'account-user', 'account@example.com', 'Account User',
                    '123456789012345678', 'test', 'bot_owner', 0, 0, 0, 1,
                    '2026-09-14T00:00:00+00:00',
                    '2026-09-14T00:00:00+00:00', '["111"]'
                )
                """
            )
            dashboard.upsert_user_server_access(
                connection,
                "account-user",
                ["111"],
                role="bot_owner",
                source="test",
                preserve_existing_roles=False,
            )
        self.client = dashboard.app.test_client()

    def tearDown(self):
        dashboard.DB_FILE = self.original_db_file
        dashboard.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def login(self, admin=False):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"
            session["sdac_account_username"] = "account-user"
            session["sdac_account_role"] = "bot_owner"
            session["sdac_discord_user_id"] = "123456789012345678"
            if admin:
                session["sdac_admin"] = True
                session["sdac_admin_username"] = "account-user"
                session["sdac_admin_role"] = "bot_owner"
                session["sdac_admin_auth"] = "test"
                session["sdac_admin_guild_ids"] = ["111"]

    def test_email_verification_enables_opt_in_email_updates(self):
        self.login()
        with patch.object(dashboard, "send_sana_email", return_value=True) as send_email:
            response = self.client.post(
                "/account/email-verification/send",
                data={"csrf_token": "test-csrf"},
            )
        self.assertEqual(response.status_code, 302)
        body = send_email.call_args.args[2]
        token_match = re.search(r"token=([A-Za-z0-9_-]+)", body)
        self.assertIsNotNone(token_match)
        confirmed = self.client.get(
            f"/account/email-verification/confirm?token={token_match.group(1)}"
        )
        self.assertEqual(confirmed.status_code, 302)
        with dashboard.database() as connection:
            row = connection.execute(
                "SELECT email_verified, notify_email FROM dashboard_admin_users WHERE username = 'account-user'"
            ).fetchone()
        self.assertEqual(row["email_verified"], 1)
        self.assertEqual(row["notify_email"], 1)

    def test_my_submissions_combines_all_submission_types(self):
        self.login()
        now = "2026-09-14T12:00:00+00:00"
        with dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO submissions (
                    guild_id, user_id, username, category, status,
                    submitted_at, created_at
                ) VALUES ('111', '123456789012345678', 'Account User',
                          'Screenshots', 'posted', ?, ?)
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO community_quotes (
                    guild_id, quote_text, speaker, status, submitter_user_id,
                    submitter_name, created_at, updated_at, review_notes
                ) VALUES ('111', 'Unified quote', 'Sana', 'approved',
                          '123456789012345678', 'Account User', ?, ?, 'Great quote')
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO community_posts (
                    post_type, status, title, guild_id, submitter_name,
                    submitter_user_id, created_at, updated_at, review_notes
                ) VALUES ('event', 'pending', 'Unified event', '111',
                          'Account User', '123456789012345678', ?, ?, 'Queued')
                """,
                (now, now),
            )
        response = self.client.get("/my-submissions")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Media submission", body)
        self.assertIn("Unified quote", body)
        self.assertIn("Unified event", body)
        self.assertIn("Great quote", body)
        self.assertIn("Queued", body)

    def test_failed_discord_delivery_can_be_retried_once(self):
        self.login(admin=True)
        with dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO notification_deliveries (
                    event_key, guild_id, channel_id, status, error_text,
                    response_message_id, payload_text, related_type,
                    related_id, recipient, retry_count, created_at
                ) VALUES (
                    'community_quote_submitted', '111', '222', 'failed',
                    'temporary failure', '', ?, 'community_quote',
                    '7', '123456789012345678', 0,
                    '2026-09-14T12:00:00+00:00'
                )
                """,
                (json.dumps({"content": "Retry me"}),),
            )
            delivery_id = connection.execute(
                "SELECT id FROM notification_deliveries ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
        with patch.object(
            dashboard,
            "post_discord_channel_payload",
            return_value={"id": "999"},
        ):
            response = self.client.post(
                "/admin/notification-center",
                data={
                    "csrf_token": "test-csrf",
                    "delivery_type": "discord",
                    "delivery_id": str(delivery_id),
                },
            )
        self.assertEqual(response.status_code, 302)
        with dashboard.database() as connection:
            retry = connection.execute(
                """
                SELECT status, response_message_id, retry_of_id, retry_count
                FROM notification_deliveries
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
        self.assertEqual(retry["status"], "sent")
        self.assertEqual(retry["response_message_id"], "999")
        self.assertEqual(retry["retry_of_id"], delivery_id)
        self.assertEqual(retry["retry_count"], 1)
        with patch.object(dashboard, "post_discord_channel_payload") as duplicate_send:
            duplicate = self.client.post(
                "/admin/notification-center",
                data={
                    "csrf_token": "test-csrf",
                    "delivery_type": "discord",
                    "delivery_id": str(delivery_id),
                },
            )
        self.assertEqual(duplicate.status_code, 302)
        duplicate_send.assert_not_called()

    def test_failed_email_delivery_uses_saved_body_for_retry(self):
        self.login(admin=True)
        with dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO email_delivery_log (
                    related_type, related_id, guild_id, recipient, subject,
                    status, detail, body_text, retry_count, created_at
                ) VALUES (
                    'community_quote', '8', '111', 'account@example.com',
                    'Quote update', 'failed', 'temporary failure',
                    'Saved private update', 0,
                    '2026-09-14T12:00:00+00:00'
                )
                """
            )
            delivery_id = connection.execute(
                "SELECT id FROM email_delivery_log ORDER BY id DESC LIMIT 1"
            ).fetchone()["id"]
        with patch.object(dashboard, "send_sana_email", return_value=True) as send_email:
            response = self.client.post(
                "/admin/notification-center",
                data={
                    "csrf_token": "test-csrf",
                    "delivery_type": "email",
                    "delivery_id": str(delivery_id),
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(send_email.call_args.args[:3], (
            "account@example.com",
            "Quote update",
            "Saved private update",
        ))
        self.assertEqual(send_email.call_args.kwargs["retry_of_id"], delivery_id)
        self.assertEqual(send_email.call_args.kwargs["retry_count"], 1)


if __name__ == "__main__":
    unittest.main()
