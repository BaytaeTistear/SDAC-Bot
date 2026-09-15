import json
from pathlib import Path
import tempfile
import unittest

import dashboard
from community_extensions import screen_content, scrub_image_metadata
from database_migrations import apply_database_migrations


class CommunityExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sdac-community-extensions-")
        root = Path(self.temp_dir.name)
        self.original_db_file = dashboard.DB_FILE
        self.original_config_file = dashboard.CONFIG_FILE
        dashboard.DB_FILE = root / "extensions.db"
        dashboard.CONFIG_FILE = root / "config.json"
        dashboard.CONFIG_FILE.write_text(json.dumps({"guilds": {"111": {"guild_name": "Test Server", "features": {"public_gallery": True}}}}), encoding="utf-8")
        with dashboard.database() as connection:
            apply_database_migrations(connection)
            connection.execute("""INSERT INTO dashboard_admin_users (username,email,display_name,discord_user_id,password_hash,role,disabled,email_verified,notify_email,notify_discord,created_at,updated_at,guild_ids_json) VALUES ('voter','','Voter','222','test','user',0,0,0,1,'2026-09-14','2026-09-14','[]')""")
            dashboard.upsert_user_server_access(connection, "voter", ["111"], role="user", source="test", preserve_existing_roles=False)
            now = dashboard.utc_now_iso()
            connection.execute("""INSERT INTO community_quotes (guild_id,quote_text,speaker,status,submitter_user_id,submitter_name,created_at,updated_at) VALUES ('111','Vote for this','Sana','approved','333','Owner',?,?)""", (now, now))
            connection.execute("""INSERT INTO community_quotes (guild_id,quote_text,speaker,status,submitter_user_id,submitter_name,created_at,updated_at) VALUES ('111','Editable quote','Sana','pending','222','Voter',?,?)""", (now, now))

    def tearDown(self):
        dashboard.DB_FILE = self.original_db_file
        dashboard.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def signed_in_client(self):
        client = dashboard.app.test_client()
        with client.session_transaction() as session:
            session["sdac_account_username"] = "voter"
            session["sdac_account_role"] = "user"
            session["sdac_discord_user_id"] = "222"
            session["csrf_token"] = "token"
        return client

    def test_safety_flags_invites_and_executable_links(self):
        findings = screen_content("join discord.gg/example", "https://example.com/file.exe")
        self.assertEqual({item["code"] for item in findings}, {"discord_invite", "executable_link"})

    def test_quote_vote_toggles_and_api_exposes_score(self):
        client = self.signed_in_client()
        response = client.post("/quotes/1/vote", data={"csrf_token": "token", "vote": "1", "next": "/quotes"})
        self.assertEqual(response.status_code, 302)
        payload = client.get("/api/v1/quotes?guild_id=111").get_json()
        quote = next(row for row in payload["data"] if row["id"] == 1)
        self.assertEqual(quote["score"], 1)
        client.post("/quotes/1/vote", data={"csrf_token": "token", "vote": "1", "next": "/quotes"})
        payload = client.get("/api/v1/quotes?guild_id=111").get_json()
        quote = next(row for row in payload["data"] if row["id"] == 1)
        self.assertEqual(quote["vote_count"], 0)

    def test_pending_quote_edit_records_revision(self):
        client = self.signed_in_client()
        response = client.post("/my-submissions/quote/2/edit", data={"csrf_token": "token", "action": "save", "quote_text": "Edited quote", "speaker": "Sana", "source_text": "", "context_text": ""})
        self.assertEqual(response.status_code, 302)
        with dashboard.database() as connection:
            quote = connection.execute("SELECT quote_text FROM community_quotes WHERE id=2").fetchone()
            revision_count = connection.execute("SELECT COUNT(*) FROM submission_revisions WHERE entity_type='quote' AND entity_id='2'").fetchone()[0]
        self.assertEqual(quote["quote_text"], "Edited quote")
        self.assertEqual(revision_count, 1)

    def test_image_metadata_is_removed(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is optional")
        path = Path(self.temp_dir.name) / "metadata.jpg"
        image = Image.new("RGB", (12, 12), "red")
        exif = Image.Exif()
        exif[0x010E] = "private note"
        image.save(path, exif=exif)
        self.assertEqual(scrub_image_metadata(path), "scrubbed")
        with Image.open(path) as scrubbed:
            self.assertFalse(scrubbed.getexif())


if __name__ == "__main__":
    unittest.main()
