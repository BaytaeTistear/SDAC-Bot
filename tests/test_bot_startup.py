import os
import tempfile
import unittest


class BotStartupTests(unittest.TestCase):
    def test_bot_import_initializes_database(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        os.environ["SDAC_DB_FILE"] = tmp.name
        try:
            import bot

            self.assertEqual(bot.OWNER_OVERRIDE_USERNAME, "baytae")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def test_experimental_anime_commands_are_opt_in(self):
        import bot

        command_names = {command.name for command in bot.tree.get_commands()}
        self.assertIn("submit", command_names)
        self.assertNotIn("animeactivities", command_names)
        self.assertNotIn("animeevent", command_names)
        self.assertNotIn("animechallenge", command_names)
        self.assertNotIn("Anime Activities", bot.USER_COMMAND_GROUPS)
        self.assertNotIn("animeactivities", bot.LOW_COST_COMMAND_COOLDOWNS)

    def test_guess_points_are_blocked_only_after_all_generated_hints(self):
        import bot

        self.assertTrue(bot.guess_points_allowed({
            "hints_json": '["First letter: A", "Word count: 2"]',
            "hint_level": 0,
            "hint_revealed_at": "",
        }))
        self.assertTrue(bot.guess_points_allowed({
            "hints_json": '["First letter: A", "Word count: 2"]',
            "hint_level": 1,
            "hint_revealed_at": "2026-07-10T00:00:00+00:00",
        }))
        self.assertFalse(bot.guess_points_allowed({
            "hints_json": '["First letter: A", "Word count: 2"]',
            "hint_level": 2,
            "hint_revealed_at": "2026-07-10T00:00:00+00:00",
        }))


if __name__ == "__main__":
    unittest.main()
