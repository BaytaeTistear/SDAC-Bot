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

    def test_docker_support_files_are_packaged(self):
        docker_files = [
            ".dockerignore",
            ".env.example",
            "Dockerfile",
            "docker-compose.yml",
            "DOCKER.md",
        ]
        package_files = [
            ROOT / "tools" / "build_installers.ps1",
            ROOT / "tools" / "release_experimental.ps1",
            ROOT / "tools" / "release_official.ps1",
        ]
        for filename in docker_files:
            self.assertTrue((ROOT / filename).is_file(), filename)
            for package_file in package_files:
                self.assertIn(filename, package_file.read_text(encoding="utf-8"), f"{filename} missing from {package_file.relative_to(ROOT)}")


    def test_release_scripts_stage_updater_sources(self):
        for filename in ("tools/release_experimental.ps1", "tools/release_official.ps1"):
            script = (ROOT / filename).read_text(encoding="utf-8")
            for staged in (
                "scripts/update_from_github.sh",
                "scripts/update_from_github_windows.ps1",
                "server/scripts/update_from_github.sh",
                "server/scripts/update_from_github_windows.ps1",
            ):
                self.assertIn(staged, script, f"{staged} missing from {filename}")

    def test_update_script_supports_docker_git_checkouts(self):
        for filename in ("scripts/update_from_github.sh", "server/scripts/update_from_github.sh"):
            script = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("DETECTED_APP_DIR", script, filename)
            self.assertIn('SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")"', script, filename)
            self.assertIn("run_git_docker_update", script, filename)
            self.assertIn("docker compose up -d --build dashboard bot", script, filename)
            self.assertIn("Use 'docker compose', not old 'docker-compose'", script, filename)
    def test_docker_compose_uses_portable_environment_syntax(self):
        compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("required: false", compose_text)
        self.assertNotIn("path: .env", compose_text)
        self.assertNotIn("env_file:", compose_text)
        self.assertIn("DISCORD_TOKEN: ${DISCORD_TOKEN:-}", compose_text)
        self.assertIn("SDAC_SECRET_KEY: ${SDAC_SECRET_KEY:-}", compose_text)

if __name__ == "__main__":
    unittest.main()
