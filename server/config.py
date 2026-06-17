import os
from pathlib import Path


def load_env_file():
    env_paths = [
        Path(__file__).resolve().with_name(".env"),
        Path("/etc/sdac-bot/sdac.env"),
    ]
    env_lines = None
    for env_path in env_paths:
        if not env_path.exists():
            continue
        try:
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        break
    if env_lines is None:
        return

    for raw_line in env_lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


load_env_file()

TOKEN = os.getenv("DISCORD_TOKEN", "")
