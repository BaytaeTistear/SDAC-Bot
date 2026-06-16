import math
import os
import json
import sqlite3
import secrets
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)

from config import TOKEN


app = Flask(__name__)

ADMIN_KEY = os.getenv("SDAC_ADMIN_KEY", "ImTheBestAdmin")
ADMIN_PASSWORD = os.getenv("SDAC_ADMIN_PASSWORD", ADMIN_KEY)
app.secret_key = os.getenv("SDAC_SECRET_KEY", secrets.token_hex(32))
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "sdac.db"
CONFIG_FILE = BASE_DIR / "config.json"
MEDIA_DIR = (BASE_DIR / "media").resolve()
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_KEEP_COUNT = 30
PAGE_SIZE = 20


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Dashboard</title>
    <style>
        :root {
            color-scheme: dark;
            --bg: #101114;
            --panel: #1b1d22;
            --border: #30333b;
            --muted: #a8adb8;
            --accent: #7c9cff;
            --danger: #e45d68;
            --success: #63c174;
        }

        * { box-sizing: border-box; }
        body {
            background: var(--bg);
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }

        main {
            margin: 0 auto;
            width: min(100%, 1000px);
        }

        h1, h2 { text-align: center; }
        h1 { margin-bottom: 8px; }
        a { color: var(--accent); }

        .mode, .empty {
            color: var(--muted);
            text-align: center;
        }

        .mode { margin: 0 0 24px; }
        .mode strong { color: var(--accent); }

        .admin-nav {
            display: flex;
            gap: 14px;
            justify-content: center;
            margin-bottom: 20px;
        }

        .filter {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }

        .filter form {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }

        select, button {
            border: 1px solid var(--border);
            border-radius: 7px;
            font-size: 16px;
            padding: 10px 12px;
        }

        button {
            background: var(--accent);
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
        }

        .section { margin-bottom: 40px; }
        .post, .audit-row {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin: 14px 0;
            padding: 16px;
        }

        .post-header {
            align-items: center;
            display: flex;
            gap: 12px;
            justify-content: space-between;
        }

        .meta {
            color: var(--muted);
            font-size: 14px;
        }

        .stars {
            color: #ffd75e;
            font-weight: bold;
        }

        .status {
            border: 1px solid var(--border);
            border-radius: 999px;
            display: inline-block;
            margin-left: 6px;
            padding: 2px 7px;
        }

        .status-posted { color: var(--success); }
        .status-pending { color: #ffd75e; }

        .message {
            margin-top: 12px;
            overflow-wrap: anywhere;
            white-space: pre-wrap;
        }

        .media-grid {
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            margin-top: 14px;
        }

        .media-grid img, .media-grid video {
            background: #090a0c;
            border-radius: 8px;
            display: block;
            max-height: 600px;
            object-fit: contain;
            width: 100%;
        }

        .media-grid audio { width: 100%; }
        .download { overflow-wrap: anywhere; }

        .delete-button {
            background: var(--danger);
            border-color: var(--danger);
            color: white;
            font-size: 13px;
            padding: 7px 10px;
        }

        .notice {
            border: 1px solid var(--border);
            border-radius: 8px;
            margin: 0 auto 20px;
            padding: 12px;
            text-align: center;
        }

        .notice.error { border-color: var(--danger); }
        .empty { margin-top: 40px; }

        .pagination {
            align-items: center;
            display: flex;
            gap: 18px;
            justify-content: center;
            margin: 30px 0;
        }

        .pagination .disabled {
            color: var(--muted);
        }
    </style>
</head>
<body>
<main>
    <h1>SDAC Dashboard</h1>
    <p class="mode">
        {% if is_admin %}
            <strong>Admin mode</strong>
        {% else %}
            Public gallery
        {% endif %}
    </p>

    <nav class="admin-nav">
        <a href="{{ url_for('index', key=admin_key if is_admin else None) }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
        {% if is_admin %}
            <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
            <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
            <a href="{{ url_for('admin_logout') }}">Log out</a>
        {% endif %}
    </nav>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    <div class="filter">
        <form method="get" action="{{ url_for('index') }}">
            {% if is_admin %}
                <input type="hidden" name="key" value="{{ admin_key }}">
            {% endif %}
            <select name="category" aria-label="Category">
                <option value="">All Categories</option>
                {% for cat in categories %}
                    <option value="{{ cat }}" {% if selected_category == cat %}selected{% endif %}>
                        {{ cat }}
                    </option>
                {% endfor %}
            </select>
            <select name="sort" aria-label="Sort">
                <option value="newest" {% if selected_sort == "newest" %}selected{% endif %}>Newest</option>
                <option value="votes" {% if selected_sort == "votes" %}selected{% endif %}>Most Votes</option>
            </select>
            <select name="month" aria-label="Month">
                <option value="">All Months</option>
                {% for month in months %}
                    <option value="{{ month }}" {% if selected_month == month %}selected{% endif %}>
                        {{ month }}
                    </option>
                {% endfor %}
            </select>
            {% if is_admin %}
                <select name="status" aria-label="Status">
                    <option value="">All Statuses</option>
                    {% for status in ("posted", "pending") %}
                        <option value="{{ status }}" {% if selected_status == status %}selected{% endif %}>
                            {{ status }}
                        </option>
                    {% endfor %}
                </select>
            {% endif %}
            <button type="submit">Filter</button>
        </form>
    </div>

    {% if grouped_posts %}
        {% if selected_month %}
            <p class="mode">Showing preserved top 10 snapshots for {{ selected_month }}.</p>
        {% endif %}
        {% for category, category_posts in grouped_posts.items() %}
            <section class="section">
                <h2>{{ category }}</h2>
                {% for post in category_posts %}
                    <article class="post">
                        <div class="post-header">
                            <div class="meta">
                                ID {{ post.id }}
                                &middot; {{ post.username }}
                                &middot; {{ post.category }}
                                &middot; <span class="stars">{{ post.stars or 0 }} votes</span>
                                {% if is_admin %}
                                    <span class="status status-{{ post.status }}">{{ post.status }}</span>
                                {% endif %}
                            </div>
                            {% if is_admin %}
                                <form method="post"
                                      action="{{ url_for(
                                          'delete_submission',
                                          submission_id=post.id,
                                          key=admin_key,
                                          category=selected_category,
                                          status=selected_status,
                                          page=page
                                      ) }}"
                                      onsubmit="return confirm('Remove this submission from the website and Discord?');">
                                    <button class="delete-button" type="submit">Remove</button>
                                </form>
                            {% endif %}
                        </div>

                        {% if post.message_text %}
                            <div class="message">{{ post.message_text }}</div>
                        {% endif %}

                        {% if post.media %}
                            <div class="media-grid">
                                {% for item in post.media %}
                                    <div>
                                        {% if item.type == "image" %}
                                            <a href="{{ item.url }}" target="_blank" rel="noopener">
                                                <img src="{{ item.url }}" alt="{{ item.name }}" loading="lazy">
                                            </a>
                                        {% elif item.type == "video" %}
                                            <video src="{{ item.url }}" controls preload="metadata"></video>
                                        {% elif item.type == "audio" %}
                                            <audio src="{{ item.url }}" controls preload="metadata"></audio>
                                        {% else %}
                                            <a class="download" href="{{ item.url }}" download>{{ item.name }}</a>
                                        {% endif %}
                                    </div>
                                {% endfor %}
                            </div>
                        {% endif %}
                    </article>
                {% endfor %}
            </section>
        {% endfor %}
    {% else %}
        <div class="empty">No matching SDAC submissions.</div>
    {% endif %}

    <nav class="pagination">
        {% if page > 1 %}
            <a href="{{ page_url(page - 1) }}">Previous</a>
        {% else %}
            <span class="disabled">Previous</span>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
            <a href="{{ page_url(page + 1) }}">Next</a>
        {% else %}
            <span class="disabled">Next</span>
        {% endif %}
    </nav>
</main>
</body>
</html>
"""


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Admin Login</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 10vh auto 0;
            max-width: 420px;
            padding: 24px;
        }
        h1 { margin-top: 0; text-align: center; }
        label { display: block; margin-bottom: 8px; }
        input, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 16px;
            padding: 10px 12px;
            width: 100%;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
            margin-top: 14px;
        }
        .error {
            border: 1px solid #e45d68;
            border-radius: 8px;
            margin-bottom: 16px;
            padding: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
<main>
    <h1>Admin Login</h1>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    <form method="post">
        <input type="hidden" name="key" value="{{ admin_key }}">
        <input type="hidden" name="next" value="{{ next_url }}">
        <label for="password">Admin password</label>
        <input id="password" name="password" type="password" required autofocus>
        <button type="submit">Log In</button>
    </form>
</main>
</body>
</html>
"""


AUDIT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Audit Log</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1 { text-align: center; }
        a { color: #7c9cff; }
        nav { margin-bottom: 24px; text-align: center; }
        .audit-row {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 10px;
            margin: 12px 0;
            padding: 14px;
        }
        .meta { color: #a8adb8; font-size: 14px; }
        .pagination {
            display: flex;
            gap: 18px;
            justify-content: center;
            margin-top: 30px;
        }
        .disabled { color: #777; }
    </style>
</head>
<body>
<main>
    <h1>SDAC Audit Log</h1>
    <nav><a href="{{ url_for('index', key=admin_key) }}">Back to submissions</a></nav>
    <nav><a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a></nav>
    <nav><a href="{{ url_for('admin_logout') }}">Log out</a></nav>
    {% for row in rows %}
        <article class="audit-row">
            <strong>{{ row.action }}</strong>
            {% if row.target_type or row.target_id %}
                {{ row.target_type or "target" }} {{ row.target_id or "unknown" }}
            {% endif %}
            <div class="meta">
                {{ row.actor_username or "unknown" }}
                &middot; {{ row.created_at }}
                {% if row.guild_id %}&middot; guild {{ row.guild_id }}{% endif %}
            </div>
            {% if row.details %}<div>{{ row.details }}</div>{% endif %}
        </article>
    {% else %}
        <p>No audit events recorded.</p>
    {% endfor %}
    <nav class="pagination">
        {% if page > 1 %}
            <a href="{{ url_for('audit_log', key=admin_key, page=page - 1) }}">Previous</a>
        {% else %}
            <span class="disabled">Previous</span>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
            <a href="{{ url_for('audit_log', key=admin_key, page=page + 1) }}">Next</a>
        {% else %}
            <span class="disabled">Next</span>
        {% endif %}
    </nav>
</main>
</body>
</html>
"""


GUESSING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Guessing Leaderboard</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav {
            display: flex;
            gap: 14px;
            justify-content: center;
            margin-bottom: 24px;
        }
        .channel {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 16px 0;
            padding: 16px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            border-bottom: 1px solid #30333b;
            padding: 10px;
            text-align: left;
        }
        .empty {
            color: #a8adb8;
            text-align: center;
        }
    </style>
</head>
<body>
<main>
    <h1>Guessing Leaderboard</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key if is_admin else None) }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
        {% if is_admin %}
            <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
            <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
            <a href="{{ url_for('admin_logout') }}">Log out</a>
        {% endif %}
    </nav>
    <h2>{{ month }}</h2>
    {% if grouped_scores %}
        {% for channel_id, rows in grouped_scores.items() %}
            <section class="channel">
                <h2>Channel {{ channel_id }}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>User</th>
                            <th>Points</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in rows %}
                            <tr>
                                <td>{{ loop.index }}</td>
                                <td>{{ row.username }}</td>
                                <td>{{ row.points }}</td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </section>
        {% endfor %}
    {% else %}
        <p class="empty">No guessing points for this month yet.</p>
    {% endif %}
</main>
</body>
</html>
"""


SETTINGS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Admin Settings</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav {
            display: flex;
            gap: 14px;
            justify-content: center;
            margin-bottom: 24px;
        }
        .panel {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 16px 0;
            padding: 16px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            border-bottom: 1px solid #30333b;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }
        button {
            background: #7c9cff;
            border: 1px solid #30333b;
            border-radius: 7px;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
            padding: 10px 12px;
        }
        .notice {
            border: 1px solid #30333b;
            border-radius: 8px;
            margin: 0 auto 20px;
            padding: 12px;
            text-align: center;
        }
        .notice.error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Admin Settings</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key) }}">Guessing leaderboard</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    <section class="panel">
        <h2>Database</h2>
        <table>
            <tbody>
                <tr><th>Database file</th><td><code>{{ db_file }}</code></td></tr>
                <tr><th>Size</th><td>{{ db_size }}</td></tr>
                <tr><th>Submissions</th><td>{{ stats.submissions }}</td></tr>
                <tr><th>Active games</th><td>{{ stats.active_games }}</td></tr>
                <tr><th>Audit entries</th><td>{{ stats.audit_entries }}</td></tr>
            </tbody>
        </table>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="action" value="backup_now">
            <button type="submit">Create Backup Now</button>
        </form>
    </section>

    <section class="panel">
        <h2>Bot Limits</h2>
        <table>
            <tbody>
                {% for key, value in limits.items() %}
                    <tr><th>{{ key }}</th><td>{{ value }}</td></tr>
                {% else %}
                    <tr><td colspan="2" class="muted">No limits configured.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Guild Settings</h2>
        {% for guild in guilds %}
            <h3>Guild {{ guild.id }}</h3>
            <table>
                <tbody>
                    <tr><th>Timezone</th><td><code>{{ guild.timezone }}</code></td></tr>
                    <tr><th>Submit channel</th><td>{{ guild.submit_channel or "Not set" }}</td></tr>
                    <tr><th>Daily channel</th><td>{{ guild.daily_top_channel or "Not set" }}</td></tr>
                    <tr><th>Daily time</th><td>{{ guild.daily_top_time_utc }} {{ guild.timezone }}</td></tr>
                    <tr><th>Approval</th><td>{{ "Enabled" if guild.approval_enabled else "Disabled" }}</td></tr>
                    <tr><th>Approval channel</th><td>{{ guild.approval_channel or "Not set" }}</td></tr>
                    <tr><th>Categories</th><td>
                        {% for category, channel_id in guild.categories %}
                            <code>{{ category }}</code> -> {{ channel_id }}<br>
                        {% else %}
                            <span class="muted">No categories set.</span>
                        {% endfor %}
                    </td></tr>
                </tbody>
            </table>
        {% else %}
            <p class="muted">No guild settings have been saved yet.</p>
        {% endfor %}
    </section>

    <section class="panel">
        <h2>Active Games</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Guild</th>
                    <th>Channel</th>
                    <th>Started By</th>
                    <th>Media</th>
                    <th>Started</th>
                </tr>
            </thead>
            <tbody>
                {% for game in active_games %}
                    <tr>
                        <td>{{ game.id }}</td>
                        <td>{{ game.guild_id }}</td>
                        <td>{{ game.channel_id }}</td>
                        <td>{{ game.starter_username }}</td>
                        <td>{{ game.media_name }}</td>
                        <td>{{ game.started_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No active games.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Recent Backups</h2>
        <table>
            <thead>
                <tr><th>File</th><th>Size</th><th>Modified</th></tr>
            </thead>
            <tbody>
                {% for backup in backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="3" class="muted">No backups found yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def current_month_key():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def load_config():
    if not CONFIG_FILE.exists():
        return {"guilds": {}, "limits": {}}
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_backup_label(label):
    return "".join(
        character if character.isalnum() or character in "_.-" else "-"
        for character in label
    ).strip("-") or "backup"


def cleanup_old_database_backups():
    if not BACKUP_DIR.exists():
        return
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup_path in backups[BACKUP_KEEP_COUNT:]:
        try:
            backup_path.unlink()
        except OSError:
            pass


def create_database_backup(label):
    if not DB_FILE.exists():
        return None, False, "Database file does not exist."

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"sdac-{safe_backup_label(label)}.db"
    if backup_path.exists():
        return backup_path, False, "Backup already exists."

    source = sqlite3.connect(DB_FILE)
    destination = sqlite3.connect(backup_path)
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()

    cleanup_old_database_backups()
    return backup_path, True, "Backup created."


def add_admin_audit_log(
    connection,
    guild_id,
    action,
    actor_user_id,
    actor_username,
    target_type="",
    target_id="",
    details="",
):
    connection.execute("""
        INSERT INTO admin_audit_log (
            guild_id, action, actor_user_id, actor_username,
            target_type, target_id, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(guild_id) if guild_id is not None else None,
        action,
        str(actor_user_id) if actor_user_id is not None else "",
        str(actor_username) if actor_username is not None else "",
        target_type,
        str(target_id) if target_id is not None else "",
        details,
        utc_now_iso(),
    ))


def available_submission_months(connection):
    months = {
        row["month"]
        for row in connection.execute("""
            SELECT DISTINCT substr(COALESCE(created_at, submitted_at), 1, 7) AS month
            FROM submissions
            WHERE COALESCE(created_at, submitted_at) IS NOT NULL
              AND COALESCE(created_at, submitted_at) != ''
        """)
        if row["month"]
    }
    months.update(
        row["month"]
        for row in connection.execute("""
            SELECT DISTINCT month
            FROM monthly_submission_top
        """)
        if row["month"]
    )
    return sorted(months, reverse=True)


def preserve_monthly_submission_top(connection, month):
    existing = connection.execute("""
        SELECT 1
        FROM monthly_submission_top
        WHERE month = ?
        LIMIT 1
    """, (month,)).fetchone()
    if existing:
        return

    rows = connection.execute("""
        SELECT *
        FROM submissions
        WHERE status = 'posted'
          AND substr(COALESCE(created_at, submitted_at), 1, 7) = ?
        ORDER BY category ASC, stars DESC, created_at DESC, id DESC
    """, (month,)).fetchall()

    ranks_by_category = {}
    captured_at = utc_now_iso()
    for row in rows:
        category = row["category"] or "Uncategorized"
        rank = ranks_by_category.get(category, 0) + 1
        if rank > 10:
            continue
        ranks_by_category[category] = rank
        connection.execute("""
            INSERT OR IGNORE INTO monthly_submission_top (
                month, category, rank, submission_id, guild_id,
                original_message_id, repost_message_id, repost_channel_id,
                user_id, username, message_text, file_paths, media_paths,
                media_names, media_types, stars, voters, submitted_at,
                created_at, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            month,
            category,
            rank,
            row["id"],
            row["guild_id"],
            row["original_message_id"],
            row["repost_message_id"],
            row["repost_channel_id"],
            row["user_id"],
            row["username"],
            row["message_text"],
            row["file_paths"],
            row["media_paths"],
            row["media_names"],
            row["media_types"],
            row["stars"] or 0,
            row["voters"],
            row["submitted_at"],
            row["created_at"],
            captured_at,
        ))


def connect_db():
    connection = sqlite3.connect(DB_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = connect_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with database() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                original_message_id TEXT,
                repost_message_id TEXT,
                repost_channel_id TEXT,
                approval_message_id TEXT,
                approval_channel_id TEXT,
                user_id TEXT,
                username TEXT,
                category TEXT,
                message_text TEXT,
                file_paths TEXT,
                media_paths TEXT,
                media_names TEXT,
                media_types TEXT,
                stars INTEGER DEFAULT 0,
                voters TEXT DEFAULT '',
                status TEXT DEFAULT 'posted',
                submitted_at TEXT,
                created_at TEXT,
                approved_at TEXT,
                daily_posted_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS moderation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                submission_id INTEGER,
                action TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                details TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                message_id TEXT,
                starter_user_id TEXT,
                starter_username TEXT,
                answer TEXT,
                answer_display TEXT,
                prompt_text TEXT,
                media_path TEXT,
                media_name TEXT,
                media_type TEXT,
                status TEXT DEFAULT 'active',
                winner_user_id TEXT,
                winner_username TEXT,
                started_at TEXT,
                solved_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                username TEXT,
                month TEXT,
                points INTEGER DEFAULT 0,
                updated_at TEXT,
                UNIQUE (guild_id, channel_id, user_id, month)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_correct_guesses (
                game_id INTEGER,
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                username TEXT,
                guessed_at TEXT,
                PRIMARY KEY (game_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_cooldowns (
                guild_id TEXT,
                channel_id TEXT,
                user_id TEXT,
                timeout_until TEXT,
                PRIMARY KEY (guild_id, channel_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_guess_runs (
                guild_id TEXT,
                channel_id TEXT,
                month TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, channel_id, month)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_guess_runs (
                guild_id TEXT,
                channel_id TEXT,
                run_date TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, channel_id, run_date)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_submission_top (
                month TEXT,
                category TEXT,
                rank INTEGER,
                submission_id INTEGER,
                guild_id TEXT,
                original_message_id TEXT,
                repost_message_id TEXT,
                repost_channel_id TEXT,
                user_id TEXT,
                username TEXT,
                message_text TEXT,
                file_paths TEXT,
                media_paths TEXT,
                media_names TEXT,
                media_types TEXT,
                stars INTEGER DEFAULT 0,
                voters TEXT DEFAULT '',
                submitted_at TEXT,
                created_at TEXT,
                captured_at TEXT,
                PRIMARY KEY (month, category, rank)
            )
        """)
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(submissions)"
            ).fetchall()
        }
        for column, definition in {
            "guild_id": "TEXT",
            "approval_message_id": "TEXT",
            "approval_channel_id": "TEXT",
            "status": "TEXT DEFAULT 'posted'",
            "approved_at": "TEXT",
        }.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE submissions ADD COLUMN {column} {definition}"
                )
        connection.execute("""
            UPDATE submissions
            SET status = 'posted'
            WHERE status IS NULL OR status = ''
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_submission_top_month
            ON monthly_submission_top (month, category, rank)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
            ON admin_audit_log (created_at, id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action
            ON admin_audit_log (action, guild_id)
        """)


initialize_database()


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


def media_relative_path(stored_path):
    path = Path(stored_path)
    parts = list(path.parts)
    if "media" in parts:
        parts = parts[parts.index("media") + 1:]
    if not parts:
        return None

    relative_path = Path(*parts)
    resolved_path = (MEDIA_DIR / relative_path).resolve()
    try:
        resolved_path.relative_to(MEDIA_DIR)
    except ValueError:
        return None
    return relative_path.as_posix()


def prepare_post(row):
    post = dict(row)
    paths = split_values(post.get("media_paths") or post.get("file_paths"))
    names = split_values(post.get("media_names"))
    types = split_values(post.get("media_types"))
    media = []

    for index, stored_path in enumerate(paths):
        relative_path = media_relative_path(stored_path)
        if not relative_path:
            continue
        media.append({
            "name": (
                names[index]
                if index < len(names)
                else Path(relative_path).name
            ),
            "type": types[index] if index < len(types) else "unknown",
            "url": url_for("serve_media", filename=relative_path),
        })
    post["media"] = media
    return post


def delete_discord_message(channel_id, message_id):
    if not channel_id or not message_id:
        return True, ""

    channel_id = str(channel_id)
    message_id = str(message_id)
    if not channel_id.isdigit() or not message_id.isdigit():
        return False, "Stored Discord message information is invalid."
    if not TOKEN:
        return False, "DISCORD_TOKEN is not set for the dashboard service."

    api_request = Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
        method="DELETE",
        headers={
            "Authorization": f"Bot {TOKEN}",
            "User-Agent": "SDAC-Dashboard/2.0",
        },
    )
    try:
        with urlopen(api_request, timeout=15) as response:
            if response.status == 204:
                return True, ""
            return False, f"Discord returned status {response.status}."
    except HTTPError as error:
        if error.code == 404:
            return True, ""
        if error.code == 403:
            return False, "Discord refused the deletion. Check bot permissions."
        return False, f"Discord returned status {error.code}."
    except (URLError, TimeoutError):
        return False, "Discord could not be reached. Nothing was removed."


def delete_local_media(row):
    for stored_path in split_values(
        row["media_paths"] or row["file_paths"]
    ):
        relative_path = media_relative_path(stored_path)
        if not relative_path:
            continue
        file_path = (MEDIA_DIR / relative_path).resolve()
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass


def has_valid_key():
    return (
        request.args.get("key") == ADMIN_KEY
        or request.form.get("key") == ADMIN_KEY
    )


def is_admin_logged_in():
    return bool(session.get("sdac_admin"))


def admin_url(endpoint, **values):
    values.setdefault("key", ADMIN_KEY)
    return url_for(endpoint, **values)


def require_admin_key():
    if not has_valid_key():
        abort(403)


def require_admin_login():
    require_admin_key()
    if not is_admin_logged_in():
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))
    return None


def positive_page(raw_value):
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 1


def web_actor():
    remote_addr = request.remote_addr or "unknown"
    return remote_addr, f"web-admin@{remote_addr}"


def recent_database_backups():
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for backup_path in backups[:10]:
        stat = backup_path.stat()
        rows.append({
            "name": backup_path.name,
            "size": format_bytes(stat.st_size),
            "modified": datetime.fromtimestamp(
                stat.st_mtime,
                timezone.utc,
            ).strftime("%Y-%m-%d %H:%M UTC"),
        })
    return rows


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not has_valid_key():
        abort(403)

    next_url = request.values.get("next") or url_for(
        "index",
        key=ADMIN_KEY,
    )
    error = ""

    if request.method == "POST":
        password = request.form.get("password", "")
        actor_id, actor_name = web_actor()
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session["sdac_admin"] = True
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "dashboard_login_success",
                    actor_id,
                    actor_name,
                    "dashboard",
                    "admin_login",
                    "Admin login succeeded.",
                )
            return redirect(next_url)
        with database() as connection:
            add_admin_audit_log(
                connection,
                None,
                "dashboard_login_failed",
                actor_id,
                actor_name,
                "dashboard",
                "admin_login",
                "Invalid admin password.",
            )
        error = "Invalid admin password."

    return render_template_string(
        LOGIN_HTML,
        admin_key=ADMIN_KEY,
        error=error,
        next_url=next_url,
    )


@app.route("/admin/logout")
def admin_logout():
    if is_admin_logged_in():
        actor_id, actor_name = web_actor()
        with database() as connection:
            add_admin_audit_log(
                connection,
                None,
                "dashboard_logout",
                actor_id,
                actor_name,
                "dashboard",
                "admin_logout",
                "Admin logged out.",
            )
    session.pop("sdac_admin", None)
    return redirect(url_for("index"))


@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    login_response = require_admin_login()
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"

    if request.method == "POST":
        action = request.form.get("action", "")
        actor_id, actor_name = web_actor()
        if action == "backup_now":
            label = datetime.now(timezone.utc).strftime("manual-%Y-%m-%d-%H%M%S")
            try:
                backup_path, created, message = create_database_backup(label)
            except (OSError, sqlite3.Error) as backup_error:
                backup_path = None
                created = False
                message = f"Backup failed: {backup_error}"
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "database_backup_manual",
                    actor_id,
                    actor_name,
                    "backup",
                    backup_path.name if backup_path else "",
                    message,
                )
            return redirect(url_for(
                "admin_settings",
                key=ADMIN_KEY,
                notice=message,
                error=0 if created else 1,
            ))

    config_data = load_config()
    limits = config_data.get("limits", {})
    guilds = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items()
    ):
        guilds.append({
            "id": guild_id,
            "submit_channel": guild_config.get("submit_channel"),
            "daily_top_channel": guild_config.get("daily_top_channel"),
            "daily_top_time_utc": guild_config.get(
                "daily_top_time_utc",
                "00:00",
            ),
            "timezone": guild_config.get("timezone", "UTC"),
            "approval_enabled": guild_config.get("approval_enabled", False),
            "approval_channel": guild_config.get("approval_channel"),
            "categories": sorted(
                (guild_config.get("categories") or {}).items()
            ),
        })

    with closing(connect_db()) as connection:
        stats = {
            "submissions": connection.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0],
            "active_games": connection.execute("""
                SELECT COUNT(*)
                FROM guess_games
                WHERE status = 'active'
            """).fetchone()[0],
            "audit_entries": connection.execute("""
                SELECT
                    (SELECT COUNT(*) FROM admin_audit_log)
                    + (SELECT COUNT(*) FROM moderation_history)
            """).fetchone()[0],
        }
        active_games = connection.execute("""
            SELECT id, guild_id, channel_id, starter_username,
                   media_name, started_at
            FROM guess_games
            WHERE status = 'active'
            ORDER BY started_at DESC, id DESC
        """).fetchall()

    db_size = format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B"
    return render_template_string(
        SETTINGS_HTML,
        active_games=active_games,
        admin_key=ADMIN_KEY,
        backups=recent_database_backups(),
        db_file=DB_FILE,
        db_size=db_size,
        error=error,
        guilds=guilds,
        limits=limits,
        notice=notice,
        stats=stats,
    )


@app.route("/")
def index():
    selected_category = request.args.get("category", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_sort = request.args.get("sort", "newest").strip()
    selected_month = request.args.get("month", "").strip()
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    page = positive_page(request.args.get("page"))
    if selected_sort not in {"newest", "votes"}:
        selected_sort = "newest"

    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    with closing(connect_db()) as connection:
        months = available_submission_months(connection)
        category_where = "" if is_admin else "WHERE status = 'posted'"
        categories = [
            row["category"]
            for row in connection.execute(f"""
                SELECT DISTINCT category
                FROM submissions
                {category_where}
                AND category IS NOT NULL AND category != ''
                ORDER BY category
            """ if category_where else """
                SELECT DISTINCT category
                FROM submissions
                WHERE category IS NOT NULL AND category != ''
                ORDER BY category
            """)
        ]

        if selected_month:
            preserve_monthly_submission_top(connection, selected_month)
            connection.commit()
            where = ["month = ?"]
            parameters = [selected_month]
            if selected_category:
                where.append("category = ?")
                parameters.append(selected_category)
            where_sql = " WHERE " + " AND ".join(where)
            total_items = connection.execute(
                f"SELECT COUNT(*) FROM monthly_submission_top{where_sql}",
                parameters,
            ).fetchone()[0]
            total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
            page = min(page, total_pages)
            rows = connection.execute(
                f"""
                    SELECT
                        submission_id AS id,
                        guild_id,
                        original_message_id,
                        repost_message_id,
                        repost_channel_id,
                        NULL AS approval_message_id,
                        NULL AS approval_channel_id,
                        user_id,
                        username,
                        category,
                        message_text,
                        file_paths,
                        media_paths,
                        media_names,
                        media_types,
                        stars,
                        voters,
                        'posted' AS status,
                        submitted_at,
                        created_at,
                        NULL AS approved_at,
                        NULL AS daily_posted_at
                    FROM monthly_submission_top
                    {where_sql}
                    ORDER BY category ASC, rank ASC
                    LIMIT ? OFFSET ?
                """,
                parameters + [PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()
        else:
            where = []
            parameters = []
            if not is_admin:
                where.append("status = 'posted'")
            elif selected_status in {"posted", "pending"}:
                where.append("status = ?")
                parameters.append(selected_status)
            if selected_category:
                where.append("category = ?")
                parameters.append(selected_category)

            where_sql = " WHERE " + " AND ".join(where) if where else ""
            order_sql = (
                "stars DESC, created_at DESC, id DESC"
                if selected_sort == "votes"
                else "created_at DESC, id DESC"
            )
            total_items = connection.execute(
                f"SELECT COUNT(*) FROM submissions{where_sql}",
                parameters,
            ).fetchone()[0]
            total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
            page = min(page, total_pages)
            rows = connection.execute(
                f"""
                    SELECT *
                    FROM submissions
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """,
                parameters + [PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()

    grouped_posts = {}
    for row in rows:
        post = prepare_post(row)
        grouped_posts.setdefault(
            post["category"] or "Uncategorized",
            [],
        ).append(post)

    def page_url(page_number):
        values = {
            "category": selected_category,
            "month": selected_month,
            "page": page_number,
            "sort": selected_sort,
        }
        if is_admin:
            values["key"] = ADMIN_KEY
            values["status"] = selected_status
        return url_for("index", **values)

    return render_template_string(
        HTML,
        admin_key=ADMIN_KEY,
        categories=categories,
        error=error,
        grouped_posts=grouped_posts,
        is_admin=is_admin,
        months=months,
        notice=notice,
        page=page,
        page_url=page_url,
        selected_category=selected_category,
        selected_month=selected_month,
        selected_sort=selected_sort,
        selected_status=selected_status,
        total_pages=total_pages,
    )


@app.route("/audit")
def audit_log():
    login_response = require_admin_login()
    if login_response:
        return login_response

    page = positive_page(request.args.get("page"))
    with closing(connect_db()) as connection:
        total_items = connection.execute("""
            SELECT
                (SELECT COUNT(*) FROM admin_audit_log)
                + (SELECT COUNT(*) FROM moderation_history)
        """).fetchone()[0]
        total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
        page = min(page, total_pages)
        rows = connection.execute("""
            SELECT *
            FROM (
                SELECT
                    id,
                    guild_id,
                    action,
                    actor_user_id,
                    actor_username,
                    target_type,
                    target_id,
                    details,
                    created_at
                FROM admin_audit_log
                UNION ALL
                SELECT
                    id,
                    guild_id,
                    'moderation_' || action AS action,
                    actor_user_id,
                    actor_username,
                    'submission' AS target_type,
                    CAST(submission_id AS TEXT) AS target_id,
                    details,
                    created_at
                FROM moderation_history
            )
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """, (PAGE_SIZE, (page - 1) * PAGE_SIZE)).fetchall()

    return render_template_string(
        AUDIT_HTML,
        admin_key=ADMIN_KEY,
        page=page,
        rows=rows,
        total_pages=total_pages,
    )


@app.route("/guessing")
def guessing_leaderboard():
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    month = request.args.get("month", "").strip() or current_month_key()

    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT channel_id, username, points
            FROM guess_points
            WHERE month = ?
            ORDER BY channel_id ASC, points DESC, username ASC
        """, (month,)).fetchall()

    grouped_scores = {}
    for row in rows:
        grouped_scores.setdefault(row["channel_id"], []).append(row)

    return render_template_string(
        GUESSING_HTML,
        admin_key=ADMIN_KEY,
        grouped_scores=grouped_scores,
        is_admin=is_admin,
        month=month,
    )


@app.route("/media/<path:filename>")
def serve_media(filename):
    resolved_path = (MEDIA_DIR / filename).resolve()
    try:
        resolved_path.relative_to(MEDIA_DIR)
    except ValueError:
        abort(404)
    return send_from_directory(MEDIA_DIR, filename)


@app.post("/delete/<int:submission_id>")
def delete_submission(submission_id):
    login_response = require_admin_login()
    if login_response:
        return login_response

    selected_category = request.args.get("category", "").strip()
    selected_status = request.args.get("status", "").strip()
    page = positive_page(request.args.get("page"))

    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    redirect_values = {
        "key": ADMIN_KEY,
        "category": selected_category,
        "status": selected_status,
        "page": page,
    }
    if not row:
        return redirect(url_for(
            "index",
            notice="Submission not found.",
            error=1,
            **redirect_values,
        ))

    for channel_id, message_id in (
        (row["repost_channel_id"], row["repost_message_id"]),
        (row["approval_channel_id"], row["approval_message_id"]),
    ):
        deleted, error_message = delete_discord_message(
            channel_id,
            message_id,
        )
        if not deleted:
            return redirect(url_for(
                "index",
                notice=error_message,
                error=1,
                **redirect_values,
            ))

    actor_id, actor = web_actor()
    with database() as connection:
        connection.execute("""
            INSERT INTO moderation_history (
                guild_id, submission_id, action, actor_user_id,
                actor_username, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["guild_id"],
            row["id"],
            "remove",
            actor_id,
            actor,
            "Removed from dashboard",
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            row["guild_id"],
            "remove_submission_dashboard",
            actor_id,
            actor,
            "submission",
            row["id"],
            "Removed from dashboard",
        )
        connection.execute(
            "DELETE FROM submissions WHERE id = ?",
            (submission_id,),
        )

    delete_local_media(row)
    return redirect(url_for(
        "index",
        notice="Submission removed from the website and Discord.",
        **redirect_values,
    ))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
