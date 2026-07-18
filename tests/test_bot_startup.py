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
        self.assertEqual(command_names, {"sana", "submit", "guess", "hint"})
        self.assertTrue(bot.SIMPLIFIED_SLASH_COMMANDS)
        self.assertIn("animeprofileimport", bot.LOW_COST_COMMAND_COOLDOWNS)
        self.assertIn("animeactivities", bot.PRUNED_SLASH_COMMANDS)
        self.assertIn("admincommands", bot.PRUNED_SLASH_COMMANDS)

    def test_command_alias_validation_supports_server_launchers(self):
        import bot

        self.assertEqual(bot.validate_command_alias("/Pepo Hub"), "pepo-hub")
        self.assertEqual(bot.validate_command_alias("sana"), "")
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

    def test_bot_avatar_validation_accepts_supported_images(self):
        import bot
        import dashboard

        self.assertEqual(
            bot.normalize_bot_avatar_url("  https://example.com/avatar.png  "),
            "https://example.com/avatar.png",
        )
        self.assertEqual(
            dashboard.discord_avatar_payload(b"abc", "image/png"),
            "data:image/png;base64,YWJj",
        )
        with self.assertRaises(ValueError):
            bot.normalize_bot_avatar_url("http://example.com/avatar.png")
        with self.assertRaises(ValueError):
            bot.validate_bot_avatar_bytes(b"abc", "text/plain")
        with self.assertRaises(ValueError):
            dashboard.validate_bot_avatar_bytes(b"", "image/png")

    def test_setup_identity_steps_are_optional(self):
        import bot

        original_avatar_timestamp = bot.config.get("bot_avatar_updated_at", "")
        try:
            bot.config["bot_avatar_updated_at"] = ""
            rows = {row["label"]: row for row in bot.setup_status_rows({})}
            self.assertFalse(rows["Bot name"]["required"])
            self.assertFalse(rows["Bot image"]["required"])
            self.assertFalse(rows["Bot name"]["ok"])
            self.assertFalse(rows["Bot image"]["ok"])

            bot.config["bot_avatar_updated_at"] = "2026-07-12T00:00:00+00:00"
            rows = {row["label"]: row for row in bot.setup_status_rows({"bot_nickname": "Media Helper"})}
            self.assertTrue(rows["Bot name"]["ok"])
            self.assertTrue(rows["Bot image"]["ok"])
        finally:
            bot.config["bot_avatar_updated_at"] = original_avatar_timestamp

    def test_command_visibility_audit_reports_simplified_surface(self):
        import bot

        lines = bot.command_visibility_audit_lines()
        joined = "\n".join(lines)
        self.assertIn("/sana", joined)
        self.assertIn("/submit", joined)
        self.assertIn("Advanced commands are behind `/sana`", joined)
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

    def test_scheduled_auto_hint_time_scales_to_question_window(self):
        from datetime import datetime, timedelta, timezone
        import bot

        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        next_question = now + timedelta(minutes=30)
        hints = ["Hint 1", "Hint 2"]
        self.assertEqual(bot.scaled_auto_hint_minutes(60, hints, next_question, now=now), 10)
        self.assertEqual(bot.scaled_auto_hint_minutes(5, hints, next_question, now=now), 5)
        self.assertEqual(bot.scaled_auto_hint_minutes(60, [], next_question, now=now), 60)


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
        exhausted_game = {
            "hints_json": '["First letter: A", "Word count: 2"]',
            "hint_level": 2,
            "hint_revealed_at": "2026-07-10T00:00:00+00:00",
        }
        self.assertFalse(bot.guess_points_allowed(exhausted_game))
        active_game = {
            "hints_json": '["First letter: A", "Word count: 2"]',
            "hint_level": 1,
            "hint_revealed_at": "2026-07-10T00:00:00+00:00",
        }
        self.assertEqual(bot.guess_points_for_correct_answer(active_game, 0), 2)
        self.assertEqual(bot.guess_points_for_correct_answer(active_game, 1), 1)
        self.assertEqual(bot.guess_points_for_correct_answer(exhausted_game, 0), 0)


    def test_sana_hub_admin_menu_includes_games(self):
        import bot

        admin_values = [value for value, _label, _description in bot.SDAC_HUB_ADMIN_OPTIONS]
        self.assertIn("games", admin_values)
        self.assertIn("games", bot.SDAC_SUBMENUS)
        game_labels = [label for _value, label, _description in bot.SDAC_SUBMENUS["games"]["options"]]
        self.assertIn("Create Game", game_labels)
        self.assertIn("Start Library Game", game_labels)
        self.assertIn("Bulk Schedule", game_labels)
        self.assertIn("Guess Timeout", game_labels)
        self.assertIn("Cancel Scheduled", game_labels)
        self.assertIn("Cancel Game", game_labels)
        self.assertIn("Create Guessing Game", bot.SDAC_SUBMENU_DETAILS["games_create"])
        self.assertTrue(bot.DASHBOARD_BASE_URL.startswith("https://"))
        self.assertNotIn("/activegame", bot.SDAC_SUBMENU_DETAILS["games_active"])
        self.assertNotIn("/startlibrarygame", bot.SDAC_SUBMENU_DETAILS["games_start_library"])
        self.assertIn("minutes, hours, or days", bot.SDAC_SUBMENU_DETAILS["games_bulk_schedule"])
        self.assertIn("wrong guess", bot.SDAC_SUBMENU_DETAILS["games_timeout"])
        self.assertIn("queued or starting", bot.SDAC_SUBMENU_DETAILS["games_cancel_scheduled"])
        self.assertNotIn("/cancelgame", bot.SDAC_SUBMENU_DETAILS["games_cancel"])
        self.assertTrue(hasattr(bot, "StartLibraryGameWizardView"))
        self.assertTrue(hasattr(bot, "ScheduleGameWizardView"))
        self.assertTrue(hasattr(bot, "ScheduleGameModal"))
        self.assertTrue(hasattr(bot, "BulkScheduleGameWizardView"))
        self.assertTrue(hasattr(bot, "BulkScheduleGameModal"))
        self.assertTrue(hasattr(bot, "BulkScheduleUnitView"))
        self.assertTrue(hasattr(bot, "BulkScheduleUnitSelect"))
        self.assertTrue(hasattr(bot, "GuessTimeoutModal"))
        self.assertTrue(hasattr(bot, "CancelScheduledGamesView"))
        self.assertTrue(hasattr(bot, "ConfirmCancelScheduledGamesButton"))
        self.assertTrue(hasattr(bot, "CancelActiveGameView"))
        self.assertTrue(hasattr(bot, "ConfirmCancelActiveGameButton"))
        self.assertTrue(hasattr(bot, "start_library_game_from_interaction"))
        self.assertTrue(hasattr(bot, "schedule_library_game_record"))
        self.assertTrue(hasattr(bot, "set_wrong_guess_timeout"))
        self.assertTrue(hasattr(bot, "scaled_auto_hint_minutes"))
        self.assertTrue(hasattr(bot, "count_cancellable_scheduled_games"))
        self.assertTrue(hasattr(bot, "cancel_all_scheduled_games"))
        self.assertTrue(hasattr(bot, "cancel_active_game_from_interaction"))
        self.assertTrue(hasattr(bot, "handle_sana_instant_action"))
        for action in [value for value, _label, _description in bot.SDAC_SUBMENUS["games"]["options"]]:
            self.assertNotIn("Run `/", bot.SDAC_SUBMENU_DETAILS[action])
            self.assertNotIn("/activegame", bot.SDAC_SUBMENU_DETAILS[action])
            self.assertNotIn("/cancelgame", bot.SDAC_SUBMENU_DETAILS[action])
        self.assertTrue(hasattr(bot, "active_guess_game_content"))
        self.assertTrue(hasattr(bot, "current_hint_content"))
        self.assertTrue(hasattr(bot, "sana_categories_content"))
        self.assertTrue(hasattr(bot, "resolve_selected_text_channel"))

    def test_scheduled_game_start_message_hides_internal_status(self):
        import inspect
        import bot

        source = inspect.getsource(bot.start_library_game_item)
        self.assertNotIn("Scheduled game `{scheduled_id}` is now live.", source)
        self.assertNotIn("Hint timing was shortened to fit before the next scheduled question.", source)
        self.assertIn("Automatic hints are enabled every", source)

    def test_hint_display_replaces_pipe_separators(self):
        import bot

        raw_hint = "Admin hint: Anime category: Drama / Romance / Supernatural|Title word count: 8|First letter: R"
        formatted = bot.format_hint_text_for_display(raw_hint)
        self.assertNotIn("|", formatted)
        self.assertIn("Supernatural Title word count", formatted)
        self.assertIn("8 First letter", formatted)
        self.assertEqual(bot.append_hint_text("First letter: R", "Extra|Detail"), "First letter: R\nExtra Detail")

if __name__ == "__main__":
    unittest.main()
