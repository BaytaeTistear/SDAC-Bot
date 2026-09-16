import json
from pathlib import Path
import tempfile
import unittest

import dashboard
from community_extensions import process_webhook_outbox
from database_migrations import apply_database_migrations
from professional_services import create_inbox_notification, enqueue_webhook, openapi_document


class ProfessionalFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sdac-professional-")
        root = Path(self.temp_dir.name)
        self.original_db = dashboard.DB_FILE
        self.original_config = dashboard.CONFIG_FILE
        self.original_backup = dashboard.BACKUP_DIR
        dashboard.DB_FILE = root / "professional.db"
        dashboard.CONFIG_FILE = root / "config.json"
        dashboard.BACKUP_DIR = root / "backups"
        dashboard.BACKUP_DIR.mkdir()
        dashboard.CONFIG_FILE.write_text(json.dumps({"guilds": {"111": {"guild_name": "Public Test", "features": {"public_gallery": True}}}}), encoding="utf-8")
        dashboard.initialize_database()
        with dashboard.database() as connection:
            connection.execute("""INSERT INTO dashboard_admin_users (username,email,display_name,discord_user_id,password_hash,role,disabled,email_verified,notify_email,notify_discord,created_at,updated_at,guild_ids_json) VALUES ('professional-user','','Professional User','222','test','user',0,0,0,1,'2026-09-16','2026-09-16','[]')""")
            dashboard.upsert_user_server_access(connection, "professional-user", ["111"], role="user", source="test", preserve_existing_roles=False)

    def tearDown(self):
        dashboard.DB_FILE = self.original_db
        dashboard.CONFIG_FILE = self.original_config
        dashboard.BACKUP_DIR = self.original_backup
        self.temp_dir.cleanup()

    def client(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as session:
            session["sdac_account_username"] = "professional-user"
            session["sdac_account_role"] = "user"
            session["sdac_discord_user_id"] = "222"
            session["csrf_token"] = "token"
        return client

    def test_schema_contains_professional_tables(self):
        expected = {"user_notifications", "webhook_outbox", "privacy_requests", "support_tickets", "moderation_assignments", "moderation_appeals", "service_metrics", "deployment_records"}
        with dashboard.database() as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertTrue(expected.issubset(tables))

    def test_openapi_status_and_docs(self):
        client = self.client()
        spec = client.get("/api/v1/openapi.json").get_json()
        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertIn("/api/v1/quotes", spec["paths"])
        self.assertEqual(client.get("/api/docs").status_code, 200)
        self.assertIn(client.get("/status?format=json").get_json()["status"], {"operational", "degraded"})

    def test_inbox_support_appeal_and_privacy_export(self):
        client = self.client()
        with dashboard.database() as connection:
            create_inbox_notification(connection, "222", "Reviewed", "Your item was approved.", "submission", "/my-submissions")
        self.assertIn("Reviewed", client.get("/notifications").get_data(as_text=True))
        self.assertEqual(client.post("/support", data={"csrf_token": "token", "subject": "Help", "message": "Something happened."}).status_code, 302)
        self.assertEqual(client.post("/appeals", data={"csrf_token": "token", "entity_type": "quote", "entity_id": "12", "reason": "Please review again."}).status_code, 302)
        export = client.post("/account/privacy", data={"csrf_token": "token", "action": "export"})
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.get_json()["user_id"], "222")

    def test_webhook_outbox_completes_without_subscribers(self):
        with dashboard.database() as connection:
            enqueue_webhook(connection, "quote.approved", "111", {"id": 1, "status": "approved"})
        self.assertEqual(process_webhook_outbox(dashboard.connect_db), 1)
        with dashboard.database() as connection:
            status = connection.execute("SELECT status FROM webhook_outbox").fetchone()[0]
        self.assertEqual(status, "delivered")

    def test_openapi_builder_has_bounded_limit(self):
        document = openapi_document("https://example.test")
        parameters = document["paths"]["/api/v1/quotes"]["get"]["parameters"]
        limit = next(item for item in parameters if item["name"] == "limit")
        self.assertEqual(limit["schema"]["maximum"], 100)


if __name__ == "__main__":
    unittest.main()
