import re
import unittest

import dashboard


class DashboardSidebarLayoutTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()
        with self.client.session_transaction() as session:
            session["sdac_account_username"] = "baytae"
            session["sdac_account_role"] = "bot_owner"
            session["sdac_admin"] = True
            session["sdac_admin_username"] = "baytae"
            session["sdac_admin_role"] = "bot_owner"
            session["sdac_admin_auth"] = "test"
            session["sdac_admin_guild_ids"] = []

    def test_body_classes_are_merged_without_duplicate_class_attributes(self):
        html = '<html><body class="existing"><main>Hi</main></body></html>'
        merged = dashboard.add_body_classes(html, "sdac-theme", "sdac-has-sidebar")
        body_tag = re.search(r"<body[^>]*>", merged).group(0)
        self.assertEqual(body_tag.count("class="), 1)
        self.assertIn("existing", body_tag)
        self.assertIn("sdac-theme", body_tag)
        self.assertIn("sdac-has-sidebar", body_tag)

    def test_admin_sidebar_uses_current_page_server_selector(self):
        response = self.client.get(f"/admin/bot-owner?key={dashboard.ADMIN_KEY}&guild_id=111&notice=test")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('class="sdac-theme sdac-has-sidebar', body)
        self.assertIn('class="sdac-sidebar-toggle"', body)
        self.assertIn('class="sdac-server-switcher"', body)
        self.assertIn('action="/admin/bot-owner"', body)
        self.assertIn('name="key"', body)
        self.assertIn('value="ImTheBestAdmin"', body)
        self.assertIn('name="notice"', body)
        self.assertNotIn('sdacSidebarCollapsed";\n    var collapsed', body)

    def test_collapsed_sidebar_keeps_menu_gutter(self):
        response = self.client.get(f"/admin/bot-owner?key={dashboard.ADMIN_KEY}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("--sdac-collapsed-sidebar-gutter: 112px", body)
        self.assertIn(
            "body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: var(--sdac-collapsed-sidebar-gutter) !important; }",
            body,
        )
        self.assertIn(
            "body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: 0 !important; }",
            body,
        )

if __name__ == "__main__":
    unittest.main()
