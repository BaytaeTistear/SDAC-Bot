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

    def test_simplified_commands_are_visible_by_default(self):
        import bot

        command_names = {command.name for command in bot.tree.get_commands()}
        self.assertEqual(command_names, {"sdac", "submit", "guess", "hint"})
        self.assertTrue(bot.SIMPLIFIED_SLASH_COMMANDS)
        self.assertIn("animeprofileimport", bot.LOW_COST_COMMAND_COOLDOWNS)
        self.assertIn("animeactivities", bot.PRUNED_SLASH_COMMANDS)
        self.assertIn("admincommands", bot.PRUNED_SLASH_COMMANDS)

    def test_command_alias_validation_supports_server_launchers(self):
        import bot

        self.assertEqual(bot.validate_command_alias("/Pepo Hub"), "pepo-hub")
        self.assertEqual(bot.validate_command_alias("sdac"), "")
        self.assertEqual(bot.command_alias_display({"command_alias": "pepo"}), "/pepo")
        self.assertTrue(bot.PROJECT_WIKI_URL.endswith("/wiki"))
        with self.assertRaises(ValueError):
            bot.validate_command_alias("submit")

    def test_bot_nickname_validation_matches_discord_limits(self):
        import bot

        self.assertEqual(bot.normalize_bot_nickname("  Media Helper  "), "Media Helper")
        self.assertEqual(bot.normalize_bot_nickname(""), "")
        with self.assertRaises(ValueError):
            bot.normalize_bot_nickname("x" * 33)
        with self.assertRaises(ValueError):
            bot.normalize_bot_nickname("bad\nname")

    def test_command_visibility_audit_reports_simplified_surface(self):
        import bot

        lines = bot.command_visibility_audit_lines()
        joined = "\n".join(lines)
        self.assertIn("/sdac", joined)
        self.assertIn("/submit", joined)
        self.assertIn("Advanced commands are behind `/sdac`", joined)
        self.assertNotIn("Extra global commands visible", joined)

    def test_mal_profile_summary_uses_public_list_data(self):
        import bot

        favorites, watching = bot.summarize_mal_profile(
            "example_user",
            {"data": [{"anime": {"title": "Watching One"}}]},
            {"data": [{"anime": {"title": "Completed One"}}]},
            {"data": {"anime": [{"title": "Favorite One"}]}},
        )
        self.assertIn("Favorite One", favorites)
        self.assertIn("example_user", favorites)
        self.assertIn("Watching One", watching)
        self.assertIn("Completed One", watching)

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
