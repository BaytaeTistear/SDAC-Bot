import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ANIME_SEED_CODE = r'''
import dashboard

client = dashboard.app.test_client()
with client.session_transaction() as session:
    session["sdac_account_username"] = "baytae"
    session["sdac_account_role"] = "bot_owner"
    session["sdac_admin"] = True
    session["sdac_admin_username"] = "baytae"
    session["sdac_admin_role"] = "bot_owner"
    session["sdac_admin_auth"] = "test"
    session["sdac_admin_guild_ids"] = []
    session["csrf_token"] = "seed-token"

response = client.post(
    f"/admin/anime-activities?key={dashboard.ADMIN_KEY}",
    data={
        "key": dashboard.ADMIN_KEY,
        "csrf_token": "seed-token",
        "action": "seed_anime_library",
        "guild_id": "111",
    },
    follow_redirects=True,
)
assert response.status_code == 200, response.status_code
body = response.get_data(as_text=True)
assert "Seeded" in body, body[:500]
with dashboard.database() as connection:
    count = connection.execute(
        "SELECT COUNT(*) FROM guess_library_items WHERE guild_id = ? AND pack_name = ?",
        ("111", "Experimental Anime Activities"),
    ).fetchone()[0]
assert count == dashboard.anime_activity_catalog_count(), count
'''


class AnimeActivitiesSeedTests(unittest.TestCase):
    def test_anime_activity_seed_creates_library_drafts(self):
        with tempfile.TemporaryDirectory(prefix="sdac-anime-seed-") as workdir:
            root = Path(workdir)
            (root / "media").mkdir(parents=True, exist_ok=True)
            (root / "backups").mkdir(parents=True, exist_ok=True)
            (root / "config.json").write_text(
                json.dumps(
                    {
                        "guilds": {
                            "111": {
                                "guild_name": "Anime Seed Server",
                                "features": {"guessing_games": True},
                                "categories": {},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "SDAC_DB_FILE": str(root / "sdac-anime-seed.db"),
                    "SDAC_CONFIG_FILE": str(root / "config.json"),
                    "SDAC_MEDIA_DIR": str(root / "media"),
                    "SDAC_BACKUP_DIR": str(root / "backups"),
                    "SDAC_BOT_STATUS_FILE": str(root / "bot_status.json"),
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(ANIME_SEED_CODE)],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
        if result.returncode != 0:
            self.fail(result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
