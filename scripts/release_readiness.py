#!/usr/bin/env python3
"""Release-readiness checks for SDAC backend builds."""

from __future__ import annotations

import argparse
import ast
import py_compile
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"

CORE_PYTHON_FILES = [
    "bot.py",
    "config.py",
    "dashboard.py",
    "dashboard_account_templates.py",
    "dashboard_admin_roles.py",
    "dashboard_shell_assets.py",
    "dashboard_sidebar.py",
    "database_backend.py",
    "database_migrations.py",
    "observability.py",
    "scripts/archive_old_history.py",
    "scripts/export_sqlite_to_postgres.py",
    "scripts/migrate_database.py",
    "scripts/pre_release_smoke.py",
    "scripts/reset_admin_login.py",
    "scripts/sdac_doctor.py",
]

MIRRORED_FILES = [
    "bot.py",
    "config.py",
    "dashboard.py",
    "dashboard_account_templates.py",
    "dashboard_admin_roles.py",
    "dashboard_shell_assets.py",
    "dashboard_sidebar.py",
    "database_backend.py",
    "database_migrations.py",
    "observability.py",
    "scripts/archive_old_history.py",
    "scripts/backup_guild_offsite.sh",
    "scripts/backup_offsite.sh",
    "scripts/check_production.sh",
    "scripts/export_sqlite_to_postgres.py",
    "scripts/install_backup_prereqs.sh",
    "scripts/install_nginx_site.sh",
    "scripts/install_ubuntu.sh",
    "scripts/migrate_database.py",
    "scripts/pre_release_smoke.py",
    "scripts/release_checklist.sh",
    "scripts/reset_admin_login.py",
    "scripts/rollback_ubuntu.sh",
    "scripts/sdac_doctor.py",
    "scripts/standardize_env_file.sh",
    "scripts/support_bundle.sh",
    "scripts/sync_media_rclone.sh",
    "scripts/test_restore.sh",
    "scripts/update_from_github.sh",
    "scripts/update_from_github_windows.ps1",
    "scripts/update_ubuntu.sh",
]

PACKAGE_FILES = [
    ".github/workflows/release.yml",
    "scripts/install_ubuntu.sh",
    "scripts/release_checklist.sh",
    "scripts/update_ubuntu.sh",
    "server/scripts/install_ubuntu.sh",
    "server/scripts/release_checklist.sh",
    "server/scripts/update_ubuntu.sh",
    "tools/build_installers.ps1",
    "tools/release_experimental.ps1",
]

FOCUSED_TESTS = [
    "tests.test_anime_activities_seed",
    "tests.test_bot_startup",
    "tests.test_dashboard_access",
    "tests.test_dashboard_packaging",
    "tests.test_dashboard_page_sweep",
    "tests.test_dashboard_release_status",
    "tests.test_dashboard_sidebar_layout",
    "tests.test_dashboard_sidebar_routes",
    "tests.test_public_bot_invite",
]


class CheckRunner:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, label: str, detail: str = "") -> None:
        suffix = f" - {detail}" if detail else ""
        print(f"[OK] {label}{suffix}")

    def fail(self, label: str, detail: str) -> None:
        self.failures.append(f"{label}: {detail}")
        print(f"[FAIL] {label} - {detail}")

    def warn(self, label: str, detail: str) -> None:
        print(f"[WARN] {label} - {detail}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized_text(path: Path) -> str:
    return read_text(path).replace("\r\n", "\n")


def dashboard_helper_modules() -> set[str]:
    tree = ast.parse(read_text(ROOT / "dashboard.py"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("dashboard_"):
            modules.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("dashboard_"):
                    modules.add(alias.name)
    return modules


def check_compile(runner: CheckRunner) -> None:
    missing = [path for path in CORE_PYTHON_FILES if not (ROOT / path).is_file()]
    if missing:
        runner.fail("Core Python files", "missing " + ", ".join(missing))
        return
    for relative in CORE_PYTHON_FILES:
        try:
            py_compile.compile(str(ROOT / relative), doraise=True)
        except py_compile.PyCompileError as error:
            runner.fail("Python compile", f"{relative}: {error.msg}")
            return
    runner.ok("Python compile", f"{len(CORE_PYTHON_FILES)} core file(s)")


def check_server_mirror(runner: CheckRunner) -> None:
    mismatches = []
    for relative in MIRRORED_FILES:
        root_path = ROOT / relative
        server_path = SERVER / relative
        if not root_path.is_file():
            mismatches.append(f"missing root {relative}")
            continue
        if not server_path.is_file():
            mismatches.append(f"missing server/{relative}")
            continue
        if normalized_text(root_path) != normalized_text(server_path):
            mismatches.append(relative)
    if mismatches:
        runner.fail("Server mirror", ", ".join(mismatches[:12]))
    else:
        runner.ok("Server mirror", f"{len(MIRRORED_FILES)} file(s) match")


def check_dashboard_packaging(runner: CheckRunner) -> None:
    modules = dashboard_helper_modules()
    missing = []
    for module in sorted(modules):
        filename = f"{module}.py"
        if not (ROOT / filename).is_file():
            missing.append(filename)
        if not (SERVER / filename).is_file():
            missing.append(f"server/{filename}")
        for package_file in PACKAGE_FILES:
            package_path = ROOT / package_file
            if filename not in read_text(package_path):
                missing.append(f"{filename} not in {package_file}")
    if missing:
        runner.fail("Dashboard helper packaging", ", ".join(missing[:12]))
    else:
        runner.ok("Dashboard helper packaging", ", ".join(sorted(modules)))


def check_release_metadata(runner: CheckRunner) -> None:
    release_text = read_text(ROOT / "RELEASE.md")
    server_release_text = read_text(SERVER / "RELEASE.md")
    match = re.search(r"SDAC Bot Version\s+([0-9]+(?:\.[0-9]+){1,2})", release_text)
    if not match:
        runner.fail("Release notes", "top RELEASE.md entry does not expose a version")
        return
    version = match.group(1)
    if not server_release_text.startswith(release_text.split("\n---\n", 1)[0]):
        runner.fail("Release notes", "server/RELEASE.md top entry differs from RELEASE.md")
        return
    updater = read_text(ROOT / "scripts/update_from_github.sh")
    required_bits = ["SDAC_RELEASE_TAG", "SDAC_RELEASE", "Resolved version"]
    missing = [item for item in required_bits if item not in updater]
    if missing:
        runner.fail("Release metadata", "updater missing " + ", ".join(missing))
        return
    runner.ok("Release metadata", f"top version {version}")


def check_support_tools(runner: CheckRunner) -> None:
    required = [
        "scripts/check_production.sh",
        "scripts/release_checklist.sh",
        "scripts/sdac_doctor.py",
        "scripts/support_bundle.sh",
        "scripts/update_from_github.sh",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        runner.fail("Support tools", "missing " + ", ".join(missing))
        return
    support_bundle = read_text(ROOT / "scripts/support_bundle.sh")
    if "sdac-doctor" not in support_bundle and "sdac_doctor.py" not in support_bundle:
        runner.warn("Support bundle", "does not capture sdac-doctor output yet")
    runner.ok("Support tools", f"{len(required)} script(s) present")


def run_tests(runner: CheckRunner) -> None:
    command = [sys.executable, "-m", "unittest", *FOCUSED_TESTS]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    if result.returncode != 0:
        runner.fail("Focused tests", (result.stdout + result.stderr).strip()[-2000:])
        return
    runner.ok("Focused tests", f"{len(FOCUSED_TESTS)} suite(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SDAC backend release-readiness checks.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip focused unittest suites.")
    args = parser.parse_args()

    runner = CheckRunner()
    print(f"SDAC backend release readiness: {ROOT}")
    check_compile(runner)
    check_server_mirror(runner)
    check_dashboard_packaging(runner)
    check_release_metadata(runner)
    check_support_tools(runner)
    if not args.skip_tests:
        run_tests(runner)

    if runner.failures:
        print("\nRelease readiness failed:")
        for failure in runner.failures:
            print(f"- {failure}")
        return 1
    print("\nRelease readiness passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
