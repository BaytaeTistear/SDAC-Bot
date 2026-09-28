import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import mal_integration


class MyAnimeListIntegrationTests(unittest.TestCase):
    def test_authorization_uses_authenticated_account_pkce_and_state(self):
        with patch.dict(os.environ, {"SANA_MAL_CLIENT_ID": "client-123"}, clear=False):
            verifier = mal_integration.new_pkce_verifier()
            url = mal_integration.mal_authorization_url(
                "https://example.test/account/mal/callback",
                "state-123",
                verifier,
            )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "myanimelist.net")
        self.assertEqual(query["client_id"], ["client-123"])
        self.assertEqual(query["state"], ["state-123"])
        self.assertEqual(query["code_challenge"], [verifier])
        self.assertEqual(query["code_challenge_method"], ["plain"])
        self.assertNotIn("client_secret", query)

    def test_tokens_are_encrypted_at_rest(self):
        encrypted = mal_integration.encrypt_mal_token("private-token", "stable-secret")
        self.assertNotIn("private-token", encrypted)
        self.assertEqual(
            mal_integration.decrypt_mal_token(encrypted, "stable-secret"),
            "private-token",
        )
        with self.assertRaises(ValueError):
            mal_integration.decrypt_mal_token(encrypted, "different-secret")

    def test_authenticated_lists_build_anime_and_manga_profile(self):
        anime = [
            {
                "node": {"title": "Currently Airing", "main_picture": {"medium": "https://img.example/anime.jpg"}},
                "list_status": {"status": "watching", "score": 8, "updated_at": "2026-09-28T01:00:00Z"},
            },
            {
                "node": {"title": "Completed Favorite"},
                "list_status": {"status": "completed", "score": 10, "updated_at": "2026-09-27T01:00:00Z"},
            },
        ]
        manga = [
            {
                "node": {"title": "Reading Now", "main_picture": {"large": "https://img.example/manga.jpg"}},
                "list_status": {"status": "reading", "score": 9, "updated_at": "2026-09-28T01:00:00Z"},
            },
        ]
        with patch.object(mal_integration, "_mal_user_list", side_effect=[anime, manga]):
            summary = mal_integration.mal_profile_summary(
                "token",
                {"id": 42, "name": "account_owner"},
            )
        self.assertEqual(summary["anime_count"], 2)
        self.assertEqual(summary["manga_count"], 1)
        self.assertIn("Completed Favorite", summary["anime_favorites"])
        self.assertIn("Currently Airing", summary["anime_watching"])
        self.assertIn("Reading Now", summary["manga_reading"])
        self.assertEqual(summary["mal_profile_url"], "https://myanimelist.net/profile/account_owner")
        self.assertEqual(summary["anime_preview_images"], ["https://img.example/anime.jpg"])


if __name__ == "__main__":
    unittest.main()
