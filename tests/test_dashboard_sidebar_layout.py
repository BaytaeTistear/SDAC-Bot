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
        self.assertIn('class="sdac-sidebar-controls"', body)
        self.assertIn('class="sdac-sidebar-toggle"', body)
        self.assertIn('class="sdac-sidebar-home', body)
        self.assertIn('>Home</a>', body)
        self.assertIn('class="sdac-sidebar-scroll"', body)
        self.assertIn('class="sdac-sidebar-nav"', body)
        self.assertIn('class="sdac-sidebar-section sdac-sidebar-main-section"', body)
        self.assertIn('class="sdac-sidebar-section-title">User</div>', body)
        self.assertIn('class="sdac-sidebar-section-title">Moderator</div>', body)
        self.assertIn('class="sdac-sidebar-section-title">Server Owner</div>', body)
        self.assertIn('class="sdac-sidebar-section-title">Bot Owner</div>', body)
        self.assertNotIn('<details class="sdac-sidebar-section"', body)
        self.assertNotIn('<summary>', body)
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
        self.assertIn("--sdac-sidebar-width: clamp(13.75rem, 17vw, 17.5rem)", body)
        self.assertIn("--sdac-content-width: min(96%, 76rem)", body)
        self.assertIn("--sdac-collapsed-sidebar-gutter: clamp(4.5rem, 7vw, 7rem)", body)
        self.assertIn(
            "body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: var(--sdac-collapsed-sidebar-gutter) !important; }",
            body,
        )
        self.assertIn(
            "body.sdac-has-sidebar.sdac-sidebar-collapsed { padding-left: 0 !important; }",
            body,
        )
        self.assertIn("body.sdac-has-sidebar table { display: block; max-width: 100%; overflow-x: auto; width: 100%; }", body)
    def test_sidebar_centers_page_content_and_has_invite_action(self):
        response = self.client.get(f"/admin/bot-owner?key={dashboard.ADMIN_KEY}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("margin-left: auto !important", body)
        self.assertIn("margin-right: auto !important", body)
        self.assertIn(".sdac-sidebar-controls {", body)
        self.assertIn(".sdac-sidebar-scroll {", body)
        self.assertIn(".sdac-sidebar-home {", body)
        self.assertIn('class="sdac-sidebar-home', body)
        self.assertIn('class="sdac-sidebar-invite"', body)
        self.assertIn(">Invite Bot</a>", body)

    def test_server_selector_css_is_hardened(self):
        response = self.client.get(f"/admin/bot-owner?key={dashboard.ADMIN_KEY}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(".sdac-server-switcher {", body)
        self.assertIn("overflow: hidden", body)
        self.assertIn("max-width: 100% !important", body)
        self.assertIn("min-width: 0 !important", body)
        self.assertIn("display: grid !important", body)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", body)
        self.assertIn("max-inline-size: 100% !important", body)
        self.assertIn("text-overflow: ellipsis", body)
        self.assertIn(".sdac-sidebar .sdac-server-switcher select, .sdac-sidebar .sdac-server-switcher button", body)

if __name__ == "__main__":
    unittest.main()
