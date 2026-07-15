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
client = dashboard.app.test_client()
with client.session_transaction() as session:
    session["sdac_account_username"] = "baytae"
    session["sdac_account_role"] = "bot_owner"
    session["sdac_admin"] = True
    session["sdac_admin_username"] = "baytae"
    session["sdac_admin_role"] = "bot_owner"
    session["sdac_admin_auth"] = "test"
    session["sdac_admin_guild_ids"] = []

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
        if '<details class="sdac-sidebar-section"' in body:
            failures.append(f"{route}: still uses collapsible sidebar sections")
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





