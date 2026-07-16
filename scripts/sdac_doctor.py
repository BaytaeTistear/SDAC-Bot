import json
import os
import importlib.util
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


BASE_DIR = Path(os.getenv("SDAC_BASE_DIR", Path(__file__).resolve().parents[1]))
CONFIG_FILE = Path(os.getenv("SDAC_CONFIG_FILE", BASE_DIR / "config.json"))
DB_FILE = Path(os.getenv("SDAC_DB_FILE", BASE_DIR / "sdac.db"))
DASHBOARD_BIND = os.getenv("SDAC_DASHBOARD_BIND", "127.0.0.1:5000")
DASHBOARD_HELPER_FILES = [
    "dashboard_account_templates.py",
    "dashboard_admin_roles.py",
    "dashboard_shell_assets.py",
    "dashboard_sidebar.py",
]


def status(label, ok, detail):
    marker = "OK" if ok else "WARN"
    print(f"[{marker}] {label}: {detail}")


def run(command, timeout=8):
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return error


def check_python():
    status("Python", sys.version_info >= (3, 10), sys.version.split()[0])


def check_config():
    if not CONFIG_FILE.exists():
        status("Config", False, f"missing {CONFIG_FILE}")
        return
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        status("Config", False, str(error))
        return
    guilds = data.get("guilds") or {}
    status("Config", True, f"{len(guilds)} configured server(s)")


def check_database():
    if not DB_FILE.exists():
        status("Database", False, f"missing {DB_FILE}")
        return
    try:
        with sqlite3.connect(DB_FILE) as connection:
            version = connection.execute("""
                SELECT version FROM schema_version WHERE id = 1
            """).fetchone()
            tables = connection.execute("""
                SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'
            """).fetchone()[0]
    except sqlite3.Error as error:
        status("Database", False, str(error))
        return
    status("Database", True, f"{tables} table(s), schema version {version[0] if version else 0}")


def check_environment():
    status("Discord token", bool(os.getenv("DISCORD_TOKEN")), "DISCORD_TOKEN set" if os.getenv("DISCORD_TOKEN") else "DISCORD_TOKEN missing")
    oauth_ready = bool(os.getenv("SDAC_DISCORD_CLIENT_ID") and os.getenv("SDAC_DISCORD_CLIENT_SECRET"))
    status("Discord OAuth", oauth_ready, "client id/secret set" if oauth_ready else "client id/secret missing")


def check_disk():
    usage = shutil.disk_usage(BASE_DIR)
    free_gb = usage.free / (1024 ** 3)
    status("Disk", free_gb > 2, f"{free_gb:.1f} GB free at {BASE_DIR}")


def check_update_command():
    update_path = (
        shutil.which("sana-update")
        or shutil.which("sanachan-update")
        or str(BASE_DIR / "scripts" / "update_from_github.sh")
    )
    status("Updater", Path(update_path).exists(), update_path)


def check_dashboard_files():
    missing = [name for name in DASHBOARD_HELPER_FILES if not (BASE_DIR / name).is_file()]
    if missing:
        status("Dashboard files", False, "missing " + ", ".join(missing))
        return
    status("Dashboard files", True, f"{len(DASHBOARD_HELPER_FILES)} helper file(s) present")


def check_dashboard_import():
    dashboard_path = BASE_DIR / "dashboard.py"
    if not dashboard_path.is_file():
        status("Dashboard import", False, f"missing {dashboard_path}")
        return
    try:
        spec = importlib.util.spec_from_file_location("sdac_doctor_dashboard", dashboard_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except ModuleNotFoundError as error:
        status("Dashboard import", False, f"missing Python module: {error.name}")
    except Exception as error:
        detail = str(error).splitlines()[0] if str(error) else error.__class__.__name__
        status("Dashboard import", False, detail)
    else:
        status("Dashboard import", True, "dashboard.py imports successfully")


def check_dashboard_health():
    url = f"http://{DASHBOARD_BIND}/health"
    try:
        with urlopen(url, timeout=5) as response:
            body = response.read(300).decode("utf-8", errors="replace").strip()
            ok = 200 <= response.status < 300
            detail = f"{response.status} {body}" if body else str(response.status)
    except HTTPError as error:
        status("Dashboard health", False, f"{url} returned {error.code}")
        return
    except (OSError, URLError) as error:
        status("Dashboard health", False, f"{url} unavailable: {error}")
        return
    status("Dashboard health", ok, detail)


def check_dashboard_service():
    result = run(["systemctl", "is-active", "sdac-dashboard"], timeout=4)
    if isinstance(result, Exception):
        status("Dashboard service", False, str(result))
        return
    detail = (result.stdout or result.stderr or "").strip() or f"exit {result.returncode}"
    status("Dashboard service", result.returncode == 0, detail)
    logs = run(["journalctl", "-u", "sdac-dashboard", "-n", "20", "--no-pager"], timeout=8)
    if not isinstance(logs, Exception) and logs.stdout:
        print("\nLast sdac-dashboard logs:")
        print(logs.stdout.strip())


def check_service():
    result = run(["systemctl", "is-active", "sdac-bot"], timeout=4)
    if isinstance(result, Exception):
        status("Service", False, str(result))
        return
    detail = (result.stdout or result.stderr or "").strip() or f"exit {result.returncode}"
    status("Service", result.returncode == 0, detail)
    logs = run(["journalctl", "-u", "sdac-bot", "-n", "20", "--no-pager"], timeout=8)
    if not isinstance(logs, Exception) and logs.stdout:
        print("\nLast sdac-bot logs:")
        print(logs.stdout.strip())


def main():
    print(f"SDAC Doctor for {BASE_DIR}")
    check_python()
    check_config()
    check_database()
    check_environment()
    check_disk()
    check_update_command()
    check_dashboard_files()
    check_dashboard_import()
    check_dashboard_service()
    check_dashboard_health()
    check_service()


if __name__ == "__main__":
    main()
