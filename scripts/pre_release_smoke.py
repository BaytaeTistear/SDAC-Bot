import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class PreReleaseSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.TemporaryDirectory(prefix="sdac-smoke-")
        root = Path(cls.workdir.name)
        os.environ["SDAC_DB_FILE"] = str(root / "sdac-smoke.db")
        os.environ["SDAC_CONFIG_FILE"] = str(root / "config.json")
        os.environ["SDAC_MEDIA_DIR"] = str(root / "media")
        os.environ["SDAC_BACKUP_DIR"] = str(root / "backups")
        os.environ["SDAC_BOT_STATUS_FILE"] = str(root / "bot_status.json")
        (root / "media").mkdir(parents=True, exist_ok=True)
        (root / "backups").mkdir(parents=True, exist_ok=True)
        (root / "config.json").write_text(json.dumps({
            "guilds": {
                "111": {
                    "guild_name": "Smoke Test Server",
                    "features": {
                        "public_gallery": True,
                        "cross_server_gallery": True,
                    },
                }
            }
        }), encoding="utf-8")
        import bot
        import dashboard
        cls.bot = bot
        cls.dashboard = dashboard

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()

    def test_bot_and_dashboard_imported(self):
        self.assertEqual(self.bot.OWNER_OVERRIDE_USERNAME, "baytae")
        self.assertTrue(hasattr(self.dashboard, "app"))

    def test_database_migration_version_is_current(self):
        with self.dashboard.database() as connection:
            row = connection.execute("""
                SELECT version
                FROM schema_version
                WHERE id = 1
            """).fetchone()
            version = int(row["version"]) if row else 0
        self.assertGreaterEqual(version, self.dashboard.DATABASE_SCHEMA_VERSION)

    def test_monthly_submission_top_preserve_insert(self):
        with self.dashboard.database() as connection:
            connection.execute("""
                INSERT INTO submissions (
                    id, guild_id, category, user_id, username, message_text,
                    file_paths, media_paths, media_names, media_types,
                    media_sizes, media_metadata_json, stars, voters,
                    status, submitted_at, created_at
                )
                VALUES (
                    1, '111', 'General', '42', 'tester', 'smoke',
                    '[]', '[]', '[]', '[]', '[]', '{}', 3, '[]',
                    'posted', '2026-07-01T00:00:00+00:00',
                    '2026-07-01T00:00:00+00:00'
                )
            """)
            self.dashboard.preserve_monthly_submission_top(connection, "2026-07")
            row = connection.execute("""
                SELECT COUNT(*) AS count
                FROM monthly_submission_top
                WHERE month = '2026-07'
            """).fetchone()
        self.assertEqual(row["count"], 1)

    def test_public_and_admin_pages_render(self):
        client = self.dashboard.app.test_client()
        for path in ["/", "/account/login", "/servers", "/app", "/manifest.webmanifest", "/sw.js", "/app-icon.svg"]:
            response = client.get(path)
            self.assertLess(response.status_code, 500, path)
        manifest_response = client.get("/manifest.webmanifest")
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(manifest_response.json["short_name"], "SDAC")
        self.assertIn("max-age", manifest_response.headers.get("Cache-Control", ""))
        compressed_response = client.get("/account/login", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(compressed_response.headers.get("Content-Encoding"), "gzip")
        self.assertIn("Accept-Encoding", compressed_response.headers.get("Vary", ""))
        self.assertIn("/sw.js", client.get("/account/login").get_data(as_text=True))
        with client.session_transaction() as session:
            session["sdac_account_username"] = "baytae"
            session["sdac_account_role"] = "bot_owner"
            session["sdac_admin"] = True
            session["sdac_admin_username"] = "baytae"
            session["sdac_admin_role"] = "bot_owner"
        for path in [
            "/account/access",
            "/admin/preview-as?key=ImTheBestAdmin&username=baytae&guild_id=111",
            "/admin/users?key=ImTheBestAdmin",
            "/admin/server-health?key=ImTheBestAdmin",
            "/admin/settings?key=ImTheBestAdmin&guild_id=111",
            "/admin/anime-activities?key=ImTheBestAdmin",
            "/admin/owner-portal?key=ImTheBestAdmin",
        ]:
            response = client.get(path)
            self.assertLess(response.status_code, 500, path)
        anime_page = client.get("/admin/anime-activities?key=ImTheBestAdmin").get_data(as_text=True)
        self.assertIn("/animeevent", anime_page)
        self.assertIn("screenshot-guess", anime_page)
        owner_page = client.get("/admin/owner-portal?key=ImTheBestAdmin").get_data(as_text=True)
        self.assertIn("Bot Owner Access Control", owner_page)

if __name__ == "__main__":
    unittest.main(verbosity=2)
