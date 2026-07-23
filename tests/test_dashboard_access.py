import io
import os
import zipfile
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class DashboardAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        cls.tmp.close()
        os.environ["SDAC_DB_FILE"] = cls.tmp.name
        import dashboard

        cls.dashboard = dashboard

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp.name)
        except OSError:
            pass

    def setUp(self):
        self.config = {
            "guilds": {
                "111": {"guild_name": "Alpha", "features": {"public_gallery": True}},
                "222": {"guild_name": "Beta", "features": {"public_gallery": False}},
            }
        }
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM dashboard_user_server_access")
            connection.execute("DELETE FROM guess_library_items")
            connection.execute("DELETE FROM background_jobs")
            connection.execute("DELETE FROM dashboard_admin_users")
            connection.execute("""
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, password_hash, role,
                    disabled, created_at, updated_at, guild_ids_json
                )
                VALUES ('scoped-user', '', 'Scoped User', 'x', 'user', 0, '', '', '["111","222"]')
            """)
            self.dashboard.upsert_user_server_access(
                connection,
                "scoped-user",
                ["111"],
                role="owner",
                source="manual",
                preserve_existing_roles=False,
            )
            self.dashboard.upsert_user_server_access(
                connection,
                "scoped-user",
                ["222"],
                role="user",
                source="oauth",
                preserve_existing_roles=False,
            )

    def test_fallback_secret_key_is_reused_from_local_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_file = Path(tmpdir) / ".sdac_secret_key"
            with mock.patch.dict(os.environ, {"SDAC_SECRET_KEY": "", "SDAC_SECRET_KEY_FILE": str(secret_file)}, clear=False):
                first_secret = self.dashboard.load_dashboard_secret_key(Path(tmpdir))
                second_secret = self.dashboard.load_dashboard_secret_key(Path(tmpdir))

        self.assertTrue(first_secret)
        self.assertEqual(first_secret, second_secret)

    def test_admin_password_login_sets_persistent_cookie(self):
        password = "correct horse battery staple"
        with self.dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, password_hash, role,
                    disabled, created_at, updated_at, guild_ids_json
                )
                VALUES (?, '', 'Remember Admin', ?, 'bot_owner', 0, '', '', '[]')
                """,
                ("remember-admin", self.dashboard.generate_password_hash(password)),
            )

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["csrf_token"] = "login-token"
            response = client.post(
                f"/admin/login?key={self.dashboard.ADMIN_KEY}",
                data={
                    "username": "remember-admin",
                    "password": password,
                    "csrf_token": "login-token",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        cookie_header = response.headers.get("Set-Cookie", "")
        self.assertIn("Expires=", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Lax", cookie_header)

    def test_account_selector_uses_access_rows_not_public_gallery(self):
        with self.dashboard.app.test_request_context("/"):
            self.dashboard.session["sdac_account_username"] = "scoped-user"
            self.dashboard.session["sdac_account_role"] = "user"
            rows = self.dashboard.sidebar_server_options(self.config)

        self.assertEqual([row["id"] for row in rows], ["111", "222"])

    def test_discord_oauth_start_uses_configured_https_public_callback(self):
        with mock.patch.dict(self.dashboard.os.environ, {"SDAC_PUBLIC_URL": "https://alpha-beta.trycloudflare.com"}, clear=False):
            with mock.patch.object(self.dashboard, "DISCORD_OAUTH_CLIENT_ID", "1234567890"):
                with mock.patch.object(self.dashboard, "DISCORD_OAUTH_CLIENT_SECRET", "secret"):
                    with self.dashboard.app.test_client() as client:
                        response = client.get("/account/oauth/start", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        location = response.headers.get("Location", "")
        self.assertIn("discord.com/api/oauth2/authorize", location)
        self.assertIn("redirect_uri=https%3A%2F%2Falpha-beta.trycloudflare.com%2Faccount%2Foauth%2Fcallback", location)
        self.assertNotIn("redirect_uri=http%3A%2F%2Falpha-beta.trycloudflare.com", location)
    def test_oauth_callback_uses_public_url(self):
        with self.dashboard.app.test_request_context("/admin/oauth-diagnostics", base_url="http://localhost:5000"):
            with mock.patch.dict(os.environ, {"SDAC_PUBLIC_URL": "https://sana.example.test"}, clear=False):
                status = self.dashboard.public_url_launch_status()

        self.assertTrue(status["ok"])
        self.assertEqual(status["callback_url"], "https://sana.example.test/account/oauth/callback")

    def test_quick_tunnel_callback_is_warning_not_missing(self):
        with self.dashboard.app.test_request_context("/admin/oauth-diagnostics", base_url="http://localhost:5000"):
            with mock.patch.dict(os.environ, {"SDAC_PUBLIC_URL": "https://alpha-beta.trycloudflare.com"}, clear=False):
                status = self.dashboard.public_url_launch_status()

        self.assertFalse(status["ok"])
        self.assertEqual(status["state"], "Temporary")
        self.assertEqual(status["callback_url"], "https://alpha-beta.trycloudflare.com/account/oauth/callback")

    def test_default_google_play_account_must_stay_low_access(self):
        with self.dashboard.database() as connection:
            connection.execute("""
                INSERT INTO dashboard_admin_users (
                    username, email, display_name, password_hash, role,
                    disabled, created_at, updated_at, guild_ids_json
                )
                VALUES ('default', '', 'Default', 'x', 'not_added', 0, '', '', '[]')
            """)
        status = self.dashboard.google_play_test_account_status()
        self.assertTrue(status["ok"])

        with self.dashboard.database() as connection:
            connection.execute("UPDATE dashboard_admin_users SET role = 'bot_owner' WHERE username = 'default'")
        status = self.dashboard.google_play_test_account_status()
        self.assertFalse(status["ok"])
        self.assertEqual(status["state"], "Too much access")
    def test_selected_server_role_overrides_global_role(self):
        with self.dashboard.app.test_request_context("/?guild_id=111"):
            self.dashboard.session["sdac_admin"] = True
            self.dashboard.session["sdac_admin_username"] = "scoped-user"
            self.dashboard.session["sdac_admin_role"] = "user"
            self.assertEqual(self.dashboard.current_admin_role(), "owner")

        with self.dashboard.app.test_request_context("/?guild_id=222"):
            self.dashboard.session["sdac_admin"] = True
            self.dashboard.session["sdac_admin_username"] = "scoped-user"
            self.dashboard.session["sdac_admin_role"] = "user"
            self.assertEqual(self.dashboard.current_admin_role(), "user")

    def test_baytae_override_gets_all_servers(self):
        with self.dashboard.app.test_request_context("/"):
            self.dashboard.session["sdac_account_username"] = "baytae"
            self.dashboard.session["sdac_account_role"] = "owner"
            rows = self.dashboard.sidebar_server_options(self.config)

        self.assertEqual([row["id"] for row in rows], ["111", "222"])

    def test_logged_in_account_can_vote_and_unvote_submission(self):
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM submissions")
            cursor = connection.execute(
                """
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_message_id, repost_channel_id,
                    user_id, username, category, message_text, file_paths, media_paths,
                    media_names, media_types, media_sizes, media_metadata_json,
                    stars, voters, status, submitted_at, created_at
                )
                VALUES (
                    '111', 'o1', 'r1', 'c1', 'owner-id', 'Owner', 'screenshots',
                    'A post', '', '', '', '', '', '[]', 0, '', 'posted', '2026-07-10T00:00:00+00:00', '2026-07-10T00:00:00+00:00'
                )
                """
            )
            submission_id = cursor.lastrowid

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_account_username"] = "scoped-user"
                session["sdac_account_role"] = "user"
                session["sdac_account_guild_ids"] = ["111"]
                session["sdac_discord_user_id"] = "123456789012345678"
                session["csrf_token"] = "vote-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    f"/submission/{submission_id}/vote?guild_id=111",
                    data={"csrf_token": "vote-token"},
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)

            with self.dashboard.database() as connection:
                row = connection.execute(
                    "SELECT stars, voters FROM submissions WHERE id = ?",
                    (submission_id,),
                ).fetchone()
            self.assertEqual(row["stars"], 1)
            self.assertIn("123456789012345678", row["voters"])

            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    f"/submission/{submission_id}/vote?guild_id=111",
                    data={"csrf_token": "vote-token"},
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)

            with self.dashboard.database() as connection:
                row = connection.execute(
                    "SELECT stars, voters FROM submissions WHERE id = ?",
                    (submission_id,),
                ).fetchone()
            self.assertEqual(row["stars"], 0)
            self.assertNotIn("123456789012345678", row["voters"] or "")

    def test_auth_code_redeems_server_access(self):
        with self.dashboard.database() as connection:
            connection.execute("DELETE FROM dashboard_account_auth_codes")
            connection.execute(
                """
                UPDATE dashboard_admin_users
                SET role = 'not_added', guild_ids_json = '[]'
                WHERE username = 'scoped-user'
                """
            )
            connection.execute(
                "DELETE FROM dashboard_user_server_access WHERE username = 'scoped-user'"
            )
            code, _ = self.dashboard.issue_dashboard_auth_code(
                connection,
                "scoped-user",
                "111",
                "moderator",
                "owner",
            )
            guild_id, role, scope, account_role = self.dashboard.redeem_dashboard_auth_code(
                connection,
                "scoped-user",
                code,
                self.config,
            )

        self.assertEqual(guild_id, "111")
        self.assertEqual(role, "moderator")
        self.assertEqual(scope, ["111"])
        self.assertEqual(account_role, "user")
        self.assertEqual(
            self.dashboard.dashboard_user_server_access_map("scoped-user"),
            {"111": "moderator"},
        )

    def test_google_play_review_account_is_low_access(self):
        with self.dashboard.database() as connection:
            import database_migrations
            database_migrations.migration_18_google_play_test_account(connection)
            row = connection.execute(
                """
                SELECT username, display_name, password_hash, role, disabled, guild_ids_json
                FROM dashboard_admin_users
                WHERE username = 'default'
                """
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["display_name"], "Default")
        self.assertEqual(row["role"], "not_added")
        self.assertEqual(row["disabled"], 0)
        self.assertEqual(row["guild_ids_json"], "[]")
        self.assertTrue(self.dashboard.check_password_hash(row["password_hash"], "JohnDoe"))
    def assert_guess_archive_media_saves_matching_file(self, filename, buffer):
        buffer.seek(0)
        upload = type("Upload", (), {"filename": filename, "stream": buffer})()
        archive, lookup = self.dashboard.open_guess_media_zip(upload)
        try:
            self.assertIn("anime/skyline.png", lookup)
            self.assertIn("skyline.png", lookup)
            with tempfile.TemporaryDirectory() as tmpdir:
                with mock.patch.object(self.dashboard, "MEDIA_DIR", Path(tmpdir)):
                    media_info = self.dashboard.save_guess_library_zip_media(
                        "111",
                        archive,
                        lookup["skyline.png"],
                        {"max_file_bytes": 1024 * 1024},
                    )
                    self.assertEqual(media_info["name"], "skyline.png")
                    self.assertEqual(media_info["type"], "image")
                    self.assertGreater(media_info["size"], 0)
                    self.assertTrue(Path(media_info["path"]).is_file())
        finally:
            archive.close()

    def test_guess_bulk_zip_media_helper_saves_matching_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("anime/skyline.png", b"not really a png, but non-empty")
        self.assert_guess_archive_media_saves_matching_file("media.zip", buffer)

    def test_guess_bulk_tar_media_helper_saves_matching_file(self):
        buffer = io.BytesIO()
        payload = b"not really a png, but non-empty"
        info = tarfile.TarInfo("anime/skyline.png")
        info.size = len(payload)
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            archive.addfile(info, io.BytesIO(payload))
        self.assert_guess_archive_media_saves_matching_file("media.tar", buffer)

    def test_game_library_filter_uses_stable_dashboard_action(self):
        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_admin"] = True
                session["sdac_admin_username"] = "baytae"
                session["sdac_admin_role"] = "bot_owner"
                session["csrf_token"] = "library-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.get(
                    f"/admin/game-library?key={self.dashboard.ADMIN_KEY}&guild_id=111"
                )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('method="get" action="/admin/game-library"', body)
        self.assertIn('method="post" enctype="multipart/form-data" action="/admin/game-library"', body)
        self.assertIn("Import preview", body)
        self.assertIn("archive indexing", body)
        self.assertNotIn("localhost", body.lower())
        self.assertNotIn("127.0.0.1", body)

    def test_game_library_buttons_stay_on_dashboard_route(self):
        with self.dashboard.database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO guess_library_items (
                    guild_id, title, answer, answer_display,
                    answer_aliases_json, prompt_text, category, hint_text,
                    auto_hint_minutes, media_path, media_name, media_type,
                    media_size, media_metadata_json, status, times_used,
                    tags_json, pack_name, enabled, notes,
                    created_by, created_at, updated_at
                )
                VALUES (
                    '111', 'Library Test', 'librarytest', 'Library Test',
                    '[{"normalized":"librarytest","display":"Library Test"}]', '',
                    'anime', '', 0, '', '', 'unknown', 0, '{}', 'draft', 0,
                    '[]', 'Regression', 1, '', 'test', '2026-07-18T00:00:00+00:00',
                    '2026-07-18T00:00:00+00:00'
                )
                """
            )
            item_id = cursor.lastrowid

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_admin"] = True
                session["sdac_admin_username"] = "baytae"
                session["sdac_admin_role"] = "bot_owner"
                session["csrf_token"] = "library-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "set_status",
                        "guild_id": "111",
                        "item_id": str(item_id),
                        "status": "disabled",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "update_item",
                        "guild_id": "111",
                        "item_id": str(item_id),
                        "title": "Library Test Updated",
                        "answer": "Library Test|Library Alias",
                        "category": "anime",
                        "pack_name": "Regression",
                        "tags": "stable, route",
                        "auto_hint_minutes": "0",
                        "prompt_text": "",
                        "hint_text": "",
                        "notes": "",
                        "status": "draft",
                        "enabled": "1",
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "delete_item",
                        "guild_id": "111",
                        "item_id": str(item_id),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

        with self.dashboard.database() as connection:
            row = connection.execute(
                "SELECT id FROM guess_library_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        self.assertIsNone(row)

    def test_game_library_bulk_actions_enable_disable_and_delete_items(self):
        with self.dashboard.database() as connection:
            item_ids = []
            for index, enabled in enumerate((1, 1, 0), start=1):
                cursor = connection.execute(
                    """
                    INSERT INTO guess_library_items (
                        guild_id, title, answer, answer_display,
                        answer_aliases_json, prompt_text, category, hint_text,
                        auto_hint_minutes, media_path, media_name, media_type,
                        media_size, media_metadata_json, status, times_used,
                        tags_json, pack_name, enabled, notes,
                        created_by, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, '', 'anime', '', 0, ?, ?, 'image',
                        0, '{}', 'draft', 0, '[]', 'Bulk', ?, '', 'test',
                        '2026-07-18T00:00:00+00:00', '2026-07-18T00:00:00+00:00')
                    """,
                    (
                        "111",
                        f"Bulk Library {index}",
                        f"bulklibrary{index}",
                        f"Bulk Library {index}",
                        '[{"normalized":"bulklibrary%s","display":"Bulk Library %s"}]' % (index, index),
                        f"game_library/bulk-library-{index}.png",
                        f"bulk-library-{index}.png",
                        enabled,
                    ),
                )
                item_ids.append(cursor.lastrowid)

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_admin"] = True
                session["sdac_admin_username"] = "baytae"
                session["sdac_admin_role"] = "bot_owner"
                session["csrf_token"] = "library-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "bulk_item_action",
                        "guild_id": "111",
                        "bulk_action": "disable",
                        "item_ids": ",".join(str(item_id) for item_id in item_ids[:2]),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "bulk_item_action",
                        "guild_id": "111",
                        "bulk_action": "enable",
                        "item_ids": str(item_ids[2]),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

                with self.dashboard.database() as connection:
                    state_rows = connection.execute(
                        """
                        SELECT id, enabled, status
                        FROM guess_library_items
                        WHERE id IN (?, ?, ?)
                        ORDER BY id ASC
                        """,
                        item_ids,
                    ).fetchall()
                self.assertEqual([row["enabled"] for row in state_rows], [0, 0, 1])
                self.assertEqual(
                    [row["status"] for row in state_rows],
                    ["disabled", "disabled", "active"],
                )

                response = client.post(
                    "/admin/game-library",
                    data={
                        "key": self.dashboard.ADMIN_KEY,
                        "csrf_token": "library-token",
                        "action": "bulk_item_action",
                        "guild_id": "111",
                        "bulk_action": "delete",
                        "item_ids": ",".join(str(item_id) for item_id in item_ids),
                    },
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/game-library", response.location)

        with self.dashboard.database() as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM guess_library_items WHERE id IN (?, ?, ?)",
                item_ids,
            ).fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_game_library_shows_recent_import_job_progress(self):
        with self.dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO background_jobs (
                    job_type, guild_id, status, requested_by,
                    requested_by_name, payload_json, result_json,
                    error, created_at, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "guess_library_bulk_import",
                    "111",
                    "running",
                    "admin-id",
                    "Admin",
                    '{"csv_filename":"anime.csv","archive_filename":"anime.7z","archive_size":7340032}',
                    '{"stage":"archive_indexed","media_entries":42,"rows_seen":10,"imported":6,"attached_media":5,"missing_media":1,"skipped":2}',
                    "",
                    "2026-07-18T00:00:00+00:00",
                    "2026-07-18T00:00:01+00:00",
                    "",
                ),
            )

        with self.dashboard.app.test_client() as client:
            with client.session_transaction() as session:
                session["sdac_admin"] = True
                session["sdac_admin_username"] = "baytae"
                session["sdac_admin_role"] = "bot_owner"
                session["csrf_token"] = "library-token"
            with mock.patch.object(self.dashboard, "load_config", return_value=self.config):
                response = client.get(
                    f"/admin/game-library?key={self.dashboard.ADMIN_KEY}&guild_id=111"
                )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Recent Imports", body)
        self.assertIn("anime.csv", body)
        self.assertIn("anime.7z", body)
        self.assertIn("archive_indexed", body)
        self.assertIn("Media entries indexed: 42", body)
        self.assertIn("Rows seen: 10", body)
        self.assertIn("Media attached: 5", body)
        self.assertIn("Missing media: 1", body)

    def test_recent_imports_show_cancel_for_active_jobs(self):
        with self.dashboard.database() as connection:
            connection.execute(
                """
                INSERT INTO background_jobs (
                    job_type, guild_id, status, requested_by,
                    requested_by_name, payload_json, result_json,
                    error, created_at, started_at, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "guess_library_bulk_import",
                    "111",
                    "queued",
                    "admin-id",
                    "Admin",
                    '{"csv_filename":"anime.csv","archive_filename":"anime.7z"}',
                    '{"stage":"queued"}',
                    "",
                    "2026-07-18T00:00:00+00:00",
                    "",
                    "",
                ),
            )

        with mock.patch.object(self.dashboard, "start_background_job"):
            jobs = self.dashboard.recent_guess_library_import_jobs(guild_id="111")

        self.assertEqual(jobs[0]["status"], "queued")
        self.assertTrue(jobs[0]["can_cancel"])
        self.assertIn("Waiting", jobs[0]["stage_label"])

    def test_cancel_background_job_marks_import_canceled(self):
        with tempfile.TemporaryDirectory() as root:
            staging_dir = Path(root) / "import-job"
            staging_dir.mkdir()
            (staging_dir / "import.csv").write_text("answer\nSana\n", encoding="utf-8")
            with self.dashboard.database() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO background_jobs (
                        job_type, guild_id, status, requested_by,
                        requested_by_name, payload_json, result_json,
                        error, created_at, started_at, finished_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "guess_library_bulk_import",
                        "111",
                        "queued",
                        "admin-id",
                        "Admin",
                        '{"staging_dir":"' + str(staging_dir).replace('\\', '\\\\') + '"}',
                        "{}",
                        "",
                        "2026-07-18T00:00:00+00:00",
                        "",
                        "",
                    ),
                )
                job_id = cursor.lastrowid

            self.dashboard.cancel_background_job(job_id, actor_id="tester", actor_name="Tester")

            with self.dashboard.database() as connection:
                row = connection.execute(
                    "SELECT status, error, finished_at FROM background_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                audit_row = connection.execute(
                    "SELECT action FROM admin_audit_log WHERE target_type = ? AND target_id = ?",
                    ("background_job", str(job_id)),
                ).fetchone()

            self.assertEqual(row["status"], "canceled")
            self.assertEqual(row["error"], "Canceled by admin.")
            self.assertTrue(row["finished_at"])
            self.assertEqual(audit_row["action"], "cancel_guess_library_import")
            self.assertFalse(staging_dir.exists())
    def test_guess_bulk_import_with_media_uses_storage_helpers(self):
        csv_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
        archive_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            csv_file.write(
                "title,answer,media_filename,status\n"
                "Skyline,Anime Skyline,anime/skyline.png,active\n"
            )
            csv_file.close()
            archive_file.close()
            with zipfile.ZipFile(archive_file.name, "w") as archive:
                archive.writestr("anime/skyline.png", b"not really a png, but non-empty")

            with tempfile.TemporaryDirectory() as media_dir:
                config = {
                    "guilds": {
                        "111": {
                            "guild_name": "Alpha",
                            "limits": {"storage_limit_bytes": 1024 * 1024},
                        }
                    },
                    "limits": {"max_file_bytes": 1024 * 1024},
                }
                with mock.patch.object(self.dashboard, "MEDIA_DIR", Path(media_dir)):
                    with mock.patch.object(self.dashboard, "load_config", return_value=config):
                        result = self.dashboard.run_guess_library_bulk_import(
                            "111",
                            csv_file.name,
                            archive_file.name,
                            "anime.zip",
                            actor_name="test",
                        )

            self.assertEqual(result["imported"], 1)
            self.assertEqual(result["attached_media"], 1)
            self.assertEqual(result["missing_media"], 0)
        finally:
            for filename in (csv_file.name, archive_file.name):
                try:
                    os.unlink(filename)
                except OSError:
                    pass

    def test_guess_bulk_import_accepts_requested_media_formats(self):
        csv_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
        archive_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        media_rows = [
            ("PNG Clue", "PNG Answer", "clues/image.png", "image"),
            ("GIF Clue", "GIF Answer", "clues/animation.gif", "image"),
            ("MP3 Clue", "MP3 Answer", "audio/theme.mp3", "audio"),
            ("MP4 Clue", "MP4 Answer", "video/opening.mp4", "video"),
            ("WAV Clue", "WAV Answer", "audio/voice.wav", "audio"),
        ]
        try:
            csv_file.write("title,answer,media_filename,status\n")
            for title, answer, media_filename, _media_type in media_rows:
                csv_file.write(f"{title},{answer},{media_filename},active\n")
            csv_file.close()
            archive_file.close()
            with zipfile.ZipFile(archive_file.name, "w") as archive:
                for _title, _answer, media_filename, _media_type in media_rows:
                    archive.writestr(media_filename, b"non-empty imported media")

            with tempfile.TemporaryDirectory() as media_dir:
                config = {
                    "guilds": {"111": {"guild_name": "Alpha"}},
                    "limits": {"max_file_bytes": 1024 * 1024},
                }
                with mock.patch.object(self.dashboard, "MEDIA_DIR", Path(media_dir)):
                    with mock.patch.object(self.dashboard, "load_config", return_value=config):
                        result = self.dashboard.run_guess_library_bulk_import(
                            "111",
                            csv_file.name,
                            archive_file.name,
                            "multi-format.zip",
                            actor_name="test",
                        )

                    with self.dashboard.database() as connection:
                        stored_rows = connection.execute(
                            """
                            SELECT media_name, media_type, status
                            FROM guess_library_items
                            WHERE guild_id = ?
                            ORDER BY id ASC
                            """,
                            ("111",),
                        ).fetchall()

            self.assertEqual(result["imported"], len(media_rows))
            self.assertEqual(result["attached_media"], len(media_rows))
            self.assertEqual(result["missing_media"], 0)
            self.assertEqual(
                [(row["media_name"], row["media_type"], row["status"]) for row in stored_rows],
                [(Path(filename).name, media_type, "active") for _title, _answer, filename, media_type in media_rows],
            )
        finally:
            for filename in (csv_file.name, archive_file.name):
                try:
                    os.unlink(filename)
                except OSError:
                    pass
    def test_recent_imports_restarts_queued_guess_import_jobs(self):
        job_id = self.dashboard.create_background_job(
            "guess_library_bulk_import",
            guild_id="111",
            payload={"guild_id": "111"},
            actor_id="tester",
            actor_name="Tester",
        )

        with mock.patch.object(self.dashboard, "start_background_job") as starter:
            self.dashboard.recent_guess_library_import_jobs(limit=3, guild_id="111")

        starter.assert_called_with(job_id)
    def test_update_background_job_marks_queued_job_running(self):
        job_id = self.dashboard.create_background_job(
            "guess_library_bulk_import",
            guild_id="111",
            payload={"guild_id": "111"},
            actor_id="tester",
            actor_name="Tester",
        )

        self.dashboard.update_background_job(
            job_id,
            status="running",
            started_at="2026-07-18T18:30:00+00:00",
            error="",
        )

        with self.dashboard.database() as connection:
            job = connection.execute(
                "SELECT status, started_at, error FROM background_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        self.assertEqual(job["status"], "running")
        self.assertEqual(job["started_at"], "2026-07-18T18:30:00+00:00")
        self.assertEqual(job["error"], "")
    def test_sqlite_write_retry_handles_temporary_lock(self):
        attempts = {"count": 0}

        def flaky_write(connection):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise self.dashboard.sqlite3.OperationalError("database is locked")
            connection.execute(
                """
                INSERT INTO background_jobs (
                    job_type, guild_id, status, requested_by,
                    requested_by_name, payload_json, created_at
                )
                VALUES ('retry_test', '111', 'complete', '', '', '{}', '')
                """
            )

        self.dashboard.run_sqlite_write_with_retry(
            flaky_write,
            attempts=2,
            initial_delay=0,
        )

        with self.dashboard.database() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM background_jobs WHERE job_type = 'retry_test'"
            ).fetchone()[0]
        self.assertEqual(attempts["count"], 2)
        self.assertEqual(total, 1)

if __name__ == "__main__":
    unittest.main()
