import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "sana-official-app"


class AppReadinessTests(unittest.TestCase):
    def test_sana_app_folder_and_identity_are_current(self):
        self.assertTrue(APP.is_dir())
        self.assertFalse((ROOT / "apps" / "sdac-official-app").exists())
        package = json.loads((APP / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "sana-chan")
        self.assertEqual(package["version"], "4.4.24")
        strings = (APP / "android" / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text(encoding="utf-8")
        self.assertIn("Sana-Chan", strings)
        self.assertIn("com.baytae.sanachan", strings)
        self.assertNotIn("SDAC App", strings)

    def test_app_version_is_consistent_across_build_files(self):
        main_ts = (APP / "src" / "main.ts").read_text(encoding="utf-8")
        build_gradle = (APP / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
        package = json.loads((APP / "package.json").read_text(encoding="utf-8"))
        self.assertIn('APP_SHELL_VERSION = "4.4.24"', main_ts)
        self.assertEqual(package["version"], "4.4.24")
        self.assertRegex(build_gradle, r'versionCode\s+44024')
        self.assertIn('versionName "4.4.24"', build_gradle)

    def test_app_defaults_to_live_sana_backend(self):
        main_ts = (APP / "src" / "main.ts").read_text(encoding="utf-8")
        env_example = (APP / ".env.example").read_text(encoding="utf-8")
        capacitor = (APP / "capacitor.config.ts").read_text(encoding="utf-8")
        self.assertIn("https://sanachan.bot.nu", main_ts)
        self.assertIn("VITE_SANA_DASHBOARD_URL=https://sanachan.bot.nu", env_example)
        self.assertNotIn("freethefishies.us.to", main_ts)
        self.assertNotIn("thelab.us.to", main_ts)
        self.assertNotIn("VITE_SDAC_DASHBOARD_URL", main_ts)
        self.assertNotIn("SDAC_APP_NAME", capacitor)
        self.assertNotIn("SDAC_APP_ID", capacitor)

    def test_app_release_files_are_staged_and_packaged(self):
        required = [
            "apps/sana-official-app/package.json",
            "apps/sana-official-app/package-lock.json",
            "apps/sana-official-app/capacitor.config.ts",
            "apps/sana-official-app/src/main.ts",
            "apps/sana-official-app/src/styles.css",
            "apps/sana-official-app/android/app/build.gradle",
        ]
        for script_name in ("tools/release_experimental.ps1", "tools/release_official.ps1"):
            script = (ROOT / script_name).read_text(encoding="utf-8")
            self.assertIn("git add -u apps/sdac-official-app", script)
            self.assertNotIn("git add -A apps/sana-official-app", script)
            for entry in required:
                self.assertIn(entry, script, f"{entry} missing from {script_name}")
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("apps/sana-official-app", workflow)
        self.assertNotIn("apps/sdac-official-app", workflow)

    def test_app_navigation_stays_in_shell_by_default(self):
        main_ts = (APP / "src" / "main.ts").read_text(encoding="utf-8")
        self.assertIn('data-app-action="frame-route"', main_ts)
        self.assertIn("function setFrameRoute", main_ts)
        self.assertIn('data-app-action="browser-route"', main_ts)
        self.assertNotIn('return `<a class="${escapeHtml(className)}" href=', main_ts)


if __name__ == "__main__":
    unittest.main()
