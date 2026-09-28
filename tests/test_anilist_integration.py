import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import anilist_integration


class AniListIntegrationTests(unittest.TestCase):
    def test_authorization_uses_code_flow_and_state(self):
        with patch.dict(os.environ, {"SANA_ANILIST_CLIENT_ID": "client-456"}, clear=False):
            url = anilist_integration.anilist_authorization_url(
                "https://example.test/account/anilist/callback",
                "state-456",
            )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "anilist.co")
        self.assertEqual(query["client_id"], ["client-456"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], ["state-456"])
        self.assertNotIn("client_secret", query)

    def test_tokens_are_encrypted_at_rest(self):
        encrypted = anilist_integration.encrypt_anilist_token("private-token", "stable-secret")
        self.assertNotIn("private-token", encrypted)
        self.assertEqual(anilist_integration.decrypt_anilist_token(encrypted, "stable-secret"), "private-token")
        with self.assertRaises(ValueError):
            anilist_integration.decrypt_anilist_token(encrypted, "different-secret")

    def test_authenticated_lists_build_profile_and_export(self):
        user = {"id": 77, "name": "account_owner", "siteUrl": "https://anilist.co/user/account_owner/"}
        anime = [
            {"id": 1, "status": "CURRENT", "score": 8, "media": {"title": {"userPreferred": "Watching Now"}, "coverImage": {"large": "https://img.example/anime.jpg"}}},
            {"id": 2, "status": "COMPLETED", "score": 10, "media": {"title": {"english": "Finished Favorite"}, "coverImage": {}}},
        ]
        manga = [{"id": 3, "status": "CURRENT", "score": 9, "media": {"title": {"romaji": "Reading Now"}, "coverImage": {"medium": "https://img.example/manga.jpg"}}}]
        account_data = {"user": user, "anime": anime, "manga": manga}
        summary = anilist_integration.anilist_profile_summary("token", account_data=account_data)
        self.assertEqual(summary["anime_count"], 2)
        self.assertEqual(summary["manga_count"], 1)
        self.assertIn("Finished Favorite", summary["anime_favorites"])
        self.assertIn("Watching Now", summary["anime_watching"])
        self.assertIn("Reading Now", summary["manga_reading"])
        self.assertEqual(summary["anilist_profile_url"], user["siteUrl"])
        with patch.object(anilist_integration, "anilist_account_data", return_value=account_data):
            exported = anilist_integration.anilist_export_payload("token", user)
        self.assertEqual(exported["schema"], "sana-chan-anilist-export-v1")
        self.assertEqual(len(exported["anime"]), 2)
        self.assertEqual(len(exported["manga"]), 1)

    def test_custom_list_duplicates_are_removed(self):
        response = {"MediaListCollection": {"lists": [
            {"name": "Watching", "entries": [{"id": 10, "media": {"title": {"userPreferred": "One"}}}]},
            {"name": "Favorites", "isCustomList": True, "entries": [{"id": 10, "media": {"title": {"userPreferred": "One"}}}]},
        ]}}
        with patch.object(anilist_integration, "anilist_graphql", return_value=response):
            rows = anilist_integration._anilist_list("token", 77, "ANIME")
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
