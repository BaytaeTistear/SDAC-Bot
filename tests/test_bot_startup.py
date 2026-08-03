import asyncio
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
        self.assertNotIn("animeprofileimport", bot.LOW_COST_COMMAND_COOLDOWNS)
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

        profile = bot.summarize_mal_profile(
            "example_user",
            {"data": [{"anime": {"title": "Watching One"}}]},
            {"data": [{"anime": {"title": "Completed One"}}]},
            {"data": {
                "anime": [{"title": "Favorite One"}],
                "manga": [{"title": "Favorite Manga"}],
            }},
            {"data": [{"manga": {"title": "Reading One"}}]},
            {"data": [{"manga": {"title": "Completed Manga"}}]},
        )
        self.assertIn("Favorite One", profile["anime_favorites"])
        self.assertIn("example_user", profile["anime_favorites"])
        self.assertIn("Watching One", profile["anime_watching"])
        self.assertIn("Completed One", profile["anime_watching"])
        self.assertIn("Favorite Manga", profile["manga_favorites"])
        self.assertIn("Reading One", profile["manga_reading"])
        self.assertIn("Completed Manga", profile["manga_reading"])

    def test_mal_xml_profile_summary_splits_anime_and_manga(self):
        import bot

        profile = bot.summarize_mal_xml_profile("""
        <myanimelist>
          <myinfo><user_name>test_user</user_name></myinfo>
          <anime><series_title>Anime Watching</series_title><my_status>Watching</my_status><series_image>https://cdn.example/anime1.jpg</series_image></anime>
          <anime><series_title>Anime Done</series_title><my_status>Completed</my_status><series_image>https://cdn.example/anime2.jpg</series_image></anime>
          <manga><manga_title>Manga Reading</manga_title><my_status>Reading</my_status><series_image>https://cdn.example/manga1.jpg</series_image></manga>
          <manga><manga_title>Manga Done</manga_title><my_status>Completed</my_status><series_image>https://cdn.example/manga2.jpg</series_image></manga>
        </myanimelist>
        """)
        self.assertEqual(profile["mal_profile_url"], "https://myanimelist.net/profile/test_user")
        self.assertIn("Anime Done", profile["anime_favorites"])
        self.assertIn("Anime Watching", profile["anime_watching"])
        self.assertIn("Manga Done", profile["manga_favorites"])
        self.assertIn("Manga Reading", profile["manga_reading"])
        self.assertEqual(profile["anime_preview_images"][:1], ["https://cdn.example/anime1.jpg"])
        self.assertEqual(profile["manga_preview_images"][:1], ["https://cdn.example/manga1.jpg"])
    def test_scheduled_auto_hint_time_scales_to_question_window(self):
        from datetime import datetime, timedelta, timezone
        import bot

        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        next_question = now + timedelta(minutes=30)
        hints = ["Hint 1", "Hint 2"]
        self.assertEqual(bot.scaled_auto_hint_minutes(60, hints, next_question, now=now), 10)
        self.assertEqual(bot.scaled_auto_hint_minutes(5, hints, next_question, now=now), 5)
        self.assertEqual(bot.scaled_auto_hint_minutes(60, [], next_question, now=now), 60)
        close_deadline = bot.scheduled_hint_deadline(close_after_minutes=30, now=now)
        self.assertEqual(bot.scaled_auto_hint_minutes(60, hints, close_deadline, now=now), 10)
        self.assertIsNone(bot.scheduled_hint_deadline(close_after_minutes=0, now=now))


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
        self.assertIn("DD:HH:MM", bot.SDAC_SUBMENU_DETAILS["games_bulk_schedule"])
        self.assertIn("wrong guess", bot.SDAC_SUBMENU_DETAILS["games_timeout"])
        self.assertIn("queued or starting", bot.SDAC_SUBMENU_DETAILS["games_cancel_scheduled"])
        self.assertNotIn("/cancelgame", bot.SDAC_SUBMENU_DETAILS["games_cancel"])
        self.assertTrue(hasattr(bot, "StartLibraryGameWizardView"))
        self.assertTrue(hasattr(bot, "ScheduleGameWizardView"))
        self.assertTrue(hasattr(bot, "ScheduleGameModal"))
        self.assertTrue(hasattr(bot, "BulkScheduleGameWizardView"))
        self.assertTrue(hasattr(bot, "BulkScheduleGameModal"))
        self.assertFalse(hasattr(bot, "BulkScheduleUnitView"))
        self.assertFalse(hasattr(bot, "BulkScheduleUnitSelect"))
        self.assertTrue(hasattr(bot, "parse_dd_hh_mm_duration"))
        self.assertTrue(hasattr(bot, "format_dd_hh_mm_duration"))
        self.assertEqual(bot.parse_dd_hh_mm_duration("00:00:30"), 30)
        self.assertEqual(bot.parse_dd_hh_mm_duration("00:03:00"), 180)
        self.assertEqual(bot.parse_dd_hh_mm_duration("07:00:00"), 10080)
        self.assertEqual(bot.format_dd_hh_mm_duration(10080), "07:00:00")
        self.assertTrue(hasattr(bot, "ScheduleHintTimingView"))
        self.assertTrue(hasattr(bot, "ScheduleHintTimingButton"))
        self.assertTrue(hasattr(bot, "BulkScheduleHintTimingView"))
        self.assertTrue(hasattr(bot, "BulkScheduleHintTimingButton"))
        import inspect
        bulk_modal_source = inspect.getsource(bot.BulkScheduleGameModal)
        self.assertIn("Start when?", bulk_modal_source)
        self.assertIn("Repeat every (DD:HH:MM)", bulk_modal_source)
        self.assertIn("parse_scheduled_start_time", bulk_modal_source)
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

    def test_event_logging_inserts_have_matching_placeholders(self):
        import inspect
        import re
        import bot

        source = inspect.getsource(bot.record_rate_limit_event)
        source += "\n" + inspect.getsource(bot.record_content_moderation_event)
        source += "\n" + inspect.getsource(bot.guess.callback)
        for match in re.finditer(r"INSERT INTO (rate_limit_events|content_moderation_events) \((.*?)\)\s*VALUES \((.*?)\)", source, re.S):
            columns = [column.strip() for column in match.group(2).replace("\n", " ").split(",") if column.strip()]
            placeholders = re.findall(r"\?", match.group(3))
            self.assertEqual(len(columns), len(placeholders), match.group(1))
    def test_scheduled_game_start_message_hides_internal_status(self):
        import inspect
        import bot

        source = inspect.getsource(bot.start_library_game_item)
        self.assertNotIn("Scheduled game `{scheduled_id}` is now live.", source)
        self.assertNotIn("Hint timing was shortened to fit before the next scheduled question.", source)
        self.assertIn("Automatic hints are enabled every", source)
        self.assertIn("scale_hint_timing", source)
        self.assertIn("scheduled_hint_deadline", source)

    def test_hint_display_replaces_pipe_separators(self):
        import bot

        raw_hint = "Admin hint: Anime category: Drama / Romance / Supernatural|Title word count: 8|First letter: R"
        formatted = bot.format_hint_text_for_display(raw_hint)
        self.assertNotIn("|", formatted)
        self.assertIn("Supernatural Title word count", formatted)
        self.assertIn("8 First letter", formatted)
        self.assertEqual(bot.append_hint_text("First letter: R", "Extra|Detail"), "First letter: R\nExtra Detail")

    def test_sana_setup_menu_includes_doctor(self):
        import inspect
        import bot

        setup_values = [value for value, _label, _description in bot.SDAC_SUBMENUS["setup"]["options"]]
        self.assertIn("setup_doctor", setup_values)
        self.assertIn("Sana-Chan Doctor", bot.SDAC_SUBMENU_DETAILS["setup_doctor"])
        self.assertTrue(hasattr(bot, "doctor_summary_lines"))
        self.assertTrue(hasattr(bot, "run_sana_doctor_action"))
        summary = "\n".join(bot.doctor_summary_lines(["[OK] Ready", "[MISSING] Fix this", "[OPTIONAL] Polish this"]))
        self.assertIn("Blockers: `1`", summary)
        self.assertIn("Go Live Checklist", summary)
        source = inspect.getsource(bot.start_library_game_from_interaction)
        self.assertIn("belongs to a different server", source)
        self.assertIn("Check the server filter, item status, and media attachment", source)

    def test_sana_anime_profile_view_is_guided(self):
        import bot

        anime_labels = [label for _value, label, _description in bot.SDAC_SUBMENUS["anime"]["options"]]
        self.assertIn("View Profile", anime_labels)
        self.assertIn("Choose a server member", bot.SDAC_SUBMENU_DETAILS["anime_view"])
        self.assertNotIn("/animeprofileview", bot.SDAC_SUBMENU_DETAILS["anime_view"])
        self.assertIn(".xml", bot.SDAC_SUBMENU_DETAILS["anime_import"])
        self.assertIn("Username import is disabled", bot.SDAC_SUBMENU_DETAILS["anime_import"])
        self.assertIn("https://myanimelist.net/panel.php?go=export", bot.SDAC_SUBMENU_DETAILS["anime_import"])
        self.assertNotIn("/animeprofileimport", bot.SDAC_SUBMENU_DETAILS["anime_import"])
        self.assertTrue(hasattr(bot, "AnimeProfileView"))
        self.assertTrue(hasattr(bot, "AnimeProfileMemberSelect"))
        self.assertTrue(hasattr(bot, "AnimeProfileSelfButton"))
        self.assertTrue(hasattr(bot, "AnimeProfileImportView"))
        self.assertFalse(hasattr(bot, "AnimeProfileImportUsernameModal"))
        self.assertTrue(hasattr(bot, "import_mal_xml_attachment_flow"))
        self.assertFalse(hasattr(bot, "AnimeProfileImportXmlModal"))
        self.assertTrue(hasattr(bot, "handle_sana_anime_action"))

if __name__ == "__main__":
    unittest.main()

