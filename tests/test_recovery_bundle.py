import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RecoveryBundleTests(unittest.TestCase):
    def test_export_contains_state_and_encrypts_with_passphrase(self):
        script = (ROOT / "scripts" / "create_recovery_bundle.sh").read_text(encoding="utf-8")

        for required in (
            "config.json",
            "sdac.db",
            "media",
            "secrets/sana.env",
            "source.backup(target)",
            "-aes-256-cbc",
            "-pbkdf2",
            "chmod 600",
        ):
            self.assertIn(required, script)
        self.assertIn("PostgreSQL", script)
        self.assertIn("special file", script)

    def test_restore_validates_archive_and_refuses_existing_data(self):
        script = (ROOT / "scripts" / "restore_recovery_bundle.sh").read_text(encoding="utf-8")

        for required in (
            "-aes-256-cbc",
            "-pbkdf2",
            "Unsafe archive path",
            "integrity_check",
            "DISCORD_TOKEN",
            "SANA_SECRET_KEY",
            "will not overwrite it",
            "install -m 600",
        ):
            self.assertIn(required, script)

    def test_one_line_installer_accepts_a_recovery_bundle(self):
        builder = (ROOT / "tools" / "build_installers.ps1").read_text(encoding="utf-8")

        self.assertIn('"scripts\\create_recovery_bundle.sh"', builder)
        self.assertIn('"scripts\\restore_recovery_bundle.sh"', builder)
        self.assertIn("SANA_RECOVERY_BUNDLE", builder)
        self.assertIn("restore_recovery_bundle.sh", builder)


if __name__ == "__main__":
    unittest.main()
