import csv
import io
import math
import os
import json
import re
import shutil
import sqlite3
import secrets
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    Response,
    send_from_directory,
    session,
    url_for,
)

from config import TOKEN
from database_migrations import DATABASE_SCHEMA_VERSION, apply_database_migrations
from observability import init_sentry


app = Flask(__name__)
init_sentry("sdac-dashboard")

ADMIN_KEY = os.getenv("SDAC_ADMIN_KEY", "ImTheBestAdmin")
ADMIN_PASSWORD = os.getenv("SDAC_ADMIN_PASSWORD", ADMIN_KEY)
app.secret_key = os.getenv("SDAC_SECRET_KEY", secrets.token_hex(32))
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "sdac.db"
CONFIG_FILE = BASE_DIR / "config.json"
MEDIA_DIR = (BASE_DIR / "media").resolve()
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_KEEP_COUNT = 30
SCHEMA_VERSION = DATABASE_SCHEMA_VERSION
PAGE_SIZE = 20
CACHE_TTL_SECONDS = 45
PUBLIC_PAGE_CACHE = {}
LOGIN_ATTEMPTS = {}
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 5
APP_STARTED_AT = datetime.now(timezone.utc)
WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
DEFAULT_LIMITS = {
    "max_file_bytes": 25 * 1024 * 1024,
    "max_total_bytes": 50 * 1024 * 1024,
    "max_text_length": 1500,
    "wrong_guess_timeout_seconds": 600,
    "submission_user_cooldown_seconds": 30,
    "submission_category_cooldown_seconds": 5,
    "guess_command_cooldown_seconds": 2,
    "admin_action_cooldown_seconds": 1,
    "rate_limit_retention_days": 30,
    "orphan_media_cleanup_enabled": True,
    "audit_retention_days": 365,
    "pending_submission_retention_hours": 48,
    "media_warning_bytes": 5 * 1024 * 1024 * 1024,
    "database_warning_bytes": 512 * 1024 * 1024,
    "restore_test_enabled": True,
    "restore_test_weekday": "sunday",
    "restore_test_time_utc": "03:30",
}


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

        select, input, button {
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
        .media-caption {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.35;
            margin-top: 8px;
            word-break: break-word;
        }
        .pill {
            border: 1px solid var(--border);
            border-radius: 999px;
            color: #cdd7ff;
            display: inline-block;
            font-size: 12px;
            margin: 3px 4px 0 0;
            padding: 2px 7px;
        }
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
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
        <a href="{{ url_for('achievements', key=admin_key if is_admin else None) }}">Achievements</a>
        {% if is_admin %}
            <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
            <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
            <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
            <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
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
            <select name="guild_id" aria-label="Discord server">
                <option value="all">All Discord Servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>
                        {{ guild.name }}
                    </option>
                {% endfor %}
            </select>
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
            <input name="q" value="{{ search_query }}" placeholder="Search text, user, ID">
            <button type="submit">Filter</button>
        </form>
    </div>
    <p class="mode">Viewing: {{ selected_guild_name }}</p>

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
                                {% if post.guild_name %}
                                    &middot; {{ post.guild_name }}
                                {% endif %}
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
                                          guild_id=selected_guild_id or 'all',
                                          q=search_query,
                                          status=selected_status,
                                          page=page
                                      ) }}"
                                      onsubmit="return confirm('Remove this submission from the website and Discord?');">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
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
                                        <div class="media-caption">
                                            <strong>{{ item.name }}</strong><br>
                                            <span class="pill">{{ item.type }}</span>
                                            {% if item.size_label %}<span class="pill">{{ item.size_label }}</span>{% endif %}
                                            {% if item.content_type %}<span class="pill">{{ item.content_type }}</span>{% endif %}
                                            {% if item.duration_label %}<span class="pill">{{ item.duration_label }}</span>{% endif %}
                                        </div>
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
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
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
        .filter form {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            margin-bottom: 24px;
        }
        input, select, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 15px;
            padding: 9px 10px;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
        }
    </style>
</head>
<body>
<main>
    <h1>SDAC Audit Log</h1>
    <nav><a href="{{ url_for('index', key=admin_key) }}">Back to submissions</a></nav>
    <nav><a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a></nav>
    <nav><a href="{{ url_for('admin_logout') }}">Log out</a></nav>
    <section class="filter">
        <form method="get" action="{{ url_for('audit_log') }}">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <select name="guild_id">
                <option value="all">All Discord Servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>
                        {{ guild.name }}
                    </option>
                {% endfor %}
            </select>
            <select name="action">
                <option value="">All Actions</option>
                {% for action in action_options %}
                    <option value="{{ action }}" {% if action_filter == action %}selected{% endif %}>{{ action }}</option>
                {% endfor %}
            </select>
            <input name="q" value="{{ search_query }}" placeholder="Search audit text">
            <button type="submit">Filter</button>
        </form>
    </section>
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
            <a href="{{ url_for('audit_log', key=admin_key, page=page - 1, guild_id=selected_guild_id or 'all', action=action_filter, q=search_query) }}">Previous</a>
        {% else %}
            <span class="disabled">Previous</span>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
            <a href="{{ url_for('audit_log', key=admin_key, page=page + 1, guild_id=selected_guild_id or 'all', action=action_filter, q=search_query) }}">Next</a>
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
        form {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            margin-bottom: 24px;
        }
        select, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 16px;
            padding: 10px 12px;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
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
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
        <a href="{{ url_for('achievements', key=admin_key if is_admin else None) }}">Achievements</a>
        {% if is_admin %}
            <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
            <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
            <a href="{{ url_for('admin_logout') }}">Log out</a>
        {% endif %}
    </nav>
    <form method="get" action="{{ url_for('guessing_leaderboard') }}">
        {% if is_admin %}
            <input type="hidden" name="key" value="{{ admin_key }}">
        {% endif %}
        <select name="guild_id" aria-label="Discord server">
            <option value="all">All Discord Servers</option>
            {% for guild in guild_options %}
                <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>
                    {{ guild.name }}
                </option>
            {% endfor %}
        </select>
        <select name="month" aria-label="Month">
            {% for available_month in months %}
                <option value="{{ available_month }}" {% if month == available_month %}selected{% endif %}>
                    {{ available_month }}
                </option>
            {% endfor %}
        </select>
        <button type="submit">Filter</button>
    </form>
    <p class="empty">Viewing: {{ selected_guild_name }}</p>

    <h2>Cross-Server Ranking - {{ month }}</h2>
    {% if cross_server_scores %}
        <section class="channel">
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>User</th>
                        <th>Total Points</th>
                        <th>Servers</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in cross_server_scores %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td>{{ row.username }}</td>
                            <td>{{ row.points }}</td>
                            <td>{{ row.server_count }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    {% else %}
        <p class="empty">No cross-server points for this month yet.</p>
    {% endif %}
    <nav>
        {% if page > 1 %}
            <a href="{{ page_url(page - 1) }}">Previous</a>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
            <a href="{{ page_url(page + 1) }}">Next</a>
        {% endif %}
    </nav>

    <h2>{{ selected_guild_name }} Channel Rankings - {{ month }}</h2>
    {% if grouped_scores %}
        {% for group in grouped_scores %}
            <section class="channel">
                <h2>{{ group.guild_name }} - Channel {{ group.channel_id }}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>User</th>
                            <th>Points</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in group.rows %}
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


SERVERS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Servers</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1 { text-align: center; }
        a { color: #7c9cff; }
        nav {
            display: flex;
            gap: 14px;
            justify-content: center;
            margin-bottom: 24px;
        }
        .server {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 14px 0;
            padding: 16px;
        }
        .meta { color: #a8adb8; }
    </style>
</head>
<body>
<main>
    <h1>SDAC Servers</h1>
    <nav>
        <a href="{{ url_for('index') }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard') }}">Guessing leaderboard</a>
        <a href="{{ url_for('achievements') }}">Achievements</a>
    </nav>
    {% for server in servers %}
        <article class="server">
            <h2><a href="{{ url_for('server_profile', guild_id=server.id) }}">{{ server.name }}</a></h2>
            <p class="meta">
                {{ server.submissions }} submission(s)
                &middot; {{ server.guess_points }} guessing point(s)
                &middot; {{ server.categories }} categor{{ "y" if server.categories == 1 else "ies" }}
            </p>
            <p>
                <a href="{{ url_for('index', guild_id=server.id) }}">Gallery</a>
                &middot;
                <a href="{{ url_for('guessing_leaderboard', guild_id=server.id) }}">Leaderboard</a>
            </p>
        </article>
    {% else %}
        <p>No Discord servers are configured yet.</p>
    {% endfor %}
</main>
</body>
</html>
"""


SERVER_PROFILE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ server.name }} - SDAC</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 900px); }
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
            margin: 14px 0;
            padding: 16px;
        }
    </style>
</head>
<body>
<main>
    <h1>{{ server.name }}</h1>
    <nav>
        <a href="{{ url_for('servers') }}">All servers</a>
        <a href="{{ url_for('index', guild_id=server.id) }}">Gallery</a>
        <a href="{{ url_for('guessing_leaderboard', guild_id=server.id) }}">Leaderboard</a>
        <a href="{{ url_for('achievements', guild_id=server.id) }}">Achievements</a>
    </nav>
    <section class="panel">
        <h2>Stats</h2>
        <p>Submissions: {{ stats.submissions }}</p>
        <p>Guessing points: {{ stats.guess_points }}</p>
        <p>Categories: {{ stats.categories }}</p>
    </section>
    <section class="panel">
        <h2>Top Submissions</h2>
        {% for post in top_posts %}
            <p><strong>{{ post.category }}</strong> - {{ post.username }} - {{ post.stars or 0 }} vote(s)</p>
        {% else %}
            <p>No submissions yet.</p>
        {% endfor %}
    </section>
    <section class="panel">
        <h2>Top Guessers</h2>
        {% for row in top_guessers %}
            <p>{{ loop.index }}. {{ row.username }} - {{ row.points }} point(s)</p>
        {% else %}
            <p>No guessing points yet.</p>
        {% endfor %}
    </section>
</main>
</body>
</html>
"""


ACHIEVEMENTS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Achievements</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav, form {
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            justify-content: center;
            margin-bottom: 24px;
        }
        select, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 16px;
            padding: 10px 12px;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
        }
        .panel {
            background: #1b1d22;
            border: 1px solid #30333b;
            border-radius: 12px;
            margin: 14px 0;
            padding: 16px;
        }
    </style>
</head>
<body>
<main>
    <h1>Achievements</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key if is_admin else None) }}">Submissions</a>
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
    </nav>
    <form method="get" action="{{ url_for('achievements') }}">
        {% if is_admin %}<input type="hidden" name="key" value="{{ admin_key }}">{% endif %}
        <select name="guild_id">
            <option value="all">All Discord Servers</option>
            {% for guild in guild_options %}
                <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
            {% endfor %}
        </select>
        <select name="month">
            {% for available_month in months %}
                <option value="{{ available_month }}" {% if month == available_month %}selected{% endif %}>{{ available_month }}</option>
            {% endfor %}
        </select>
        <button type="submit">Filter</button>
    </form>
    <section class="panel">
        <h2>Monthly Guessing Winner</h2>
        {% if top_guesser %}
            <p>{{ top_guesser.username }} - {{ top_guesser.points }} point(s)</p>
        {% else %}
            <p>No guessing points for this month.</p>
        {% endif %}
    </section>
    <section class="panel">
        <h2>Most Voted Submission</h2>
        {% if top_submission %}
            <p>{{ top_submission.username }} - {{ top_submission.category }} - {{ top_submission.stars or 0 }} vote(s)</p>
        {% else %}
            <p>No submissions for this month.</p>
        {% endif %}
    </section>
    <section class="panel">
        <h2>Top Submitter</h2>
        {% if top_submitter %}
            <p>{{ top_submitter.username }} - {{ top_submitter.submission_count }} submission(s)</p>
        {% else %}
            <p>No submitter stats for this month.</p>
        {% endif %}
    </section>
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
        input, select, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 15px;
            padding: 9px 10px;
        }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
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
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_health', key=admin_key) }}">Health</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    {% if security_warnings %}
        <section class="panel">
            <h2>Security Warnings</h2>
            {% for warning in security_warnings %}
                <p class="notice error">{{ warning }}</p>
            {% endfor %}
        </section>
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
                <tr><th>Rate-limit events</th><td>{{ stats.rate_limit_events }}</td></tr>
                <tr><th>Media size</th><td>{{ stats.media_size }}</td></tr>
            </tbody>
        </table>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="action" value="backup_now">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <button type="submit">Create Backup Now</button>
        </form>
        <p>
            Export:
            <a href="{{ url_for('export_submissions', key=admin_key) }}">Submissions CSV</a>
            &middot;
            <a href="{{ url_for('export_guessing', key=admin_key) }}">Guessing CSV</a>
            &middot;
            <a href="{{ url_for('export_audit', key=admin_key) }}">Audit CSV</a>
        </p>
    </section>

    <section class="panel">
        <h2>Bot Limits</h2>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="action" value="update_limits">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <table>
                <tbody>
                    <tr><th>Wrong guess timeout seconds</th><td><input name="wrong_guess_timeout_seconds" value="{{ limits.get('wrong_guess_timeout_seconds', 600) }}"></td></tr>
                    <tr><th>Submit user cooldown seconds</th><td><input name="submission_user_cooldown_seconds" value="{{ limits.get('submission_user_cooldown_seconds', 30) }}"></td></tr>
                    <tr><th>Submit category cooldown seconds</th><td><input name="submission_category_cooldown_seconds" value="{{ limits.get('submission_category_cooldown_seconds', 5) }}"></td></tr>
                    <tr><th>Guess command cooldown seconds</th><td><input name="guess_command_cooldown_seconds" value="{{ limits.get('guess_command_cooldown_seconds', 2) }}"></td></tr>
                    <tr><th>Admin action cooldown seconds</th><td><input name="admin_action_cooldown_seconds" value="{{ limits.get('admin_action_cooldown_seconds', 1) }}"></td></tr>
                    <tr><th>Rate-limit retention days</th><td><input name="rate_limit_retention_days" value="{{ limits.get('rate_limit_retention_days', 30) }}"></td></tr>
                    <tr><th>Audit retention days</th><td><input name="audit_retention_days" value="{{ limits.get('audit_retention_days', 365) }}"></td></tr>
                    <tr><th>Pending submission retention hours</th><td><input name="pending_submission_retention_hours" value="{{ limits.get('pending_submission_retention_hours', 48) }}"></td></tr>
                    <tr><th>Media warning bytes</th><td><input name="media_warning_bytes" value="{{ limits.get('media_warning_bytes', 5368709120) }}"></td></tr>
                    <tr><th>Database warning bytes</th><td><input name="database_warning_bytes" value="{{ limits.get('database_warning_bytes', 536870912) }}"></td></tr>
                    <tr><th>Restore test weekday</th><td>
                        <select name="restore_test_weekday">
                            {% for day in weekdays %}
                                <option value="{{ day }}" {% if limits.get('restore_test_weekday', 'sunday') == day %}selected{% endif %}>{{ day.title() }}</option>
                            {% endfor %}
                        </select>
                    </td></tr>
                    <tr><th>Restore test time UTC</th><td><input name="restore_test_time_utc" value="{{ limits.get('restore_test_time_utc', '03:30') }}" placeholder="HH:MM"></td></tr>
                    <tr><th>Restore test</th><td>
                        <select name="restore_test_enabled">
                            <option value="1" {% if limits.get('restore_test_enabled', True) %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not limits.get('restore_test_enabled', True) %}selected{% endif %}>Disabled</option>
                        </select>
                    </td></tr>
                    <tr><th>Orphan media cleanup</th><td>
                        <select name="orphan_media_cleanup_enabled">
                            <option value="1" {% if limits.get('orphan_media_cleanup_enabled', True) %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not limits.get('orphan_media_cleanup_enabled', True) %}selected{% endif %}>Disabled</option>
                        </select>
                    </td></tr>
                </tbody>
            </table>
            <button type="submit">Save Limits</button>
        </form>
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
            <h3>{{ guild.name }} ({{ guild.id }})</h3>
            <form method="post">
                <input type="hidden" name="key" value="{{ admin_key }}">
                <input type="hidden" name="action" value="update_guild">
                <input type="hidden" name="guild_id" value="{{ guild.id }}">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <table>
                    <tbody>
                        <tr><th>Timezone</th><td><input name="timezone" value="{{ guild.timezone }}"></td></tr>
                        <tr><th>Submit channel ID</th><td><input name="submit_channel" value="{{ guild.submit_channel or '' }}"></td></tr>
                        <tr><th>Weekly channel ID</th><td><input name="weekly_channel" value="{{ guild.daily_top_channel or '' }}"></td></tr>
                        <tr><th>Weekly day</th><td>
                            <select name="weekly_top_day">
                                {% for day in weekdays %}
                                    <option value="{{ day }}" {% if guild.weekly_top_day_lower == day %}selected{% endif %}>{{ day.title() }}</option>
                                {% endfor %}
                            </select>
                        </td></tr>
                        <tr><th>Weekly time</th><td><input name="weekly_time" value="{{ guild.daily_top_time_utc }}" placeholder="HH:MM"></td></tr>
                        <tr><th>Approval</th><td>
                            <select name="approval_enabled">
                                <option value="0" {% if not guild.approval_enabled %}selected{% endif %}>Disabled</option>
                                <option value="1" {% if guild.approval_enabled %}selected{% endif %}>Enabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Approval channel ID</th><td><input name="approval_channel" value="{{ guild.approval_channel or '' }}"></td></tr>
                        <tr><th>Game summary channel ID</th><td><input name="game_summary_channel" value="{{ guild.game_summary_channel or '' }}"></td></tr>
                        <tr><th>Error channel ID</th><td><input name="error_channel" value="{{ guild.error_channel or '' }}"></td></tr>
                        <tr><th>Admin role IDs</th><td><input name="admin_role_ids" value="{{ guild.admin_role_ids }}"></td></tr>
                    </tbody>
                </table>
                <button type="submit">Save Guild Settings</button>
            </form>
            <form method="post">
                <input type="hidden" name="key" value="{{ admin_key }}">
                <input type="hidden" name="action" value="save_category">
                <input type="hidden" name="guild_id" value="{{ guild.id }}">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <input name="category" placeholder="category">
                <input name="channel_id" placeholder="channel ID">
                <button type="submit">Add / Update Category</button>
            </form>
            <table>
                <tbody>
                    <tr><th>Timezone</th><td><code>{{ guild.timezone }}</code></td></tr>
                    <tr><th>Submit channel</th><td>{{ guild.submit_channel or "Not set" }}</td></tr>
                    <tr><th>Weekly channel</th><td>{{ guild.daily_top_channel or "Not set" }}</td></tr>
                    <tr><th>Weekly day</th><td>{{ guild.weekly_top_day }}</td></tr>
                    <tr><th>Weekly time</th><td>{{ guild.daily_top_time_utc }} {{ guild.timezone }}</td></tr>
                    <tr><th>Approval</th><td>{{ "Enabled" if guild.approval_enabled else "Disabled" }}</td></tr>
                    <tr><th>Approval channel</th><td>{{ guild.approval_channel or "Not set" }}</td></tr>
                    <tr><th>Categories</th><td>
                        {% for category, channel_id in guild.categories %}
                            <form method="post">
                                <input type="hidden" name="key" value="{{ admin_key }}">
                                <input type="hidden" name="action" value="delete_category">
                                <input type="hidden" name="guild_id" value="{{ guild.id }}">
                                <input type="hidden" name="category" value="{{ category }}">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                <code>{{ category }}</code> -> {{ channel_id }}
                                <button type="submit">Delete</button>
                            </form>
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


MAINTENANCE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Maintenance</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        button { background: #7c9cff; border: 0; border-radius: 7px; color: #0b1020; cursor: pointer; font-weight: bold; padding: 9px 10px; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin: 0 auto 20px; padding: 12px; text-align: center; }
        .notice.error { border-color: #e45d68; }
        .ok { color: #63c174; font-weight: bold; }
        .bad { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Maintenance</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_health', key=admin_key) }}">Health JSON</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    {% if warnings %}
        <section class="panel">
            <h2>Warnings</h2>
            {% for warning in warnings %}
                <p class="notice error">{{ warning }}</p>
            {% endfor %}
        </section>
    {% endif %}

    <section class="panel">
        <h2>Runtime</h2>
        <table>
            <tbody>
                <tr><th>Release</th><td>{{ release }}</td></tr>
                <tr><th>Server name</th><td>{{ server_name }}</td></tr>
                <tr><th>Started</th><td>{{ started_at }}</td></tr>
                <tr><th>Uptime</th><td>{{ uptime }}</td></tr>
                <tr><th>Database</th><td><code>{{ db_file }}</code></td></tr>
                <tr><th>Database size</th><td>{{ db_size }}</td></tr>
                <tr><th>Media files</th><td>{{ media_files }}</td></tr>
                <tr><th>Media size</th><td>{{ media_size }}</td></tr>
                <tr><th>Cache entries</th><td>{{ cache_entries }}</td></tr>
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Actions</h2>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <button name="action" value="backup_now" type="submit">Create Backup Now</button>
            <button name="action" value="restore_test" type="submit">Run Restore Test</button>
        </form>
    </section>

    <section class="panel">
        <h2>Recent Restore Tests</h2>
        <table>
            <thead><tr><th>Run</th><th>Backup</th><th>Status</th><th>Details</th><th>Created</th></tr></thead>
            <tbody>
                {% for row in restore_runs %}
                    <tr>
                        <td><code>{{ row.run_key }}</code></td>
                        <td>{{ row.backup_name }}</td>
                        <td class="{{ 'ok' if row.status == 'passed' else 'bad' }}">{{ row.status }}</td>
                        <td>{{ row.details }}</td>
                        <td>{{ row.created_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="muted">No restore tests have run yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Recent Backups</h2>
        <table>
            <thead><tr><th>File</th><th>Size</th><th>Modified</th></tr></thead>
            <tbody>
                {% for backup in backups %}
                    <tr><td><code>{{ backup.name }}</code></td><td>{{ backup.size }}</td><td>{{ backup.modified }}</td></tr>
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


MODERATION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Moderation</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
        img, video { max-height: 110px; max-width: 180px; }
    </style>
</head>
<body>
<main>
    <h1>Moderation</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    <section class="panel">
        <h2>Pending Queue</h2>
        <table>
            <thead><tr><th>ID</th><th>Server</th><th>User</th><th>Category</th><th>Media</th><th>Text</th><th>Created</th></tr></thead>
            <tbody>
                {% for post in pending_posts %}
                    <tr>
                        <td><a href="{{ url_for('index', key=admin_key, status='pending', q=post.id) }}">{{ post.id }}</a></td>
                        <td>{{ guild_names.get(post.guild_id, post.guild_id) }}</td>
                        <td>{{ post.username }}</td>
                        <td>{{ post.category }}</td>
                        <td>
                            {% for item in post.media[:2] %}
                                {% if item.type == "image" %}
                                    <img src="{{ item.url }}" alt="{{ item.name }}">
                                {% elif item.type == "video" %}
                                    <video controls src="{{ item.url }}"></video>
                                {% elif item.type == "audio" %}
                                    <audio controls src="{{ item.url }}"></audio>
                                {% else %}
                                    <a href="{{ item.url }}">{{ item.name }}</a>
                                {% endif %}
                            {% else %}
                                <span class="muted">No media found</span>
                            {% endfor %}
                        </td>
                        <td>{{ post.message_text or "" }}</td>
                        <td>{{ post.created_at or post.submitted_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" class="muted">No pending submissions.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Recent Moderation History</h2>
        <table>
            <thead><tr><th>Submission</th><th>Server</th><th>Action</th><th>Actor</th><th>Details</th><th>Created</th></tr></thead>
            <tbody>
                {% for row in history %}
                    <tr>
                        <td>{{ row.submission_id }}</td>
                        <td>{{ guild_names.get(row.guild_id, row.guild_id) }}</td>
                        <td><code>{{ row.action }}</code></td>
                        <td>{{ row.actor_username }}</td>
                        <td>{{ row.details }}</td>
                        <td>{{ row.created_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No moderation history yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


ONBOARDING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Server Onboarding</title>
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
        nav {
            display: flex;
            gap: 14px;
            justify-content: center;
            margin-bottom: 24px;
        }
        .server {
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
        .ok { color: #63c174; font-weight: bold; }
        .missing { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Server Onboarding</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% for server in servers %}
        <article class="server">
            <h2>{{ server.name }} <span class="muted">({{ server.id }})</span></h2>
            <p>{{ server.complete_count }} of {{ server.total_count }} required item(s) complete.</p>
            <table>
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Item</th>
                        <th>How to fix</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in server.items %}
                        <tr>
                            <td class="{{ 'ok' if item.ok else 'missing' }}">{{ 'OK' if item.ok else 'Missing' }}</td>
                            <td>{{ item.label }}{% if item.optional %}<br><span class="muted">Recommended</span>{% endif %}</td>
                            <td><code>{{ item.fix }}</code></td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </article>
    {% else %}
        <p>No Discord servers are configured yet. Invite the bot and let it start once, then refresh this page.</p>
    {% endfor %}
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
        return {"guilds": {}, "limits": dict(DEFAULT_LIMITS)}
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    limits = data.setdefault("limits", {})
    changed = False
    for key, value in DEFAULT_LIMITS.items():
        if key not in limits:
            limits[key] = value
            changed = True
    if changed:
        save_config(data)
    return data


def save_config(data):
    with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=4)
        file.write("\n")
    PUBLIC_PAGE_CACHE.clear()


def cache_key(name, *parts):
    return ":".join([name] + [str(part) for part in parts])


def cached_public_page(key):
    cached = PUBLIC_PAGE_CACHE.get(key)
    if not cached:
        return None
    expires_at, body = cached
    if expires_at < time.time():
        PUBLIC_PAGE_CACHE.pop(key, None)
        return None
    return body


def store_public_page(key, body):
    PUBLIC_PAGE_CACHE[key] = (time.time() + CACHE_TTL_SECONDS, body)
    if len(PUBLIC_PAGE_CACHE) > 128:
        oldest_key = min(
            PUBLIC_PAGE_CACHE,
            key=lambda item: PUBLIC_PAGE_CACHE[item][0],
        )
        PUBLIC_PAGE_CACHE.pop(oldest_key, None)
    return body


def media_directory_stats():
    total = 0
    files = 0
    if not MEDIA_DIR.exists():
        return {"bytes": total, "files": files}
    for path in MEDIA_DIR.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
                files += 1
            except OSError:
                pass
    return {"bytes": total, "files": files}


def media_directory_size():
    return media_directory_stats()["bytes"]


def latest_database_backup():
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def validate_database_backup(backup_path):
    backup_path = Path(backup_path) if backup_path else None
    if backup_path is None or not backup_path.is_file():
        return False, "Backup file was not found."

    with tempfile.TemporaryDirectory(prefix="sdac-restore-test-") as temp_dir:
        restore_path = Path(temp_dir) / "sdac.db"
        shutil.copy2(backup_path, restore_path)
        connection = sqlite3.connect(restore_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA foreign_keys = ON")
            apply_database_migrations(connection)
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                return False, f"Integrity check failed: {integrity}"
            tables = {
                row["name"]
                for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
            }
            required = {
                "submissions",
                "admin_audit_log",
                "schema_version",
            }
            missing = sorted(required - tables)
            if missing:
                return (
                    False,
                    "Missing required table(s): " + ", ".join(missing),
                )
            connection.commit()
        finally:
            connection.close()
    return True, f"Restore test passed for {backup_path.name}."


def record_restore_test_run(run_key, backup_path, status, details):
    with database() as connection:
        connection.execute("""
            INSERT INTO restore_test_runs (
                run_key, backup_name, status, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_key) DO UPDATE SET
                backup_name = excluded.backup_name,
                status = excluded.status,
                details = excluded.details,
                created_at = excluded.created_at
        """, (
            run_key,
            backup_path.name if backup_path else "",
            status,
            details,
            utc_now_iso(),
        ))


def run_manual_restore_test():
    backup_path = latest_database_backup()
    passed, details = validate_database_backup(backup_path)
    status = "passed" if passed else "failed"
    run_key = datetime.now(timezone.utc).strftime("manual:%Y-%m-%d-%H%M%S")
    record_restore_test_run(run_key, backup_path, status, details)
    return passed, backup_path, details


def storage_warnings(config_data=None):
    config_data = config_data or load_config()
    limits = config_data.get("limits", {})
    warnings = []
    try:
        media_limit = int(limits.get("media_warning_bytes") or 0)
        database_limit = int(limits.get("database_warning_bytes") or 0)
    except (TypeError, ValueError):
        return ["Storage warning thresholds must be numeric."]
    media_size = media_directory_size()
    database_size = DB_FILE.stat().st_size if DB_FILE.exists() else 0
    if media_limit and media_size >= media_limit:
        warnings.append(
            f"Media folder is {format_bytes(media_size)} "
            f"(warning at {format_bytes(media_limit)})."
        )
    if database_limit and database_size >= database_limit:
        warnings.append(
            f"Database is {format_bytes(database_size)} "
            f"(warning at {format_bytes(database_limit)})."
        )
    return warnings


def security_warnings():
    warnings = []
    if ADMIN_PASSWORD == ADMIN_KEY:
        warnings.append(
            "SDAC_ADMIN_PASSWORD matches SDAC_ADMIN_KEY. Use a separate "
            "password for the admin login."
        )
    if ADMIN_KEY == "ImTheBestAdmin":
        warnings.append(
            "SDAC_ADMIN_KEY is still using the development default."
        )
    if not os.getenv("SDAC_SECRET_KEY"):
        warnings.append(
            "SDAC_SECRET_KEY is not set. Sessions will reset on dashboard "
            "restart and are not production-stable."
        )
    if not os.getenv("SDAC_ADMIN_PASSWORD"):
        warnings.append(
            "SDAC_ADMIN_PASSWORD is not set. The dashboard falls back to the "
            "admin key as the password."
        )
    return warnings


def csv_response(filename, rows, columns):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[column] for column in columns])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


def nullable_channel_id(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return None
    if not value.isdigit():
        raise ValueError("Channel IDs must be numbers.")
    return int(value)


def role_id_list(raw_value):
    role_ids = []
    for value in re_split_ids(raw_value):
        if not value.isdigit():
            raise ValueError("Role IDs must be numbers.")
        role_ids.append(value)
    return sorted(set(role_ids))


def re_split_ids(raw_value):
    return [
        value
        for value in str(raw_value or "").replace(",", " ").split()
        if value.strip()
    ]


def clean_category_name(category):
    return category.lower().strip().replace(" ", "")


def validate_time(value):
    value = str(value or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        raise ValueError("Time must be HH:MM.")
    hour, minute = [int(part) for part in value.split(":")]
    if hour > 23 or minute > 59:
        raise ValueError("Time must be between 00:00 and 23:59.")
    return value


def guild_options(config_data=None):
    config_data = config_data or load_config()
    options = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items(),
        key=lambda item: (
            item[1].get("guild_name") or item[0]
        ).casefold(),
    ):
        options.append({
            "id": guild_id,
            "name": guild_config.get("guild_name") or f"Discord {guild_id}",
        })
    return options


def guild_name_map(config_data=None):
    return {
        option["id"]: option["name"]
        for option in guild_options(config_data)
    }


def onboarding_item(ok, label, fix, optional=False):
    return {
        "ok": bool(ok),
        "label": label,
        "fix": fix,
        "optional": optional,
    }


def build_onboarding_rows(config_data):
    rows = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items(),
        key=lambda item: (
            item[1].get("guild_name") or item[0]
        ).casefold(),
    ):
        categories = guild_config.get("categories") or {}
        approval_enabled = guild_config.get("approval_enabled", False)
        items = [
            onboarding_item(
                guild_config.get("submit_channel"),
                "Submit channel configured",
                "/setsubmit #channel",
            ),
            onboarding_item(
                categories,
                "At least one submission category",
                "/setcategory category #channel",
            ),
            onboarding_item(
                guild_config.get("timezone"),
                "Timezone configured",
                "/settimezone America/New_York",
            ),
            onboarding_item(
                not approval_enabled or guild_config.get("approval_channel"),
                "Approval channel ready when approval is enabled",
                "/setapproval enabled #channel",
            ),
            onboarding_item(
                guild_config.get("error_channel"),
                "Error notification channel",
                "/seterrorchannel #staff-errors",
                optional=True,
            ),
            onboarding_item(
                guild_config.get("game_summary_channel"),
                "Guessing game summary channel",
                "/setgamesummarychannel #channel",
                optional=True,
            ),
            onboarding_item(
                guild_config.get("daily_top_channel"),
                "Weekly top submissions channel",
                "/setweeklychannel #channel",
                optional=True,
            ),
            onboarding_item(
                guild_config.get("admin_role_ids"),
                "SDAC admin role",
                "/setadminrole @role",
                optional=True,
            ),
        ]
        required_items = [item for item in items if not item["optional"]]
        rows.append({
            "id": guild_id,
            "name": guild_config.get("guild_name") or f"Discord {guild_id}",
            "items": items,
            "complete_count": sum(1 for item in required_items if item["ok"]),
            "total_count": len(required_items),
        })
    return rows


def selected_guild_id(options):
    valid_ids = {option["id"] for option in options}
    requested = request.values.get("guild_id", "").strip()
    if requested == "all":
        session.pop("sdac_guild_id", None)
        return ""
    if requested in valid_ids:
        session["sdac_guild_id"] = requested
        return requested

    stored = session.get("sdac_guild_id", "")
    if stored in valid_ids:
        return stored
    session.pop("sdac_guild_id", None)
    return ""


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


def available_submission_months(connection, guild_id=""):
    submission_where = """
            WHERE COALESCE(created_at, submitted_at) IS NOT NULL
              AND COALESCE(created_at, submitted_at) != ''
    """
    submission_parameters = []
    snapshot_where = ""
    snapshot_parameters = []
    if guild_id:
        submission_where += " AND guild_id = ?"
        submission_parameters.append(guild_id)
        snapshot_where = "WHERE guild_id = ?"
        snapshot_parameters.append(guild_id)

    months = {
        row["month"]
        for row in connection.execute("""
            SELECT DISTINCT substr(COALESCE(created_at, submitted_at), 1, 7) AS month
            FROM submissions
            """ + submission_where, submission_parameters)
        if row["month"]
    }
    months.update(
        row["month"]
        for row in connection.execute(f"""
            SELECT DISTINCT month
            FROM monthly_submission_top
            {snapshot_where}
        """, snapshot_parameters)
        if row["month"]
    )
    return sorted(months, reverse=True)


def available_guess_months(connection):
    months = [
        row["month"]
        for row in connection.execute("""
            SELECT DISTINCT month
            FROM guess_points
            WHERE month IS NOT NULL AND month != ''
            ORDER BY month DESC
        """)
        if row["month"]
    ]
    current_month = current_month_key()
    if current_month not in months:
        months.insert(0, current_month)
    return months


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
                media_names, media_types, media_sizes, media_metadata_json,
                stars, voters, submitted_at, created_at, captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            row["media_sizes"],
            row["media_metadata_json"],
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
                media_sizes TEXT,
                media_metadata_json TEXT,
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
            CREATE TABLE IF NOT EXISTS restore_test_runs (
                run_key TEXT PRIMARY KEY,
                backup_name TEXT,
                status TEXT,
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
                media_size INTEGER DEFAULT 0,
                media_metadata_json TEXT,
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
                media_sizes TEXT,
                media_metadata_json TEXT,
                stars INTEGER DEFAULT 0,
                voters TEXT DEFAULT '',
                submitted_at TEXT,
                created_at TEXT,
                captured_at TEXT,
                PRIMARY KEY (month, category, rank)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
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
            "media_sizes": "TEXT",
            "media_metadata_json": "TEXT",
        }.items():
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE submissions ADD COLUMN {column} {definition}"
                )
        guess_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(guess_games)"
            ).fetchall()
        }
        for column, definition in {
            "hint_text": "TEXT",
            "hint_revealed_at": "TEXT",
            "media_size": "INTEGER DEFAULT 0",
            "media_metadata_json": "TEXT",
        }.items():
            if column not in guess_columns:
                connection.execute(
                    f"ALTER TABLE guess_games ADD COLUMN {column} {definition}"
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
            CREATE INDEX IF NOT EXISTS idx_submissions_gallery
            ON submissions (guild_id, status, category, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_search
            ON submissions (guild_id, status, username, message_text, category)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_points_global_month
            ON guess_points (month, user_id, points)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
            ON admin_audit_log (created_at, id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action
            ON admin_audit_log (action, guild_id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_restore_test_runs_created
            ON restore_test_runs (created_at)
        """)
        apply_database_migrations(connection)


initialize_database()


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


def parse_metadata_list(raw_value):
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item if isinstance(item, dict) else {} for item in parsed]


def duration_label(seconds):
    if seconds in (None, ""):
        return ""
    try:
        total_seconds = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    minutes, remaining = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


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
    sizes = split_values(post.get("media_sizes"))
    metadata_items = parse_metadata_list(post.get("media_metadata_json"))
    media = []

    for index, stored_path in enumerate(paths):
        relative_path = media_relative_path(stored_path)
        if not relative_path:
            continue
        metadata = metadata_items[index] if index < len(metadata_items) else {}
        size = metadata.get("size")
        if size in (None, "") and index < len(sizes):
            try:
                size = int(sizes[index])
            except ValueError:
                size = 0
        try:
            size = int(size or 0)
        except (TypeError, ValueError):
            size = 0
        media.append({
            "name": (
                names[index]
                if index < len(names)
                else Path(relative_path).name
            ),
            "type": (
                metadata.get("media_type")
                or (types[index] if index < len(types) else "unknown")
            ),
            "url": url_for("serve_media", filename=relative_path),
            "size": size,
            "size_label": format_bytes(size) if size else "",
            "content_type": metadata.get("content_type") or "",
            "duration_label": duration_label(
                metadata.get("duration_seconds")
            ),
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


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def require_csrf_token():
    expected = session.get("csrf_token", "")
    provided = request.form.get("csrf_token", "")
    if not expected or not secrets.compare_digest(provided, expected):
        abort(400)


def login_remote_key():
    return request.remote_addr or "unknown"


def prune_login_attempts(remote_key):
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    attempts = [
        attempt
        for attempt in LOGIN_ATTEMPTS.get(remote_key, [])
        if attempt >= cutoff
    ]
    if attempts:
        LOGIN_ATTEMPTS[remote_key] = attempts
    else:
        LOGIN_ATTEMPTS.pop(remote_key, None)
    return attempts


def login_rate_limited(remote_key):
    return len(prune_login_attempts(remote_key)) >= LOGIN_MAX_ATTEMPTS


def record_login_failure(remote_key):
    attempts = prune_login_attempts(remote_key)
    attempts.append(time.time())
    LOGIN_ATTEMPTS[remote_key] = attempts


def clear_login_failures(remote_key):
    LOGIN_ATTEMPTS.pop(remote_key, None)


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
        require_csrf_token()
        password = request.form.get("password", "")
        actor_id, actor_name = web_actor()
        remote_key = login_remote_key()
        if login_rate_limited(remote_key):
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "dashboard_login_rate_limited",
                    actor_id,
                    actor_name,
                    "dashboard",
                    "admin_login",
                    "Too many failed admin login attempts.",
                )
            error = "Too many failed login attempts. Try again in a few minutes."
        elif secrets.compare_digest(password, ADMIN_PASSWORD):
            clear_login_failures(remote_key)
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
        else:
            record_login_failure(remote_key)
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
        csrf_token=get_csrf_token(),
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
        require_csrf_token()
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
        if action == "update_limits":
            config_data = load_config()
            limits = config_data.setdefault("limits", {})
            try:
                for field in (
                    "wrong_guess_timeout_seconds",
                    "submission_user_cooldown_seconds",
                    "submission_category_cooldown_seconds",
                    "guess_command_cooldown_seconds",
                    "admin_action_cooldown_seconds",
                    "rate_limit_retention_days",
                    "audit_retention_days",
                    "pending_submission_retention_hours",
                    "media_warning_bytes",
                    "database_warning_bytes",
                ):
                    value = int(request.form.get(field, "0"))
                    if value < 0:
                        raise ValueError("Limits cannot be negative.")
                    limits[field] = value
                restore_weekday = request.form.get(
                    "restore_test_weekday",
                    "sunday",
                )
                if restore_weekday not in WEEKDAYS:
                    raise ValueError("Invalid restore test weekday.")
                limits["restore_test_weekday"] = restore_weekday
                limits["restore_test_time_utc"] = validate_time(
                    request.form.get("restore_test_time_utc")
                )
                limits["restore_test_enabled"] = (
                    request.form.get("restore_test_enabled") == "1"
                )
                limits["orphan_media_cleanup_enabled"] = (
                    request.form.get("orphan_media_cleanup_enabled") == "1"
                )
            except ValueError as form_error:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice=str(form_error),
                    error=1,
                ))
            save_config(config_data)
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "dashboard_update_limits",
                    actor_id,
                    actor_name,
                    "limits",
                    "",
                    "Updated bot limits from dashboard.",
                )
            return redirect(url_for(
                "admin_settings",
                key=ADMIN_KEY,
                notice="Bot limits saved.",
            ))
        if action in {"update_guild", "save_category", "delete_category"}:
            config_data = load_config()
            guild_id = request.form.get("guild_id", "").strip()
            guild_config = (config_data.get("guilds") or {}).get(guild_id)
            if not guild_config:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice="Unknown guild.",
                    error=1,
                ))
            try:
                if action == "update_guild":
                    guild_config["timezone"] = request.form.get(
                        "timezone",
                        "UTC",
                    ).strip() or "UTC"
                    guild_config["submit_channel"] = nullable_channel_id(
                        request.form.get("submit_channel")
                    )
                    guild_config["daily_top_channel"] = nullable_channel_id(
                        request.form.get("weekly_channel")
                    )
                    guild_config["daily_top_time_utc"] = validate_time(
                        request.form.get("weekly_time")
                    )
                    weekday = request.form.get("weekly_top_day", "sunday")
                    if weekday not in WEEKDAYS:
                        raise ValueError("Invalid weekly day.")
                    guild_config["weekly_top_day"] = weekday
                    guild_config["approval_enabled"] = (
                        request.form.get("approval_enabled") == "1"
                    )
                    guild_config["approval_channel"] = nullable_channel_id(
                        request.form.get("approval_channel")
                    )
                    guild_config["game_summary_channel"] = nullable_channel_id(
                        request.form.get("game_summary_channel")
                    )
                    guild_config["error_channel"] = nullable_channel_id(
                        request.form.get("error_channel")
                    )
                    guild_config["admin_role_ids"] = role_id_list(
                        request.form.get("admin_role_ids")
                    )
                    message = "Guild settings saved."
                elif action == "save_category":
                    category = clean_category_name(request.form.get("category"))
                    channel_id = nullable_channel_id(
                        request.form.get("channel_id")
                    )
                    if not category or channel_id is None:
                        raise ValueError("Category and channel ID are required.")
                    guild_config.setdefault("categories", {})[category] = channel_id
                    message = f"Category {category} saved."
                else:
                    category = clean_category_name(request.form.get("category"))
                    guild_config.setdefault("categories", {}).pop(category, None)
                    message = f"Category {category} deleted."
            except ValueError as form_error:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice=str(form_error),
                    error=1,
                ))

            save_config(config_data)
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    guild_id,
                    f"dashboard_{action}",
                    actor_id,
                    actor_name,
                    "guild",
                    guild_id,
                    message,
                )
            return redirect(url_for(
                "admin_settings",
                key=ADMIN_KEY,
                notice=message,
            ))

    config_data = load_config()
    limits = config_data.get("limits", {})
    warnings = security_warnings() + storage_warnings(config_data)
    guilds = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items()
    ):
        guilds.append({
            "id": guild_id,
            "name": guild_config.get("guild_name") or f"Discord {guild_id}",
            "submit_channel": guild_config.get("submit_channel"),
            "daily_top_channel": guild_config.get("daily_top_channel"),
            "daily_top_time_utc": guild_config.get(
                "daily_top_time_utc",
                "00:00",
            ),
            "weekly_top_day": guild_config.get("weekly_top_day", "sunday").title(),
            "weekly_top_day_lower": guild_config.get("weekly_top_day", "sunday"),
            "timezone": guild_config.get("timezone", "UTC"),
            "approval_enabled": guild_config.get("approval_enabled", False),
            "approval_channel": guild_config.get("approval_channel"),
            "game_summary_channel": guild_config.get("game_summary_channel"),
            "error_channel": guild_config.get("error_channel"),
            "admin_role_ids": " ".join(
                str(role_id)
                for role_id in guild_config.get("admin_role_ids", [])
            ),
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
            "rate_limit_events": connection.execute("""
                SELECT COUNT(*)
                FROM rate_limit_events
            """).fetchone()[0],
            "media_size": format_bytes(media_directory_size()),
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
        csrf_token=get_csrf_token(),
        db_file=DB_FILE,
        db_size=db_size,
        error=error,
        guilds=guilds,
        limits=limits,
        notice=notice,
        security_warnings=warnings,
        stats=stats,
        weekdays=WEEKDAYS,
    )


@app.route("/admin/maintenance", methods=["GET", "POST"])
def admin_maintenance():
    login_response = require_admin_login()
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    actor_id, actor_name = web_actor()

    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
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
                    "maintenance_backup_manual",
                    actor_id,
                    actor_name,
                    "backup",
                    backup_path.name if backup_path else "",
                    message,
                )
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=message,
                error=0 if created else 1,
            ))
        if action == "restore_test":
            try:
                passed, backup_path, message = run_manual_restore_test()
            except (OSError, sqlite3.Error) as restore_error:
                passed = False
                backup_path = None
                message = f"Restore test failed: {restore_error}"
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "maintenance_restore_test",
                    actor_id,
                    actor_name,
                    "backup",
                    backup_path.name if backup_path else "",
                    message,
                )
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=message,
                error=0 if passed else 1,
            ))

    media_stats = media_directory_stats()
    config_data = load_config()
    uptime_seconds = int(
        (datetime.now(timezone.utc) - APP_STARTED_AT).total_seconds()
    )
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    with closing(connect_db()) as connection:
        restore_runs = connection.execute("""
            SELECT run_key, backup_name, status, details, created_at
            FROM restore_test_runs
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()

    return render_template_string(
        MAINTENANCE_HTML,
        admin_key=ADMIN_KEY,
        backups=recent_database_backups(),
        cache_entries=len(PUBLIC_PAGE_CACHE),
        csrf_token=get_csrf_token(),
        db_file=DB_FILE,
        db_size=format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B",
        error=error,
        media_files=media_stats["files"],
        media_size=format_bytes(media_stats["bytes"]),
        notice=notice,
        release=os.getenv("SDAC_RELEASE") or "development",
        restore_runs=restore_runs,
        server_name=os.getenv("SDAC_SERVER_NAME") or "local",
        started_at=APP_STARTED_AT.strftime("%Y-%m-%d %H:%M UTC"),
        uptime=f"{days}d {hours}h {minutes}m",
        warnings=security_warnings() + storage_warnings(config_data),
    )


@app.route("/admin/moderation")
def admin_moderation():
    login_response = require_admin_login()
    if login_response:
        return login_response

    config_data = load_config()
    guild_names = guild_name_map(config_data)
    with closing(connect_db()) as connection:
        pending_rows = connection.execute("""
            SELECT *
            FROM submissions
            WHERE status = 'pending'
            ORDER BY created_at DESC, id DESC
            LIMIT 50
        """).fetchall()
        history = connection.execute("""
            SELECT guild_id, submission_id, action, actor_username,
                   details, created_at
            FROM moderation_history
            ORDER BY created_at DESC, id DESC
            LIMIT 50
        """).fetchall()
    pending_posts = [prepare_post(row) for row in pending_rows]
    return render_template_string(
        MODERATION_HTML,
        admin_key=ADMIN_KEY,
        guild_names=guild_names,
        history=history,
        pending_posts=pending_posts,
    )


@app.route("/admin/onboarding")
def admin_onboarding():
    login_response = require_admin_login()
    if login_response:
        return login_response

    config_data = load_config()
    return render_template_string(
        ONBOARDING_HTML,
        admin_key=ADMIN_KEY,
        servers=build_onboarding_rows(config_data),
    )


@app.route("/")
def index():
    config_data = load_config()
    server_options = guild_options(config_data)
    guild_names = guild_name_map(config_data)
    selected_server_id = selected_guild_id(server_options)
    selected_server_name = (
        guild_names.get(selected_server_id, "Selected Server")
        if selected_server_id
        else "All Discord Servers"
    )
    selected_category = request.args.get("category", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_sort = request.args.get("sort", "newest").strip()
    selected_month = request.args.get("month", "").strip()
    search_query = request.args.get("q", "").strip()
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

    public_cache_key = None
    if not is_admin and not notice and not error and request.method == "GET":
        public_cache_key = cache_key(
            "index",
            selected_server_id or "all",
            selected_category,
            selected_sort,
            selected_month,
            search_query,
            page,
        )
        cached = cached_public_page(public_cache_key)
        if cached is not None:
            return cached

    with closing(connect_db()) as connection:
        months = available_submission_months(connection, selected_server_id)
        category_conditions = ["category IS NOT NULL", "category != ''"]
        category_parameters = []
        if not is_admin:
            category_conditions.append("status = 'posted'")
        if selected_server_id:
            category_conditions.append("guild_id = ?")
            category_parameters.append(selected_server_id)
        category_where = " WHERE " + " AND ".join(category_conditions)
        categories = [
            row["category"]
            for row in connection.execute(f"""
                SELECT DISTINCT category
                FROM submissions
                {category_where}
                ORDER BY category
            """, category_parameters)
        ]

        if selected_month:
            preserve_monthly_submission_top(connection, selected_month)
            connection.commit()
            where = ["month = ?"]
            parameters = [selected_month]
            if selected_server_id:
                where.append("guild_id = ?")
                parameters.append(selected_server_id)
            if selected_category:
                where.append("category = ?")
                parameters.append(selected_category)
            if search_query:
                where.append("""
                    (
                        CAST(submission_id AS TEXT) = ?
                        OR username LIKE ?
                        OR category LIKE ?
                        OR message_text LIKE ?
                    )
                """)
                like_query = f"%{search_query}%"
                parameters.extend([
                    search_query,
                    like_query,
                    like_query,
                    like_query,
                ])
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
                        media_sizes,
                        media_metadata_json,
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
            if selected_server_id:
                where.append("guild_id = ?")
                parameters.append(selected_server_id)
            if selected_category:
                where.append("category = ?")
                parameters.append(selected_category)
            if search_query:
                where.append("""
                    (
                        CAST(id AS TEXT) = ?
                        OR username LIKE ?
                        OR category LIKE ?
                        OR message_text LIKE ?
                    )
                """)
                like_query = f"%{search_query}%"
                parameters.extend([
                    search_query,
                    like_query,
                    like_query,
                    like_query,
                ])

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
        post["guild_name"] = guild_names.get(
            post.get("guild_id"),
            f"Discord {post.get('guild_id')}" if post.get("guild_id") else "",
        )
        grouped_posts.setdefault(
            post["category"] or "Uncategorized",
            [],
        ).append(post)

    def page_url(page_number):
        values = {
            "category": selected_category,
            "month": selected_month,
            "page": page_number,
            "q": search_query,
            "sort": selected_sort,
            "guild_id": selected_server_id or "all",
        }
        if is_admin:
            values["key"] = ADMIN_KEY
            values["status"] = selected_status
        return url_for("index", **values)

    rendered = render_template_string(
        HTML,
        admin_key=ADMIN_KEY,
        categories=categories,
        error=error,
        grouped_posts=grouped_posts,
        csrf_token=get_csrf_token() if is_admin else "",
        guild_options=server_options,
        is_admin=is_admin,
        months=months,
        notice=notice,
        page=page,
        page_url=page_url,
        selected_category=selected_category,
        selected_guild_name=selected_server_name,
        selected_guild_id=selected_server_id,
        selected_month=selected_month,
        search_query=search_query,
        selected_sort=selected_sort,
        selected_status=selected_status,
        total_pages=total_pages,
    )
    if public_cache_key:
        return store_public_page(public_cache_key, rendered)
    return rendered


@app.route("/audit")
def audit_log():
    login_response = require_admin_login()
    if login_response:
        return login_response

    page = positive_page(request.args.get("page"))
    config_data = load_config()
    server_options = guild_options(config_data)
    selected_server_id = request.args.get("guild_id", "").strip()
    if selected_server_id == "all":
        selected_server_id = ""
    valid_server_ids = {option["id"] for option in server_options}
    if selected_server_id and selected_server_id not in valid_server_ids:
        selected_server_id = ""
    action_filter = request.args.get("action", "").strip()
    search_query = request.args.get("q", "").strip()

    base_query = """
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
            UNION ALL
            SELECT
                id,
                guild_id,
                'rate_limit_' || bucket AS action,
                user_id AS actor_user_id,
                username AS actor_username,
                action AS target_type,
                CAST(retry_after_seconds AS TEXT) AS target_id,
                details,
                created_at
            FROM rate_limit_events
        )
    """
    where = []
    parameters = []
    if selected_server_id:
        where.append("guild_id = ?")
        parameters.append(selected_server_id)
    if action_filter:
        where.append("action = ?")
        parameters.append(action_filter)
    if search_query:
        where.append("""
            (
                action LIKE ?
                OR actor_username LIKE ?
                OR target_type LIKE ?
                OR target_id LIKE ?
                OR details LIKE ?
            )
        """)
        like_query = f"%{search_query}%"
        parameters.extend([like_query] * 5)
    where_sql = " WHERE " + " AND ".join(where) if where else ""

    with closing(connect_db()) as connection:
        action_options = [
            row["action"]
            for row in connection.execute(f"""
                SELECT DISTINCT action
                FROM ({base_query})
                WHERE action IS NOT NULL AND action != ''
                ORDER BY action
            """)
        ]
        total_items = connection.execute(
            f"SELECT COUNT(*) FROM ({base_query}{where_sql})",
            parameters,
        ).fetchone()[0]
        total_pages = max(1, math.ceil(total_items / PAGE_SIZE))
        page = min(page, total_pages)
        rows = connection.execute(f"""
            {base_query}
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """, parameters + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()

    return render_template_string(
        AUDIT_HTML,
        action_filter=action_filter,
        action_options=action_options,
        admin_key=ADMIN_KEY,
        guild_options=server_options,
        page=page,
        rows=rows,
        search_query=search_query,
        selected_guild_id=selected_server_id,
        total_pages=total_pages,
    )


@app.route("/guessing")
def guessing_leaderboard():
    config_data = load_config()
    server_options = guild_options(config_data)
    guild_names = guild_name_map(config_data)
    selected_server_id = selected_guild_id(server_options)
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    month = request.args.get("month", "").strip()
    page = positive_page(request.args.get("page"))

    public_cache_key = None
    if not is_admin and request.method == "GET":
        public_cache_key = cache_key(
            "guessing",
            selected_server_id or "all",
            month or current_month_key(),
            page,
        )
        cached = cached_public_page(public_cache_key)
        if cached is not None:
            return cached

    with closing(connect_db()) as connection:
        months = available_guess_months(connection)
        if not month:
            month = months[0] if months else current_month_key()
        total_cross = connection.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT user_id
                FROM guess_points
                WHERE month = ?
                GROUP BY user_id
            )
        """, (month,)).fetchone()[0]
        total_pages = max(1, math.ceil(total_cross / PAGE_SIZE))
        page = min(page, total_pages)
        cross_server_scores = connection.execute("""
            SELECT
                COALESCE(MAX(NULLIF(username, '')), user_id) AS username,
                SUM(points) AS points,
                COUNT(DISTINCT guild_id) AS server_count
            FROM guess_points
            WHERE month = ?
            GROUP BY user_id
            ORDER BY points DESC, username ASC
            LIMIT ? OFFSET ?
        """, (month, PAGE_SIZE, (page - 1) * PAGE_SIZE)).fetchall()

        where = ["month = ?"]
        parameters = [month]
        if selected_server_id:
            where.append("guild_id = ?")
            parameters.append(selected_server_id)
        rows = connection.execute(f"""
            SELECT guild_id, channel_id, username, points
            FROM guess_points
            WHERE {" AND ".join(where)}
            ORDER BY guild_id ASC, channel_id ASC, points DESC, username ASC
        """, parameters).fetchall()

    grouped_lookup = {}
    for row in rows:
        key = (row["guild_id"], row["channel_id"])
        if key not in grouped_lookup:
            grouped_lookup[key] = {
                "guild_id": row["guild_id"],
                "guild_name": guild_names.get(
                    row["guild_id"],
                    f"Discord {row['guild_id']}",
                ),
                "channel_id": row["channel_id"],
                "rows": [],
            }
        grouped_lookup[key]["rows"].append(row)
    grouped_scores = list(grouped_lookup.values())

    selected_guild_name = (
        guild_names.get(selected_server_id, "Selected Server")
        if selected_server_id
        else "All Servers"
    )

    def page_url(page_number):
        values = {
            "guild_id": selected_server_id or "all",
            "month": month,
            "page": page_number,
        }
        if is_admin:
            values["key"] = ADMIN_KEY
        return url_for("guessing_leaderboard", **values)

    rendered = render_template_string(
        GUESSING_HTML,
        admin_key=ADMIN_KEY,
        cross_server_scores=cross_server_scores,
        grouped_scores=grouped_scores,
        guild_options=server_options,
        is_admin=is_admin,
        month=month,
        months=months,
        page=page,
        page_url=page_url,
        selected_guild_id=selected_server_id,
        selected_guild_name=selected_guild_name,
        total_pages=total_pages,
    )
    if public_cache_key:
        return store_public_page(public_cache_key, rendered)
    return rendered


@app.route("/servers")
def servers():
    config_data = load_config()
    options = guild_options(config_data)
    with closing(connect_db()) as connection:
        rows = []
        for option in options:
            submissions = connection.execute("""
                SELECT COUNT(*)
                FROM submissions
                WHERE guild_id = ? AND status = 'posted'
            """, (option["id"],)).fetchone()[0]
            guess_points = connection.execute("""
                SELECT COALESCE(SUM(points), 0)
                FROM guess_points
                WHERE guild_id = ?
            """, (option["id"],)).fetchone()[0]
            categories = len(
                (config_data.get("guilds") or {})
                .get(option["id"], {})
                .get("categories", {})
            )
            rows.append({
                "id": option["id"],
                "name": option["name"],
                "submissions": submissions,
                "guess_points": guess_points,
                "categories": categories,
            })
    return render_template_string(SERVERS_HTML, servers=rows)


@app.route("/server/<guild_id>")
def server_profile(guild_id):
    config_data = load_config()
    names = guild_name_map(config_data)
    if guild_id not in names:
        abort(404)
    with closing(connect_db()) as connection:
        stats = {
            "submissions": connection.execute("""
                SELECT COUNT(*)
                FROM submissions
                WHERE guild_id = ? AND status = 'posted'
            """, (guild_id,)).fetchone()[0],
            "guess_points": connection.execute("""
                SELECT COALESCE(SUM(points), 0)
                FROM guess_points
                WHERE guild_id = ?
            """, (guild_id,)).fetchone()[0],
            "categories": len(
                (config_data.get("guilds") or {})
                .get(guild_id, {})
                .get("categories", {})
            ),
        }
        top_posts = connection.execute("""
            SELECT username, category, stars
            FROM submissions
            WHERE guild_id = ? AND status = 'posted'
            ORDER BY stars DESC, created_at DESC
            LIMIT 5
        """, (guild_id,)).fetchall()
        top_guessers = connection.execute("""
            SELECT username, SUM(points) AS points
            FROM guess_points
            WHERE guild_id = ?
            GROUP BY user_id
            ORDER BY points DESC, username ASC
            LIMIT 5
        """, (guild_id,)).fetchall()
    return render_template_string(
        SERVER_PROFILE_HTML,
        server={"id": guild_id, "name": names[guild_id]},
        stats=stats,
        top_guessers=top_guessers,
        top_posts=top_posts,
    )


@app.route("/achievements")
def achievements():
    config_data = load_config()
    server_options = guild_options(config_data)
    selected_server_id = selected_guild_id(server_options)
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    month = request.args.get("month", "").strip()

    with closing(connect_db()) as connection:
        months = available_guess_months(connection)
        for submission_month in available_submission_months(
            connection,
            selected_server_id,
        ):
            if submission_month not in months:
                months.append(submission_month)
        months = sorted(months, reverse=True)
        if not month:
            month = months[0] if months else current_month_key()

        guess_where = ["month = ?"]
        guess_params = [month]
        submission_where = [
            "status = 'posted'",
            "substr(COALESCE(created_at, submitted_at), 1, 7) = ?",
        ]
        submission_params = [month]
        if selected_server_id:
            guess_where.append("guild_id = ?")
            guess_params.append(selected_server_id)
            submission_where.append("guild_id = ?")
            submission_params.append(selected_server_id)

        top_guesser = connection.execute(f"""
            SELECT username, SUM(points) AS points
            FROM guess_points
            WHERE {" AND ".join(guess_where)}
            GROUP BY user_id
            ORDER BY points DESC, username ASC
            LIMIT 1
        """, guess_params).fetchone()
        top_submission = connection.execute(f"""
            SELECT username, category, stars
            FROM submissions
            WHERE {" AND ".join(submission_where)}
            ORDER BY stars DESC, created_at DESC
            LIMIT 1
        """, submission_params).fetchone()
        top_submitter = connection.execute(f"""
            SELECT username, COUNT(*) AS submission_count
            FROM submissions
            WHERE {" AND ".join(submission_where)}
            GROUP BY user_id
            ORDER BY submission_count DESC, username ASC
            LIMIT 1
        """, submission_params).fetchone()

    return render_template_string(
        ACHIEVEMENTS_HTML,
        admin_key=ADMIN_KEY,
        guild_options=server_options,
        is_admin=is_admin,
        month=month,
        months=months,
        selected_guild_id=selected_server_id,
        top_guesser=top_guesser,
        top_submission=top_submission,
        top_submitter=top_submitter,
    )


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "sdac-dashboard",
    })


@app.route("/admin/health")
def admin_health():
    login_response = require_admin_login()
    if login_response:
        return login_response

    media_stats = media_directory_stats()
    with closing(connect_db()) as connection:
        schema_row = connection.execute("""
            SELECT version, updated_at
            FROM schema_version
            WHERE id = 1
        """).fetchone()
        payload = {
            "ok": True,
            "service": "sdac-dashboard",
            "schema_version": schema_row["version"] if schema_row else None,
            "schema_updated_at": schema_row["updated_at"] if schema_row else None,
            "expected_schema_version": SCHEMA_VERSION,
            "uptime_seconds": int(
                (datetime.now(timezone.utc) - APP_STARTED_AT).total_seconds()
            ),
            "db_size_bytes": DB_FILE.stat().st_size if DB_FILE.exists() else 0,
            "media_size_bytes": media_stats["bytes"],
            "media_file_count": media_stats["files"],
            "submissions": connection.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0],
            "active_games": connection.execute("""
                SELECT COUNT(*)
                FROM guess_games
                WHERE status = 'active'
            """).fetchone()[0],
            "rate_limit_events": connection.execute("""
                SELECT COUNT(*)
                FROM rate_limit_events
            """).fetchone()[0],
            "cache_entries": len(PUBLIC_PAGE_CACHE),
            "login_rate_limit_entries": len(LOGIN_ATTEMPTS),
        }
    return jsonify(payload)


@app.route("/export/submissions.csv")
def export_submissions():
    login_response = require_admin_login()
    if login_response:
        return login_response
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT id, guild_id, user_id, username, category, stars,
                   status, media_sizes, media_metadata_json,
                   created_at, submitted_at
            FROM submissions
            ORDER BY created_at DESC, id DESC
        """).fetchall()
    return csv_response(
        "sdac-submissions.csv",
        rows,
        [
            "id",
            "guild_id",
            "user_id",
            "username",
            "category",
            "stars",
            "status",
            "media_sizes",
            "media_metadata_json",
            "created_at",
            "submitted_at",
        ],
    )


@app.route("/export/guessing.csv")
def export_guessing():
    login_response = require_admin_login()
    if login_response:
        return login_response
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT guild_id, channel_id, user_id, username, month, points,
                   updated_at
            FROM guess_points
            ORDER BY month DESC, points DESC
        """).fetchall()
    return csv_response(
        "sdac-guessing.csv",
        rows,
        ["guild_id", "channel_id", "user_id", "username", "month", "points", "updated_at"],
    )


@app.route("/export/audit.csv")
def export_audit():
    login_response = require_admin_login()
    if login_response:
        return login_response
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT guild_id, action, actor_user_id, actor_username,
                   target_type, target_id, details, created_at
            FROM (
                SELECT id AS sort_id, guild_id, action, actor_user_id, actor_username,
                       target_type, target_id, details, created_at
                FROM admin_audit_log
                UNION ALL
                SELECT id AS sort_id, guild_id, 'moderation_' || action AS action,
                       actor_user_id, actor_username,
                       'submission' AS target_type,
                       CAST(submission_id AS TEXT) AS target_id,
                       details, created_at
                FROM moderation_history
                UNION ALL
                SELECT id AS sort_id, guild_id, 'rate_limit_' || bucket AS action,
                       user_id AS actor_user_id, username AS actor_username,
                       action AS target_type,
                       CAST(retry_after_seconds AS TEXT) AS target_id,
                       details, created_at
                FROM rate_limit_events
            )
            ORDER BY created_at DESC, sort_id DESC
        """).fetchall()
    return csv_response(
        "sdac-audit.csv",
        rows,
        ["guild_id", "action", "actor_user_id", "actor_username", "target_type", "target_id", "details", "created_at"],
    )


@app.route("/media/<path:filename>")
def serve_media(filename):
    resolved_path = (MEDIA_DIR / filename).resolve()
    try:
        resolved_path.relative_to(MEDIA_DIR)
    except ValueError:
        abort(404)
    if not resolved_path.is_file():
        abort(404)
    return send_from_directory(MEDIA_DIR, filename)


@app.post("/delete/<int:submission_id>")
def delete_submission(submission_id):
    login_response = require_admin_login()
    if login_response:
        return login_response
    require_csrf_token()

    selected_category = request.args.get("category", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_server_id = request.args.get("guild_id", "all").strip()
    page = positive_page(request.args.get("page"))

    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    redirect_values = {
        "key": ADMIN_KEY,
        "category": selected_category,
        "guild_id": selected_server_id or "all",
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
    PUBLIC_PAGE_CACHE.clear()
    return redirect(url_for(
        "index",
        notice="Submission removed from the website and Discord.",
        **redirect_values,
    ))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
