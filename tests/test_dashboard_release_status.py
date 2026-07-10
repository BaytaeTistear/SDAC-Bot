import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dashboard


class DashboardReleaseStatusTests(unittest.TestCase):
    def setUp(self):
        dashboard.RELEASE_CACHE.clear()

    def tearDown(self):
        dashboard.RELEASE_CACHE.clear()

    def test_release_status_exposes_banner_versions(self):
        with tempfile.TemporaryDirectory(prefix="sdac-release-status-") as workdir:
            release_file = Path(workdir) / "RELEASE.md"
            release_file.write_text(
                "# SDAC Bot Version 3.1.17 Experimental\n\n---\n\n# Older\n",
                encoding="utf-8",
            )
            fake_releases = {
                "latest-official": {"tag": "latest-official", "name": "Latest Official (3.1.0)", "version": "3.1.0", "published_at": ""},
                "latest-experimental": {"tag": "latest-experimental", "name": "Latest Experimental (3.1.18)", "version": "3.1.18", "published_at": ""},
            }
            with mock.patch.object(dashboard, "BASE_DIR", Path(workdir)):
                with mock.patch.object(dashboard, "fetch_github_release", side_effect=lambda tag: fake_releases[tag]):
                    with mock.patch.dict(os.environ, {"SDAC_RELEASE": ""}, clear=False):
                        status = dashboard.release_status()

        self.assertEqual(status["installed_version"], "3.1.17")
        self.assertEqual(status["official_version"], "3.1.0")
        self.assertEqual(status["experimental_version"], "3.1.18")
        banner = dashboard.release_banner_context()
        self.assertNotEqual(banner["official"], "unknown")
        self.assertNotEqual(banner["experimental"], "unknown")


if __name__ == "__main__":
    unittest.main()
