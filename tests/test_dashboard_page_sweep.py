import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PAGE_SWEEP_CODE = r'''
import dashboard

routes = [
    "/admin",
    "/admin/moderator",
    "/admin/server-owner",
    "/admin/bot-owner",
    "/admin/setup-checklist",
    "/admin/categories",
    "/admin/permission-health",
    "/admin/global-control",
    "/admin/config-history",
    "/admin/maintenance-mode",
    "/admin/moderation",
    "/admin/removal-reasons",
    "/admin/community-submissions",
    "/admin/onboarding",
    "/admin/theme",
    "/admin/layout",
    "/admin/server-switcher",
    "/admin/owner-portal",
    "/admin/server-health",
    "/admin/seasons",
    "/admin/overview",
    "/admin/audit",
    "/admin/health",
    "/admin/anime-activities",
    "/admin/game-library/example.csv",
    "/admin/game-library",
    "/admin/users",
    "/admin/settings",
    "/admin/optimization",
    "/admin/maintenance",
    "/admin/media",
    "/admin/jobs",
    "/admin/install-doctor",
    "/admin/approvals",
    "/admin/privacy",
    "/admin/analytics",
    "/admin/monthly-report",
    "/admin/polls",
    "/admin/releases",
    "/admin/release-checklist, "
    "/admin/go-live-checklist",
    "/admin/production-health",
    "/",
    "/my-submissions",
    "/events",
    "/meetups",
    "/servers",
    "/stats",
    "/guessing",
    "/achievements",
    "/about",
    "/invite",
    "/privacy",
    "/terms",
    "/setup-guide",
]
api_routes = {"/admin/health", "/admin/game-library/example.csv"}
redirect_ok = {"/admin/server-switcher"}
failures = []


assert "community_event_submitted" in dashboard.NOTIFICATION_EVENT_LABELS
assert "community_meetup_submitted" in dashboard.NOTIFICATION_EVENT_LABELS
assert "community_event_approved" in dashboard.NOTIFICATION_EVENT_LABELS
assert "community_meetup_approved" in dashboard.NOTIFICATION_EVENT_LABELS
message = dashboard.community_discord_notification_message(
    {
        "post_type": "event",
        "title": "Launch Watch Party",
        "description": "A community event for release night.",
        "location": "Discord stage",
        "starts_at": "2026-08-15T19:00:00+00:00",
        "host_name": "Sana Team",
        "tags": "Watch Party",
    },
    "https://sanachan.bot.nu/events",
)
assert "New Event: Launch Watch Party" in message
assert "Where: Discord stage" in message
assert "Host: Sana Team" in message
assert "https://sanachan.bot.nu/events" in message
assert message.endswith("||@here||")
with dashboard.app.test_request_context("/events"):
    submitted_message = dashboard.community_submission_notification_message({
        "post_type": "event",
        "title": "Launch Watch Party",
        "starts_at": "2026-08-15T19:00:00+00:00",
        "location": "Discord stage",
    })
assert "needs review" in submitted_message
assert "Submitter:" not in submitted_message
assert "Review:" in submitted_message
poll_payload = dashboard.community_rsvp_poll_payload(
    "Community announcement",
    {"title": "Launch Watch Party"},
)
assert poll_payload["poll"]["question"]["text"] == "RSVP for Launch Watch Party"
assert [answer["poll_media"]["text"] for answer in poll_payload["poll"]["answers"]] == ["Going", "Not going"]
assert dashboard.smtp_email_status()["configured"] is False
assert "SANA_SMTP_HOST" in dashboard.smtp_email_status()["missing"]
with dashboard.app.test_request_context("/admin/community-submissions"):
    dm_payload = dashboard.community_admin_dm_payload({
        "id": 55,
        "post_type": "event",
        "title": "Launch Watch Party",
        "starts_at": "2026-08-15T19:00:00+00:00",
        "location": "Discord stage",
        "guild_id": "111",
    })
assert dm_payload["embeds"][0]["title"] == "New Event needs review"
assert dm_payload["components"][0]["components"][0]["label"] == "Open review page"
assert "/admin/community-submissions" in dm_payload["components"][0]["components"][0]["url"]

client = dashboard.app.test_client()
with client.session_transaction() as session:
    session["sdac_account_username"] = "baytae"
    session["sdac_account_role"] = "bot_owner"
    session["sdac_admin"] = True
    session["sdac_admin_username"] = "baytae"
    session["sdac_admin_role"] = "bot_owner"
    session["sdac_admin_auth"] = "test"
    session["sdac_admin_guild_ids"] = []



community_now = dashboard.utc_now_iso()
dashboard.ensure_community_posts_table()
with dashboard.database() as connection:
    connection.execute(
        """
        INSERT INTO community_posts (
            post_type, category, status, title, description, guild_id, created_at, updated_at
        ) VALUES
            ('event', 'Events', 'approved', 'Alpha Only Event', 'Shown only on server 111.', '111', ?, ?),
            ('event', 'Events', 'approved', 'Beta Only Event', 'Shown only on server 222.', '222', ?, ?)
        """,
        (community_now, community_now, community_now, community_now),
    )
    alpha_post_id = connection.execute(
        "SELECT id FROM community_posts WHERE title = 'Alpha Only Event' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    connection.execute(
        """
        INSERT INTO community_post_rsvps (
            post_id, guild_id, user_id, username, status, source_message_id, created_at, updated_at
        ) VALUES (?, '111', '42', 'AttendeeOne', 'going', '999', ?, ?)
        """,
        (alpha_post_id, community_now, community_now),
    )
    connection.execute(
        """
        INSERT INTO community_post_announcements (
            post_id, guild_id, channel_id, message_id, poll_question,
            going_answer_id, not_going_answer_id, created_at
        ) VALUES (?, '111', '222', '333', 'RSVP for Alpha Only Event', '1', '2', ?)
        """,
        (alpha_post_id, community_now),
    )
    connection.execute(
        """
        INSERT INTO dashboard_admin_users (
            username, email, display_name, discord_user_id, password_hash, role,
            disabled, created_at, updated_at, guild_ids_json
        ) VALUES ('linked-mod', 'linked@example.com', 'Linked Mod', '444444444444444444', 'x', 'user', 0, ?, ?, '[]')
        """,
        (community_now, community_now),
    )
    dashboard.upsert_user_server_access(
        connection,
        'linked-mod',
        ['111'],
        role='moderator',
        source='test',
        preserve_existing_roles=False,
    )
all_events = client.get("/events")
alpha_events = client.get(f"/events?guild_id=111")
beta_events = client.get(f"/events?guild_id=222")
assert all_events.status_code == 200
assert alpha_events.status_code == 200
assert beta_events.status_code == 200
all_body = all_events.get_data(as_text=True)
alpha_body = alpha_events.get_data(as_text=True)
beta_body = beta_events.get_data(as_text=True)
for expected, label in [
    ("Alpha Only Event", "all events missing alpha"),
    ("Beta Only Event", "all events missing beta"),
    ("1 attending", "rsvp count missing"),
    ("View attendee names", "attendee names disclosure missing"),
    ("AttendeeOne", "attendee name missing"),
    ("RSVP in Discord", "rsvp discord button missing"),
    ("https://discord.com/channels/111/222/333", "discord rsvp URL missing"),
]:
    if expected not in all_body:
        print(label)
        print(all_body[:1200])
        raise SystemExit(1)
targets = dashboard.community_admin_notice_targets("111")
if not any(target["email"] == "linked@example.com" for target in targets):
    print("linked email target missing", targets)
    raise SystemExit(1)
if not any(target["discord_user_id"] == "444444444444444444" for target in targets):
    print("linked discord target missing", targets)
    raise SystemExit(1)
approval_body = client.get(f"/admin/community-submissions?key={dashboard.ADMIN_KEY}&status=all")
assert approval_body.status_code == 200
assert "Resend Email" in approval_body.get_data(as_text=True)
assert "Email Delivery" in client.get(f"/admin/settings?key={dashboard.ADMIN_KEY}").get_data(as_text=True)
assert ".meta-item + .meta-item::before" in all_body
assert 'class="meta-item"' in all_body
assert 'class="pill">{{ post.category }}' not in all_body
assert "Alpha Only Event" in alpha_body
assert "1 attending" in alpha_body
assert "Beta Only Event" not in alpha_body
assert "Beta Only Event" in beta_body
assert "Alpha Only Event" not in beta_body
assert 'select[data-placeholder="true"], input[type="datetime-local"][data-placeholder="true"]' in alpha_body
assert "document.querySelectorAll(\"select, input[type='datetime-local']\")" in alpha_body
assert 'data-placeholder="{{' not in alpha_body

for route in routes:
    response = client.get(f"{route}?key={dashboard.ADMIN_KEY}")
    if response.status_code >= 500:
        failures.append(f"{route}: server error {response.status_code}")
        continue
    if response.status_code in {301, 302, 303, 307, 308}:
        if route not in redirect_ok:
            failures.append(f"{route}: unexpected redirect {response.status_code}")
        continue
    if response.status_code == 200 and route not in api_routes:
        body = response.get_data(as_text=True)
        if "sdac-sidebar" not in body or "sdac-sidebar-style" not in body:
            failures.append(f"{route}: missing shared sidebar")
        if "sdac-sidebar-home" not in body or ">Home</a>" not in body:
            failures.append(f"{route}: missing top Home button")
        if "sdac-sidebar-controls" not in body:
            failures.append(f"{route}: missing shared Menu/Home controls")
        if "sdac-sidebar-scroll" not in body or "sdac-sidebar-nav" not in body:
            failures.append(f"{route}: missing unified sidebar scroll area")
        if "sdac-sidebar-main-section" not in body or "sdac-sidebar-section-title" not in body:
            failures.append(f"{route}: missing role navigation sections")
        if '<details class="sdac-sidebar-section sdac-sidebar-main-section' not in body or '<summary class="sdac-sidebar-section-title">' not in body:
            failures.append(f"{route}: missing collapsible role navigation sections")
        if "--sdac-content-width" not in body or "--sdac-sidebar-width" not in body or "--sdac-layout-gap" not in body:
            failures.append(f"{route}: missing saved layout variables")
        if "body.sdac-has-sidebar {" not in body or "overflow-x: hidden !important" not in body or ".sdac-sidebar * { box-sizing: border-box; max-width: 100%; min-width: 0; }" not in body:
            failures.append(f"{route}: missing horizontal overflow layout guard")
        if ".sdac-sidebar .sdac-server-switcher select, .sdac-sidebar .sdac-server-switcher button" not in body or "grid-template-columns: minmax(0, 1fr)" not in body:
            failures.append(f"{route}: missing hardened server selector css")
if failures:
    print("FAILURES:", failures)
    raise SystemExit(1)
print("FAILURES: []")
'''


class DashboardPageSweepTests(unittest.TestCase):
    def test_admin_and_public_pages_render_with_expected_sidebar(self):
        with tempfile.TemporaryDirectory(prefix="sdac-page-sweep-") as workdir:
            root = Path(workdir)
            (root / "media").mkdir(parents=True, exist_ok=True)
            (root / "backups").mkdir(parents=True, exist_ok=True)
            (root / "config.json").write_text(
                json.dumps(
                    {
                        "guilds": {
                            "111": {
                                "guild_name": "Sweep Test Server",
                                "features": {
                                    "public_gallery": True,
                                    "cross_server_gallery": True,
                                },
                                "categories": {
                                    "screenshots": "1234567890",
                                },
                            },
                            "222": {
                                "guild_name": "Second Sweep Server",
                                "features": {
                                    "public_gallery": True,
                                    "cross_server_gallery": True,
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "SDAC_DB_FILE": str(root / "sdac-page-sweep.db"),
                    "SDAC_CONFIG_FILE": str(root / "config.json"),
                    "SDAC_MEDIA_DIR": str(root / "media"),
                    "SDAC_BACKUP_DIR": str(root / "backups"),
                    "SDAC_BOT_STATUS_FILE": str(root / "bot_status.json"),
                }
            )
            result = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(PAGE_SWEEP_CODE)],
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
        if result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        self.assertIn("FAILURES: []", result.stdout)


if __name__ == "__main__":
    unittest.main()





