import os
import unittest
from unittest import mock

import dashboard


class PublicBotInviteTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.app.test_client()

    def test_bot_invite_url_uses_public_discord_scopes(self):
        env = {
            "SDAC_BOT_CLIENT_ID": "1234567890",
            "SDAC_BOT_PERMISSIONS": "274878221376",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            invite_url = dashboard.bot_invite_url()
        self.assertIn("client_id=1234567890", invite_url)
        self.assertIn("permissions=274878221376", invite_url)
        self.assertIn("scope=bot+applications.commands", invite_url)

    def test_public_invite_page_renders_without_client_id(self):
        with mock.patch.dict(os.environ, {"SDAC_BOT_CLIENT_ID": "", "DISCORD_CLIENT_ID": ""}, clear=False):
            response = self.client.get("/invite")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Invite", body)
        self.assertIn("SDAC_BOT_CLIENT_ID", body)

    def test_public_invite_page_renders_invite_link(self):
        with mock.patch.dict(os.environ, {"SDAC_BOT_CLIENT_ID": "1234567890"}, clear=False):
            response = self.client.get("/invite")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("discord.com/oauth2/authorize", body)
        self.assertIn("applications.commands", body)

    def test_app_bootstrap_exposes_public_links(self):
        with mock.patch.dict(os.environ, {"SDAC_BOT_CLIENT_ID": "1234567890", "SDAC_SUPPORT_URL": "https://discord.gg/example"}, clear=False):
            response = self.client.get("/api/app/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("invite_url", payload["app"])
        self.assertIn("support_url", payload["app"])
        self.assertEqual(payload["routes"]["invite"], "/invite")
        self.assertEqual(payload["routes"]["setup_guide"], "/setup-guide")


if __name__ == "__main__":
    unittest.main()
