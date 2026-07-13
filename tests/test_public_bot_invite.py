import os
import unittest
from urllib.parse import parse_qs, urlparse
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

    def test_public_invite_page_is_guided_without_admin_key(self):
        with mock.patch.dict(os.environ, {"SDAC_BOT_CLIENT_ID": "1234567890"}, clear=False):
            response = self.client.get("/invite")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Guided Setup Flow", body)
        self.assertIn("OAuth Details", body)
        self.assertIn("Release Checklist", body)
        self.assertNotIn(dashboard.ADMIN_KEY, body)

    def test_sidebar_exposes_invite_bot_action(self):
        with self.client.session_transaction() as session:
            session["sdac_account_username"] = "baytae"
            session["sdac_account_role"] = "bot_owner"
            session["sdac_admin"] = True
            session["sdac_admin_username"] = "baytae"
            session["sdac_admin_role"] = "bot_owner"
            session["sdac_admin_auth"] = "test"
            session["sdac_admin_guild_ids"] = []
        response = self.client.get(f"/?key={dashboard.ADMIN_KEY}")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('class="sdac-sidebar-invite"', body)
        self.assertIn('href="/invite"', body)

    def test_app_bootstrap_exposes_public_links(self):
        with mock.patch.dict(os.environ, {"SDAC_BOT_CLIENT_ID": "1234567890", "SDAC_SUPPORT_URL": "https://discord.gg/example"}, clear=False):
            response = self.client.get("/api/app/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("invite_url", payload["app"])
        self.assertIn("support_url", payload["app"])
        self.assertEqual(payload["routes"]["invite"], "/invite")
        self.assertEqual(payload["routes"]["setup_guide"], "/setup-guide")
        self.assertIn("diagnostics", payload)
        self.assertIn("release_checklist", payload["routes"])
        self.assertIn("official_version", payload["release"])
        self.assertIn("experimental_version", payload["release"])

    def test_app_bootstrap_allows_capacitor_origin_by_default(self):
        response = self.client.get(
            "/api/app/bootstrap",
            headers={"Origin": "capacitor://localhost"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "capacitor://localhost")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_app_bootstrap_rejects_unknown_origin_by_default(self):
        response = self.client.get(
            "/api/app/bootstrap",
            headers={"Origin": "https://not-sdac.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_account_oauth_start_is_interactive_by_default(self):
        with mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_ID", "1234567890"), mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_SECRET", "secret"):
            response = self.client.get("/account/oauth/start?next=/app")
        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        query = parse_qs(urlparse(location).query)
        self.assertEqual(query["client_id"], ["1234567890"])
        self.assertEqual(query["redirect_uri"], ["http://localhost/account/oauth/callback"])
        self.assertNotIn("prompt", query)

    def test_account_oauth_start_supports_explicit_silent_prompt(self):
        with mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_ID", "1234567890"), mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_SECRET", "secret"):
            response = self.client.get("/account/oauth/start?next=/app&silent=1")
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response.headers["Location"]).query)
        self.assertEqual(query.get("prompt"), ["none"])


    def test_app_bootstrap_discord_login_uses_app_handoff(self):
        with mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_ID", "1234567890"), mock.patch.object(dashboard, "DISCORD_OAUTH_CLIENT_SECRET", "secret"):
            response = self.client.get("/api/app/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("/account/oauth/start", payload["routes"]["discord_login"])
        self.assertIn("next=/app/login/complete", payload["routes"]["discord_login"])
        self.assertIn("app=1", payload["routes"]["discord_login"])

    def test_app_claim_login_rejects_bad_ticket(self):
        response = self.client.post("/api/app/claim-login", json={"ticket": "bad-ticket"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_app_claim_login_options_allows_post(self):
        response = self.client.open(
            "/api/app/claim-login",
            method="OPTIONS",
            headers={"Origin": "capacitor://localhost"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
if __name__ == "__main__":
    unittest.main()
