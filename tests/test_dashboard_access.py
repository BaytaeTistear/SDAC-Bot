import os
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
