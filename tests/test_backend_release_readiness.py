import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BackendReleaseReadinessTests(unittest.TestCase):
    def test_release_readiness_skip_tests_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/release_readiness.py", "--skip-tests"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        self.assertIn("Release readiness passed.", result.stdout)

    def test_release_readiness_is_packaged(self):
        filename = "scripts/release_readiness.py"
        package_files = [
            ROOT / "tools" / "build_installers.ps1",
            ROOT / "tools" / "release_experimental.ps1",
            ROOT / ".github" / "workflows" / "release.yml",
        ]
        self.assertTrue((ROOT / filename).is_file())
        self.assertTrue((ROOT / "server" / filename).is_file())
        for path in package_files:
            self.assertIn("release_readiness.py", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
