import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_FILE = ROOT / "dashboard.py"
PACKAGE_FILES = [
    ROOT / ".github" / "workflows" / "release.yml",
    ROOT / "scripts" / "install_ubuntu.sh",
    ROOT / "scripts" / "release_checklist.sh",
    ROOT / "scripts" / "update_ubuntu.sh",
    ROOT / "server" / "scripts" / "install_ubuntu.sh",
    ROOT / "server" / "scripts" / "release_checklist.sh",
    ROOT / "server" / "scripts" / "update_ubuntu.sh",
    ROOT / "tools" / "build_installers.ps1",
    ROOT / "tools" / "release_experimental.ps1",
]


class DashboardPackagingTests(unittest.TestCase):
    def dashboard_helper_modules(self):
        tree = ast.parse(DASHBOARD_FILE.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("dashboard_"):
                    modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("dashboard_"):
                        modules.add(alias.name)
        return modules

    def test_dashboard_helper_modules_are_packaged(self):
        modules = self.dashboard_helper_modules()
        self.assertGreaterEqual(modules, {
            "dashboard_account_templates",
            "dashboard_admin_roles",
            "dashboard_shell_assets",
            "dashboard_sidebar",
        })
        for module in sorted(modules):
            filename = f"{module}.py"
            self.assertTrue((ROOT / filename).is_file(), filename)
            self.assertTrue((ROOT / "server" / filename).is_file(), f"server/{filename}")
            for package_file in PACKAGE_FILES:
                text = package_file.read_text(encoding="utf-8")
                self.assertIn(filename, text, f"{filename} missing from {package_file.relative_to(ROOT)}")


if __name__ == "__main__":
    unittest.main()
