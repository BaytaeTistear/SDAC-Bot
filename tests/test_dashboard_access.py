import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class DashboardAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.tmp.close()
        os.environ["SDAC_DB_FILE"] = cls.tmp.name
        import dashboard

        cls.dashboard = dashboard

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp.name)
        except OSError:
            pass

    def setUp(self):
        self.config = {
            "guilds": {
                "111": {"guild_name": "Alpha", "features": {"public_gallery": True}},
                "222": {"guild_name": "Beta", "features": {"public_gallery": False}},
            }
        }
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM dashboard_user_server_access")
            connection.execute("DELETE FROM dashboard_admin_users")
            connection.execute("""
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, password_hash, role,
                    disabled, created_at, updated_at, guild_ids_json
                )
                VALUES ('scoped-user', '', 'Scoped User', 'x', 'user', 0, '', '', '["111","222"]')
            """)
            self.dashboard.upsert_user_server_access(
                connection,
                "scoped-user",
                ["111"],
                role="owner",
                source="manual",
                preserve_existing_roles=False,
            )
            self.dashboard.upsert_user_server_access(
                connection,
                "scoped-user",
                ["222"],
                role="user",
                source="oauth",
                preserve_existing_roles=False,
            )

    def test_fallback_secret_key_is_reused_from_local_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_file = Path(tmpdir) / ".sdac_secret_key"
            with mock.patch.dict(os.environ, {"SDAC_SECRET_KEY": "", "SDAC_SECRET_KEY_FILE": str(secret_file)}, clear=False):
                first_secret = self.dashboard.load_dashboard_secret_key(Path(tmpdir))
                second_secret = self.dashboard.load_dashboard_secret_key(Path(tmpdir))

        self.assertTrue(first_secret)
        self.assertEqual(first_secret, second_secret)

    def test_admin_password_login_sets_persistent_cookie(self):
        password = "correct horse battery staple"
        with self.dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, password_hash, role,
                    disabled, created_at, updated_at, guild_ids_json
                )
                VALUES (?, '', 'Remember Admin', ?, 'bot_owner', 0, '', '', '[]')
                """,
                ("remember-admin", self.dashboard.generate_password_hash(password)),
            )

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["csrf_token"] = "login-token"
            response = client.post(
                f"/admin/login?key={self.dashboard.ADMIN_KEY}",
                data={
                    "username": "remember-admin",
                    "password": password,
                    "csrf_token": "login-token",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        cookie_header = response.headers.get("Set-Cookie", "")
        self.assertIn("Expires=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Lax", cookie_header)

    def test_account_selector_uses_access_rows_not_public_gallery(self):
        with self.dashboard.app.test_request_context("/"):
            self.dashboard.session["sdac_account_username"] = "scoped-user"
            self.dashboard.session["sdac_account_role"] = "user"
            rows = self.dashboard.sidebar_server_options(self.config)

        self.assertEqual([row["id"] for row in rows], ["111", "222"])

    def test_selected_server_role_overrides_global_role(self):
        with self.dashboard.app.test_request_context("/?guild_id=111"):
            self.dashboard.session["sdac_admin"] = True
            self.dashboard.session["sdac_admin_username"] = "scoped-user"
            self.dashboard.session["sdac_admin_role"] = "user"
            self.assertEqual(self.dashboard.current_admin_role(), "owner")

        with self.dashboard.app.test_request_context("/?guild_id=222"):
            self.dashboard.session["sdac_admin"] = True
            self.dashboard.session["sdac_admin_username"] = "scoped-user"
            self.dashboard.session["sdac_admin_role"] = "user"
            self.assertEqual(self.dashboard.current_admin_role(), "user")

    def test_baytae_override_gets_all_servers(self):
        with self.dashboard.app.test_request_context("/"):
            self.dashboard.session["sdac_account_username"] = "baytae"
            self.dashboard.session["sdac_account_role"] = "owner"
            rows = self.dashboard.sidebar_server_options(self.config)

        self.assertEqual([row["id"] for row in rows], ["111", "222"])

    def test_logged_in_account_can_vote_and_unvote_submission(self):
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM submissions")
            cursor = connection.execute(
                """
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_message_id, repost_channel_id,
                    user_id, username, category, message_text, file_paths, media_paths,
                    media_names, media_types, media_sizes, media_metadata_json,
                    stars, voters, status, submitted_at, created_at
                )
                VALUES (
                    '111', 'o1', 'r1', 'c1', 'owner-id', 'Owner', 'screenshots',
                    'A post', '', '', '', '', '', '[]', 0, '', 'posted', '2026-07-10T00:00:00+00:00', '2026-07-10T00:00:00+00:00'
                )
                """
            )
            submission_id = cursor.lastrowid

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_account_username"] = "scoped-user"
                session["sdac_account_role"] = "user"
                session["sdac_account_guild_ids"] = ["111"]
                session["sdac_discord_user_id"] = "123456789012345678"
                session["csrf_token"] = "vote-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    f"/submission/{submission_id}/vote?guild_id=111",
                    data={"csrf_token": "vote-token"},
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)

            with self.dashboard.database() as connection:
                row = connection.execute(
                    "SELECT stars, voters FROM submissions WHERE id = ?",
                    (submission_id,),
                ).fetchone()
            self.assertEqual(row["stars"], 1)
            self.assertIn("123456789012345678", row["voters"])

            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    f"/submission/{submission_id}/vote?guild_id=111",
                    data={"csrf_token": "vote-token"},
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)

            with self.dashboard.database() as connection:
                row = connection.execute(
                    "SELECT stars, voters FROM submissions WHERE id = ?",
                    (submission_id,),
                ).fetchone()
            self.assertEqual(row["stars"], 0)
            self.assertNotIn("123456789012345678", row["voters"] or "")

    def test_auth_code_redeems_server_access(self):
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM dashboard_account_auth_codes")
            connection.execute(
                """
                UPDATE dashboard_admin_users
                SET role = 'not_added', guild_ids_json = '[]'
                WHERE username = 'scoped-user'
                """
            )
            connection.execute(
                "DELETE FROM dashboard_user_server_access WHERE username = 'scoped-user'"
            )
            code, _ = self.dashboard.issue_dashboard_auth_code(
                connection,
                "scoped-user",
                "111",
                "moderator",
                "owner",
            )
            guild_id, role, scope, account_role = self.dashboard.redeem_dashboard_auth_code(
                connection,
                "scoped-user",
                code,
                self.config,
            )

        self.assertEqual(guild_id, "111")
        self.assertEqual(role, "moderator")
        self.assertEqual(scope, ["111"])
        self.assertEqual(account_role, "user")
        self.assertEqual(
            self.dashboard.dashboard_user_server_access_map("scoped-user"),
            {"111": "moderator"},
        )


if __name__ == "__main__":
    unittest.main()
