import csv
import io
import math
import os
import json
import re
import shlex
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
BOT_STATUS_FILE = BASE_DIR / "bot_status.json"
BACKUP_KEEP_COUNT = 30
CONFIG_BACKUP_KEEP_COUNT = 30
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
ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".mov", ".webm", ".mkv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a",
}
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

DEFAULT_FEATURES = {
    "submissions": True,
    "approval_queue": True,
    "guessing_games": True,
    "weekly_posts": True,
    "public_gallery": True,
    "cross_server_leaderboard": True,
}

FEATURE_LABELS = {
    "submissions": "Submissions",
    "approval_queue": "Approval Queue",
    "guessing_games": "Guessing Games",
    "weekly_posts": "Weekly Posts",
    "public_gallery": "Public Gallery",
    "cross_server_leaderboard": "Cross-Server Leaderboard",
}

DEFAULT_GUILD_FIELDS = {
    "guild_name": "",
    "brand_name": "",
    "brand_accent": "#7c9cff",
    "brand_logo_url": "",
    "setup_preset": "",
    "admin_role_ids": [],
    "submit_channel": None,
    "daily_top_channel": None,
    "daily_top_time_utc": "00:00",
    "weekly_top_day": "sunday",
    "game_summary_channel": None,
    "error_channel": None,
    "timezone": "UTC",
    "approval_enabled": False,
    "approval_channel": None,
    "categories": {},
    "features": DEFAULT_FEATURES,
}

RELEASE_REPO = os.getenv("SDAC_GITHUB_REPO", "BaytaeTistear/SDAC-Bot")
UPDATE_ENV_FILE = Path(os.getenv("SDAC_UPDATE_CONFIG", "/etc/sdac-bot/update.env"))
RELEASE_CACHE = {
    "expires_at": 0,
    "status": None,
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
            <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
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
                                &middot;
                                <a href="{{ url_for('user_profile', user_id=post.user_id, guild_id=post.guild_id or 'all', key=admin_key if is_admin else None) }}">{{ post.username }}</a>
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
                        <p class="meta">
                            <a href="{{ url_for('report_submission', submission_id=post.id) }}">Report this submission</a>
                        </p>
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


REPORT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Report Submission</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 40px auto; padding: 24px; width: min(100%, 640px); }
        a { color: #7c9cff; }
        label { display: block; font-weight: bold; margin: 16px 0 6px; }
        input, textarea, button { border: 1px solid #30333b; border-radius: 7px; font-size: 16px; padding: 10px 12px; width: 100%; }
        textarea { min-height: 130px; resize: vertical; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; margin-top: 16px; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 12px; }
        .error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
    </style>
</head>
<body>
<main>
    <h1>Report Submission {{ submission.id }}</h1>
    <p class="muted">
        {{ submission.username }} &middot; {{ submission.category }}
        {% if submission.guild_name %}&middot; {{ submission.guild_name }}{% endif %}
    </p>
    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}
    <form method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <label for="reporter_name">Your name or Discord username</label>
        <input id="reporter_name" name="reporter_name" maxlength="120" placeholder="Optional">
        <label for="reason">What should admins review?</label>
        <textarea id="reason" name="reason" maxlength="1000" required></textarea>
        <button type="submit">Send Report</button>
    </form>
    <p><a href="{{ url_for('index', guild_id=submission.guild_id or 'all') }}">Back to submissions</a></p>
</main>
</body>
</html>
"""


USER_PROFILE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ profile.username }} - SDAC Profile</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; }
        .muted { color: #a8adb8; }
    </style>
</head>
<body>
<main>
    <h1>{{ profile.username }}</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key if is_admin else None, guild_id=selected_guild_id or 'all') }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None, guild_id=selected_guild_id or 'all') }}">Guessing leaderboard</a>
    </nav>
    <section class="panel">
        <h2>Stats</h2>
        <p>Submissions: {{ profile.submissions }}</p>
        <p>Total votes: {{ profile.total_votes }}</p>
        <p>Guessing points: {{ profile.guess_points }}</p>
        <p>Correct guesses: {{ profile.correct_guesses }}</p>
    </section>
    <section class="panel">
        <h2>Recent Submissions</h2>
        <table>
            <thead><tr><th>ID</th><th>Server</th><th>Category</th><th>Votes</th><th>Created</th></tr></thead>
            <tbody>
                {% for post in posts %}
                    <tr>
                        <td><a href="{{ url_for('index', q=post.id, guild_id=post.guild_id or 'all', key=admin_key if is_admin else None) }}">{{ post.id }}</a></td>
                        <td>{{ guild_names.get(post.guild_id, post.guild_id) }}</td>
                        <td>{{ post.category }}</td>
                        <td>{{ post.stars or 0 }}</td>
                        <td>{{ post.created_at or post.submitted_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="muted">No public submissions yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
    <section class="panel">
        <h2>Guessing Points By Month</h2>
        <table>
            <thead><tr><th>Month</th><th>Points</th></tr></thead>
            <tbody>
                {% for row in monthly_points %}
                    <tr><td>{{ row.month }}</td><td>{{ row.points }}</td></tr>
                {% else %}
                    <tr><td colspan="2" class="muted">No points yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
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
    <nav><a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a></nav>
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
            <input name="actor" value="{{ actor_filter }}" placeholder="Actor user/name">
            <input type="date" name="date_from" value="{{ date_from }}">
            <input type="date" name="date_to" value="{{ date_to }}">
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
            <a href="{{ url_for('audit_log', key=admin_key, page=page - 1, guild_id=selected_guild_id or 'all', action=action_filter, q=search_query, actor=actor_filter, date_from=date_from, date_to=date_to) }}">Previous</a>
        {% else %}
            <span class="disabled">Previous</span>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
            <a href="{{ url_for('audit_log', key=admin_key, page=page + 1, guild_id=selected_guild_id or 'all', action=action_filter, q=search_query, actor=actor_filter, date_from=date_from, date_to=date_to) }}">Next</a>
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
            <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
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


GAME_LIBRARY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Game Library</title>
    <style>
        :root { color-scheme: dark; }
        body {
            background: #101114;
            color: #f4f5f7;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 24px;
        }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav {
            display: flex;
            flex-wrap: wrap;
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
        input, select, textarea, button {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 15px;
            padding: 9px 10px;
        }
        input, select, textarea { width: 100%; }
        textarea { min-height: 84px; resize: vertical; }
        button {
            background: #7c9cff;
            color: #0b1020;
            cursor: pointer;
            font-weight: bold;
            width: auto;
        }
        .danger {
            background: #e45d68;
            color: white;
        }
        .notice {
            border: 1px solid #30333b;
            border-radius: 8px;
            margin: 0 auto 20px;
            padding: 12px;
            text-align: center;
        }
        .notice.error { border-color: #e45d68; }
        .grid {
            display: grid;
            gap: 12px;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        }
        .actions form {
            display: inline-block;
            margin: 0 6px 6px 0;
        }
        .actions button { padding: 7px 9px; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Game Library</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>
    {% endif %}

    <section class="panel">
        <h2>Add Guess Item</h2>
        <p class="muted">
            Add reusable media and answers here, then start one in Discord with
            <code>/startlibrarygame #channel item_id</code>. Use <code>|</code>
            between alternate answers, for example <code>Jack Black|Jables</code>.
            Matching ignores capitalization and special characters.
        </p>
        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <input type="hidden" name="action" value="create_item">
            <div class="grid">
                <label>Discord server
                    <select name="guild_id" required>
                        {% for guild in guild_options %}
                            <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                        {% endfor %}
                    </select>
                </label>
                <label>Title
                    <input name="title" maxlength="120" placeholder="Optional display title">
                </label>
                <label>Answer and aliases
                    <input name="answer" required maxlength="300" placeholder="Minecraft: The Movie | Minecraft Movie">
                </label>
                <label>Category
                    <input name="category" maxlength="80" placeholder="movie, game, music, etc.">
                </label>
                <label>Auto hint minutes
                    <input name="auto_hint_minutes" type="number" min="0" max="1440" value="0">
                </label>
                <label>Media
                    <input name="media" type="file" required>
                </label>
            </div>
            <p class="muted">Maximum file size: {{ max_file_label }}.</p>
            <label>Prompt text
                <textarea name="prompt_text" maxlength="{{ max_text_length }}" placeholder="Optional text shown with the media"></textarea>
            </label>
            <label>Custom hint
                <textarea name="hint_text" maxlength="500" placeholder="Optional hint included in generated hints"></textarea>
            </label>
            <p><button type="submit">Add Library Item</button></p>
        </form>
    </section>

    <section class="panel">
        <h2>Bulk Import Answer Drafts</h2>
        <p class="muted">
            Upload a CSV to add many guess answers at once. Supported columns:
            <code>title</code>, <code>answer</code>, <code>aliases</code>,
            <code>category</code>, <code>hint</code>, <code>prompt_text</code>,
            <code>auto_hint_minutes</code>, and optional <code>status</code>.
            Rows without valid media stay as drafts, so they will not be chosen
            by <code>/startlibrarygame</code> until media is added through a normal item.
        </p>
        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <input type="hidden" name="action" value="bulk_import">
            <div class="grid">
                <label>Discord server
                    <select name="guild_id" required>
                        {% for guild in guild_options %}
                            <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                        {% endfor %}
                    </select>
                </label>
                <label>CSV file
                    <input name="csv_file" type="file" accept=".csv,text/csv" required>
                </label>
            </div>
            <p><button type="submit">Import Drafts</button></p>
        </form>
    </section>

    <section class="panel">
        <h2>Saved Items</h2>
        <form method="get">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <select name="guild_id">
                <option value="all">All Discord Servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                {% endfor %}
            </select>
            <button type="submit">Filter</button>
        </form>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Server</th>
                    <th>Title / Answer</th>
                    <th>Media</th>
                    <th>Status</th>
                    <th>Used</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                    <tr>
                        <td><code>{{ item.id }}</code></td>
                        <td>{{ item.guild_name }}</td>
                        <td>
                            <strong>{{ item.title or item.answer_display }}</strong><br>
                            Answer: <code>{{ item.answer_display }}</code><br>
                            Aliases: {{ item.alias_count }}<br>
                            {% if item.category %}Category: {{ item.category }}<br>{% endif %}
                            {% if item.prompt_text %}<span class="muted">{{ item.prompt_text }}</span>{% endif %}
                        </td>
                        <td>
                            {% if item.media_url %}
                                <a href="{{ item.media_url }}" target="_blank">{{ item.media_name }}</a>
                            {% else %}
                                <span class="muted">No media attached</span>
                            {% endif %}
                            <br>{{ item.media_type }}{% if item.size_label %} - {{ item.size_label }}{% endif %}
                        </td>
                        <td><code>{{ item.status }}</code></td>
                        <td>
                            {{ item.times_used or 0 }} time(s)<br>
                            <span class="muted">Last: {{ item.last_used_at or "Never" }}</span><br>
                            <span class="muted">Created: {{ item.created_at or "" }}</span>
                        </td>
                        <td class="actions">
                            {% if item.media_url %}
                                <form method="post">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="action" value="set_status">
                                    <input type="hidden" name="guild_id" value="{{ selected_guild_id or 'all' }}">
                                    <input type="hidden" name="item_id" value="{{ item.id }}">
                                    <input type="hidden" name="status" value="{{ 'disabled' if item.status == 'active' else 'active' }}">
                                    <button type="submit">{{ 'Disable' if item.status == 'active' else 'Enable' }}</button>
                                </form>
                            {% else %}
                                <span class="muted">Create a media item to activate.</span>
                            {% endif %}
                            <form method="post">
                                <input type="hidden" name="key" value="{{ admin_key }}">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                <input type="hidden" name="action" value="delete_item">
                                <input type="hidden" name="guild_id" value="{{ selected_guild_id or 'all' }}">
                                <input type="hidden" name="item_id" value="{{ item.id }}">
                                <button class="danger" type="submit">Delete</button>
                            </form>
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" class="muted">No game library items yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
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
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
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
                        <tr><th>Brand display name</th><td><input name="brand_name" value="{{ guild.brand_name }}"></td></tr>
                        <tr><th>Brand accent</th><td><input name="brand_accent" value="{{ guild.brand_accent }}" placeholder="#7c9cff"></td></tr>
                        <tr><th>Brand logo URL</th><td><input name="brand_logo_url" value="{{ guild.brand_logo_url }}"></td></tr>
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
                        {% for feature in guild.features %}
                            <tr><th>{{ feature.label }}</th><td>
                                <select name="feature_{{ feature.key }}">
                                    <option value="1" {% if feature.enabled %}selected{% endif %}>Enabled</option>
                                    <option value="0" {% if not feature.enabled %}selected{% endif %}>Disabled</option>
                                </select>
                            </td></tr>
                        {% endfor %}
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
                    <tr><th>Brand display name</th><td>{{ guild.brand_name or guild.name }}</td></tr>
                    <tr><th>Brand accent</th><td><code>{{ guild.brand_accent }}</code></td></tr>
                    <tr><th>Brand logo URL</th><td>{{ guild.brand_logo_url or "Not set" }}</td></tr>
                    <tr><th>Timezone</th><td><code>{{ guild.timezone }}</code></td></tr>
                    <tr><th>Submit channel</th><td>{{ guild.submit_channel or "Not set" }}</td></tr>
                    <tr><th>Weekly channel</th><td>{{ guild.daily_top_channel or "Not set" }}</td></tr>
                    <tr><th>Weekly day</th><td>{{ guild.weekly_top_day }}</td></tr>
                    <tr><th>Weekly time</th><td>{{ guild.daily_top_time_utc }} {{ guild.timezone }}</td></tr>
                    <tr><th>Approval</th><td>{{ "Enabled" if guild.approval_enabled else "Disabled" }}</td></tr>
                    <tr><th>Approval channel</th><td>{{ guild.approval_channel or "Not set" }}</td></tr>
                    <tr><th>Features</th><td>
                        {% for feature in guild.features %}
                            <div>{{ feature.label }}: <code>{{ "Enabled" if feature.enabled else "Disabled" }}</code></div>
                        {% endfor %}
                    </td></tr>
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
                <tr><th>File</th><th>Size</th><th>Modified</th><th>Download</th></tr>
            </thead>
            <tbody>
                {% for backup in backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                        <td><a href="{{ url_for('download_backup', name=backup.name, key=admin_key) }}">Download</a></td>
                    </tr>
                {% else %}
                    <tr><td colspan="4" class="muted">No backups found yet.</td></tr>
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
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
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
                <tr><th>Update repo</th><td><code>{{ release_status.repo }}</code></td></tr>
                <tr><th>Configured update tag</th><td><code>{{ release_status.configured_tag }}</code></td></tr>
                <tr><th>Latest official</th><td><code>{{ release_status.official.tag }}</code>{% if release_status.official.published_at %} ({{ release_status.official.published_at }}){% endif %}</td></tr>
                <tr><th>Latest experimental</th><td><code>{{ release_status.experimental.tag }}</code>{% if release_status.experimental.published_at %} ({{ release_status.experimental.published_at }}){% endif %}</td></tr>
                {% if release_status.error %}<tr><th>Release check</th><td>{{ release_status.error }}</td></tr>{% endif %}
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
        <h2>Bot Status</h2>
        <table>
            <tbody>
                <tr><th>Heartbeat</th><td class="{{ 'ok' if bot_status.fresh else 'bad' }}">{{ bot_status.message }}</td></tr>
                <tr><th>Updated</th><td>{{ bot_status.updated_at or "Unknown" }}</td></tr>
                <tr><th>Bot user</th><td>{{ bot_status.bot_user or "Unknown" }}</td></tr>
                <tr><th>Guild count</th><td>{{ bot_status.guild_count or 0 }}</td></tr>
                <tr><th>Slash commands synced</th><td>{{ "Yes" if bot_status.slash_commands_synced else "No" }}</td></tr>
                <tr><th>Last event</th><td>{{ bot_status.event or "Unknown" }}</td></tr>
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
            <button name="action" value="restore_config" type="submit">Restore Latest Config Backup</button>
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
            <thead><tr><th>File</th><th>Size</th><th>Modified</th><th>Download</th></tr></thead>
            <tbody>
                {% for backup in backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                        <td><a href="{{ url_for('download_backup', name=backup.name, key=admin_key) }}">Download</a></td>
                    </tr>
                {% else %}
                    <tr><td colspan="4" class="muted">No backups found yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Recent Config Backups</h2>
        <table>
            <thead><tr><th>File</th><th>Size</th><th>Modified</th></tr></thead>
            <tbody>
                {% for backup in config_backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="3" class="muted">No config backups found yet.</td></tr>
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
        input, button { border: 1px solid #30333b; border-radius: 7px; padding: 8px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin: 0 auto 20px; padding: 12px; text-align: center; }
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
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice">{{ notice }}</div>
    {% endif %}

    <section class="panel">
        <h2>Open Submission Reports</h2>
        <table>
            <thead><tr><th>Report</th><th>Submission</th><th>Server</th><th>Reporter</th><th>Reason</th><th>Created</th><th>Action</th></tr></thead>
            <tbody>
                {% for report in reports %}
                    <tr>
                        <td>{{ report.id }}</td>
                        <td><a href="{{ url_for('index', key=admin_key, q=report.submission_id, guild_id=report.guild_id or 'all') }}">{{ report.submission_id }}</a></td>
                        <td>{{ guild_names.get(report.guild_id, report.guild_id) }}</td>
                        <td>{{ report.reporter_name }}</td>
                        <td>{{ report.reason }}</td>
                        <td>{{ report.created_at }}</td>
                        <td>
                            <form method="post">
                                <input type="hidden" name="key" value="{{ admin_key }}">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                <input type="hidden" name="action" value="resolve_report">
                                <input type="hidden" name="report_id" value="{{ report.id }}">
                                <input name="admin_notes" placeholder="Notes">
                                <button type="submit">Mark Reviewed</button>
                            </form>
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" class="muted">No open reports.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

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
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% for server in servers %}
        <article class="server">
            <h2>{{ server.name }} <span class="muted">({{ server.id }})</span></h2>
            {% if server.guild_name != server.name or server.brand_logo_url %}
                <p>
                    Discord name: <code>{{ server.guild_name }}</code>
                    &middot; Accent: <code>{{ server.brand_accent }}</code>
                    {% if server.brand_logo_url %}&middot; Logo: <a href="{{ server.brand_logo_url }}" target="_blank">open</a>{% endif %}
                </p>
            {% endif %}
            <p>
                Setup health: <strong>{{ server.health_score }}%</strong>
                &middot; {{ server.complete_count }} of {{ server.total_count }} required item(s) complete
                &middot; {{ server.optional_complete_count }} of {{ server.optional_total_count }} recommended item(s) complete
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Item</th>
                        <th>How to fix</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in server["items"] %}
                        <tr>
                            <td class="{{ 'ok' if item.ok else 'missing' }}">{{ 'OK' if item.ok else 'Missing' }}</td>
                            <td>{{ item.label }}{% if item.optional %}<br><span class="muted">Recommended</span>{% endif %}</td>
                            <td><code>{{ item.fix }}</code></td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
            <h3>Quick Setup Wizard</h3>
            <ol>
                {% for command in server.command_steps %}
                    <li><code>{{ command }}</code></li>
                {% endfor %}
            </ol>
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
    for guild_config in (data.get("guilds") or {}).values():
        for key, value in DEFAULT_GUILD_FIELDS.items():
            if key not in guild_config:
                guild_config[key] = json.loads(json.dumps(value))
                changed = True
        features = guild_config.setdefault("features", {})
        for key, value in DEFAULT_FEATURES.items():
            if key not in features:
                features[key] = value
                changed = True
    if changed:
        save_config(data)
    return data


def cleanup_old_config_backups():
    if not BACKUP_DIR.exists():
        return
    backups = sorted(
        BACKUP_DIR.glob("config-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup_path in backups[CONFIG_BACKUP_KEEP_COUNT:]:
        try:
            backup_path.unlink()
        except OSError:
            pass


def backup_config_file(label="auto"):
    if not CONFIG_FILE.is_file():
        return None
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(label)).strip("-")
    safe_label = safe_label or "auto"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"config-{safe_label}-{stamp}.json"
    shutil.copy2(CONFIG_FILE, backup_path)
    cleanup_old_config_backups()
    return backup_path


def save_config(data):
    payload = json.dumps(data, indent=4) + "\n"
    if CONFIG_FILE.exists():
        try:
            if CONFIG_FILE.read_text(encoding="utf-8") == payload:
                return
        except OSError:
            pass
        backup_config_file()
    with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as file:
        file.write(payload)
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


def normalize_guess(value):
    cleaned = re.sub(r"[^\w\s]", " ", str(value or "").casefold())
    cleaned = re.sub(r"[_\s]+", " ", cleaned)
    return cleaned.strip()


def parse_answer_aliases(answer):
    aliases = []
    seen = set()
    for part in str(answer or "").split("|"):
        display = part.strip()
        normalized = normalize_guess(display)
        if not display or not normalized or normalized in seen:
            continue
        aliases.append({
            "display": display,
            "normalized": normalized,
        })
        seen.add(normalized)
    return aliases


def is_allowed_file(filename):
    return Path(filename or "").suffix.lower() in ALLOWED_EXTENSIONS


def get_media_type(filename):
    extension = Path(filename or "").suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if extension in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if extension in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
        return "audio"
    return "unknown"


def safe_upload_filename(filename):
    basename = Path(filename or "").name.replace("\\", "_")
    basename = re.sub(r"[^A-Za-z0-9_.-]+", "-", basename).strip("-")
    return basename or "media"


def guess_library_media_metadata(filename, path, content_type=""):
    try:
        size = Path(path).stat().st_size
    except OSError:
        size = 0
    media_type = get_media_type(filename)
    return {
        "filename": filename,
        "media_type": media_type,
        "size": int(size or 0),
        "size_label": format_bytes(int(size or 0)),
        "content_type": content_type or "",
    }


def save_guess_library_upload(guild_id, upload, limits):
    if upload is None or not upload.filename:
        raise ValueError("Game media is required.")
    if not is_allowed_file(upload.filename):
        raise ValueError("Game media must be an image, video, or audio file.")

    folder = MEDIA_DIR / str(guild_id) / "guess_library"
    folder.mkdir(parents=True, exist_ok=True)
    filename = safe_upload_filename(upload.filename)
    stored_name = f"{int(time.time())}-{secrets.token_hex(4)}-{filename}"
    path = folder / stored_name
    upload.save(path)

    size = path.stat().st_size if path.exists() else 0
    max_file_bytes = int(limits.get("max_file_bytes", 25 * 1024 * 1024))
    if size <= 0:
        try:
            path.unlink()
        except OSError:
            pass
        raise ValueError("Uploaded media was empty.")
    if max_file_bytes and size > max_file_bytes:
        try:
            path.unlink()
        except OSError:
            pass
        raise ValueError("Uploaded media exceeds the per-file size limit.")

    metadata = guess_library_media_metadata(
        filename,
        path,
        getattr(upload, "mimetype", "") or "",
    )
    return {
        "path": str(path),
        "name": filename,
        "type": metadata["media_type"],
        "size": size,
        "metadata": metadata,
    }


def delete_guess_library_media(stored_path):
    relative_path = media_relative_path(stored_path)
    if not relative_path:
        return
    file_path = (MEDIA_DIR / relative_path).resolve()
    try:
        file_path.relative_to(MEDIA_DIR)
    except ValueError:
        return
    if file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass


def validate_time(value):
    value = str(value or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", value):
        raise ValueError("Time must be HH:MM.")
    hour, minute = [int(part) for part in value.split(":")]
    if hour > 23 or minute > 59:
        raise ValueError("Time must be between 00:00 and 23:59.")
    return value


def feature_enabled(guild_config, feature):
    features = (guild_config or {}).get("features") or {}
    return bool(features.get(feature, DEFAULT_FEATURES.get(feature, True)))


def feature_guild_ids(config_data, feature):
    return {
        guild_id
        for guild_id, guild_config in (config_data.get("guilds") or {}).items()
        if feature_enabled(guild_config, feature)
    }


def guild_id_filter(column, guild_ids):
    guild_ids = sorted(str(guild_id) for guild_id in (guild_ids or set()))
    if not guild_ids:
        return "1 = 0", []
    placeholders = ", ".join("?" for _ in guild_ids)
    return f"{column} IN ({placeholders})", guild_ids


def guild_options(config_data=None, public_only=False):
    config_data = config_data or load_config()
    options = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items(),
        key=lambda item: (
            item[1].get("guild_name") or item[0]
        ).casefold(),
    ):
        if public_only and not feature_enabled(guild_config, "public_gallery"):
            continue
        display_name = (
            guild_config.get("brand_name")
            or guild_config.get("guild_name")
            or f"Discord {guild_id}"
        )
        options.append({
            "id": guild_id,
            "name": display_name,
            "guild_name": guild_config.get("guild_name") or display_name,
            "brand_accent": guild_config.get("brand_accent") or "#7c9cff",
            "brand_logo_url": guild_config.get("brand_logo_url") or "",
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
            onboarding_item(
                guild_config.get("brand_name"),
                "Server branding",
                "/setbranding name:#7c9cff",
                optional=True,
            ),
        ]
        required_items = [item for item in items if not item["optional"]]
        optional_items = [item for item in items if item["optional"]]
        weighted_total = len(required_items) * 2 + len(optional_items)
        weighted_complete = (
            sum(1 for item in required_items if item["ok"]) * 2
            + sum(1 for item in optional_items if item["ok"])
        )
        health_score = (
            round((weighted_complete / weighted_total) * 100)
            if weighted_total
            else 100
        )
        rows.append({
            "id": guild_id,
            "name": (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or f"Discord {guild_id}"
            ),
            "guild_name": guild_config.get("guild_name") or f"Discord {guild_id}",
            "brand_accent": guild_config.get("brand_accent") or "#7c9cff",
            "brand_logo_url": guild_config.get("brand_logo_url") or "",
            "command_steps": [
                "/setup",
                "/setupstatus",
                "/setuptest",
                "/settings",
                "/checkpermissions",
            ],
            "items": items,
            "complete_count": sum(1 for item in required_items if item["ok"]),
            "total_count": len(required_items),
            "optional_complete_count": sum(
                1 for item in optional_items if item["ok"]
            ),
            "optional_total_count": len(optional_items),
            "health_score": health_score,
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


def available_submission_months(connection, guild_id="", guild_ids=None):
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
    elif guild_ids is not None:
        submission_filter, submission_parameters = guild_id_filter(
            "guild_id",
            guild_ids,
        )
        submission_where += " AND " + submission_filter
        snapshot_filter, snapshot_parameters = guild_id_filter(
            "guild_id",
            guild_ids,
        )
        snapshot_where = "WHERE " + snapshot_filter

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


def available_guess_months(connection, guild_ids=None):
    where = "WHERE month IS NOT NULL AND month != ''"
    parameters = []
    if guild_ids is not None:
        guild_filter, parameters = guild_id_filter("guild_id", guild_ids)
        where += " AND " + guild_filter
    months = [
        row["month"]
        for row in connection.execute(f"""
            SELECT DISTINCT month
            FROM guess_points
            {where}
            ORDER BY month DESC
        """, parameters)
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
                hint_text TEXT,
                hint_revealed_at TEXT,
                answer_aliases_json TEXT,
                hints_json TEXT,
                hint_level INTEGER DEFAULT 0,
                next_hint_at TEXT,
                auto_hint_minutes INTEGER DEFAULT 0,
                hint_category TEXT,
                library_item_id INTEGER,
                status TEXT DEFAULT 'active',
                winner_user_id TEXT,
                winner_username TEXT,
                started_at TEXT,
                solved_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guess_library_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                title TEXT,
                answer TEXT,
                answer_display TEXT,
                answer_aliases_json TEXT,
                prompt_text TEXT,
                category TEXT,
                hint_text TEXT,
                auto_hint_minutes INTEGER DEFAULT 0,
                media_path TEXT,
                media_name TEXT,
                media_type TEXT,
                media_size INTEGER DEFAULT 0,
                media_metadata_json TEXT,
                status TEXT DEFAULT 'active',
                times_used INTEGER DEFAULT 0,
                last_used_at TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT
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
            CREATE TABLE IF NOT EXISTS submission_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER,
                guild_id TEXT,
                reporter_name TEXT,
                reason TEXT,
                status TEXT DEFAULT 'open',
                admin_notes TEXT,
                created_at TEXT,
                resolved_at TEXT
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
            "answer_aliases_json": "TEXT",
            "hints_json": "TEXT",
            "hint_level": "INTEGER DEFAULT 0",
            "next_hint_at": "TEXT",
            "auto_hint_minutes": "INTEGER DEFAULT 0",
            "hint_category": "TEXT",
            "library_item_id": "INTEGER",
        }.items():
            if column not in guess_columns:
                connection.execute(
                    f"ALTER TABLE guess_games ADD COLUMN {column} {definition}"
                )
        library_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(guess_library_items)"
            ).fetchall()
        }
        for column, definition in {
            "guild_id": "TEXT",
            "title": "TEXT",
            "answer": "TEXT",
            "answer_display": "TEXT",
            "answer_aliases_json": "TEXT",
            "prompt_text": "TEXT",
            "category": "TEXT",
            "hint_text": "TEXT",
            "auto_hint_minutes": "INTEGER DEFAULT 0",
            "media_path": "TEXT",
            "media_name": "TEXT",
            "media_type": "TEXT",
            "media_size": "INTEGER DEFAULT 0",
            "media_metadata_json": "TEXT",
            "status": "TEXT DEFAULT 'active'",
            "times_used": "INTEGER DEFAULT 0",
            "last_used_at": "TEXT",
            "created_by": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }.items():
            if column not in library_columns:
                connection.execute(
                    f"ALTER TABLE guess_library_items ADD COLUMN {column} {definition}"
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
            CREATE INDEX IF NOT EXISTS idx_guess_library_items_guild_status
            ON guess_library_items (guild_id, status, id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_library_items_last_used
            ON guess_library_items (guild_id, status, last_used_at)
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
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submission_reports_status
            ON submission_reports (status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submission_reports_submission
            ON submission_reports (submission_id)
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


def recent_config_backups():
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(
        BACKUP_DIR.glob("config-*.json"),
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


def latest_config_backup():
    backups = recent_config_backups()
    if not backups:
        return None
    backup_path = (BACKUP_DIR / backups[0]["name"]).resolve()
    try:
        backup_path.relative_to(BACKUP_DIR.resolve())
    except ValueError:
        return None
    return backup_path if backup_path.is_file() else None


def restore_latest_config_backup():
    backup_path = latest_config_backup()
    if backup_path is None:
        return None, False, "No config backup was found."
    backup_config_file("pre-restore")
    shutil.copy2(backup_path, CONFIG_FILE)
    PUBLIC_PAGE_CACHE.clear()
    return backup_path, True, f"Restored config backup {backup_path.name}."


def read_bot_status():
    if not BOT_STATUS_FILE.is_file():
        return {
            "available": False,
            "message": "No bot status heartbeat has been written yet.",
        }
    try:
        data = json.loads(BOT_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "message": f"Bot status file could not be read: {error}",
        }
    updated_at = data.get("updated_at") or ""
    age_seconds = None
    if updated_at:
        try:
            updated = datetime.fromisoformat(updated_at)
            age_seconds = int(
                (datetime.now(timezone.utc) - updated).total_seconds()
            )
        except ValueError:
            age_seconds = None
    data["available"] = True
    data["age_seconds"] = age_seconds
    data["fresh"] = age_seconds is not None and age_seconds <= 600
    data["message"] = (
        "Fresh heartbeat"
        if data["fresh"]
        else "Heartbeat is older than 10 minutes"
    )
    return data


def read_update_config():
    values = {}
    try:
        if not UPDATE_ENV_FILE.is_file():
            return values
        with UPDATE_ENV_FILE.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                key = key.strip()
                raw_value = raw_value.strip()
                try:
                    parsed = shlex.split(raw_value)
                    values[key] = parsed[0] if parsed else ""
                except ValueError:
                    values[key] = raw_value.strip("'\"")
    except OSError:
        return values
    return values


def fetch_github_release(tag):
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SDAC-Dashboard/2.5",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api_request = Request(
        f"https://api.github.com/repos/{RELEASE_REPO}/releases/tags/{tag}",
        headers=headers,
    )
    with urlopen(api_request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {
        "tag": payload.get("tag_name") or tag,
        "name": payload.get("name") or "",
        "published_at": payload.get("published_at") or "",
    }


def release_status():
    cached = RELEASE_CACHE.get("status")
    if cached and RELEASE_CACHE.get("expires_at", 0) > time.time():
        return cached

    update_config = read_update_config()
    status = {
        "repo": RELEASE_REPO,
        "installed": os.getenv("SDAC_RELEASE") or "development",
        "configured_tag": (
            os.getenv("SDAC_RELEASE_TAG")
            or update_config.get("SDAC_RELEASE_TAG")
            or "latest-official"
        ),
        "official": {"tag": "unknown", "published_at": ""},
        "experimental": {"tag": "unknown", "published_at": ""},
        "error": "",
    }
    try:
        status["official"] = fetch_github_release("latest-official")
        status["experimental"] = fetch_github_release("latest-experimental")
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        status["error"] = str(error)

    RELEASE_CACHE["status"] = status
    RELEASE_CACHE["expires_at"] = time.time() + 600
    return status


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


def game_library_redirect(message, error=False, guild_id="all"):
    return redirect(url_for(
        "admin_game_library",
        key=ADMIN_KEY,
        guild_id=guild_id or "all",
        notice=message,
        error=1 if error else 0,
    ))


@app.route("/admin/game-library", methods=["GET", "POST"])
def admin_game_library():
    login_response = require_admin_login()
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    config_data = load_config()
    options = guild_options(config_data)
    valid_guild_ids = {option["id"] for option in options}
    selected_server_id = request.values.get("guild_id", "all").strip()
    if selected_server_id == "all":
        selected_server_id = ""
    if selected_server_id and selected_server_id not in valid_guild_ids:
        selected_server_id = ""

    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        actor_id, actor_name = web_actor()
        redirect_guild_id = request.form.get(
            "guild_id",
            selected_server_id or "all",
        ).strip() or "all"
        try:
            if action == "create_item":
                guild_id = request.form.get("guild_id", "").strip()
                if guild_id not in valid_guild_ids:
                    raise ValueError("Choose a valid Discord server.")
                answer_aliases = parse_answer_aliases(
                    request.form.get("answer", "")
                )
                if not answer_aliases:
                    raise ValueError("Answer is required.")
                answer_display = answer_aliases[0]["display"]
                normalized_answer = answer_aliases[0]["normalized"]
                title = request.form.get("title", "").strip()[:120]
                prompt_text = request.form.get("prompt_text", "").strip()
                max_text_length = int(
                    config_data.get("limits", {}).get(
                        "max_text_length",
                        DEFAULT_LIMITS["max_text_length"],
                    )
                )
                if len(prompt_text) > max_text_length:
                    raise ValueError(
                        f"Prompt text is limited to {max_text_length} characters."
                    )
                category = request.form.get("category", "").strip()[:80]
                hint_text = request.form.get("hint_text", "").strip()
                if len(hint_text) > 500:
                    raise ValueError("Hints are limited to 500 characters.")
                try:
                    auto_hint_minutes = int(
                        request.form.get("auto_hint_minutes", "0") or 0
                    )
                except ValueError as form_error:
                    raise ValueError(
                        "Automatic hint minutes must be a number."
                    ) from form_error
                if auto_hint_minutes < 0 or auto_hint_minutes > 1440:
                    raise ValueError(
                        "Automatic hint minutes must be between 0 and 1440."
                    )

                media_info = save_guess_library_upload(
                    guild_id,
                    request.files.get("media"),
                    config_data.get("limits", {}),
                )
                now = utc_now_iso()
                try:
                    with database() as connection:
                        cursor = connection.execute("""
                            INSERT INTO guess_library_items (
                                guild_id, title, answer, answer_display,
                                answer_aliases_json, prompt_text, category,
                                hint_text, auto_hint_minutes, media_path,
                                media_name, media_type, media_size,
                                media_metadata_json, status, times_used,
                                created_by, created_at, updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, ?, ?)
                        """, (
                            guild_id,
                            title or answer_display,
                            normalized_answer,
                            answer_display,
                            json.dumps(answer_aliases, separators=(",", ":")),
                            prompt_text,
                            category,
                            hint_text,
                            auto_hint_minutes,
                            media_info["path"],
                            media_info["name"],
                            media_info["type"],
                            int(media_info["size"] or 0),
                            json.dumps(
                                media_info["metadata"],
                                separators=(",", ":"),
                            ),
                            actor_name,
                            now,
                            now,
                        ))
                        item_id = cursor.lastrowid
                        add_admin_audit_log(
                            connection,
                            guild_id,
                            "dashboard_create_guess_library_item",
                            actor_id,
                            actor_name,
                            "guess_library_item",
                            item_id,
                            f"Created website game-library item {item_id}.",
                        )
                except Exception:
                    delete_guess_library_media(media_info["path"])
                    raise
                return game_library_redirect(
                    f"Library item {item_id} added.",
                    guild_id=guild_id,
                )

            if action == "bulk_import":
                guild_id = request.form.get("guild_id", "").strip()
                if guild_id not in valid_guild_ids:
                    raise ValueError("Choose a valid Discord server.")
                upload = request.files.get("csv_file")
                if upload is None or not upload.filename:
                    raise ValueError("Choose a CSV file to import.")
                raw_content = upload.stream.read()
                if not raw_content:
                    raise ValueError("CSV file was empty.")
                try:
                    decoded = raw_content.decode("utf-8-sig")
                except UnicodeDecodeError as decode_error:
                    raise ValueError(
                        "CSV must be UTF-8 encoded."
                    ) from decode_error
                reader = csv.DictReader(io.StringIO(decoded))
                if not reader.fieldnames:
                    raise ValueError("CSV must include a header row.")

                max_text_length = int(
                    config_data.get("limits", {}).get(
                        "max_text_length",
                        DEFAULT_LIMITS["max_text_length"],
                    )
                )
                imported = 0
                skipped = 0
                now = utc_now_iso()
                with database() as connection:
                    for raw_row in reader:
                        row = {
                            str(key or "").strip().lower(): str(value or "").strip()
                            for key, value in raw_row.items()
                        }
                        answer_value = (
                            row.get("answer")
                            or row.get("answers")
                            or row.get("answer_aliases")
                            or ""
                        )
                        aliases_value = row.get("aliases") or ""
                        alias_source = answer_value
                        if aliases_value:
                            alias_source = (
                                alias_source
                                + "|"
                                + aliases_value.replace(",", "|")
                            )
                        answer_aliases = parse_answer_aliases(alias_source)
                        if not answer_aliases:
                            skipped += 1
                            continue
                        answer_display = answer_aliases[0]["display"]
                        normalized_answer = answer_aliases[0]["normalized"]
                        title = (row.get("title") or answer_display)[:120]
                        prompt_text = (row.get("prompt_text") or row.get("prompt") or "")[:max_text_length]
                        category = (row.get("category") or "")[:80]
                        hint_text = (row.get("hint") or row.get("hint_text") or "")[:500]
                        try:
                            auto_hint_minutes = int(
                                row.get("auto_hint_minutes") or "0"
                            )
                        except ValueError:
                            auto_hint_minutes = 0
                        auto_hint_minutes = max(0, min(1440, auto_hint_minutes))
                        requested_status = (row.get("status") or "draft").lower()
                        status = (
                            requested_status
                            if requested_status in {"draft", "disabled"}
                            else "draft"
                        )
                        cursor = connection.execute("""
                            INSERT INTO guess_library_items (
                                guild_id, title, answer, answer_display,
                                answer_aliases_json, prompt_text, category,
                                hint_text, auto_hint_minutes, media_path,
                                media_name, media_type, media_size,
                                media_metadata_json, status, times_used,
                                created_by, created_at, updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', 'unknown', 0, '{}', ?, 0, ?, ?, ?)
                        """, (
                            guild_id,
                            title,
                            normalized_answer,
                            answer_display,
                            json.dumps(answer_aliases, separators=(",", ":")),
                            prompt_text,
                            category,
                            hint_text,
                            auto_hint_minutes,
                            status,
                            actor_name,
                            now,
                            now,
                        ))
                        imported += 1
                    add_admin_audit_log(
                        connection,
                        guild_id,
                        "dashboard_bulk_import_guess_library",
                        actor_id,
                        actor_name,
                        "guess_library_item",
                        "",
                        (
                            f"Imported {imported} draft/disabled library "
                            f"item(s); skipped {skipped} row(s)."
                        ),
                    )
                return game_library_redirect(
                    f"Imported {imported} library draft(s); skipped {skipped} row(s).",
                    guild_id=guild_id,
                )

            if action == "set_status":
                item_id = int(request.form.get("item_id", "0") or 0)
                new_status = request.form.get("status", "").strip()
                if new_status not in {"active", "disabled", "draft"}:
                    raise ValueError("Invalid library item status.")
                with database() as connection:
                    item = connection.execute("""
                        SELECT id, guild_id, title
                        FROM guess_library_items
                        WHERE id = ?
                    """, (item_id,)).fetchone()
                    if not item:
                        raise ValueError("Library item was not found.")
                    connection.execute("""
                        UPDATE guess_library_items
                        SET status = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (new_status, utc_now_iso(), item_id))
                    add_admin_audit_log(
                        connection,
                        item["guild_id"],
                        "dashboard_update_guess_library_item_status",
                        actor_id,
                        actor_name,
                        "guess_library_item",
                        item_id,
                        f"Set website game-library item to {new_status}.",
                    )
                return game_library_redirect(
                    f"Library item {item_id} set to {new_status}.",
                    guild_id=redirect_guild_id,
                )

            if action == "delete_item":
                item_id = int(request.form.get("item_id", "0") or 0)
                with database() as connection:
                    item = connection.execute("""
                        SELECT id, guild_id, title, media_path
                        FROM guess_library_items
                        WHERE id = ?
                    """, (item_id,)).fetchone()
                    if not item:
                        raise ValueError("Library item was not found.")
                    connection.execute(
                        "DELETE FROM guess_library_items WHERE id = ?",
                        (item_id,),
                    )
                    add_admin_audit_log(
                        connection,
                        item["guild_id"],
                        "dashboard_delete_guess_library_item",
                        actor_id,
                        actor_name,
                        "guess_library_item",
                        item_id,
                        "Deleted website game-library item.",
                    )
                delete_guess_library_media(item["media_path"])
                return game_library_redirect(
                    f"Library item {item_id} deleted.",
                    guild_id=redirect_guild_id,
                )

            raise ValueError("Unknown game-library action.")
        except (ValueError, OSError, sqlite3.Error) as form_error:
            return game_library_redirect(
                str(form_error),
                error=True,
                guild_id=redirect_guild_id,
            )

    guild_names = guild_name_map(config_data)
    where = []
    parameters = []
    if selected_server_id:
        where.append("guild_id = ?")
        parameters.append(selected_server_id)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT *
            FROM guess_library_items
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT 200
        """, parameters).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        try:
            aliases = json.loads(item.get("answer_aliases_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            aliases = []
        relative_path = media_relative_path(item.get("media_path") or "")
        size = int(item.get("media_size") or 0)
        item["alias_count"] = len(aliases)
        item["guild_name"] = guild_names.get(
            item.get("guild_id"),
            item.get("guild_id") or "Unknown",
        )
        item["media_url"] = (
            url_for("serve_media", filename=relative_path)
            if relative_path
            else ""
        )
        item["size_label"] = format_bytes(size) if size else ""
        item["status"] = item.get("status") or "active"
        items.append(item)

    max_file_bytes = int(
        config_data.get("limits", {}).get(
            "max_file_bytes",
            DEFAULT_LIMITS["max_file_bytes"],
        )
    )
    max_text_length = int(
        config_data.get("limits", {}).get(
            "max_text_length",
            DEFAULT_LIMITS["max_text_length"],
        )
    )
    return render_template_string(
        GAME_LIBRARY_HTML,
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        error=error,
        guild_options=options,
        items=items,
        max_file_label=format_bytes(max_file_bytes),
        max_text_length=max_text_length,
        notice=notice,
        selected_guild_id=selected_server_id,
    )


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
                    brand_accent = (
                        request.form.get("brand_accent", "#7c9cff").strip()
                        or "#7c9cff"
                    )
                    if not re.match(r"^#[0-9A-Fa-f]{6}$", brand_accent):
                        raise ValueError(
                            "Brand accent must be a hex color like #7c9cff."
                        )
                    guild_config["brand_name"] = request.form.get(
                        "brand_name",
                        "",
                    ).strip()[:80]
                    guild_config["brand_accent"] = brand_accent
                    guild_config["brand_logo_url"] = request.form.get(
                        "brand_logo_url",
                        "",
                    ).strip()[:200]
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
                    features = guild_config.setdefault("features", {})
                    for feature_key in DEFAULT_FEATURES:
                        features[feature_key] = (
                            request.form.get(f"feature_{feature_key}") == "1"
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
        features = guild_config.get("features") or {}
        guilds.append({
            "id": guild_id,
            "name": (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or f"Discord {guild_id}"
            ),
            "guild_name": guild_config.get("guild_name") or f"Discord {guild_id}",
            "brand_name": guild_config.get("brand_name") or "",
            "brand_accent": guild_config.get("brand_accent") or "#7c9cff",
            "brand_logo_url": guild_config.get("brand_logo_url") or "",
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
            "features": [
                {
                    "key": key,
                    "label": label,
                    "enabled": features.get(key, DEFAULT_FEATURES[key]),
                }
                for key, label in FEATURE_LABELS.items()
            ],
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
        if action == "restore_config":
            try:
                backup_path, restored, message = restore_latest_config_backup()
            except OSError as restore_error:
                backup_path = None
                restored = False
                message = f"Config restore failed: {restore_error}"
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "maintenance_restore_config",
                    actor_id,
                    actor_name,
                    "config_backup",
                    backup_path.name if backup_path else "",
                    message,
                )
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=message,
                error=0 if restored else 1,
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
        bot_status=read_bot_status(),
        backups=recent_database_backups(),
        cache_entries=len(PUBLIC_PAGE_CACHE),
        config_backups=recent_config_backups(),
        csrf_token=get_csrf_token(),
        db_file=DB_FILE,
        db_size=format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B",
        error=error,
        media_files=media_stats["files"],
        media_size=format_bytes(media_stats["bytes"]),
        notice=notice,
        release=os.getenv("SDAC_RELEASE") or "development",
        release_status=release_status(),
        restore_runs=restore_runs,
        server_name=os.getenv("SDAC_SERVER_NAME") or "local",
        started_at=APP_STARTED_AT.strftime("%Y-%m-%d %H:%M UTC"),
        uptime=f"{days}d {hours}h {minutes}m",
        warnings=security_warnings() + storage_warnings(config_data),
    )


@app.route("/admin/moderation", methods=["GET", "POST"])
def admin_moderation():
    login_response = require_admin_login()
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    config_data = load_config()
    guild_names = guild_name_map(config_data)
    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        actor_id, actor_name = web_actor()
        if action == "resolve_report":
            report_id = request.form.get("report_id", "").strip()
            admin_notes = request.form.get("admin_notes", "").strip()[:500]
            with database() as connection:
                report = connection.execute("""
                    SELECT *
                    FROM submission_reports
                    WHERE id = ?
                """, (report_id,)).fetchone()
                if report:
                    connection.execute("""
                        UPDATE submission_reports
                        SET status = 'resolved',
                            admin_notes = ?,
                            resolved_at = ?
                        WHERE id = ?
                    """, (admin_notes, utc_now_iso(), report["id"]))
                    add_admin_audit_log(
                        connection,
                        report["guild_id"],
                        "submission_report_resolved",
                        actor_id,
                        actor_name,
                        "submission_report",
                        report["id"],
                        admin_notes or "Marked reviewed.",
                    )
                    notice = "Report marked reviewed."
                else:
                    notice = "Report not found."
            PUBLIC_PAGE_CACHE.clear()
            return redirect(url_for(
                "admin_moderation",
                key=ADMIN_KEY,
                notice=notice,
            ))

    with closing(connect_db()) as connection:
        reports = connection.execute("""
            SELECT reports.id, reports.submission_id, reports.guild_id,
                   reports.reporter_name, reports.reason, reports.created_at
            FROM submission_reports AS reports
            WHERE reports.status = 'open'
            ORDER BY reports.created_at DESC, reports.id DESC
            LIMIT 50
        """).fetchall()
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
        csrf_token=get_csrf_token(),
        guild_names=guild_names,
        history=history,
        notice=notice,
        pending_posts=pending_posts,
        reports=reports,
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
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    server_options = guild_options(config_data, public_only=not is_admin)
    guild_names = guild_name_map(config_data)
    visible_guild_ids = {option["id"] for option in server_options}
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
    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    page = positive_page(request.args.get("page"))
    if selected_sort not in {"newest", "votes"}:
        selected_sort = "newest"

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
        months = available_submission_months(
            connection,
            selected_server_id,
            guild_ids=visible_guild_ids if not is_admin and not selected_server_id else None,
        )
        category_conditions = ["category IS NOT NULL", "category != ''"]
        category_parameters = []
        if not is_admin:
            category_conditions.append("status = 'posted'")
        if selected_server_id:
            category_conditions.append("guild_id = ?")
            category_parameters.append(selected_server_id)
        elif not is_admin:
            visible_filter, visible_params = guild_id_filter(
                "guild_id",
                visible_guild_ids,
            )
            category_conditions.append(visible_filter)
            category_parameters.extend(visible_params)
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
            elif not is_admin:
                visible_filter, visible_params = guild_id_filter(
                    "guild_id",
                    visible_guild_ids,
                )
                where.append(visible_filter)
                parameters.extend(visible_params)
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
            elif not is_admin:
                visible_filter, visible_params = guild_id_filter(
                    "guild_id",
                    visible_guild_ids,
                )
                where.append(visible_filter)
                parameters.extend(visible_params)
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


@app.route("/report/<int:submission_id>", methods=["GET", "POST"])
def report_submission(submission_id):
    config_data = load_config()
    guild_names = guild_name_map(config_data)
    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT *
            FROM submissions
            WHERE id = ?
              AND status = 'posted'
        """, (submission_id,)).fetchone()

    if not row:
        abort(404)

    guild_config = (config_data.get("guilds") or {}).get(row["guild_id"], {})
    if not feature_enabled(guild_config, "public_gallery"):
        abort(404)

    notice = ""
    error = False
    if request.method == "POST":
        require_csrf_token()
        reporter_name = request.form.get("reporter_name", "").strip()[:120]
        reason = request.form.get("reason", "").strip()[:1000]
        if not reason:
            notice = "Please include a reason so admins know what to review."
            error = True
        else:
            actor_id = request.remote_addr or "public"
            actor_name = reporter_name or f"public-report@{actor_id}"
            with database() as connection:
                connection.execute("""
                    INSERT INTO submission_reports (
                        submission_id, guild_id, reporter_name,
                        reason, status, created_at
                    )
                    VALUES (?, ?, ?, ?, 'open', ?)
                """, (
                    row["id"],
                    row["guild_id"],
                    actor_name,
                    reason,
                    utc_now_iso(),
                ))
                add_admin_audit_log(
                    connection,
                    row["guild_id"],
                    "submission_report_created",
                    actor_id,
                    actor_name,
                    "submission",
                    row["id"],
                    reason,
                )
            PUBLIC_PAGE_CACHE.clear()
            notice = "Report sent. Thank you."

    submission = dict(row)
    submission["guild_name"] = guild_names.get(
        submission.get("guild_id"),
        f"Discord {submission.get('guild_id')}" if submission.get("guild_id") else "",
    )
    return render_template_string(
        REPORT_HTML,
        csrf_token=get_csrf_token(),
        error=error,
        notice=notice,
        submission=submission,
    )


@app.route("/user/<user_id>")
def user_profile(user_id):
    user_id = str(user_id or "").strip()
    if not user_id:
        abort(404)

    config_data = load_config()
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    server_options = guild_options(config_data, public_only=not is_admin)
    guild_names = guild_name_map(config_data)
    selected_server_id = selected_guild_id(server_options)
    visible_guild_ids = {option["id"] for option in server_options}

    submission_where = ["user_id = ?", "status = 'posted'"]
    submission_params = [user_id]
    guess_where = ["user_id = ?"]
    guess_params = [user_id]
    correct_where = ["user_id = ?"]
    correct_params = [user_id]
    if selected_server_id:
        submission_where.append("guild_id = ?")
        submission_params.append(selected_server_id)
        guess_where.append("guild_id = ?")
        guess_params.append(selected_server_id)
        correct_where.append("guild_id = ?")
        correct_params.append(selected_server_id)
    elif not is_admin:
        visible_filter, visible_params = guild_id_filter(
            "guild_id",
            visible_guild_ids,
        )
        submission_where.append(visible_filter)
        submission_params.extend(visible_params)
        guess_where.append(visible_filter)
        guess_params.extend(visible_params)
        correct_where.append(visible_filter)
        correct_params.extend(visible_params)

    with closing(connect_db()) as connection:
        stats = connection.execute(f"""
            SELECT
                COALESCE(MAX(NULLIF(username, '')), ?) AS username,
                COUNT(*) AS submissions,
                COALESCE(SUM(stars), 0) AS total_votes
            FROM submissions
            WHERE {" AND ".join(submission_where)}
        """, [user_id] + submission_params).fetchone()
        guess_stats = connection.execute(f"""
            SELECT
                COALESCE(MAX(NULLIF(username, '')), ?) AS username,
                COALESCE(SUM(points), 0) AS points
            FROM guess_points
            WHERE {" AND ".join(guess_where)}
        """, [stats["username"] or user_id] + guess_params).fetchone()
        correct_count = connection.execute(f"""
            SELECT COUNT(*)
            FROM guess_correct_guesses
            WHERE {" AND ".join(correct_where)}
        """, correct_params).fetchone()[0]
        posts = connection.execute(f"""
            SELECT id, guild_id, username, category, stars,
                   created_at, submitted_at
            FROM submissions
            WHERE {" AND ".join(submission_where)}
            ORDER BY created_at DESC, id DESC
            LIMIT 25
        """, submission_params).fetchall()
        monthly_points = connection.execute(f"""
            SELECT month, SUM(points) AS points
            FROM guess_points
            WHERE {" AND ".join(guess_where)}
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, guess_params).fetchall()

    username = (
        guess_stats["username"]
        or stats["username"]
        or f"Discord user {user_id}"
    )
    profile = {
        "username": username,
        "submissions": stats["submissions"] or 0,
        "total_votes": stats["total_votes"] or 0,
        "guess_points": guess_stats["points"] or 0,
        "correct_guesses": correct_count,
    }
    return render_template_string(
        USER_PROFILE_HTML,
        admin_key=ADMIN_KEY,
        guild_names=guild_names,
        is_admin=is_admin,
        monthly_points=monthly_points,
        posts=posts,
        profile=profile,
        selected_guild_id=selected_server_id,
    )


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
    actor_filter = request.args.get("actor", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_from):
        date_from = ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_to):
        date_to = ""

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
    if actor_filter:
        where.append("""
            (
                actor_user_id LIKE ?
                OR actor_username LIKE ?
            )
        """)
        like_actor = f"%{actor_filter}%"
        parameters.extend([like_actor, like_actor])
    if date_from:
        where.append("created_at >= ?")
        parameters.append(f"{date_from}T00:00:00")
    if date_to:
        where.append("created_at <= ?")
        parameters.append(f"{date_to}T23:59:59")
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
        actor_filter=actor_filter,
        action_filter=action_filter,
        action_options=action_options,
        admin_key=ADMIN_KEY,
        date_from=date_from,
        date_to=date_to,
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
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))
    all_server_options = guild_options(config_data, public_only=not is_admin)
    guild_configs = config_data.get("guilds") or {}
    server_options = [
        option
        for option in all_server_options
        if feature_enabled(guild_configs.get(option["id"], {}), "guessing_games")
    ]
    visible_guess_ids = {option["id"] for option in server_options}
    cross_server_ids = visible_guess_ids & feature_guild_ids(
        config_data,
        "cross_server_leaderboard",
    )
    guild_names = guild_name_map(config_data)
    selected_server_id = selected_guild_id(server_options)

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
        months = available_guess_months(connection, visible_guess_ids)
        if not month:
            month = months[0] if months else current_month_key()
        cross_filter, cross_filter_params = guild_id_filter(
            "guild_id",
            cross_server_ids,
        )
        total_cross = connection.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT user_id
                FROM guess_points
                WHERE month = ?
                  AND """ + cross_filter + """
                GROUP BY user_id
            )
        """, [month] + cross_filter_params).fetchone()[0]
        total_pages = max(1, math.ceil(total_cross / PAGE_SIZE))
        page = min(page, total_pages)
        cross_server_scores = connection.execute("""
            SELECT
                COALESCE(MAX(NULLIF(username, '')), user_id) AS username,
                SUM(points) AS points,
                COUNT(DISTINCT guild_id) AS server_count
            FROM guess_points
            WHERE month = ?
              AND """ + cross_filter + """
            GROUP BY user_id
            ORDER BY points DESC, username ASC
            LIMIT ? OFFSET ?
        """, [month] + cross_filter_params + [
            PAGE_SIZE,
            (page - 1) * PAGE_SIZE,
        ]).fetchall()

        where = ["month = ?"]
        parameters = [month]
        if selected_server_id:
            where.append("guild_id = ?")
            parameters.append(selected_server_id)
        else:
            visible_filter, visible_params = guild_id_filter(
                "guild_id",
                visible_guess_ids,
            )
            where.append(visible_filter)
            parameters.extend(visible_params)
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
    options = guild_options(config_data, public_only=True)
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
    guild_config = (config_data.get("guilds") or {}).get(guild_id, {})
    if not feature_enabled(guild_config, "public_gallery"):
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
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))
    server_options = guild_options(config_data, public_only=not is_admin)
    visible_guild_ids = {option["id"] for option in server_options}
    selected_server_id = selected_guild_id(server_options)
    month = request.args.get("month", "").strip()

    with closing(connect_db()) as connection:
        month_guild_ids = (
            {selected_server_id}
            if selected_server_id
            else visible_guild_ids
        )
        months = available_guess_months(
            connection,
            month_guild_ids,
        )
        for submission_month in available_submission_months(
            connection,
            selected_server_id,
            guild_ids=visible_guild_ids if not selected_server_id else None,
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
        else:
            visible_filter, visible_params = guild_id_filter(
                "guild_id",
                visible_guild_ids,
            )
            guess_where.append(visible_filter)
            guess_params.extend(visible_params)
            submission_where.append(visible_filter)
            submission_params.extend(visible_params)

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
    bot_status = read_bot_status()
    return jsonify({
        "ok": True,
        "service": "sdac-dashboard",
        "bot_heartbeat_fresh": bool(bot_status.get("fresh")),
    })


@app.route("/admin/health")
def admin_health():
    login_response = require_admin_login()
    if login_response:
        return login_response

    media_stats = media_directory_stats()
    setup_rows = build_onboarding_rows(load_config())
    bot_status = read_bot_status()
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
            "bot_status": bot_status,
            "setup_health": {
                row["id"]: row["health_score"]
                for row in setup_rows
            },
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


@app.route("/admin/backup/<path:name>")
def download_backup(name):
    login_response = require_admin_login()
    if login_response:
        return login_response

    backup_name = Path(name).name
    if backup_name != name or not re.match(r"^sdac-[A-Za-z0-9_.-]+\.db$", backup_name):
        abort(404)
    backup_path = (BACKUP_DIR / backup_name).resolve()
    try:
        backup_path.relative_to(BACKUP_DIR.resolve())
    except ValueError:
        abort(404)
    if not backup_path.is_file():
        abort(404)

    actor_id, actor_name = web_actor()
    with database() as connection:
        add_admin_audit_log(
            connection,
            None,
            "database_backup_download",
            actor_id,
            actor_name,
            "backup",
            backup_name,
            "Backup downloaded from dashboard.",
        )
    return send_from_directory(
        BACKUP_DIR,
        backup_name,
        as_attachment=True,
        download_name=backup_name,
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
