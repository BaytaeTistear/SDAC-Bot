import csv
import gzip
import hashlib
import io
import math
import os
import json
import re
import shlex
import shutil
import socket
import sqlite3
import secrets
import subprocess
import tempfile
import threading
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from werkzeug.security import check_password_hash, generate_password_hash

from flask import (
    Flask,
    abort,
    jsonify,
    has_request_context,
    redirect,
    render_template_string,
    request,
    Response,
    send_from_directory,
    session,
    url_for,
)

from config import TOKEN
from database_backend import connect_database, using_postgres
from database_migrations import DATABASE_SCHEMA_VERSION, apply_database_migrations
from observability import init_sentry


app = Flask(__name__)
init_sentry("sdac-dashboard")

ADMIN_KEY = os.getenv("SDAC_ADMIN_KEY", "ImTheBestAdmin")
ADMIN_PASSWORD = os.getenv("SDAC_ADMIN_PASSWORD", ADMIN_KEY)
DISCORD_OAUTH_CLIENT_ID = (
    os.getenv("SDAC_DISCORD_CLIENT_ID")
    or os.getenv("DISCORD_CLIENT_ID")
    or os.getenv("SDAC_BOT_CLIENT_ID")
    or ""
)
DISCORD_OAUTH_CLIENT_SECRET = (
    os.getenv("SDAC_DISCORD_CLIENT_SECRET")
    or os.getenv("DISCORD_CLIENT_SECRET")
    or ""
)
DISCORD_OAUTH_REDIRECT_URI = os.getenv("SDAC_OAUTH_REDIRECT_URI", "")
DISCORD_ADMINISTRATOR_PERMISSION = 0x8
app.secret_key = os.getenv("SDAC_SECRET_KEY", secrets.token_hex(32))
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = Path(os.getenv("SDAC_DB_FILE", BASE_DIR / "sdac.db"))
CONFIG_FILE = Path(os.getenv("SDAC_CONFIG_FILE", BASE_DIR / "config.json"))
MEDIA_DIR = Path(os.getenv("SDAC_MEDIA_DIR", BASE_DIR / "media")).resolve()
MEDIA_QUARANTINE_DIR = Path(
    os.getenv("SDAC_MEDIA_QUARANTINE_DIR", BASE_DIR / "media_quarantine")
).resolve()
BACKUP_DIR = Path(os.getenv("SDAC_BACKUP_DIR", BASE_DIR / "backups"))
BOT_STATUS_FILE = Path(os.getenv("SDAC_BOT_STATUS_FILE", BASE_DIR / "bot_status.json"))
BACKUP_KEEP_COUNT = 30
CONFIG_BACKUP_KEEP_COUNT = 30
SCHEMA_VERSION = DATABASE_SCHEMA_VERSION
PAGE_SIZE = 20
CACHE_TTL_SECONDS = 45
PUBLIC_PAGE_CACHE = {}
LOGIN_ATTEMPTS = {}
NOTIFICATION_THROTTLES = {}
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
    "restore_drill_enabled": True,
    "monthly_digest_enabled": True,
    "two_admin_approval_enabled": False,
    "monthly_submission_limit_per_guild": 0,
    "active_game_limit_per_guild": 0,
    "guild_storage_limit_bytes": 0,
    "offsite_backup_warning_hours": 72,
    "local_original_retention_days": 30,
    "thumbnail_max_dimension": 640,
    "image_compression_enabled": False,
    "image_compression_quality": 85,
    "archive_full_history_after_months": 18,
    "spam_review_threshold": 40,
    "spam_burst_count": 5,
    "spam_burst_window_minutes": 10,
}

DEFAULT_OFFSITE_BACKUP = {
    "provider": "",
    "remote": "",
    "last_success_at": "",
    "last_status": "",
    "last_details": "",
}

DEFAULT_FEATURES = {
    "submissions": True,
    "approval_queue": True,
    "guessing_games": True,
    "weekly_posts": True,
    "public_gallery": True,
    "cross_server_leaderboard": True,
}

DEFAULT_GUILD_EXTERNAL_BACKUP = {
    "enabled": False,
    "provider": "rclone",
    "remote": "",
    "public_base_url": "",
    "include_media": True,
    "include_database_export": True,
    "delete_local_media_after_success": False,
    "last_success_at": "",
    "last_status": "",
    "last_details": "",
}

FEATURE_LABELS = {
    "submissions": "Submissions",
    "approval_queue": "Approval Queue",
    "guessing_games": "Guessing Games",
    "weekly_posts": "Weekly Posts",
    "public_gallery": "Public Gallery",
    "cross_server_leaderboard": "Cross-Server Leaderboard",
}

ROLE_LEVELS = {
    "moderator": 1,
    "admin": 2,
    "owner": 3,
}

ROLE_LABELS = {
    "moderator": "Moderator",
    "admin": "Admin",
    "owner": "Owner",
}

NOTIFICATION_EVENT_LABELS = {
    "system_errors": "System Errors",
    "backup_failed": "Backup Failed",
    "restore_test_failed": "Restore Test Failed",
    "storage_warning": "Storage Warning",
    "repost_delete_failed": "Discord Repost Delete Failed",
    "heartbeat_stale": "Bot Heartbeat Stale",
    "permission_drift": "Permission Drift",
    "restore_drill_failed": "Restore Drill Failed",
    "monthly_digest": "Monthly Digest",
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
    "emergency_paused": False,
    "emergency_reason": "",
    "limits": {
        "max_file_bytes": 0,
        "max_total_bytes": 0,
        "monthly_submission_limit": 0,
        "active_game_limit": 0,
        "storage_limit_bytes": 0,
    },
    "moderation": {
        "blocked_words": [],
        "allowed_media_types": ["image", "video", "audio"],
        "require_approval_for_new_users": False,
        "new_user_days": 7,
        "spoiler_requires_approval": False,
        "duplicate_requires_approval": True,
        "spam_burst_count": 5,
        "spam_burst_window_minutes": 10,
        "spam_review_threshold": 40,
    },
    "game_settings": {
        "reuse_cooldown_days": 30,
        "default_auto_hint_minutes": 0,
        "default_difficulty": "normal",
    },
    "public_stats_enabled": True,
    "external_backup": DEFAULT_GUILD_EXTERNAL_BACKUP,
    "categories": {},
    "features": DEFAULT_FEATURES,
}

SETUP_TEMPLATE_ROWS = [
    {
        "key": "simple",
        "label": "Submission-only server",
        "description": "Submissions, public gallery, weekly posts, and light game support.",
        "command": "/setup -> Apply Simple Gallery preset",
    },
    {
        "key": "game",
        "label": "Game-only server",
        "description": "Guessing games and cross-server leaderboards with submissions disabled.",
        "command": "/setup -> Apply Game Night preset",
    },
    {
        "key": "full",
        "label": "Full community server",
        "description": "Submissions, approvals, games, reports, analytics, and public stats.",
        "command": "/setup -> Apply Full Community preset",
    },
    {
        "key": "low_storage",
        "label": "Low-storage server",
        "description": "Compression, backups, pruning, and smaller storage limits for cheap hosts.",
        "command": "/setlimit storage_mb 1024 + /setserverbackup",
    },
    {
        "key": "private",
        "label": "Private/admin-only server",
        "description": "Approval-focused setup with public gallery and cross-server visibility disabled.",
        "command": "/setup -> Apply Private Review preset",
    },
]

ORIGINAL_REPO = os.getenv("SDAC_UPSTREAM_GITHUB_REPO", "BaytaeTistear/SDAC-Bot")
RELEASE_REPO = os.getenv("SDAC_GITHUB_REPO", ORIGINAL_REPO)
DASHBOARD_INSTANCE_ID = (
    os.getenv("SDAC_INSTANCE_ID")
    or f"{socket.gethostname()}:{hashlib.sha1(str(BASE_DIR).encode('utf-8')).hexdigest()[:8]}"
)
UPDATE_ENV_FILE = Path(os.getenv("SDAC_UPDATE_CONFIG", "/etc/sdac-bot/update.env"))
RELEASE_CACHE = {
    "expires_at": 0,
    "status": None,
}
GUILD_MEDIA_BASE_CACHE = {
    "mtime": None,
    "bases": {},
}
BACKGROUND_JOB_THREADS = {}
BACKGROUND_JOB_LOCK = threading.Lock()


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

        @media (max-width: 700px) {
            body { padding: 12px; }
            .admin-nav, .filter form, .post-header {
                align-items: stretch;
                flex-direction: column;
            }
            .admin-nav {
                flex-wrap: wrap;
                gap: 10px;
            }
            select, input, button { width: 100%; }
            .media-grid { grid-template-columns: 1fr; }
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
        <a href="{{ url_for('my_submissions', key=admin_key if is_admin else None) }}">My submissions</a>
        <a href="{{ url_for('about') }}">About</a>
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('setup_guide') }}">Setup guide</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
        <a href="{{ url_for('achievements', key=admin_key if is_admin else None) }}">Achievements</a>
        {% if is_admin %}
            <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
            <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
            <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
            <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
            <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
            <a href="{{ url_for('admin_monthly_report', key=admin_key) }}">Reports</a>
            <a href="{{ url_for('admin_jobs', key=admin_key) }}">Jobs</a>
            <a href="{{ url_for('admin_privacy', key=admin_key) }}">Privacy</a>
            <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
            <a href="{{ url_for('admin_releases', key=admin_key) }}">Releases</a>
            <a href="{{ url_for('admin_install_doctor', key=admin_key) }}">Install Doctor</a>
            <a href="{{ url_for('admin_approvals', key=admin_key) }}">Approvals</a>
            <a href="{{ url_for('admin_owner_portal', key=admin_key) }}">Owner Portal</a>
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
                    {% for status in ("posted", "pending", "needs_review", "removed") %}
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
                                    {% if post.spam_score %}
                                        <span class="status status-pending" title="{{ post.spam_reasons|join('; ') }}">score {{ post.spam_score }}</span>
                                    {% endif %}
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
                                <form method="post"
                                      action="{{ url_for(
                                          'set_submission_status',
                                          submission_id=post.id,
                                          key=admin_key,
                                          category=selected_category,
                                          guild_id=selected_guild_id or 'all',
                                          q=search_query,
                                          status=selected_status,
                                          page=page
                                      ) }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="new_status" value="{{ 'posted' if post.status == 'needs_review' else 'needs_review' }}">
                                    <button type="submit">{{ 'Clear Review' if post.status == 'needs_review' else 'Needs Review' }}</button>
                                </form>
                                <form method="post"
                                      action="{{ url_for(
                                          'quarantine_submission',
                                          submission_id=post.id,
                                          key=admin_key,
                                          category=selected_category,
                                          guild_id=selected_guild_id or 'all',
                                          q=search_query,
                                          status=selected_status,
                                          page=page
                                      ) }}"
                                      onsubmit="return confirm('Move this submission media into quarantine?');">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="reason" value="Manual dashboard quarantine">
                                    <button type="submit">Quarantine</button>
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
                                                <img src="{{ item.thumbnail_url or item.url }}" alt="{{ item.name }}" loading="lazy">
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
                                            {% if not item.local_original_available %}
                                                <span class="pill">remote original</span>
                                                {% if is_admin and post.guild_id %}
                                                    <form method="post" action="{{ url_for('admin_media_cleanup', key=admin_key) }}">
                                                        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                                        <input type="hidden" name="guild_id" value="{{ post.guild_id }}">
                                                        <button type="submit" name="action" value="restore_guild_media">Restore Server Media</button>
                                                    </form>
                                                {% endif %}
                                            {% endif %}
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
        .oauth {
            display: block;
            background: #5865f2;
            border-radius: 8px;
            color: white;
            margin: 0 0 18px;
            padding: 11px;
            text-align: center;
            text-decoration: none;
        }
    </style>
</head>
<body>
<main>
    <h1>Admin Login</h1>
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    {% if oauth_enabled %}
        <a class="oauth" href="{{ url_for('admin_oauth_start', key=admin_key, next=next_url) }}">Log in with Discord</a>
    {% endif %}
    <form method="post">
        <input type="hidden" name="key" value="{{ admin_key }}">
        <input type="hidden" name="next" value="{{ next_url }}">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <label for="username">Admin username</label>
        <input id="username" name="username" value="{{ username }}" placeholder="owner" autofocus>
        <label for="password">Admin password</label>
        <input id="password" name="password" type="password" required>
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
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
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


MY_SUBMISSIONS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>My SDAC Submissions</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav, form { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 20px; }
        input, select, button { border: 1px solid #30333b; border-radius: 7px; font-size: 16px; padding: 10px 12px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; }
        .muted { color: #a8adb8; }
        .status { border: 1px solid #30333b; border-radius: 999px; display: inline-block; padding: 2px 7px; }
    </style>
</head>
<body>
<main>
    <h1>My Submissions</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key if is_admin else None) }}">Gallery</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key if is_admin else None) }}">Guessing leaderboard</a>
    </nav>
    <section class="panel">
        <form method="get">
            {% if is_admin %}<input type="hidden" name="key" value="{{ admin_key }}">{% endif %}
            <input name="q" value="{{ search_query }}" placeholder="Discord user ID or username">
            <select name="guild_id">
                <option value="all">All public servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                {% endfor %}
            </select>
            <button type="submit">Find Submissions</button>
        </form>
        <p class="muted">Tip: Discord user ID is the most accurate search. Public users only see posted submissions.</p>
    </section>
    <section class="panel">
        <h2>Results</h2>
        <table>
            <thead><tr><th>ID</th><th>Server</th><th>Category</th><th>Votes</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
                {% for row in rows %}
                    <tr>
                        <td><a href="{{ url_for('index', q=row.id, guild_id=row.guild_id or 'all', key=admin_key if is_admin else None) }}">{{ row.id }}</a></td>
                        <td>{{ guild_names.get(row.guild_id, row.guild_id) }}</td>
                        <td>{{ row.category }}</td>
                        <td>{{ row.stars or 0 }}</td>
                        <td><span class="status">{{ row.status }}</span></td>
                        <td>{{ row.created_at or row.submitted_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No matching submissions yet.</td></tr>
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
        input, select, button, textarea {
            border: 1px solid #30333b;
            border-radius: 7px;
            font-size: 15px;
            padding: 9px 10px;
        }
        textarea { box-sizing: border-box; min-height: 120px; width: 100%; }
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
            flex-wrap: wrap;
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
        <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_analytics', key=admin_key) }}">Analytics</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_jobs', key=admin_key) }}">Jobs</a>
        <a href="{{ url_for('admin_privacy', key=admin_key) }}">Privacy</a>
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
                            <details>
                                <summary>Edit / attach media</summary>
                                <form method="post" enctype="multipart/form-data">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="action" value="update_item">
                                    <input type="hidden" name="guild_id" value="{{ selected_guild_id or 'all' }}">
                                    <input type="hidden" name="item_id" value="{{ item.id }}">
                                    <input name="title" value="{{ item.title or '' }}" placeholder="Title">
                                    <input name="answer" value="{{ item.answer_display }}" placeholder="Answer | Alias">
                                    <input name="category" value="{{ item.category or '' }}" placeholder="Category">
                                    <input name="auto_hint_minutes" type="number" min="0" max="1440" value="{{ item.auto_hint_minutes or 0 }}">
                                    <textarea name="prompt_text" placeholder="Prompt text">{{ item.prompt_text or '' }}</textarea>
                                    <textarea name="hint_text" placeholder="Hint text">{{ item.hint_text or '' }}</textarea>
                                    <select name="status">
                                        {% for status in ["draft", "active", "disabled"] %}
                                            <option value="{{ status }}" {% if item.status == status %}selected{% endif %}>{{ status }}</option>
                                        {% endfor %}
                                    </select>
                                    <input name="media" type="file">
                                    <button type="submit">Save Item</button>
                                </form>
                            </details>
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
        @media (max-width: 760px) {
            body { padding: 12px; }
            input, select, button, textarea { box-sizing: border-box; width: 100%; }
            table, thead, tbody, tr, th, td { display: block; }
            thead { display: none; }
            tr { border-bottom: 1px solid #30333b; padding: 10px 0; }
            th, td { border-bottom: 0; padding: 6px 0; }
        }
    </style>
</head>
<body>
<main>
    <h1>Admin Settings</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('guessing_leaderboard', key=admin_key) }}">Guessing leaderboard</a>
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
        <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_analytics', key=admin_key) }}">Analytics</a>
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
        <h2>Dashboard Access</h2>
        <p>
            Logged in as <code>{{ current_admin_username }}</code>
            with <code>{{ current_admin_role }}</code> access.
        </p>
        {% if can_manage_users %}
            <form method="post">
                <input type="hidden" name="key" value="{{ admin_key }}">
                <input type="hidden" name="action" value="create_dashboard_user">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <table>
                    <tbody>
                        <tr><th>Username</th><td><input name="username" placeholder="moderator-name"></td></tr>
                        <tr><th>Password</th><td><input name="password" type="password"></td></tr>
                        <tr><th>Role</th><td>
                            <select name="role">
                                {% for role_key, role_label in role_labels.items() %}
                                    <option value="{{ role_key }}">{{ role_label }}</option>
                                {% endfor %}
                            </select>
                        </td></tr>
                        <tr><th>Server scope</th><td><input name="guild_ids" placeholder="Blank = all servers; otherwise IDs separated by spaces"></td></tr>
                    </tbody>
                </table>
                <button type="submit">Create / Replace Dashboard User</button>
            </form>
        {% else %}
            <p class="muted">Only owners can create, update, or disable dashboard users.</p>
        {% endif %}
        <table>
            <thead><tr><th>User</th><th>Role</th><th>Scope</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>
            <tbody>
                {% for user in dashboard_users %}
                    <tr>
                        <td><code>{{ user.username }}</code></td>
                        <td>{{ role_labels.get(user.role, user.role) }}</td>
                        <td>
                            {% set scope = parse_guild_scope(user.guild_ids_json) %}
                            {{ scope|join(", ") if scope else "All servers" }}
                        </td>
                        <td>{{ "Disabled" if user.disabled else "Active" }}</td>
                        <td>{{ user.last_login_at or "Never" }}</td>
                        <td>
                            {% if can_manage_users %}
                                <form method="post">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="action" value="update_dashboard_user">
                                    <input type="hidden" name="username" value="{{ user.username }}">
                                    <select name="role">
                                        {% for role_key, role_label in role_labels.items() %}
                                            <option value="{{ role_key }}" {% if user.role == role_key %}selected{% endif %}>{{ role_label }}</option>
                                        {% endfor %}
                                    </select>
                                    <input name="guild_ids" value="{{ parse_guild_scope(user.guild_ids_json)|join(' ') }}" placeholder="Server IDs or blank for all">
                                    <input name="password" type="password" placeholder="New password optional">
                                    <button type="submit">Update</button>
                                </form>
                                <form method="post">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="action" value="disable_dashboard_user">
                                    <input type="hidden" name="username" value="{{ user.username }}">
                                    <button type="submit">Disable</button>
                                </form>
                            {% else %}
                                <span class="muted">Owner only</span>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No named dashboard users yet. Legacy owner login is still active.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Admin Notifications</h2>
        <p class="muted">
            Route important SDAC alerts to a Discord channel. If no route exists,
            system errors fall back to each server's Error channel.
        </p>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="action" value="set_notification_route">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <table>
                <tbody>
                    <tr><th>Server</th><td>
                        <select name="guild_id">
                            {% for guild in guilds %}
                                <option value="{{ guild.id }}">{{ guild.name }} ({{ guild.id }})</option>
                            {% endfor %}
                        </select>
                    </td></tr>
                    <tr><th>Event</th><td>
                        <select name="event_key">
                            {% for event_key, event_label in notification_event_labels.items() %}
                                <option value="{{ event_key }}">{{ event_label }}</option>
                            {% endfor %}
                        </select>
                    </td></tr>
                    <tr><th>Channel ID</th><td><input name="channel_id" placeholder="Discord channel ID"></td></tr>
                    <tr><th>Status</th><td>
                        <select name="enabled">
                            <option value="1" selected>Enabled</option>
                            <option value="0">Disabled</option>
                        </select>
                    </td></tr>
                </tbody>
            </table>
            <button type="submit">Save Notification Route</button>
        </form>
        <table>
            <thead><tr><th>Server</th><th>Event</th><th>Channel</th><th>Status</th><th>Updated</th></tr></thead>
            <tbody>
                {% for route in notification_routes %}
                    <tr>
                        <td>{{ route.guild_name }} <br><code>{{ route.guild_id }}</code></td>
                        <td>{{ route.event_label }}</td>
                        <td><code>{{ route.channel_id or "Not set" }}</code></td>
                        <td>{{ "Enabled" if route.enabled else "Disabled" }}</td>
                        <td>{{ route.updated_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="muted">No notification routes configured yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

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
                    <tr><th>Monthly submissions per guild</th><td><input name="monthly_submission_limit_per_guild" value="{{ limits.get('monthly_submission_limit_per_guild', 0) }}"></td></tr>
                    <tr><th>Active games per guild</th><td><input name="active_game_limit_per_guild" value="{{ limits.get('active_game_limit_per_guild', 0) }}"></td></tr>
                    <tr><th>Guild storage limit bytes</th><td><input name="guild_storage_limit_bytes" value="{{ limits.get('guild_storage_limit_bytes', 0) }}"></td></tr>
                    <tr><th>Offsite backup warning hours</th><td><input name="offsite_backup_warning_hours" value="{{ limits.get('offsite_backup_warning_hours', 72) }}"></td></tr>
                    <tr><th>Local original retention days</th><td><input name="local_original_retention_days" value="{{ limits.get('local_original_retention_days', 30) }}"></td></tr>
                    <tr><th>Thumbnail max dimension</th><td><input name="thumbnail_max_dimension" value="{{ limits.get('thumbnail_max_dimension', 640) }}"></td></tr>
                    <tr><th>Image compression quality</th><td><input name="image_compression_quality" value="{{ limits.get('image_compression_quality', 85) }}"></td></tr>
                    <tr><th>Archive full history after months</th><td><input name="archive_full_history_after_months" value="{{ limits.get('archive_full_history_after_months', 18) }}"></td></tr>
                    <tr><th>Spam review score threshold</th><td><input name="spam_review_threshold" value="{{ limits.get('spam_review_threshold', 40) }}"></td></tr>
                    <tr><th>Spam burst count</th><td><input name="spam_burst_count" value="{{ limits.get('spam_burst_count', 5) }}"></td></tr>
                    <tr><th>Spam burst window minutes</th><td><input name="spam_burst_window_minutes" value="{{ limits.get('spam_burst_window_minutes', 10) }}"></td></tr>
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
                    <tr><th>Monthly restore drill</th><td>
                        <select name="restore_drill_enabled">
                            <option value="1" {% if limits.get('restore_drill_enabled', True) %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not limits.get('restore_drill_enabled', True) %}selected{% endif %}>Disabled</option>
                        </select>
                    </td></tr>
                    <tr><th>Monthly digest posts</th><td>
                        <select name="monthly_digest_enabled">
                            <option value="1" {% if limits.get('monthly_digest_enabled', True) %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not limits.get('monthly_digest_enabled', True) %}selected{% endif %}>Disabled</option>
                        </select>
                    </td></tr>
                    <tr><th>Two-admin approval for dangerous actions</th><td>
                        <select name="two_admin_approval_enabled">
                            <option value="0" {% if not limits.get('two_admin_approval_enabled', False) %}selected{% endif %}>Disabled</option>
                            <option value="1" {% if limits.get('two_admin_approval_enabled', False) %}selected{% endif %}>Enabled</option>
                        </select>
                    </td></tr>
                    <tr><th>Orphan media cleanup</th><td>
                        <select name="orphan_media_cleanup_enabled">
                            <option value="1" {% if limits.get('orphan_media_cleanup_enabled', True) %}selected{% endif %}>Enabled</option>
                            <option value="0" {% if not limits.get('orphan_media_cleanup_enabled', True) %}selected{% endif %}>Disabled</option>
                        </select>
                    </td></tr>
                    <tr><th>Image compression</th><td>
                        <select name="image_compression_enabled">
                            <option value="0" {% if not limits.get('image_compression_enabled', False) %}selected{% endif %}>Disabled</option>
                            <option value="1" {% if limits.get('image_compression_enabled', False) %}selected{% endif %}>Enabled</option>
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
            <div class="panel">
                <h4>Config Portability</h4>
                <p class="muted">Export this server's SDAC settings or paste a previous export to restore/copy setup.</p>
                <p><a href="{{ url_for('admin_export_guild_config', guild_id=guild.id, key=admin_key) }}">Download server config JSON</a></p>
                <form method="post" action="{{ url_for('admin_import_guild_config') }}">
                    <input type="hidden" name="key" value="{{ admin_key }}">
                    <input type="hidden" name="guild_id" value="{{ guild.id }}">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                    <textarea name="config_json" placeholder="Paste exported sdac-guild-config JSON here"></textarea>
                    <button type="submit">Preview Import</button>
                </form>
            </div>
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
                        <tr><th>Emergency pause</th><td>
                            <select name="emergency_paused">
                                <option value="0" {% if not guild.emergency_paused %}selected{% endif %}>Disabled</option>
                                <option value="1" {% if guild.emergency_paused %}selected{% endif %}>Enabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Emergency reason</th><td><input name="emergency_reason" value="{{ guild.emergency_reason }}" placeholder="Shown to users while paused"></td></tr>
                        <tr><th>Game summary channel ID</th><td><input name="game_summary_channel" value="{{ guild.game_summary_channel or '' }}"></td></tr>
                        <tr><th>Error channel ID</th><td><input name="error_channel" value="{{ guild.error_channel or '' }}"></td></tr>
                        <tr><th>Admin role IDs</th><td><input name="admin_role_ids" value="{{ guild.admin_role_ids }}"></td></tr>
                        <tr><th>Public stats</th><td>
                            <select name="public_stats_enabled">
                                <option value="1" {% if guild.public_stats_enabled %}selected{% endif %}>Enabled</option>
                                <option value="0" {% if not guild.public_stats_enabled %}selected{% endif %}>Disabled</option>
                            </select>
                        </td></tr>
                        <tr><th>External backup</th><td>
                            <select name="external_backup_enabled">
                                <option value="1" {% if guild.external_backup.enabled %}selected{% endif %}>Enabled</option>
                                <option value="0" {% if not guild.external_backup.enabled %}selected{% endif %}>Disabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Backup remote</th><td><input name="external_backup_remote" value="{{ guild.external_backup.remote }}" placeholder="drive:sdac/{{ guild.id }}"></td></tr>
                        <tr><th>Public media base URL</th><td><input name="external_backup_public_base_url" value="{{ guild.external_backup.public_base_url }}" placeholder="https://cdn.example.com/sdac/{{ guild.id }}"></td></tr>
                        <tr><th>Backup includes media</th><td>
                            <select name="external_backup_include_media">
                                <option value="1" {% if guild.external_backup.include_media %}selected{% endif %}>Enabled</option>
                                <option value="0" {% if not guild.external_backup.include_media %}selected{% endif %}>Disabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Backup includes DB export</th><td>
                            <select name="external_backup_include_database_export">
                                <option value="1" {% if guild.external_backup.include_database_export %}selected{% endif %}>Enabled</option>
                                <option value="0" {% if not guild.external_backup.include_database_export %}selected{% endif %}>Disabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Delete local media after backup</th><td>
                            <select name="external_backup_delete_local_media_after_success">
                                <option value="0" {% if not guild.external_backup.delete_local_media_after_success %}selected{% endif %}>Disabled</option>
                                <option value="1" {% if guild.external_backup.delete_local_media_after_success %}selected{% endif %}>Enabled after successful rclone copy</option>
                            </select>
                        </td></tr>
                        <tr><th>Max file bytes override</th><td><input name="guild_max_file_bytes" value="{{ guild.limits.max_file_bytes }}"></td></tr>
                        <tr><th>Max total bytes override</th><td><input name="guild_max_total_bytes" value="{{ guild.limits.max_total_bytes }}"></td></tr>
                        <tr><th>Monthly submission limit</th><td><input name="guild_monthly_submission_limit" value="{{ guild.limits.monthly_submission_limit }}"></td></tr>
                        <tr><th>Active game limit</th><td><input name="guild_active_game_limit" value="{{ guild.limits.active_game_limit }}"></td></tr>
                        <tr><th>Storage limit bytes</th><td><input name="guild_storage_limit_bytes" value="{{ guild.limits.storage_limit_bytes }}"></td></tr>
                        <tr><th>Blocked words</th><td><input name="blocked_words" value="{{ guild.moderation.blocked_words|join(', ') }}" placeholder="comma separated"></td></tr>
                        <tr><th>Allowed media types</th><td><input name="allowed_media_types" value="{{ guild.moderation.allowed_media_types|join(',') }}" placeholder="image,video,audio"></td></tr>
                        <tr><th>New-user approval</th><td>
                            <select name="require_approval_for_new_users">
                                <option value="0" {% if not guild.moderation.require_approval_for_new_users %}selected{% endif %}>Disabled</option>
                                <option value="1" {% if guild.moderation.require_approval_for_new_users %}selected{% endif %}>Enabled</option>
                            </select>
                        </td></tr>
                        <tr><th>New-user days</th><td><input name="new_user_days" value="{{ guild.moderation.new_user_days }}"></td></tr>
                        <tr><th>Spoiler approval</th><td>
                            <select name="spoiler_requires_approval">
                                <option value="0" {% if not guild.moderation.spoiler_requires_approval %}selected{% endif %}>Disabled</option>
                                <option value="1" {% if guild.moderation.spoiler_requires_approval %}selected{% endif %}>Enabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Duplicate media review</th><td>
                            <select name="duplicate_requires_approval">
                                <option value="1" {% if guild.moderation.duplicate_requires_approval %}selected{% endif %}>Enabled</option>
                                <option value="0" {% if not guild.moderation.duplicate_requires_approval %}selected{% endif %}>Disabled</option>
                            </select>
                        </td></tr>
                        <tr><th>Spam burst count</th><td><input name="spam_burst_count" value="{{ guild.moderation.spam_burst_count }}"></td></tr>
                        <tr><th>Spam burst window minutes</th><td><input name="spam_burst_window_minutes" value="{{ guild.moderation.spam_burst_window_minutes }}"></td></tr>
                        <tr><th>Spam review score threshold</th><td><input name="spam_review_threshold" value="{{ guild.moderation.spam_review_threshold }}"></td></tr>
                        <tr><th>Answer reuse cooldown days</th><td><input name="reuse_cooldown_days" value="{{ guild.game_settings.reuse_cooldown_days }}"></td></tr>
                        <tr><th>Default auto-hint minutes</th><td><input name="default_auto_hint_minutes" value="{{ guild.game_settings.default_auto_hint_minutes }}"></td></tr>
                        <tr><th>Default difficulty</th><td><input name="default_difficulty" value="{{ guild.game_settings.default_difficulty }}"></td></tr>
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
                    <tr><th>Emergency pause</th><td>{{ "Enabled" if guild.emergency_paused else "Disabled" }}{% if guild.emergency_reason %}: {{ guild.emergency_reason }}{% endif %}</td></tr>
                    <tr><th>External backup</th><td>
                        <div>Enabled: <code>{{ "Yes" if guild.external_backup.enabled else "No" }}</code></div>
                        <div>Remote: <code>{{ guild.external_backup.remote or "Not set" }}</code></div>
                        <div>Public media URL: <code>{{ guild.external_backup.public_base_url or "Not set" }}</code></div>
                        <div>Last status: <code>{{ guild.external_backup.last_status or "Unknown" }}</code></div>
                        <div>Last success: <code>{{ guild.external_backup.last_success_at or "Never" }}</code></div>
                    </td></tr>
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
                <tr><th>File</th><th>Size</th><th>Modified</th><th>Checksum</th><th>Restore</th><th>Download</th></tr>
            </thead>
            <tbody>
                {% for backup in backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                        <td><code>{{ backup.sha256[:12] if backup.sha256 else "Not checked" }}</code></td>
                        <td class="{{ 'ok' if backup.restore_status == 'passed' else 'bad' if backup.restore_status == 'failed' else '' }}">{{ backup.restore_status or "Not tested" }}</td>
                        <td><a href="{{ url_for('download_backup', name=backup.name, key=admin_key) }}">Download</a></td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No backups found yet.</td></tr>
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
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
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
        <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
        <a href="{{ url_for('admin_monthly_report', key=admin_key) }}">Monthly Report</a>
        <a href="{{ url_for('admin_releases', key=admin_key) }}">Releases</a>
        <a href="{{ url_for('admin_install_doctor', key=admin_key) }}">Install Doctor</a>
        <a href="{{ url_for('admin_approvals', key=admin_key) }}">Approvals</a>
        <a href="{{ url_for('admin_owner_portal', key=admin_key) }}">Owner Portal</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_jobs', key=admin_key) }}">Jobs</a>
        <a href="{{ url_for('admin_production_health', key=admin_key) }}">Health Score</a>
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
                <tr><th>Release dashboard</th><td><a href="{{ url_for('admin_releases', key=admin_key) }}">Open release channel page</a></td></tr>
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
                <tr><th>Bot instance</th><td><code>{{ bot_status.instance_id or "Unknown" }}</code></td></tr>
                <tr><th>Bot host / PID</th><td>{{ bot_status.hostname or "Unknown" }} / {{ bot_status.pid or "Unknown" }}</td></tr>
                <tr><th>Bot directory</th><td><code>{{ bot_status.base_dir or "Unknown" }}</code></td></tr>
                <tr><th>Dashboard instance</th><td><code>{{ dashboard_instance_id }}</code></td></tr>
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
            <button name="action" value="archive_history" type="submit">Archive Old History</button>
            <button name="action" value="archive_history_delete" type="submit" onclick="return confirm('Archive and remove old full submission rows from the live database? Monthly top snapshots stay preserved.');">Archive And Remove Old Full History</button>
            <button name="action" value="rollback_latest_snapshot" type="submit" onclick="return confirm('Queue rollback to the latest deploy snapshot? This can restart SDAC services if the server permissions allow it.');">Rollback Latest Snapshot</button>
            <button name="action" value="optimize_database" type="submit">Optimize SQLite Database</button>
        </form>
        <p class="muted">
            Monthly report export:
            <a href="{{ url_for('admin_monthly_report', key=admin_key) }}">open report page</a>
            or
            <a href="{{ url_for('export_monthly_report', key=admin_key) }}">download current month CSV</a>.
        </p>
    </section>

    <section class="panel">
        <h2>Storage Forecast</h2>
        <table>
            <thead><tr><th>Server</th><th>Current</th><th>Limit</th><th>Recent Growth</th><th>Forecast</th></tr></thead>
            <tbody>
                {% for row in storage_forecasts %}
                    <tr>
                        <td>{{ row.name }}<br><code>{{ row.guild_id }}</code></td>
                        <td>{{ row.current }}</td>
                        <td>{{ row.limit }}</td>
                        <td>{{ row.average }}</td>
                        <td>{{ row.forecast }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="muted">No server storage history yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Offsite Backups</h2>
        <table>
            <tbody>
                <tr><th>Provider</th><td>{{ offsite_backup.provider or "Not set" }}</td></tr>
                <tr><th>Remote</th><td><code>{{ offsite_backup.remote or "Not set" }}</code></td></tr>
                <tr><th>Last success</th><td>{{ offsite_backup.last_success_at or "Unknown" }}</td></tr>
                <tr><th>Last status</th><td>{{ offsite_backup.last_status or "Unknown" }}</td></tr>
                <tr><th>Details</th><td>{{ offsite_backup.last_details or "" }}</td></tr>
            </tbody>
        </table>
        <p class="muted">
            Free options: Google Drive via rclone, Mega via rclone,
            Backblaze B2 free allowance, an existing VPS with rsync, or encrypted
            config-only archives stored in a private GitHub release.
        </p>
        <p><code>bash scripts/backup_offsite.sh remote:sdac-backups</code></p>
        <p><code>bash scripts/sync_media_rclone.sh remote:sdac-media</code></p>
        <h3>Per-Server Backup Targets</h3>
        <table>
            <thead><tr><th>Server</th><th>Remote</th><th>Media URL</th><th>Last status</th><th>Last success</th></tr></thead>
            <tbody>
                {% for row in guild_backup_rows %}
                    <tr>
                        <td>{{ row.name }}<br><code>{{ row.guild_id }}</code></td>
                        <td><code>{{ row.remote or "Not set" }}</code></td>
                        <td><code>{{ row.public_base_url or "Not set" }}</code></td>
                        <td>{{ row.last_status or "Unknown" }}</td>
                        <td>{{ row.last_success_at or "Never" }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5" class="muted">No per-server backup targets configured yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
        <p><code>SDAC_GUILD_ID=123456789 bash scripts/backup_guild_offsite.sh</code></p>
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
            <thead><tr><th>File</th><th>Size</th><th>Modified</th><th>Checksum</th><th>Restore</th><th>Download</th></tr></thead>
            <tbody>
                {% for backup in backups %}
                    <tr>
                        <td><code>{{ backup.name }}</code></td>
                        <td>{{ backup.size }}</td>
                        <td>{{ backup.modified }}</td>
                        <td><code>{{ backup.sha256[:12] if backup.sha256 else "Not checked" }}</code></td>
                        <td class="{{ 'ok' if backup.restore_status == 'passed' else 'bad' if backup.restore_status == 'failed' else '' }}">{{ backup.restore_status or "Not tested" }}</td>
                        <td><a href="{{ url_for('download_backup', name=backup.name, key=admin_key) }}">Download</a></td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No backups found yet.</td></tr>
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


MEDIA_CLEANUP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Media Cleanup</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; word-break: break-word; }
        button { background: #e45d68; border: 0; border-radius: 7px; color: white; cursor: pointer; font-weight: bold; padding: 9px 10px; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 12px; text-align: center; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
        @media (max-width: 760px) {
            body { padding: 12px; }
            table, thead, tbody, tr, th, td { display: block; }
            thead { display: none; }
            tr { border-bottom: 1px solid #30333b; padding: 10px 0; }
            th, td { border-bottom: 0; padding: 6px 0; }
            button { margin-top: 6px; width: 100%; }
        }
    </style>
</head>
<body>
<main>
    <h1>Media Cleanup</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_analytics', key=admin_key) }}">Analytics</a>
        <a href="{{ url_for('admin_jobs', key=admin_key) }}">Jobs</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    {% if notice %}<div class="notice">{{ notice }}</div>{% endif %}

    <section class="panel">
        <h2>Summary</h2>
        <p>
            Orphaned files: <code>{{ report.orphaned_total }}</code> |
            Missing referenced files: <code>{{ report.missing_total }}</code> |
            Oversized files: <code>{{ report.oversized_total }}</code>
        </p>
        <form method="post" onsubmit="return confirm('Delete all listed orphaned files? This cannot be undone.');">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <button type="submit" name="action" value="delete_orphans">Delete Orphaned Files</button>
            <button type="submit" name="action" value="generate_thumbnails">Generate Missing Thumbnails</button>
            <button type="submit" name="action" value="rebuild_media_fingerprints">Rebuild Duplicate Index</button>
            <button type="submit" name="action" value="prune_backed_up_originals" onclick="return confirm('Prune old backed-up originals for all safe servers? Thumbnails stay local.');">Prune Backed-Up Originals</button>
        </form>
    </section>

    <section class="panel">
        <h2>Media Quarantine</h2>
        <table>
            <thead><tr><th>ID</th><th>Submission</th><th>File</th><th>Reason</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
            <tbody>
                {% for item in quarantine_items %}
                    <tr>
                        <td>{{ item.id }}</td>
                        <td><a href="{{ url_for('index', key=admin_key, q=item.submission_id, guild_id=item.guild_id or 'all') }}">#{{ item.submission_id }}</a></td>
                        <td><code>{{ item.media_name or item.original_path }}</code></td>
                        <td>{{ item.reason }}</td>
                        <td><code>{{ item.status }}</code></td>
                        <td>{{ item.created_at }}</td>
                        <td>
                            {% if item.status == "quarantined" %}
                                <form method="post">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="quarantine_id" value="{{ item.id }}">
                                    <button type="submit" name="action" value="restore_quarantine">Restore</button>
                                    <button type="submit" name="action" value="delete_quarantine" onclick="return confirm('Delete this quarantined file?');">Delete</button>
                                </form>
                            {% else %}
                                <span class="muted">Resolved</span>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" class="muted">No quarantined media.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    <section class="panel">
        <h2>Per-Server Storage</h2>
        <table>
            <thead>
                <tr>
                    <th>Server</th>
                    <th>Originals</th>
                    <th>Thumbnails</th>
                    <th>Limit</th>
                    <th>Oldest</th>
                    <th>Backup</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for row in guild_storage_rows %}
                    <tr>
                        <td>{{ row.name }}<br><code>{{ row.guild_id }}</code></td>
                        <td>{{ row.size_label }}<br><span class="muted">{{ row.files }} file(s)</span></td>
                        <td>{{ row.thumbnail_size_label }}<br><span class="muted">{{ row.thumbnail_files }} file(s)</span></td>
                        <td>{{ row.limit_label }}{% if row.limit_percent %}<br><span class="muted">{{ row.limit_percent }}%</span>{% endif %}</td>
                        <td>{{ row.oldest }}</td>
                        <td>
                            {% if row.safe_to_prune %}
                                <strong>Safe to prune</strong>
                            {% else %}
                                <span class="muted">Not safe yet</span>
                            {% endif %}
                            <br><code>{{ row.backup.remote or "No remote" }}</code>
                            {% if row.backup.last_success_at %}<br><span class="muted">{{ row.backup.last_success_at }}</span>{% endif %}
                        </td>
                        <td>
                            <form method="post">
                                <input type="hidden" name="key" value="{{ admin_key }}">
                                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                <input type="hidden" name="guild_id" value="{{ row.guild_id }}">
                                <button type="submit" name="action" value="restore_guild_media">Restore</button>
                                <button type="submit" name="action" value="prune_guild_originals" onclick="return confirm('Prune old backed-up originals for this server?');">Prune</button>
                            </form>
                            {% if row.restore_command %}
                                <p class="muted"><code>{{ row.restore_command }}</code></p>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" class="muted">No configured servers found.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

    {% for title, rows, total in [
        ("Orphaned Files", report.orphaned, report.orphaned_total),
        ("Missing References", report.missing, report.missing_total),
        ("Oversized Files", report.oversized, report.oversized_total)
    ] %}
        <section class="panel">
            <h2>{{ title }}</h2>
            <p class="muted">Showing up to {{ rows|length }} of {{ total }}.</p>
            <table>
                <thead><tr><th>Path</th><th>Size</th></tr></thead>
                <tbody>
                    {% for row in rows %}
                        <tr><td><code>{{ row.relative }}</code></td><td>{{ row.size_label }}</td></tr>
                    {% else %}
                        <tr><td colspan="2" class="muted">Nothing found.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    {% endfor %}
</main>
</body>
</html>
"""


JOBS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Jobs</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; word-break: break-word; }
        .queued { color: #ffd75e; }
        .running { color: #7c9cff; }
        .complete { color: #63c174; }
        .failed { color: #e45d68; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
        @media (max-width: 760px) {
            body { padding: 12px; }
            table, thead, tbody, tr, th, td { display: block; }
            thead { display: none; }
            tr { border-bottom: 1px solid #30333b; padding: 10px 0; }
            th, td { border-bottom: 0; padding: 6px 0; }
        }
    </style>
</head>
<body>
<main>
    <h1>Background Jobs</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_privacy', key=admin_key) }}">Privacy</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <h2>Recent Work</h2>
        <p class="muted">Long-running maintenance tasks are tracked here so the dashboard stays responsive.</p>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Job</th>
                    <th>Server</th>
                    <th>Status</th>
                    <th>Requested By</th>
                    <th>Created</th>
                    <th>Finished</th>
                    <th>Result / Error</th>
                </tr>
            </thead>
            <tbody>
                {% for job in jobs %}
                    <tr>
                        <td><code>#{{ job.id }}</code></td>
                        <td>{{ job.label }}<br><code>{{ job.job_type }}</code></td>
                        <td><code>{{ job.guild_id or "all" }}</code></td>
                        <td class="{{ job.status }}">{{ job.status }}</td>
                        <td>{{ job.requested_by_name or job.requested_by or "unknown" }}</td>
                        <td>{{ job.created_at or "" }}</td>
                        <td>{{ job.finished_at or "" }}</td>
                        <td>
                            {% if job.error %}
                                <span class="failed">{{ job.error }}</span>
                            {% elif job.result %}
                                <code>{{ job.result }}</code>
                            {% else %}
                                <span class="muted">{{ job.payload }}</span>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="8" class="muted">No background jobs yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


PRIVACY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Privacy Tools</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        input, select, button, textarea { border: 1px solid #30333b; border-radius: 7px; font-size: 15px; padding: 9px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .danger { background: #e45d68; color: white; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 12px; text-align: center; }
        .notice.error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
        @media (max-width: 760px) {
            body { padding: 12px; }
            input, select, button { box-sizing: border-box; width: 100%; }
            table, thead, tbody, tr, th, td { display: block; }
            thead { display: none; }
            tr { border-bottom: 1px solid #30333b; padding: 10px 0; }
            th, td { border-bottom: 0; padding: 6px 0; }
        }
    </style>
</head>
<body>
<main>
    <h1>Privacy Tools</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_jobs', key=admin_key) }}">Jobs</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    {% if notice %}<div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>{% endif %}

    <section class="panel">
        <h2>User Data Request</h2>
        <p class="muted">Exports and deletes are scoped to one Discord server. Deleting removes submissions, local media, duplicate fingerprints, points, correct guesses, and cooldown rows for that user.</p>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <table>
                <tbody>
                    <tr><th>Server</th><td>
                        <select name="guild_id">
                            {% for guild in guild_options %}
                                <option value="{{ guild.id }}">{{ guild.name }} ({{ guild.id }})</option>
                            {% endfor %}
                        </select>
                    </td></tr>
                    <tr><th>User ID</th><td><input name="user_id" placeholder="Discord user ID" required></td></tr>
                    <tr><th>Delete confirmation</th><td><input name="confirm_delete" placeholder="Type DELETE before deleting"></td></tr>
                </tbody>
            </table>
            <button type="submit" name="action" value="export">Export User Data</button>
            <button class="danger" type="submit" name="action" value="delete" onclick="return confirm('Delete this user data from the selected server?');">Delete User Data</button>
        </form>
    </section>

    <section class="panel">
        <h2>Recent Privacy Actions</h2>
        <table>
            <thead><tr><th>Server</th><th>User</th><th>Action</th><th>Actor</th><th>Details</th><th>Created</th></tr></thead>
            <tbody>
                {% for action in actions %}
                    <tr>
                        <td><code>{{ action.guild_id }}</code></td>
                        <td><code>{{ action.user_id }}</code></td>
                        <td>{{ action.action }}</td>
                        <td>{{ action.actor_username }}</td>
                        <td><code>{{ action.details_json }}</code></td>
                        <td>{{ action.created_at }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="6" class="muted">No privacy actions have been recorded yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


ANALYTICS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Analytics</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; }
        select, button { border: 1px solid #30333b; border-radius: 7px; font-size: 15px; padding: 9px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Analytics</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_monthly_report', key=admin_key) }}">Monthly Report</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <form method="get">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <select name="guild_id">
                <option value="all">All available servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                {% endfor %}
            </select>
            <button type="submit">Filter</button>
        </form>
    </section>

    <section class="grid">
        {% for label, value in totals.items() %}
            <div class="panel"><h2>{{ label }}</h2><p><code>{{ value }}</code></p></div>
        {% endfor %}
    </section>

    <section class="grid">
        <div class="panel">
            <h2>Submissions By Month</h2>
            <table><tbody>
                {% for row in submissions_by_month %}
                    <tr><td>{{ row.month }}</td><td>{{ row.count }}</td></tr>
                {% else %}<tr><td colspan="2" class="muted">No submissions yet.</td></tr>{% endfor %}
            </tbody></table>
        </div>
        <div class="panel">
            <h2>Top Categories</h2>
            <table><tbody>
                {% for row in top_categories %}
                    <tr><td>{{ row.category or "Uncategorized" }}</td><td>{{ row.count }}</td></tr>
                {% else %}<tr><td colspan="2" class="muted">No categories yet.</td></tr>{% endfor %}
            </tbody></table>
        </div>
        <div class="panel">
            <h2>Top Submitters</h2>
            <table><tbody>
                {% for row in top_submitters %}
                    <tr><td>{{ row.username }}</td><td>{{ row.count }}</td></tr>
                {% else %}<tr><td colspan="2" class="muted">No submitters yet.</td></tr>{% endfor %}
            </tbody></table>
        </div>
        <div class="panel">
            <h2>Recent Game Answers</h2>
            <table>
                <thead><tr><th>Answer</th><th>Category</th><th>Source</th><th>Used</th></tr></thead>
                <tbody>
                    {% for row in answer_history %}
                        <tr><td>{{ row.answer_display }}</td><td>{{ row.category or "-" }}</td><td>{{ row.source }}</td><td>{{ row.created_at }}</td></tr>
                    {% else %}<tr><td colspan="4" class="muted">No game answers recorded yet.</td></tr>{% endfor %}
                </tbody>
            </table>
        </div>
    </section>
</main>
</body>
</html>
"""


MONTHLY_REPORT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Monthly Report</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav, form { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        select, input, button { border: 1px solid #30333b; border-radius: 7px; font-size: 15px; padding: 9px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Monthly Report</h1>
    <nav>
        <a href="{{ url_for('admin_analytics', key=admin_key) }}">Analytics</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <form method="get">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <select name="guild_id">
                <option value="all">All available servers</option>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}" {% if selected_guild_id == guild.id %}selected{% endif %}>{{ guild.name }}</option>
                {% endfor %}
            </select>
            <input name="month" value="{{ month }}" pattern="\\d{4}-\\d{2}" placeholder="YYYY-MM">
            <button type="submit">View Report</button>
            <a href="{{ url_for('export_monthly_report', key=admin_key, guild_id=selected_guild_id or 'all', month=month) }}">Download CSV</a>
        </form>
    </section>
    <section class="grid">
        {% for label, value in totals.items() %}
            <div class="panel"><h2>{{ label }}</h2><p><code>{{ value }}</code></p></div>
        {% endfor %}
    </section>
    <section class="grid">
        <div class="panel">
            <h2>Top Submissions</h2>
            <table>
                <thead><tr><th>Rank</th><th>User</th><th>Category</th><th>Votes</th><th>Submission</th></tr></thead>
                <tbody>
                    {% for row in top_submissions %}
                        <tr><td>{{ loop.index }}</td><td>{{ row.username }}</td><td>{{ row.category or "Uncategorized" }}</td><td>{{ row.stars }}</td><td><a href="{{ url_for('index', key=admin_key, q=row.id, guild_id=row.guild_id or 'all') }}">#{{ row.id }}</a></td></tr>
                    {% else %}<tr><td colspan="5" class="muted">No submissions for this month.</td></tr>{% endfor %}
                </tbody>
            </table>
        </div>
        <div class="panel">
            <h2>Top Guessers</h2>
            <table>
                <thead><tr><th>Rank</th><th>User</th><th>Points</th><th>Server</th></tr></thead>
                <tbody>
                    {% for row in top_guessers %}
                        <tr><td>{{ loop.index }}</td><td>{{ row.username }}</td><td>{{ row.points }}</td><td>{{ guild_names.get(row.guild_id, row.guild_id) }}</td></tr>
                    {% else %}<tr><td colspan="4" class="muted">No guessing points for this month.</td></tr>{% endfor %}
                </tbody>
            </table>
        </div>
    </section>
    <section class="panel">
        <h2>Activity</h2>
        <table>
            <thead><tr><th>Metric</th><th>Value</th></tr></thead>
            <tbody>
                {% for row in activity %}
                    <tr><td>{{ row.label }}</td><td>{{ row.value }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


RELEASES_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Release Channel</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        .ok { color: #63c174; font-weight: bold; }
        .bad { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Release Channel</h1>
    <nav>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_production_health', key=admin_key) }}">Health Score</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <h2>Installed And Available</h2>
        <table>
            <tbody>
                <tr><th>Installed release</th><td><code>{{ release_status.installed }}</code></td></tr>
                <tr><th>Configured update tag</th><td><code>{{ release_status.configured_tag }}</code></td></tr>
                <tr><th>User/fork repository</th><td><code>{{ release_status.repo }}</code></td></tr>
                <tr><th>Original repository</th><td><code>{{ release_status.original_repo }}</code></td></tr>
                <tr><th>Latest official</th><td><code>{{ release_status.official.tag }}</code>{% if release_status.official.published_at %} ({{ release_status.official.published_at }}){% endif %}</td></tr>
                <tr><th>Latest experimental</th><td><code>{{ release_status.experimental.tag }}</code>{% if release_status.experimental.published_at %} ({{ release_status.experimental.published_at }}){% endif %}</td></tr>
                {% if release_status.error %}<tr><th>Release check</th><td class="bad">{{ release_status.error }}</td></tr>{% endif %}
            </tbody>
        </table>
    </section>
    <section class="panel">
        <h2>Update Commands</h2>
        {% if release_status.configured_tag == "latest-experimental" %}
            <p class="bad">This install is tracking the experimental channel. Use it for validation before promoting a build to official.</p>
        {% elif release_status.configured_tag == "latest-official" or release_status.configured_tag == "Version 2" %}
            <p class="ok">This install is tracking the official channel.</p>
        {% else %}
            <p class="muted">This install is pinned to an explicit release. That is safest when you need repeatable deploys.</p>
        {% endif %}
        <p>Stable official channel:</p>
        <p><code>sudo sdac-update latest-official</code></p>
        <p>Version 2 alias:</p>
        <p><code>sudo sdac-update "Version 2"</code></p>
        <p>Exact release:</p>
        <p><code>sudo sdac-update 2.8.2</code></p>
        <p>Experimental test channel:</p>
        <p><code>sudo sdac-update latest-experimental</code></p>
        <p class="muted">Recommendation: run <code>latest-experimental</code> only on a test/verification server, then update production with <code>latest-official</code> after the release is promoted.</p>
    </section>
    <section class="panel">
        <h2>Rollback</h2>
        <p>
            The updater can restore the latest deploy snapshot with:
            <code>sudo sdac-update rollback</code>
        </p>
        <p class="muted">
            You can also queue rollback from Maintenance. The dashboard service
            user must have permission to restart the SDAC systemd services.
        </p>
        <table>
            <thead><tr><th>Snapshot</th><th>Modified</th></tr></thead>
            <tbody>
                {% for snapshot in snapshots %}
                    <tr><td><code>{{ snapshot.name }}</code></td><td>{{ snapshot.modified }}</td></tr>
                {% else %}
                    <tr><td colspan="2" class="muted">No deploy snapshots found yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


CONFIG_DIFF_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Preview Server Config Import</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        .notice { background: #223057; border: 1px solid #4d6ee8; border-radius: 10px; padding: 12px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        pre { background: #111318; border: 1px solid #30333b; border-radius: 8px; margin: 0; max-height: 220px; overflow: auto; padding: 8px; white-space: pre-wrap; }
        .ok { color: #63c174; font-weight: bold; }
        .bad { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
        button { background: #2f6fed; border: 0; border-radius: 8px; color: white; cursor: pointer; margin: 6px; padding: 10px 14px; }
        .secondary { background: #3b3f4a; }
    </style>
</head>
<body>
<main>
    <h1>Preview Config Import</h1>
    <nav>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Back to Settings</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <h2>{{ guild_name }} ({{ guild_id }})</h2>
        <p class="notice">
            Review the changed fields before importing. Confirming replaces this server's SDAC config with the imported server config.
        </p>
        <p class="muted">Source export guild: <code>{{ source_guild_id or "unknown" }}</code></p>
        <form method="post" action="{{ url_for('admin_import_guild_config') }}">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="guild_id" value="{{ guild_id }}">
            <input type="hidden" name="confirm_import" value="1">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <textarea name="config_json" hidden>{{ normalized_json }}</textarea>
            <button type="submit" onclick="return confirm('Import this server config now?');">Confirm Import</button>
            <a class="secondary" href="{{ url_for('admin_settings', key=admin_key) }}">Cancel</a>
        </form>
    </section>
    <section class="panel">
        <h2>Changes</h2>
        <table>
            <thead><tr><th>Field</th><th>Current</th><th>Imported</th></tr></thead>
            <tbody>
                {% for row in diff_rows %}
                    <tr>
                        <td><code>{{ row.path }}</code></td>
                        <td><pre>{{ row.old }}</pre></td>
                        <td><pre>{{ row.new }}</pre></td>
                    </tr>
                {% else %}
                    <tr><td colspan="3" class="muted">No changes detected. You can still confirm to normalize defaults.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


INSTALL_DOCTOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Install Doctor</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        .ok { color: #63c174; font-weight: bold; }
        .bad { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Install Doctor</h1>
    <nav>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_releases', key=admin_key) }}">Releases</a>
        <a href="{{ url_for('admin_health', key=admin_key) }}">Health JSON</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <h2>Score: {{ report.score }} / {{ report.max_score }}</h2>
        <table>
            <thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead>
            <tbody>
                {% for check in report.checks %}
                    <tr>
                        <td>{{ check.label }}</td>
                        <td class="{{ 'ok' if check.ok else 'bad' }}">{{ "OK" if check.ok else "Needs attention" }}</td>
                        <td>{{ check.details }}</td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


APPROVALS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Admin Approvals</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav, form.filters { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        button, select { border: 1px solid #30333b; border-radius: 7px; padding: 8px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .danger { background: #e45d68; color: white; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin-bottom: 16px; padding: 12px; text-align: center; }
        .notice.error { border-color: #e45d68; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Admin Approvals</h1>
    <nav>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_privacy', key=admin_key) }}">Privacy</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    {% if notice %}<div class="notice {{ 'error' if error else '' }}">{{ notice }}</div>{% endif %}
    <section class="panel">
        <form class="filters" method="get">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <select name="status">
                {% for option in ["pending", "complete", "denied", "failed", "all"] %}
                    <option value="{{ option }}" {% if selected_status == option %}selected{% endif %}>{{ option }}</option>
                {% endfor %}
            </select>
            <button type="submit">Filter</button>
        </form>
        <p class="muted">
            When two-admin approval is enabled in Settings, dangerous actions
            are queued here and must be approved by a different dashboard admin.
        </p>
        <table>
            <thead><tr><th>ID</th><th>Action</th><th>Target</th><th>Requested By</th><th>Status</th><th>Payload</th><th>Result</th><th>Actions</th></tr></thead>
            <tbody>
                {% for item in actions %}
                    <tr>
                        <td>{{ item.id }}</td>
                        <td><code>{{ item.action_type }}</code></td>
                        <td>{{ item.target_type }}<br><code>{{ item.target_id }}</code></td>
                        <td>{{ item.requested_by_name }}<br><span class="muted">{{ item.created_at }}</span></td>
                        <td><code>{{ item.status }}</code></td>
                        <td><code>{{ item.payload }}</code></td>
                        <td>{{ item.result_text or "" }}</td>
                        <td>
                            {% if item.status == "pending" %}
                                <form method="post">
                                    <input type="hidden" name="key" value="{{ admin_key }}">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                    <input type="hidden" name="action_id" value="{{ item.id }}">
                                    <button name="decision" value="approve" type="submit">Approve</button>
                                    <button class="danger" name="decision" value="deny" type="submit">Deny</button>
                                </form>
                            {% else %}
                                <span class="muted">Resolved</span>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="8" class="muted">No matching approval actions.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


OWNER_PORTAL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Owner Portal</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .server { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Server Owner Portal</h1>
    <nav>
        <a href="{{ url_for('admin_onboarding', key=admin_key) }}">Onboarding</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_media_cleanup', key=admin_key) }}">Media</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    {% for server in servers %}
        <article class="server">
            <h2>{{ server.name }} <span class="muted">({{ server.id }})</span></h2>
            <table>
                <tbody>
                    <tr><th>Setup score</th><td>{{ server.health }}%</td></tr>
                    <tr><th>Storage</th><td>{{ server.forecast.current if server.forecast else "Unknown" }}; {{ server.forecast.forecast if server.forecast else "No forecast yet." }}</td></tr>
                    <tr><th>Backup</th><td>
                        Enabled: <code>{{ "Yes" if server.backup.enabled else "No" }}</code><br>
                        Remote: <code>{{ server.backup.remote or "Not set" }}</code><br>
                        Last status: <code>{{ server.backup.last_status or "Unknown" }}</code>
                    </td></tr>
                    <tr><th>Quick commands</th><td>
                        {% for command in server.commands %}<code>{{ command }}</code>{% if not loop.last %}<br>{% endif %}{% endfor %}
                    </td></tr>
                    <tr><th>Invite link</th><td>
                        {% if server.invite_url %}<a href="{{ server.invite_url }}" target="_blank">Invite/Re-authorize SDAC</a>{% else %}<span class="muted">Set bot client ID to show invite link.</span>{% endif %}
                    </td></tr>
                </tbody>
            </table>
        </article>
    {% else %}
        <p class="muted">No servers are available to this dashboard admin.</p>
    {% endfor %}
</main>
</body>
</html>
"""


PUBLIC_STATS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Public Stats</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>SDAC Public Stats</h1>
    <nav>
        <a href="{{ url_for('index') }}">Submissions</a>
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('guessing_leaderboard') }}">Guessing leaderboard</a>
        <a href="{{ url_for('achievements') }}">Achievements</a>
    </nav>
    <section class="grid">
        {% for label, value in totals.items() %}
            <div class="panel"><h2>{{ label }}</h2><p><code>{{ value }}</code></p></div>
        {% endfor %}
    </section>
    <section class="panel">
        <h2>Top Servers</h2>
        <table>
            <thead><tr><th>Server</th><th>Submissions</th><th>Guess Points</th></tr></thead>
            <tbody>
                {% for row in servers %}
                    <tr>
                        <td><a href="{{ url_for('server_profile', guild_id=row.id) }}">{{ row.name }}</a></td>
                        <td>{{ row.submissions }}</td>
                        <td>{{ row.guess_points }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="3" class="muted">No public servers yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
    <section class="panel">
        <h2>Monthly Winners</h2>
        <table>
            <thead><tr><th>Month</th><th>User</th><th>Points</th></tr></thead>
            <tbody>
                {% for row in winners %}
                    <tr><td>{{ row.month }}</td><td>{{ row.username }}</td><td>{{ row.points }}</td></tr>
                {% else %}
                    <tr><td colspan="3" class="muted">No winners yet.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
</main>
</body>
</html>
"""


PRODUCTION_HEALTH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Production Health</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1000px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        .ok { color: #63c174; font-weight: bold; }
        .bad { color: #e45d68; font-weight: bold; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Production Health</h1>
    <nav>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_health', key=admin_key) }}">Health JSON</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    <section class="panel">
        <h2>Score: {{ score }} / {{ max_score }}</h2>
        <table>
            <thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead>
            <tbody>
                {% for check in checks %}
                    <tr>
                        <td>{{ check.label }}</td>
                        <td class="{{ 'ok' if check.ok else 'bad' }}">{{ "OK" if check.ok else "Needs attention" }}</td>
                        <td>{{ check.details }}</td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
    <section class="panel">
        <h2>Free Offsite Backup Options</h2>
        <ul>
            {% for option in free_backup_options %}
                <li><strong>{{ option.name }}</strong>: {{ option.details }}</li>
            {% endfor %}
        </ul>
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
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
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
        <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    {% if notice %}
        <div class="notice">{{ notice }}</div>
    {% endif %}

    <section class="panel">
        <h2>Open Submission Reports</h2>
        <form id="bulk-report-form" method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <input type="hidden" name="action" value="bulk_resolve_reports">
            <input name="admin_notes" placeholder="Bulk review notes">
            <button type="submit">Mark Selected Reviewed</button>
        </form>
        <table>
            <thead><tr><th>Select</th><th>Report</th><th>Submission</th><th>Server</th><th>Reporter</th><th>Reason</th><th>Created</th><th>Action</th></tr></thead>
            <tbody>
                {% for report in reports %}
                    <tr>
                        <td><input form="bulk-report-form" type="checkbox" name="report_ids" value="{{ report.id }}"></td>
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
                    <tr><td colspan="8" class="muted">No open reports.</td></tr>
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
        <a href="{{ url_for('admin_seasons', key=admin_key) }}">Seasons</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('audit_log', key=admin_key) }}">Audit log</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>

    <section class="server">
        <h2>New Server Setup Link</h2>
        {% if invite_url %}
            <p><a href="{{ invite_url }}" target="_blank">Invite SDAC Bot to a Discord server</a></p>
        {% else %}
            <p class="muted">
                Set <code>SDAC_BOT_CLIENT_ID</code> or <code>DISCORD_CLIENT_ID</code>
                to show a ready-to-use bot invite link here.
            </p>
        {% endif %}
        <ol>
            <li>Invite the bot with bot and application command scopes.</li>
            <li>Grant the bot channel permissions.</li>
            <li>Run <code>/setup</code> in Discord.</li>
            <li>Run <code>/setuptest</code> or <code>/diagnose</code>.</li>
        </ol>
    </section>

    <section class="server">
        <h2>Setup Templates</h2>
        <table>
            <thead><tr><th>Template</th><th>Best For</th><th>How To Apply</th></tr></thead>
            <tbody>
                {% for template in setup_templates %}
                    <tr>
                        <td>{{ template.label }}</td>
                        <td>{{ template.description }}</td>
                        <td><code>{{ template.command }}</code></td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>

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
            {% if server.last_setup_test %}
                <p>
                    Last setup test:
                    <strong class="{{ 'ok' if server.last_setup_test.status == 'passed' else 'missing' }}">{{ server.last_setup_test.status }}</strong>
                    &middot; {{ server.last_setup_test.summary }}
                    &middot; {{ server.last_setup_test.created_at }}
                    &middot; by {{ server.last_setup_test.actor_username or "unknown" }}
                </p>
            {% else %}
                <p class="muted">No saved setup test yet. Run <code>/setuptest</code> or <code>/diagnose</code> in Discord.</p>
            {% endif %}
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


ABOUT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>About SDAC Bot</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
        code { color: #cdd7ff; }
        .muted { color: #a8adb8; }
        li { margin: 8px 0; }
    </style>
</head>
<body>
<main>
    <h1>About SDAC Bot</h1>
    <nav>
        <a href="{{ url_for('index') }}">Submissions</a>
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('public_stats') }}">Stats</a>
        <a href="{{ url_for('setup_guide') }}">Setup guide</a>
    </nav>

    <section class="panel">
        <h2>What It Does</h2>
        <p>
            SDAC Bot lets Discord communities collect media submissions,
            repost them into organized category channels, vote on favorites,
            and run media guessing games with monthly and cross-server rankings.
        </p>
        <p>
            It includes a web dashboard for approvals, moderation, game-library
            management, analytics, backups, privacy tools, setup health, and
            production maintenance.
        </p>
    </section>

    <section class="grid">
        <div class="panel">
            <h2>Discord Commands</h2>
            <ul>
                <li><code>/submit</code> starts a guided media submission.</li>
                <li><code>/setup</code> walks admins through server setup.</li>
                <li><code>/startgame</code>, <code>/guess</code>, and <code>/correct</code> run guessing games.</li>
                <li><code>/diagnose</code> checks database, folders, permissions, and runtime health.</li>
            </ul>
        </div>
        <div class="panel">
            <h2>Dashboard</h2>
            <ul>
                <li>Public gallery, stats, leaderboards, and server pages.</li>
                <li>Admin review, moderation, audit log, reports, jobs, and privacy actions.</li>
                <li>Release channel, backups, storage forecast, and production checks.</li>
            </ul>
        </div>
    </section>

    <section class="panel">
        <h2>Add It To A Server</h2>
        {% if invite_url %}
            <p><a href="{{ invite_url }}" target="_blank">Invite SDAC Bot with the required permissions</a></p>
        {% else %}
            <p class="muted">
                The invite link is not configured yet. Set
                <code>SDAC_BOT_CLIENT_ID</code> or <code>DISCORD_CLIENT_ID</code>
                on the host.
            </p>
        {% endif %}
        <ol>
            <li>Invite the bot with the bot and application command scopes.</li>
            <li>Run <code>/setup</code> in Discord.</li>
            <li>Run <code>/setuptest</code> or <code>/diagnose</code>.</li>
            <li>Open the dashboard onboarding page if you want a browser checklist.</li>
        </ol>
    </section>
</main>
</body>
</html>
"""


SETUP_GUIDE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Setup Guide</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 900px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        li { margin: 8px 0; }
        code { color: #cdd7ff; }
        .muted { color: #a8adb8; }
    </style>
</head>
<body>
<main>
    <h1>Set Up SDAC In Your Discord</h1>
    <nav>
        <a href="{{ url_for('index') }}">Gallery</a>
        <a href="{{ url_for('servers') }}">Servers</a>
        <a href="{{ url_for('guessing_leaderboard') }}">Guessing leaderboard</a>
    </nav>
    <section class="panel">
        <h2>Fast Path</h2>
        {% if invite_url %}
            <p><a href="{{ invite_url }}" target="_blank" rel="noopener">Invite SDAC Bot</a></p>
        {% else %}
            <p class="muted">The bot invite link is not configured on this dashboard yet.</p>
        {% endif %}
        <ol>
            <li>Invite the bot with <code>bot</code> and <code>applications.commands</code> scopes.</li>
            <li>In Discord, run <code>/setup</code> and walk through the buttons.</li>
            <li>Run <code>/repairpermissions</code> if any channel is missing bot access.</li>
            <li>Run <code>/setuptest</code> to confirm the database, folders, channels, and slash commands are healthy.</li>
            <li>Use <code>/submit category</code> for submissions and <code>/startgame</code> / <code>/guess</code> for guessing games.</li>
        </ol>
    </section>
    <section class="panel">
        <h2>Recommended Channels</h2>
        <ol>
            <li>Submit channel: where users start <code>/submit</code>.</li>
            <li>Category channels: where approved submissions are reposted.</li>
            <li>Approval channel: optional queue for admin review.</li>
            <li>Game summary channel: optional place for daily/monthly guessing results.</li>
            <li>Error channel: private admin channel for bot alerts.</li>
        </ol>
    </section>
    <section class="panel">
        <h2>Admin Commands</h2>
        <p>
            The Discord setup wizard writes the same config as the dashboard.
            If a server is already configured elsewhere, an owner can also export/import
            that server config from the dashboard Settings page.
        </p>
        <p><code>/setup</code> <code>/setupstatus</code> <code>/setuptest</code> <code>/repairpermissions</code></p>
    </section>
</main>
</body>
</html>
"""


SEASONS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SDAC Game Seasons</title>
    <style>
        :root { color-scheme: dark; }
        body { background: #101114; color: #f4f5f7; font-family: Arial, sans-serif; margin: 0; padding: 24px; }
        main { margin: 0 auto; width: min(100%, 1100px); }
        h1, h2 { text-align: center; }
        a { color: #7c9cff; }
        nav { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-bottom: 24px; }
        .panel { background: #1b1d22; border: 1px solid #30333b; border-radius: 12px; margin: 16px 0; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border-bottom: 1px solid #30333b; padding: 10px; text-align: left; vertical-align: top; }
        input, select, button { border: 1px solid #30333b; border-radius: 7px; font-size: 15px; padding: 9px 10px; }
        button { background: #7c9cff; color: #0b1020; cursor: pointer; font-weight: bold; }
        .notice { border: 1px solid #30333b; border-radius: 8px; margin: 0 auto 20px; padding: 12px; text-align: center; }
        .muted { color: #a8adb8; }
        code { color: #cdd7ff; }
    </style>
</head>
<body>
<main>
    <h1>Game Seasons</h1>
    <nav>
        <a href="{{ url_for('index', key=admin_key) }}">Submissions</a>
        <a href="{{ url_for('admin_settings', key=admin_key) }}">Settings</a>
        <a href="{{ url_for('admin_game_library', key=admin_key) }}">Game Library</a>
        <a href="{{ url_for('admin_moderation', key=admin_key) }}">Moderation</a>
        <a href="{{ url_for('admin_maintenance', key=admin_key) }}">Maintenance</a>
        <a href="{{ url_for('admin_logout') }}">Log out</a>
    </nav>
    {% if notice %}<div class="notice">{{ notice }}</div>{% endif %}

    <section class="panel">
        <h2>Create Season</h2>
        <form method="post">
            <input type="hidden" name="key" value="{{ admin_key }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <input type="hidden" name="action" value="create_season">
            <select name="guild_id" required>
                {% for guild in guild_options %}
                    <option value="{{ guild.id }}">{{ guild.name }}</option>
                {% endfor %}
            </select>
            <input name="name" maxlength="120" placeholder="Summer Season" required>
            <input name="starts_at" placeholder="2026-07-01">
            <input name="ends_at" placeholder="2026-07-31">
            <button type="submit">Create Season</button>
        </form>
    </section>

    {% for season in seasons %}
        <section class="panel">
            <h2>{{ season.name }} <span class="muted">({{ season.status }})</span></h2>
            <p>
                {{ season.guild_name }} &middot;
                <code>{{ season.starts_at }}</code> to <code>{{ season.ends_at }}</code>
                {% if season.winner_username %}
                    &middot; Winner: <strong>{{ season.winner_username }}</strong> ({{ season.winner_points }})
                {% endif %}
            </p>
            <form method="post">
                <input type="hidden" name="key" value="{{ admin_key }}">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <input type="hidden" name="action" value="close_season">
                <input type="hidden" name="season_id" value="{{ season.id }}">
                <button type="submit">Close And Archive Winner</button>
            </form>
            <table>
                <thead><tr><th>Rank</th><th>User</th><th>Correct Guesses</th></tr></thead>
                <tbody>
                    {% for row in season.leaderboard %}
                        <tr><td>{{ loop.index }}</td><td>{{ row.username }}</td><td>{{ row.points }}</td></tr>
                    {% else %}
                        <tr><td colspan="3" class="muted">No correct guesses in this season window yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>
    {% else %}
        <p class="muted">No seasons have been created yet.</p>
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


def fill_nested_defaults(target, defaults):
    changed = False
    for key, value in defaults.items():
        if key not in target:
            target[key] = json.loads(json.dumps(value))
            changed = True
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            if fill_nested_defaults(target[key], value):
                changed = True
    return changed


def load_config():
    if not CONFIG_FILE.exists():
        return {
            "guilds": {},
            "limits": dict(DEFAULT_LIMITS),
            "offsite_backup": dict(DEFAULT_OFFSITE_BACKUP),
        }
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    limits = data.setdefault("limits", {})
    offsite_backup = data.setdefault("offsite_backup", {})
    changed = False
    for key, value in DEFAULT_LIMITS.items():
        if key not in limits:
            limits[key] = value
            changed = True
    if fill_nested_defaults(offsite_backup, DEFAULT_OFFSITE_BACKUP):
        changed = True
    for guild_config in (data.get("guilds") or {}).values():
        for key, value in DEFAULT_GUILD_FIELDS.items():
            if key not in guild_config:
                guild_config[key] = json.loads(json.dumps(value))
                changed = True
            elif isinstance(value, dict) and isinstance(guild_config.get(key), dict):
                if fill_nested_defaults(guild_config[key], value):
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
                "background_jobs",
                "media_fingerprints",
                "privacy_actions",
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
    if backup_path:
        record_backup_integrity(backup_path, status, details)
    return passed, backup_path, details


def archive_old_submission_history(delete_exported=False):
    config_data = load_config()
    limits = config_data.get("limits") or {}
    try:
        months = int(limits.get("archive_full_history_after_months") or 18)
    except (TypeError, ValueError):
        months = 18
    months = max(1, months)
    now = datetime.now(timezone.utc)
    cutoff_year = now.year
    cutoff_month = now.month - months
    while cutoff_month <= 0:
        cutoff_month += 12
        cutoff_year -= 1
    cutoff = f"{cutoff_year:04d}-{cutoff_month:02d}"
    archive_dir = BACKUP_DIR / "history-archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"submissions-before-{cutoff}"
        f"{'-removed' if delete_exported else ''}.json.gz"
    )
    with closing(connect_db()) as connection:
        month_rows = connection.execute("""
            SELECT DISTINCT substr(COALESCE(created_at, submitted_at), 1, 7) AS month
            FROM submissions
            WHERE COALESCE(created_at, submitted_at, '') != ''
              AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            ORDER BY month
        """, (cutoff,)).fetchall()
        for row in month_rows:
            preserve_monthly_submission_top(connection, row["month"])
        rows = connection.execute("""
            SELECT *
            FROM submissions
            WHERE COALESCE(created_at, submitted_at, '') != ''
              AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            ORDER BY created_at, id
        """, (cutoff,)).fetchall()
        payload = {
            "created_at": utc_now_iso(),
            "cutoff_month": cutoff,
            "delete_exported": bool(delete_exported),
            "rows": [
                {key: row[key] for key in row.keys()}
                for row in rows
            ],
        }
        with gzip.open(archive_path, "wt", encoding="utf-8") as archive_file:
            json.dump(payload, archive_file, indent=2)
            archive_file.write("\n")
        if delete_exported and rows:
            connection.execute("""
                DELETE FROM submissions
                WHERE COALESCE(created_at, submitted_at, '') != ''
                  AND substr(COALESCE(created_at, submitted_at), 1, 7) < ?
            """, (cutoff,))
        connection.commit()
    return archive_path, len(rows), cutoff


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


def free_offsite_backup_options():
    return [
        {
            "name": "Google Drive via rclone",
            "details": "Free personal storage tier; easiest rclone target for many small installs.",
        },
        {
            "name": "Mega via rclone",
            "details": "Large free tier in many regions; good for compressed media snapshots.",
        },
        {
            "name": "Backblaze B2 free allowance",
            "details": "Free daily download allowance and small free storage amount; good for testing.",
        },
        {
            "name": "GitHub private release/manual upload",
            "details": "Free for config-only encrypted archives; do not upload tokens or public media dumps.",
        },
        {
            "name": "Another cheap/free VPS with rsync",
            "details": "Free if you already have another machine; use SSH keys and encrypted archives.",
        },
    ]


def production_health_report(config_data=None):
    config_data = config_data or load_config()
    bot_status = read_bot_status()
    warnings = security_warnings() + storage_warnings(config_data)
    offsite = config_data.get("offsite_backup") or {}
    guild_backups = [
        (guild_config.get("external_backup") or {})
        for guild_config in (config_data.get("guilds") or {}).values()
    ]
    configured_guild_backups = [
        backup
        for backup in guild_backups
        if backup.get("enabled") and backup.get("remote")
    ]
    checks = []

    def add(label, ok, details):
        checks.append({"label": label, "ok": bool(ok), "details": details})

    add("Secrets", not security_warnings(), "No default/missing dashboard secrets." if not security_warnings() else "; ".join(security_warnings()))
    add("Discord OAuth", oauth_enabled(), "OAuth configured." if oauth_enabled() else "Set SDAC_DISCORD_CLIENT_ID and SDAC_DISCORD_CLIENT_SECRET.")
    add("Bot heartbeat", bot_status.get("fresh"), bot_status.get("message") or "No heartbeat.")
    add("Database backend", True, "PostgreSQL mode." if using_postgres() else "SQLite mode.")
    add("Backups", bool(recent_database_backups()), "Recent backup found." if recent_database_backups() else "No database backup found yet.")
    add(
        "Offsite backups",
        bool(offsite.get("last_success_at") or offsite.get("remote")),
        offsite.get("last_success_at") or offsite.get("remote") or "No offsite backup destination recorded.",
    )
    add(
        "Per-server backups",
        bool(configured_guild_backups),
        (
            f"{len(configured_guild_backups)} guild backup target(s) configured."
            if configured_guild_backups
            else "No guild-specific backup targets configured."
        ),
    )
    add("Storage warnings", not storage_warnings(config_data), "No storage warnings." if not storage_warnings(config_data) else "; ".join(storage_warnings(config_data)))
    add("Public URL", bool(os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN")), "Public URL configured." if os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN") else "Set SDAC_PUBLIC_URL.")
    add("Guilds configured", bool(config_data.get("guilds")), f"{len(config_data.get('guilds') or {})} guild(s) configured.")
    add(
        "Instance ID",
        bool(os.getenv("SDAC_INSTANCE_ID")),
        (
            f"Explicit SDAC_INSTANCE_ID={DASHBOARD_INSTANCE_ID}."
            if os.getenv("SDAC_INSTANCE_ID")
            else f"Using generated instance ID {DASHBOARD_INSTANCE_ID}; set SDAC_INSTANCE_ID for multi-instance hosts."
        ),
    )
    add(
        "Release updater",
        bool(release_status().get("configured_tag")),
        f"Configured tag: {release_status().get('configured_tag') or 'unknown'}",
    )
    add("Warnings", not warnings, "No warnings." if not warnings else "; ".join(warnings))
    score = sum(1 for check in checks if check["ok"])
    return {
        "score": score,
        "max_score": len(checks),
        "checks": checks,
    }


def doctor_item(label, ok, details, severity="warn"):
    return {
        "label": label,
        "ok": bool(ok),
        "details": details,
        "severity": severity,
    }


def command_available(command):
    return shutil.which(command) is not None


def check_directory_writable(path):
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".sdac-write-test-{secrets.token_hex(4)}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, f"Writable: {path}"
    except OSError as error:
        return False, f"Not writable: {path} ({error})"


def install_doctor_report():
    checks = []
    config_data = load_config()
    update_config = read_update_config()

    def add(label, ok, details, severity="warn"):
        checks.append(doctor_item(label, ok, details, severity))

    add("Discord token", bool(TOKEN), "DISCORD_TOKEN is set." if TOKEN else "DISCORD_TOKEN is missing.", "critical")
    add("Admin password", ADMIN_PASSWORD != ADMIN_KEY, "Separate dashboard password configured." if ADMIN_PASSWORD != ADMIN_KEY else "SDAC_ADMIN_PASSWORD still matches the admin key.", "critical")
    add("Session secret", bool(os.getenv("SDAC_SECRET_KEY")), "SDAC_SECRET_KEY is set." if os.getenv("SDAC_SECRET_KEY") else "Set SDAC_SECRET_KEY for stable sessions.", "critical")
    add("Public URL", bool(os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN")), os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN") or "Set SDAC_PUBLIC_URL or SDAC_DOMAIN.")
    add("Configured guilds", bool(config_data.get("guilds")), f"{len(config_data.get('guilds') or {})} guild(s) configured.")
    add("Repository", bool(RELEASE_REPO), f"User/fork repo: {RELEASE_REPO}; original repo: {ORIGINAL_REPO}.")

    for label, path in (
        ("Media folder", MEDIA_DIR),
        ("Backup folder", BACKUP_DIR),
        ("Config folder", CONFIG_FILE.parent),
        ("Quarantine folder", MEDIA_QUARANTINE_DIR),
    ):
        ok, details = check_directory_writable(path)
        add(label, ok, details, "critical" if not ok else "warn")

    try:
        with closing(connect_db()) as connection:
            schema_row = connection.execute("""
                SELECT version
                FROM schema_version
                WHERE id = 1
            """).fetchone()
            version = int(schema_row["version"]) if schema_row else 0
            if using_postgres():
                table_details = "PostgreSQL backend."
            else:
                table_count = connection.execute("""
                    SELECT COUNT(*)
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchone()[0]
                table_details = f"{table_count} table(s)."
        add("Database schema", version >= SCHEMA_VERSION, f"Schema v{version}; expected v{SCHEMA_VERSION}; {table_details}", "critical")
    except Exception as error:
        add("Database schema", False, f"Database check failed: {error}", "critical")

    bot_status = read_bot_status()
    add("Bot heartbeat", bot_status.get("fresh"), bot_status.get("message") or "No heartbeat.", "critical")
    add(
        "Instance ID",
        bool(os.getenv("SDAC_INSTANCE_ID")),
        (
            f"Explicit SDAC_INSTANCE_ID={DASHBOARD_INSTANCE_ID}; bot reports {bot_status.get('instance_id') or 'unknown'}."
            if os.getenv("SDAC_INSTANCE_ID")
            else f"Generated ID {DASHBOARD_INSTANCE_ID}; set SDAC_INSTANCE_ID when running multiple installs on one host."
        ),
    )

    add("Updater config", bool(update_config), f"Update config: {UPDATE_ENV_FILE}" if update_config else f"No readable updater config at {UPDATE_ENV_FILE}.")
    add("Updater command", Path("/usr/local/bin/sdac-update").exists() or (BASE_DIR / "scripts" / "update_from_github.sh").is_file(), "sdac-update command or bundled updater script found.")
    add("Rollback script", (BASE_DIR / "scripts" / "rollback_ubuntu.sh").is_file(), "Rollback script is bundled." if (BASE_DIR / "scripts" / "rollback_ubuntu.sh").is_file() else "Missing scripts/rollback_ubuntu.sh.")

    systemd_available = command_available("systemctl")
    add("systemd", systemd_available, "systemctl is available." if systemd_available else "systemctl is not available on this host.")
    if os.name != "nt":
        add("sdac-bot unit", Path("/etc/systemd/system/sdac-bot.service").exists(), "/etc/systemd/system/sdac-bot.service")
        add("sdac-dashboard unit", Path("/etc/systemd/system/sdac-dashboard.service").exists(), "/etc/systemd/system/sdac-dashboard.service")

    nginx_available = command_available("nginx")
    add("Nginx", nginx_available, "nginx command found." if nginx_available else "nginx command not found.")
    if nginx_available:
        try:
            result = subprocess.run(
                ["nginx", "-t"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            add("Nginx config", result.returncode == 0, (result.stderr or result.stdout or "nginx -t ran.")[-500:])
        except (OSError, subprocess.SubprocessError) as error:
            add("Nginx config", False, f"nginx -t failed: {error}")

    certbot_needed = bool(os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN"))
    certbot_available = command_available("certbot")
    add("Certbot", (not certbot_needed) or certbot_available, "certbot found." if certbot_available else "certbot not found; needed for public HTTPS hosts.")

    release = release_status()
    add("Release check", not release.get("error"), release.get("error") or f"Official: {release['official']['tag']}; Experimental: {release['experimental']['tag']}.")

    score = sum(1 for check in checks if check["ok"])
    return {
        "score": score,
        "max_score": len(checks),
        "checks": checks,
    }


def owner_portal_rows():
    config_data = load_config()
    onboarding = {row["id"]: row for row in build_onboarding_rows(config_data)}
    forecasts = {row["guild_id"]: row for row in storage_forecast_rows(config_data)}
    backup_rows = {row["guild_id"]: row for row in guild_storage_rows(config_data)}
    rows = []
    for option in guild_options(config_data):
        guild_id = option["id"]
        guild_config = (config_data.get("guilds") or {}).get(guild_id) or {}
        backup = guild_config.get("external_backup") or {}
        rows.append({
            "id": guild_id,
            "name": option["name"],
            "health": (onboarding.get(guild_id) or {}).get("health_score", 0),
            "forecast": forecasts.get(guild_id),
            "storage": backup_rows.get(guild_id),
            "backup": backup,
            "invite_url": bot_invite_url(),
            "commands": [
                "/setup",
                "/diagnose",
                "/repairpermissions",
                "/serverbackupstatus",
            ],
        })
    return rows


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
        "thumbnail_path": create_media_thumbnail(path, filename),
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
    maybe_compress_image(path, filename)

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
    thumb_path = thumbnail_path_for_media(file_path)
    if thumb_path and thumb_path.is_file():
        try:
            thumb_path.unlink()
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


def admin_scope_filter(column, config_data=None, include_global=False):
    if current_admin_role() == "owner":
        return "", []
    filter_sql, parameters = guild_id_filter(
        column,
        current_admin_allowed_guild_ids(config_data),
    )
    if include_global:
        filter_sql = f"({filter_sql} OR {column} IS NULL OR {column} = '')"
    return filter_sql, parameters


def guild_options(config_data=None, public_only=False):
    config_data = config_data or load_config()
    allowed_admin_ids = None
    if (
        not public_only
        and has_request_context()
        and is_admin_logged_in()
        and current_admin_role() != "owner"
    ):
        allowed_admin_ids = current_admin_allowed_guild_ids(config_data)
    options = []
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items(),
        key=lambda item: (
            item[1].get("guild_name") or item[0]
        ).casefold(),
    ):
        if allowed_admin_ids is not None and str(guild_id) not in allowed_admin_ids:
            continue
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


def bot_invite_url():
    client_id = (
        os.getenv("SDAC_BOT_CLIENT_ID")
        or os.getenv("DISCORD_CLIENT_ID")
        or ""
    ).strip()
    if not client_id:
        return ""
    permissions = os.getenv("SDAC_BOT_PERMISSIONS", "274878221376")
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}"
        f"&permissions={permissions}"
        "&scope=bot%20applications.commands"
    )


def onboarding_item(ok, label, fix, optional=False):
    return {
        "ok": bool(ok),
        "label": label,
        "fix": fix,
        "optional": optional,
    }


def latest_setup_test_rows():
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT *
            FROM setup_test_runs
            ORDER BY created_at DESC, id DESC
        """).fetchall()
    latest = {}
    for row in rows:
        guild_id = row["guild_id"] or ""
        if guild_id and guild_id not in latest:
            latest[guild_id] = row
    return latest


def season_leaderboard(connection, season, limit=10):
    return connection.execute("""
        SELECT user_id, username, COUNT(*) AS points
        FROM guess_correct_guesses
        WHERE guild_id = ?
          AND guessed_at >= ?
          AND guessed_at <= ?
        GROUP BY user_id, username
        ORDER BY points DESC, MIN(guessed_at) ASC
        LIMIT ?
    """, (
        season["guild_id"],
        season["starts_at"],
        season["ends_at"],
        limit,
    )).fetchall()


def build_onboarding_rows(config_data):
    rows = []
    setup_tests = latest_setup_test_rows()
    allowed_ids = (
        current_admin_allowed_guild_ids(config_data)
        if has_request_context() and is_admin_logged_in()
        else set((config_data.get("guilds") or {}).keys())
    )
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items(),
        key=lambda item: (
            item[1].get("guild_name") or item[0]
        ).casefold(),
    ):
        if str(guild_id) not in allowed_ids:
            continue
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
            "last_setup_test": setup_tests.get(guild_id),
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
    restricted_admin = is_admin_logged_in() and current_admin_role() != "owner"
    if requested == "all":
        session.pop("sdac_guild_id", None)
        if restricted_admin and valid_ids:
            selected = sorted(valid_ids)[0]
            session["sdac_guild_id"] = selected
            return selected
        return ""
    if requested in valid_ids:
        session["sdac_guild_id"] = requested
        return requested

    stored = session.get("sdac_guild_id", "")
    if stored in valid_ids:
        return stored
    session.pop("sdac_guild_id", None)
    if restricted_admin and valid_ids:
        selected = sorted(valid_ids)[0]
        session["sdac_guild_id"] = selected
        return selected
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
    record_backup_integrity(backup_path)
    return backup_path, True, "Backup created."


def backup_sha256(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def record_backup_integrity(backup_path, restore_status="", restore_details=""):
    if not backup_path or not Path(backup_path).is_file():
        return
    backup_path = Path(backup_path)
    stat = backup_path.stat()
    digest = backup_sha256(backup_path)
    with database() as connection:
        connection.execute("""
            INSERT INTO backup_integrity (
                backup_name, sha256, size_bytes, restore_status,
                restore_details, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(backup_name) DO UPDATE SET
                sha256 = excluded.sha256,
                size_bytes = excluded.size_bytes,
                restore_status = COALESCE(NULLIF(excluded.restore_status, ''), backup_integrity.restore_status),
                restore_details = COALESCE(NULLIF(excluded.restore_details, ''), backup_integrity.restore_details),
                checked_at = excluded.checked_at
        """, (
            backup_path.name,
            digest,
            int(stat.st_size),
            restore_status,
            restore_details,
            utc_now_iso(),
        ))


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
    return connect_database(DB_FILE, timeout=30)


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
            CREATE TABLE IF NOT EXISTS background_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT,
                guild_id TEXT,
                status TEXT DEFAULT 'queued',
                requested_by TEXT,
                requested_by_name TEXT,
                payload_json TEXT,
                result_json TEXT,
                error TEXT,
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_admin_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'moderator',
                disabled INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                last_login_at TEXT,
                guild_ids_json TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS setup_test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                status TEXT,
                summary TEXT,
                details_json TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                event_key TEXT,
                channel_id TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE (guild_id, event_key)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS game_seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                name TEXT,
                starts_at TEXT,
                ends_at TEXT,
                status TEXT DEFAULT 'active',
                winner_user_id TEXT,
                winner_username TEXT,
                winner_points INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS backup_integrity (
                backup_name TEXT PRIMARY KEY,
                sha256 TEXT,
                size_bytes INTEGER DEFAULT 0,
                restore_status TEXT,
                restore_details TEXT,
                checked_at TEXT
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
            CREATE TABLE IF NOT EXISTS guess_answer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                game_id INTEGER,
                library_item_id INTEGER,
                answer TEXT,
                answer_display TEXT,
                category TEXT,
                source TEXT,
                started_by TEXT,
                created_at TEXT
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
            CREATE TABLE IF NOT EXISTS media_fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_hash TEXT,
                guild_id TEXT,
                submission_id INTEGER,
                media_path TEXT,
                media_name TEXT,
                size_bytes INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS privacy_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                user_id TEXT,
                action TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                details_json TEXT,
                created_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS pending_admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action_type TEXT,
                target_type TEXT,
                target_id TEXT,
                payload_json TEXT,
                requested_by TEXT,
                requested_by_name TEXT,
                approved_by TEXT,
                approved_by_name TEXT,
                status TEXT DEFAULT 'pending',
                result_text TEXT,
                created_at TEXT,
                approved_at TEXT,
                completed_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS media_quarantine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                submission_id INTEGER,
                original_path TEXT,
                quarantine_path TEXT,
                media_name TEXT,
                reason TEXT,
                status TEXT DEFAULT 'quarantined',
                actor_user_id TEXT,
                actor_username TEXT,
                created_at TEXT,
                resolved_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monthly_digest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                month TEXT,
                status TEXT,
                details_json TEXT,
                posted_at TEXT,
                created_at TEXT
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
            "media_hashes": "TEXT",
            "spam_score": "INTEGER DEFAULT 0",
            "spam_reasons_json": "TEXT",
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
        dashboard_user_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(dashboard_admin_users)"
            ).fetchall()
        }
        if "guild_ids_json" not in dashboard_user_columns:
            connection.execute(
                "ALTER TABLE dashboard_admin_users ADD COLUMN guild_ids_json TEXT"
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
            CREATE INDEX IF NOT EXISTS idx_submissions_user_created
            ON submissions (guild_id, user_id, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_jobs_status_created
            ON background_jobs (status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_background_jobs_guild_created
            ON background_jobs (guild_id, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_fingerprints_guild_hash
            ON media_fingerprints (guild_id, media_hash)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_privacy_actions_guild_user_created
            ON privacy_actions (guild_id, user_id, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_admin_actions_status_created
            ON pending_admin_actions (status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_admin_actions_guild_status
            ON pending_admin_actions (guild_id, status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_quarantine_status_created
            ON media_quarantine (status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_quarantine_submission
            ON media_quarantine (submission_id, status)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_digest_runs_guild_month
            ON monthly_digest_runs (guild_id, month, created_at)
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
            CREATE INDEX IF NOT EXISTS idx_guess_answer_history_guild_answer
            ON guess_answer_history (guild_id, answer, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_answer_history_library
            ON guess_answer_history (library_item_id, created_at)
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
            CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_role
            ON dashboard_admin_users (role, disabled)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_setup_test_runs_guild_created
            ON setup_test_runs (guild_id, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_notifications_guild_event
            ON admin_notifications (guild_id, event_key, enabled)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_game_seasons_guild_status
            ON game_seasons (guild_id, status, starts_at, ends_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_backup_integrity_checked
            ON backup_integrity (checked_at)
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


def guild_media_public_base_url(guild_id, config_data=None):
    if not guild_id:
        return ""
    if config_data is not None:
        guild_config = (config_data.get("guilds") or {}).get(str(guild_id)) or {}
        backup = guild_config.get("external_backup") or {}
        return (backup.get("public_base_url") or "").strip().rstrip("/")
    try:
        config_mtime = CONFIG_FILE.stat().st_mtime
    except OSError:
        config_mtime = None
    if GUILD_MEDIA_BASE_CACHE["mtime"] != config_mtime:
        loaded = load_config()
        GUILD_MEDIA_BASE_CACHE["mtime"] = config_mtime
        GUILD_MEDIA_BASE_CACHE["bases"] = {
            str(cached_guild_id): (
                ((cached_guild.get("external_backup") or {}).get("public_base_url") or "")
                .strip()
                .rstrip("/")
            )
            for cached_guild_id, cached_guild in (loaded.get("guilds") or {}).items()
        }
    return GUILD_MEDIA_BASE_CACHE["bases"].get(str(guild_id), "")


def media_url(relative_path, guild_id=None):
    if not relative_path:
        return None
    public_base = guild_media_public_base_url(guild_id)
    if not public_base:
        public_base = os.getenv("SDAC_MEDIA_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base:
        return f"{public_base}/{str(relative_path).lstrip('/')}"
    return url_for("serve_media", filename=relative_path)


def local_media_url(relative_path):
    if not relative_path:
        return None
    return url_for("serve_media", filename=relative_path)


def thumbnail_path_for_media(path):
    try:
        relative_path = Path(path).resolve().relative_to(MEDIA_DIR.resolve())
    except (OSError, ValueError):
        return None
    if relative_path.parts and relative_path.parts[0] == "_thumbs":
        return None
    return (MEDIA_DIR / "_thumbs" / relative_path).with_suffix(".webp")


def create_media_thumbnail(path, filename, max_dimension=None):
    if get_media_type(filename) != "image":
        return ""
    if Path(filename).suffix.lower() == ".gif":
        return ""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return ""
    thumb_path = thumbnail_path_for_media(path)
    if thumb_path is None:
        return ""
    if max_dimension is None:
        try:
            max_dimension = int(
                load_config().get("limits", {}).get("thumbnail_max_dimension", 640)
            )
        except (TypeError, ValueError):
            max_dimension = 640
    max_dimension = max(160, min(2048, int(max_dimension or 640)))
    try:
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_dimension, max_dimension))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(thumb_path, "WEBP", quality=82, method=4)
        return str(thumb_path)
    except (OSError, ValueError):
        return ""


def maybe_compress_image(path, filename):
    limits = load_config().get("limits", {})
    if not limits.get("image_compression_enabled", False):
        return False
    if get_media_type(filename) != "image":
        return False
    if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return False
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    try:
        quality = int(limits.get("image_compression_quality") or 85)
    except (TypeError, ValueError):
        quality = 85
    quality = max(40, min(95, quality))
    image_path = Path(path)
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            save_kwargs = {"optimize": True}
            if image_path.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
                save_kwargs["quality"] = quality
            if image_path.suffix.lower() in {".jpg", ".jpeg"}:
                image = image.convert("RGB")
            image.save(image_path, **save_kwargs)
        return True
    except (OSError, ValueError):
        return False


def thumbnail_url_from_metadata(metadata, fallback_path, filename):
    thumbnail_path = metadata.get("thumbnail_path") if isinstance(metadata, dict) else ""
    thumbnail_relative = media_relative_path(thumbnail_path) if thumbnail_path else None
    if thumbnail_relative and (MEDIA_DIR / thumbnail_relative).is_file():
        return local_media_url(thumbnail_relative)
    predicted_thumb = thumbnail_path_for_media(fallback_path) if fallback_path else None
    if predicted_thumb and predicted_thumb.is_file():
        predicted_relative = media_relative_path(predicted_thumb)
        if predicted_relative:
            return local_media_url(predicted_relative)
    if fallback_path and Path(fallback_path).is_file():
        created = create_media_thumbnail(fallback_path, filename)
        created_relative = media_relative_path(created) if created else None
        if created_relative:
            return local_media_url(created_relative)
    return ""


def referenced_media_paths(connection):
    paths = set()
    for row in connection.execute("""
        SELECT media_paths, file_paths
        FROM submissions
    """):
        for value in split_values(row["media_paths"] or row["file_paths"]):
            relative_path = media_relative_path(value)
            if relative_path:
                paths.add((MEDIA_DIR / relative_path).resolve())
    for table in ("guess_games", "guess_library_items"):
        for row in connection.execute(f"""
            SELECT media_path
            FROM {table}
            WHERE media_path IS NOT NULL AND media_path != ''
        """):
            relative_path = media_relative_path(row["media_path"])
            if relative_path:
                paths.add((MEDIA_DIR / relative_path).resolve())
    return paths


def media_cleanup_report(limit=200):
    max_file_bytes = int(
        load_config().get("limits", {}).get(
            "max_file_bytes",
            DEFAULT_LIMITS["max_file_bytes"],
        )
    )
    with closing(connect_db()) as connection:
        referenced = referenced_media_paths(connection)
    media_root = MEDIA_DIR.resolve()
    orphaned = []
    oversized = []
    seen_files = set()
    if media_root.exists():
        for file_path in media_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                resolved = file_path.resolve()
                resolved.relative_to(media_root)
                size = resolved.stat().st_size
            except (OSError, ValueError):
                continue
            seen_files.add(resolved)
            item = {
                "path": resolved,
                "relative": resolved.relative_to(media_root).as_posix(),
                "size": size,
                "size_label": format_bytes(size),
            }
            if resolved not in referenced:
                orphaned.append(item)
            if size > max_file_bytes:
                oversized.append(item)
    missing = []
    for referenced_path in sorted(referenced):
        if referenced_path not in seen_files and not referenced_path.is_file():
            try:
                relative = referenced_path.relative_to(media_root).as_posix()
            except ValueError:
                relative = str(referenced_path)
            missing.append({
                "path": referenced_path,
                "relative": relative,
                "size": 0,
                "size_label": "Missing",
            })
    return {
        "orphaned": orphaned[:limit],
        "orphaned_total": len(orphaned),
        "oversized": oversized[:limit],
        "oversized_total": len(oversized),
        "missing": missing[:limit],
        "missing_total": len(missing),
    }


def delete_orphaned_media_files():
    report = media_cleanup_report(limit=100000)
    deleted = 0
    media_root = MEDIA_DIR.resolve()
    for item in report["orphaned"]:
        path = Path(item["path"])
        try:
            path.resolve().relative_to(media_root)
            path.unlink()
            deleted += 1
        except (OSError, ValueError):
            continue
    return deleted


def path_tree_stats(path):
    path = Path(path)
    total = 0
    files = 0
    oldest = None
    if not path.exists():
        return {"bytes": 0, "files": 0, "oldest": ""}
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            stat = file_path.stat()
        except OSError:
            continue
        total += stat.st_size
        files += 1
        if oldest is None or stat.st_mtime < oldest:
            oldest = stat.st_mtime
    oldest_label = (
        datetime.fromtimestamp(oldest, timezone.utc).strftime("%Y-%m-%d")
        if oldest
        else ""
    )
    return {"bytes": total, "files": files, "oldest": oldest_label}


def latest_deploy_snapshots(limit=10):
    deploy_root = BASE_DIR / "deploy-backups"
    if not deploy_root.exists():
        return []
    snapshots = []
    for path in deploy_root.iterdir():
        if not path.is_dir():
            continue
        try:
            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                timezone.utc,
            ).strftime("%Y-%m-%d %H:%M UTC")
        except OSError:
            modified = ""
        snapshots.append({
            "name": path.name,
            "path": str(path),
            "modified": modified,
        })
    snapshots.sort(key=lambda item: item["modified"], reverse=True)
    return snapshots[:limit]


def run_latest_rollback():
    script_path = BASE_DIR / "scripts" / "rollback_ubuntu.sh"
    if os.name == "nt":
        return {
            "ok": False,
            "message": "Dashboard rollback is only available on Linux hosts.",
        }
    if not script_path.is_file():
        return {
            "ok": False,
            "message": f"Rollback script not found: {script_path}",
        }
    try:
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "message": f"Rollback failed to start: {error}"}
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return {
            "ok": False,
            "message": (output or f"Rollback exited with {result.returncode}")[-1000:],
        }
    return {
        "ok": True,
        "message": (output or "Rollback completed.")[-1000:],
    }


def storage_forecast_rows(config_data=None):
    config_data = config_data or load_config()
    rows = []
    try:
        global_limit = int(
            (config_data.get("limits") or {}).get("guild_storage_limit_bytes") or 0
        )
    except (TypeError, ValueError):
        global_limit = 0
    with closing(connect_db()) as connection:
        for guild_id, guild_config in sorted((config_data.get("guilds") or {}).items()):
            if not can_admin_access_guild(guild_id, config_data):
                continue
            media_stats = path_tree_stats(MEDIA_DIR / str(guild_id))
            limits = guild_config.get("limits") or {}
            try:
                limit_bytes = int(limits.get("storage_limit_bytes") or global_limit)
            except (TypeError, ValueError):
                limit_bytes = 0
            month_rows = connection.execute("""
                SELECT substr(COALESCE(created_at, submitted_at), 1, 7) AS month,
                       SUM(COALESCE(CAST(media_sizes AS INTEGER), 0)) AS bytes,
                       COUNT(*) AS submissions
                FROM submissions
                WHERE guild_id = ?
                  AND status != 'removed'
                  AND COALESCE(created_at, submitted_at, '') != ''
                GROUP BY month
                ORDER BY month DESC
                LIMIT 3
            """, (str(guild_id),)).fetchall()
            recent_bytes = [
                int(row["bytes"] or 0)
                for row in month_rows
                if row["month"]
            ]
            average_monthly_bytes = (
                int(sum(recent_bytes) / len(recent_bytes))
                if recent_bytes
                else 0
            )
            if limit_bytes and average_monthly_bytes > 0 and media_stats["bytes"] < limit_bytes:
                months_left = round(
                    (limit_bytes - media_stats["bytes"]) / average_monthly_bytes,
                    1,
                )
                forecast = f"About {months_left} month(s) until limit."
            elif limit_bytes and media_stats["bytes"] >= limit_bytes:
                forecast = "At or above configured limit."
            elif average_monthly_bytes > 0:
                forecast = f"Growing about {format_bytes(average_monthly_bytes)} per month."
            else:
                forecast = "Not enough history yet."
            rows.append({
                "guild_id": guild_id,
                "name": (
                    guild_config.get("brand_name")
                    or guild_config.get("guild_name")
                    or f"Discord {guild_id}"
                ),
                "current": format_bytes(media_stats["bytes"]),
                "current_bytes": media_stats["bytes"],
                "limit": format_bytes(limit_bytes) if limit_bytes else "No limit",
                "average": (
                    format_bytes(average_monthly_bytes)
                    if average_monthly_bytes
                    else "Unknown"
                ),
                "forecast": forecast,
            })
    rows.sort(key=lambda row: row["current_bytes"], reverse=True)
    return rows


def month_start_end(month):
    if not re.match(r"^\d{4}-\d{2}$", str(month or "")):
        month = current_month_key()
    return month, f"{month}-01T00:00:00", f"{month}-31T23:59:59"


def monthly_report_data(month, guild_id=None):
    month, start_at, end_at = month_start_end(month)
    config_data = load_config()
    allowed_ids = (
        {str(guild_id)}
        if guild_id
        else current_admin_allowed_guild_ids(config_data)
    )
    scope_sql, scope_params = guild_id_filter("guild_id", allowed_ids)
    created_sql = (
        "COALESCE(created_at, submitted_at, '') >= ? "
        "AND COALESCE(created_at, submitted_at, '') <= ?"
    )
    with closing(connect_db()) as connection:
        top_submissions = connection.execute(f"""
            SELECT id, guild_id, username, category, stars, created_at
            FROM submissions
            WHERE {scope_sql}
              AND status = 'posted'
              AND {created_sql}
            ORDER BY stars DESC, created_at DESC, id DESC
            LIMIT 10
        """, scope_params + [start_at, end_at]).fetchall()
        top_guessers = connection.execute(f"""
            SELECT guild_id, user_id, username, SUM(points) AS points
            FROM guess_points
            WHERE {scope_sql}
              AND month = ?
            GROUP BY guild_id, user_id, username
            ORDER BY points DESC, username ASC
            LIMIT 10
        """, scope_params + [month]).fetchall()
        totals = {
            "Submissions": connection.execute(f"""
                SELECT COUNT(*)
                FROM submissions
                WHERE {scope_sql}
                  AND status = 'posted'
                  AND {created_sql}
            """, scope_params + [start_at, end_at]).fetchone()[0],
            "Votes": connection.execute(f"""
                SELECT COALESCE(SUM(stars), 0)
                FROM submissions
                WHERE {scope_sql}
                  AND status = 'posted'
                  AND {created_sql}
            """, scope_params + [start_at, end_at]).fetchone()[0],
            "Guess Points": connection.execute(f"""
                SELECT COALESCE(SUM(points), 0)
                FROM guess_points
                WHERE {scope_sql}
                  AND month = ?
            """, scope_params + [month]).fetchone()[0],
            "Correct Guesses": connection.execute(f"""
                SELECT COUNT(*)
                FROM guess_correct_guesses
                WHERE {scope_sql}
                  AND guessed_at >= ?
                  AND guessed_at <= ?
            """, scope_params + [start_at, end_at]).fetchone()[0],
        }
    return {
        "month": month,
        "totals": totals,
        "top_submissions": top_submissions,
        "top_guessers": top_guessers,
        "activity": [
            {"label": label, "value": value}
            for label, value in totals.items()
        ],
    }


def backup_safe_for_pruning(backup):
    backup = backup or {}
    return bool(
        backup.get("enabled")
        and backup.get("remote")
        and backup.get("public_base_url")
        and backup.get("last_status") == "success"
        and backup.get("last_success_at")
    )


def delete_original_files_keep_thumbnails(paths):
    deleted = 0
    media_root = MEDIA_DIR.resolve()
    for raw_path in paths:
        try:
            path = Path(raw_path).resolve()
            path.relative_to(media_root)
        except (OSError, ValueError):
            continue
        try:
            relative_parts = path.relative_to(media_root).parts
        except ValueError:
            continue
        if relative_parts and relative_parts[0] == "_thumbs":
            continue
        if path.is_file():
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def prune_backed_up_originals(config_data, guild_id=None):
    limits = config_data.get("limits") or {}
    try:
        retention_days = int(limits.get("local_original_retention_days") or 30)
    except (TypeError, ValueError):
        retention_days = 30
    if retention_days <= 0:
        return 0
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=retention_days)
    ).isoformat()
    deleted = 0
    guilds = config_data.get("guilds") or {}
    with closing(connect_db()) as connection:
        for current_guild_id, guild_config in guilds.items():
            if guild_id and str(current_guild_id) != str(guild_id):
                continue
            if not can_admin_access_guild(current_guild_id, config_data):
                continue
            if not backup_safe_for_pruning(guild_config.get("external_backup")):
                continue
            rows = connection.execute("""
                SELECT media_paths, file_paths
                FROM submissions
                WHERE guild_id = ?
                  AND status IN ('posted', 'removed')
                  AND COALESCE(created_at, submitted_at, '') < ?
            """, (str(current_guild_id), cutoff)).fetchall()
            for row in rows:
                deleted += delete_original_files_keep_thumbnails(
                    split_values(row["media_paths"] or row["file_paths"])
                )
            game_rows = connection.execute("""
                SELECT media_path
                FROM guess_games
                WHERE guild_id = ?
                  AND status != 'active'
                  AND COALESCE(started_at, '') < ?
            """, (str(current_guild_id), cutoff)).fetchall()
            for row in game_rows:
                deleted += delete_original_files_keep_thumbnails([row["media_path"]])
    return deleted


def generate_missing_thumbnails(limit=5000):
    generated = 0
    media_root = MEDIA_DIR.resolve()
    if not media_root.exists():
        return 0
    for file_path in media_root.rglob("*"):
        if generated >= limit:
            break
        if not file_path.is_file():
            continue
        try:
            relative_parts = file_path.resolve().relative_to(media_root).parts
        except (OSError, ValueError):
            continue
        if relative_parts and relative_parts[0] == "_thumbs":
            continue
        if get_media_type(file_path.name) != "image":
            continue
        thumb_path = thumbnail_path_for_media(file_path)
        if thumb_path and thumb_path.is_file():
            continue
        if create_media_thumbnail(file_path, file_path.name):
            generated += 1
    return generated


def guild_storage_rows(config_data):
    rows = []
    for guild_id, guild_config in sorted((config_data.get("guilds") or {}).items()):
        if not can_admin_access_guild(guild_id, config_data):
            continue
        guild_media = path_tree_stats(MEDIA_DIR / str(guild_id))
        guild_thumbs = path_tree_stats(MEDIA_DIR / "_thumbs" / str(guild_id))
        limits = guild_config.get("limits") or {}
        try:
            limit_bytes = int(
                limits.get("storage_limit_bytes")
                or (config_data.get("limits") or {}).get("guild_storage_limit_bytes")
                or 0
            )
        except (TypeError, ValueError):
            limit_bytes = 0
        backup = {
            **DEFAULT_GUILD_FIELDS["external_backup"],
            **(guild_config.get("external_backup") or {}),
        }
        rows.append({
            "guild_id": guild_id,
            "name": (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or f"Discord {guild_id}"
            ),
            "files": guild_media["files"],
            "size_bytes": guild_media["bytes"],
            "size_label": format_bytes(guild_media["bytes"]),
            "thumbnail_files": guild_thumbs["files"],
            "thumbnail_size_label": format_bytes(guild_thumbs["bytes"]),
            "oldest": guild_media["oldest"] or "None",
            "limit_label": format_bytes(limit_bytes) if limit_bytes else "No limit",
            "limit_percent": (
                round((guild_media["bytes"] / limit_bytes) * 100, 1)
                if limit_bytes
                else 0
            ),
            "backup": backup,
            "safe_to_prune": backup_safe_for_pruning(backup),
            "restore_command": (
                f"rclone copy {backup.get('remote', '').rstrip('/')}/media "
                f"{MEDIA_DIR / str(guild_id)}"
                if backup.get("remote")
                else ""
            ),
        })
    return rows


def restore_guild_media_from_remote(config_data, guild_id):
    guild_config = (config_data.get("guilds") or {}).get(str(guild_id)) or {}
    backup = guild_config.get("external_backup") or {}
    remote = str(backup.get("remote") or "").strip().rstrip("/")
    if not remote:
        return False, "No remote is configured for that server."
    if not can_admin_access_guild(guild_id, config_data):
        abort(403)
    destination = (MEDIA_DIR / str(guild_id)).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.relative_to(MEDIA_DIR.resolve())
    try:
        result = subprocess.run(
            [
                "rclone",
                "copy",
                f"{remote}/media",
                str(destination),
                "--copy-links",
                "--fast-list",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except FileNotFoundError:
        return False, "rclone is not installed on this server."
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"Restore failed: {error}"
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "rclone failed").strip()
        return False, details[-500:]
    return True, f"Restored media for guild {guild_id} from {remote}/media."


def prepare_post(row):
    post = dict(row)
    try:
        post["spam_reasons"] = json.loads(post.get("spam_reasons_json") or "[]")
    except (TypeError, ValueError):
        post["spam_reasons"] = []
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
        original_path = (MEDIA_DIR / relative_path).resolve()
        thumbnail_url = thumbnail_url_from_metadata(
            metadata,
            original_path,
            names[index] if index < len(names) else Path(relative_path).name,
        )
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
            "url": media_url(relative_path, post.get("guild_id")),
            "thumbnail_url": thumbnail_url,
            "local_original_available": original_path.is_file(),
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


def configured_notification_rows(event_key, guild_id=None):
    query = """
        SELECT guild_id, event_key, channel_id
        FROM admin_notifications
        WHERE event_key = ?
          AND enabled = 1
          AND channel_id IS NOT NULL
          AND channel_id != ''
    """
    parameters = [event_key]
    if guild_id is not None:
        query += " AND guild_id = ?"
        parameters.append(str(guild_id))
    query += " ORDER BY guild_id, event_key"
    try:
        with closing(connect_db()) as connection:
            return connection.execute(query, parameters).fetchall()
    except sqlite3.Error:
        return []


def post_discord_channel_message(channel_id, content):
    channel_id = str(channel_id or "")
    if not channel_id.isdigit() or not TOKEN:
        return False
    payload = json.dumps({"content": content[:1900]}).encode("utf-8")
    api_request = Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bot {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "SDAC-Dashboard/2.0",
        },
    )
    try:
        with urlopen(api_request, timeout=10) as response:
            return response.status in {200, 201}
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def send_admin_notification(
    event_key,
    message,
    guild_id=None,
    throttle_key=None,
    throttle_seconds=3600,
):
    if event_key not in NOTIFICATION_EVENT_LABELS:
        return
    route_rows = configured_notification_rows(event_key, guild_id)
    if not route_rows:
        return
    throttle_id = throttle_key or f"{event_key}:{guild_id or 'all'}:{message[:80]}"
    now = time.time()
    if now - NOTIFICATION_THROTTLES.get(throttle_id, 0) < throttle_seconds:
        return
    NOTIFICATION_THROTTLES[throttle_id] = now
    title = NOTIFICATION_EVENT_LABELS.get(event_key, event_key)
    content = f"**SDAC {title}**\n{message}"
    for row in route_rows:
        post_discord_channel_message(row["channel_id"], content)


def maybe_notify_stale_bot(bot_status):
    if bot_status.get("fresh"):
        return
    send_admin_notification(
        "heartbeat_stale",
        bot_status.get("message") or "The SDAC bot heartbeat is stale.",
        throttle_key="heartbeat_stale",
        throttle_seconds=3600,
    )


def file_sha256(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def rebuild_media_fingerprints(guild_id=None, limit=10000):
    scanned = 0
    inserted = 0
    updated = 0
    where = []
    params = []
    if guild_id:
        where.append("guild_id = ?")
        params.append(str(guild_id))
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with database() as connection:
        rows = connection.execute(f"""
            SELECT id, guild_id, media_paths, file_paths, media_names,
                   media_sizes, media_hashes
            FROM submissions
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
        """, params + [int(limit)]).fetchall()
        for row in rows:
            paths = split_values(row["media_paths"] or row["file_paths"])
            names = split_values(row["media_names"])
            sizes = split_values(row["media_sizes"])
            existing_hashes = split_values(row["media_hashes"])
            hashes = []
            for index, raw_path in enumerate(paths):
                if scanned >= limit:
                    break
                relative_path = media_relative_path(raw_path)
                media_path = (
                    (MEDIA_DIR / relative_path)
                    if relative_path
                    else Path(raw_path)
                )
                media_hash = file_sha256(media_path) if media_path.is_file() else ""
                hashes.append(media_hash)
                if media_hash:
                    try:
                        size_bytes = (
                            int(sizes[index])
                            if index < len(sizes)
                            else media_path.stat().st_size
                        )
                    except (OSError, TypeError, ValueError):
                        size_bytes = 0
                    exists = connection.execute("""
                        SELECT 1
                        FROM media_fingerprints
                        WHERE media_hash = ?
                          AND guild_id = ?
                          AND submission_id = ?
                        LIMIT 1
                    """, (
                        media_hash,
                        str(row["guild_id"] or ""),
                        row["id"],
                    )).fetchone()
                    if not exists:
                        connection.execute("""
                            INSERT INTO media_fingerprints (
                                media_hash, guild_id, submission_id,
                                media_path, media_name, size_bytes, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            media_hash,
                            str(row["guild_id"] or ""),
                            row["id"],
                            raw_path,
                            names[index] if index < len(names) else "",
                            size_bytes,
                            utc_now_iso(),
                        ))
                        inserted += 1
                scanned += 1
            if hashes and hashes != existing_hashes:
                connection.execute(
                    "UPDATE submissions SET media_hashes = ? WHERE id = ?",
                    (";".join(hashes), row["id"]),
                )
                updated += 1
    return {
        "scanned": scanned,
        "inserted": inserted,
        "updated_submissions": updated,
    }


def background_job_label(job_type):
    labels = {
        "generate_thumbnails": "Generate missing thumbnails",
        "prune_backed_up_originals": "Prune backed-up originals",
        "restore_guild_media": "Restore guild media",
        "archive_history": "Archive old history",
        "rebuild_media_fingerprints": "Rebuild media fingerprints",
        "rollback_latest_snapshot": "Rollback latest deploy snapshot",
        "optimize_database": "Optimize SQLite database",
    }
    return labels.get(job_type, str(job_type or "").replace("_", " ").title())


def create_background_job(job_type, guild_id=None, payload=None, actor_id="", actor_name=""):
    payload = payload or {}
    now = utc_now_iso()
    with database() as connection:
        cursor = connection.execute("""
            INSERT INTO background_jobs (
                job_type, guild_id, status, requested_by,
                requested_by_name, payload_json, created_at
            )
            VALUES (?, ?, 'queued', ?, ?, ?, ?)
        """, (
            job_type,
            str(guild_id) if guild_id else None,
            str(actor_id or ""),
            str(actor_name or ""),
            json.dumps(payload, separators=(",", ":")),
            now,
        ))
        job_id = cursor.lastrowid
        add_admin_audit_log(
            connection,
            guild_id,
            "background_job_queued",
            actor_id,
            actor_name,
            "background_job",
            str(job_id),
            f"Queued {background_job_label(job_type)}.",
        )
    return job_id


def update_background_job(job_id, **fields):
    if not fields:
        return
    allowed = {
        "status",
        "result_json",
        "error",
        "started_at",
        "finished_at",
    }
    assignments = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        assignments.append(f"{key} = ?")
        params.append(value)
    if not assignments:
        return
    params.append(job_id)
    with database() as connection:
        connection.execute(
            f"UPDATE background_jobs SET {', '.join(assignments)} WHERE id = ?",
            params,
        )


def load_background_job(job_id):
    with closing(connect_db()) as connection:
        return connection.execute("""
            SELECT *
            FROM background_jobs
            WHERE id = ?
        """, (job_id,)).fetchone()


def process_background_job(job_id):
    with app.app_context():
        job = load_background_job(job_id)
        if not job or job["status"] not in {"queued", "retry"}:
            return
        update_background_job(
            job_id,
            status="running",
            started_at=utc_now_iso(),
            error="",
        )
        try:
            payload = json.loads(job["payload_json"] or "{}")
            config_data = load_config()
            if job["job_type"] == "generate_thumbnails":
                result = {"generated": generate_missing_thumbnails()}
            elif job["job_type"] == "prune_backed_up_originals":
                result = {
                    "deleted": prune_backed_up_originals(
                        config_data,
                        payload.get("guild_id") or job["guild_id"],
                    )
                }
            elif job["job_type"] == "restore_guild_media":
                ok, message = restore_guild_media_from_remote(
                    config_data,
                    payload.get("guild_id") or job["guild_id"],
                )
                result = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)
            elif job["job_type"] == "archive_history":
                archive_path, row_count, cutoff = archive_old_submission_history(
                    delete_exported=bool(payload.get("delete_exported")),
                )
                result = {
                    "archive": archive_path.name,
                    "rows": row_count,
                    "cutoff": cutoff,
                    "delete_exported": bool(payload.get("delete_exported")),
                }
            elif job["job_type"] == "rebuild_media_fingerprints":
                result = rebuild_media_fingerprints(
                    guild_id=payload.get("guild_id") or job["guild_id"],
                    limit=int(payload.get("limit") or 10000),
                )
            elif job["job_type"] == "rollback_latest_snapshot":
                result = run_latest_rollback()
                if not result.get("ok"):
                    raise RuntimeError(result.get("message") or "Rollback failed.")
            elif job["job_type"] == "optimize_database":
                ok, message = optimize_database()
                result = {"ok": ok, "message": message}
                if not ok:
                    raise RuntimeError(message)
            else:
                raise ValueError(f"Unknown background job type: {job['job_type']}")
            update_background_job(
                job_id,
                status="complete",
                result_json=json.dumps(result, separators=(",", ":")),
                finished_at=utc_now_iso(),
            )
        except Exception as error:
            update_background_job(
                job_id,
                status="failed",
                error=str(error),
                finished_at=utc_now_iso(),
            )
            send_admin_notification(
                "system_errors",
                f"Background job `{job_id}` failed: `{error}`",
                guild_id=job["guild_id"],
                throttle_key=f"background_job_failed:{job_id}",
                throttle_seconds=60,
            )
        finally:
            with BACKGROUND_JOB_LOCK:
                BACKGROUND_JOB_THREADS.pop(job_id, None)


def start_background_job(job_id):
    with BACKGROUND_JOB_LOCK:
        thread = BACKGROUND_JOB_THREADS.get(job_id)
        if thread and thread.is_alive():
            return
        thread = threading.Thread(
            target=process_background_job,
            args=(job_id,),
            daemon=True,
            name=f"sdac-job-{job_id}",
        )
        BACKGROUND_JOB_THREADS[job_id] = thread
        thread.start()


def queue_background_job(job_type, guild_id=None, payload=None, actor_id="", actor_name=""):
    job_id = create_background_job(
        job_type,
        guild_id=guild_id,
        payload=payload,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    start_background_job(job_id)
    return job_id


def recent_background_jobs(limit=50, guild_id=None):
    where = []
    params = []
    if guild_id:
        where.append("guild_id = ?")
        params.append(str(guild_id))
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT *
            FROM background_jobs
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
        """, params + [int(limit)]).fetchall()
    jobs = []
    for row in rows:
        job = dict(row)
        job["label"] = background_job_label(job.get("job_type"))
        try:
            job["payload"] = json.loads(job.get("payload_json") or "{}")
        except (TypeError, ValueError):
            job["payload"] = {}
        try:
            job["result"] = json.loads(job.get("result_json") or "{}")
        except (TypeError, ValueError):
            job["result"] = {}
        jobs.append(job)
    return jobs


def resume_queued_background_jobs(limit=10):
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT id
            FROM background_jobs
            WHERE status = 'queued'
            ORDER BY id ASC
            LIMIT ?
        """, (int(limit),)).fetchall()
    for row in rows:
        start_background_job(row["id"])


def exportable_guild_config(config_data, guild_id):
    guild_id = str(guild_id)
    guild_config = (config_data.get("guilds") or {}).get(guild_id)
    if not guild_config:
        abort(404)
    return {
        "format": "sdac-guild-config-v1",
        "exported_at": utc_now_iso(),
        "guild_id": guild_id,
        "guild_config": guild_config,
    }


def normalize_imported_guild_config(payload):
    if not isinstance(payload, dict):
        raise ValueError("Imported config must be a JSON object.")
    source = payload.get("guild_config") if "guild_config" in payload else payload
    if not isinstance(source, dict):
        raise ValueError("Imported guild_config must be a JSON object.")
    allowed_keys = set(DEFAULT_GUILD_FIELDS)
    imported = {
        key: value
        for key, value in source.items()
        if key in allowed_keys
    }
    if not imported:
        raise ValueError("No supported guild settings were found.")
    merged = json.loads(json.dumps(DEFAULT_GUILD_FIELDS))
    fill_nested_defaults(imported, merged)
    for key, value in imported.items():
        if key in allowed_keys:
            merged[key] = value
    if not isinstance(merged.get("categories"), dict):
        merged["categories"] = {}
    if not isinstance(merged.get("features"), dict):
        merged["features"] = dict(DEFAULT_FEATURES)
    fill_nested_defaults(merged, DEFAULT_GUILD_FIELDS)
    return merged


def config_value_display(value):
    if value is None:
        return "(unset)"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)


def flatten_config_values(value, prefix=""):
    rows = {}
    if isinstance(value, dict):
        if not value and prefix:
            rows[prefix] = {}
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.update(flatten_config_values(value[key], child_prefix))
    else:
        rows[prefix or "(root)"] = value
    return rows


def guild_config_diff(current_config, imported_config):
    current_flat = flatten_config_values(current_config or {})
    imported_flat = flatten_config_values(imported_config or {})
    rows = []
    for path in sorted(set(current_flat) | set(imported_flat)):
        old_value = current_flat.get(path)
        new_value = imported_flat.get(path)
        if old_value == new_value:
            continue
        rows.append({
            "path": path,
            "old": config_value_display(old_value),
            "new": config_value_display(new_value),
        })
    return rows


def sql_placeholders(values):
    return ",".join("?" for _ in values)


def rows_as_dicts(rows):
    return [dict(row) for row in rows]


def user_privacy_export_payload(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    with closing(connect_db()) as connection:
        submissions = connection.execute("""
            SELECT *
            FROM submissions
            WHERE guild_id = ?
              AND user_id = ?
            ORDER BY created_at DESC, id DESC
        """, (guild_id, user_id)).fetchall()
        submission_ids = [row["id"] for row in submissions]
        reports = []
        if submission_ids:
            placeholders = sql_placeholders(submission_ids)
            reports = connection.execute(f"""
                SELECT *
                FROM submission_reports
                WHERE submission_id IN ({placeholders})
                ORDER BY created_at DESC, id DESC
            """, submission_ids).fetchall()
        return {
            "exported_at": utc_now_iso(),
            "guild_id": guild_id,
            "user_id": user_id,
            "submissions": rows_as_dicts(submissions),
            "submission_reports": rows_as_dicts(reports),
            "guess_points": rows_as_dicts(connection.execute("""
                SELECT *
                FROM guess_points
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY month DESC, channel_id
            """, (guild_id, user_id)).fetchall()),
            "correct_guesses": rows_as_dicts(connection.execute("""
                SELECT *
                FROM guess_correct_guesses
                WHERE guild_id = ?
                  AND user_id = ?
                ORDER BY guessed_at DESC
            """, (guild_id, user_id)).fetchall()),
            "guess_cooldowns": rows_as_dicts(connection.execute("""
                SELECT *
                FROM guess_cooldowns
                WHERE guild_id = ?
                  AND user_id = ?
            """, (guild_id, user_id)).fetchall()),
            "started_or_won_games": rows_as_dicts(connection.execute("""
                SELECT id, guild_id, channel_id, starter_user_id,
                       starter_username, winner_user_id, winner_username,
                       started_at, solved_at, status
                FROM guess_games
                WHERE guild_id = ?
                  AND (starter_user_id = ? OR winner_user_id = ?)
                ORDER BY started_at DESC, id DESC
            """, (guild_id, user_id, user_id)).fetchall()),
        }


def delete_user_privacy_data(guild_id, user_id, actor_id, actor_name):
    guild_id = str(guild_id)
    user_id = str(user_id)
    payload = user_privacy_export_payload(guild_id, user_id)
    submissions = payload["submissions"]
    discord_deleted = 0
    discord_errors = []
    for row in submissions:
        for channel_id, message_id in (
            (row.get("repost_channel_id"), row.get("repost_message_id")),
            (row.get("approval_channel_id"), row.get("approval_message_id")),
        ):
            if not channel_id or not message_id:
                continue
            deleted, error_message = delete_discord_message(channel_id, message_id)
            if deleted:
                discord_deleted += 1
            else:
                discord_errors.append({
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "error": error_message,
                })

    submission_ids = [row["id"] for row in submissions]
    with database() as connection:
        if submission_ids:
            placeholders = sql_placeholders(submission_ids)
            connection.execute(
                f"DELETE FROM submission_reports WHERE submission_id IN ({placeholders})",
                submission_ids,
            )
            connection.execute(
                f"DELETE FROM media_fingerprints WHERE submission_id IN ({placeholders})",
                submission_ids,
            )
            connection.execute(
                f"DELETE FROM submissions WHERE id IN ({placeholders})",
                submission_ids,
            )
        connection.execute("""
            DELETE FROM guess_points
            WHERE guild_id = ?
              AND user_id = ?
        """, (guild_id, user_id))
        connection.execute("""
            DELETE FROM guess_correct_guesses
            WHERE guild_id = ?
              AND user_id = ?
        """, (guild_id, user_id))
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE guild_id = ?
              AND user_id = ?
        """, (guild_id, user_id))
        connection.execute("""
            UPDATE guess_games
            SET starter_username = 'Deleted User',
                starter_user_id = ''
            WHERE guild_id = ?
              AND starter_user_id = ?
        """, (guild_id, user_id))
        connection.execute("""
            UPDATE guess_games
            SET winner_username = 'Deleted User',
                winner_user_id = ''
            WHERE guild_id = ?
              AND winner_user_id = ?
        """, (guild_id, user_id))
        details = {
            "submissions_deleted": len(submissions),
            "discord_messages_deleted": discord_deleted,
            "discord_errors": discord_errors[:10],
        }
        connection.execute("""
            INSERT INTO privacy_actions (
                guild_id, user_id, action, actor_user_id,
                actor_username, details_json, created_at
            )
            VALUES (?, ?, 'delete_user_data', ?, ?, ?, ?)
        """, (
            guild_id,
            user_id,
            actor_id,
            actor_name,
            json.dumps(details, separators=(",", ":")),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            guild_id,
            "privacy_delete_user_data",
            actor_id,
            actor_name,
            "user",
            user_id,
            json.dumps(details, separators=(",", ":")),
        )

    for row in submissions:
        delete_local_media(row)
    PUBLIC_PAGE_CACHE.clear()
    return details


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


def move_path_with_parents(source_path, target_path):
    source_path = Path(source_path)
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path = target_path.with_name(
            f"{target_path.stem}-{int(time.time())}{target_path.suffix}"
        )
    shutil.move(str(source_path), str(target_path))
    return target_path


def quarantine_submission_media(submission_id, reason, actor_id, actor_name):
    reason = (reason or "Manual admin quarantine").strip()[:500]
    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if not row:
        return False, "Submission not found."

    moved = 0
    now = utc_now_iso()
    paths = split_values(row["media_paths"] or row["file_paths"])
    names = split_values(row["media_names"])
    with database() as connection:
        for index, stored_path in enumerate(paths):
            relative_path = media_relative_path(stored_path)
            if not relative_path:
                continue
            original_path = (MEDIA_DIR / relative_path).resolve()
            try:
                original_path.relative_to(MEDIA_DIR)
            except ValueError:
                continue
            if not original_path.is_file():
                continue
            quarantine_path = move_path_with_parents(
                original_path,
                MEDIA_QUARANTINE_DIR / relative_path,
            )
            moved += 1
            connection.execute("""
                INSERT INTO media_quarantine (
                    guild_id, submission_id, original_path, quarantine_path,
                    media_name, reason, status, actor_user_id,
                    actor_username, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'quarantined', ?, ?, ?)
            """, (
                row["guild_id"],
                row["id"],
                str(original_path),
                str(quarantine_path),
                names[index] if index < len(names) else original_path.name,
                reason,
                actor_id,
                actor_name,
                now,
            ))
        if moved:
            connection.execute(
                "UPDATE submissions SET status = 'needs_review' WHERE id = ?",
                (row["id"],),
            )
            connection.execute("""
                INSERT INTO moderation_history (
                    guild_id, submission_id, action, actor_user_id,
                    actor_username, details, created_at
                )
                VALUES (?, ?, 'quarantine', ?, ?, ?, ?)
            """, (
                row["guild_id"],
                row["id"],
                actor_id,
                actor_name,
                f"Quarantined {moved} file(s): {reason}",
                now,
            ))
            add_admin_audit_log(
                connection,
                row["guild_id"],
                "quarantine_submission_media",
                actor_id,
                actor_name,
                "submission",
                row["id"],
                f"Quarantined {moved} file(s): {reason}",
            )
    if moved:
        PUBLIC_PAGE_CACHE.clear()
        return True, f"Quarantined {moved} media file(s)."
    return False, "No local media files were available to quarantine."


def quarantine_items(status="quarantined", limit=100):
    where = []
    params = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    scope_sql, scope_params = admin_scope_filter("guild_id", load_config())
    if scope_sql:
        where.append(scope_sql)
        params.extend(scope_params)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with closing(connect_db()) as connection:
        return connection.execute(f"""
            SELECT *
            FROM media_quarantine
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, params + [int(limit)]).fetchall()


def resolve_quarantine_item(item_id, action, actor_id, actor_name):
    with closing(connect_db()) as connection:
        item = connection.execute("""
            SELECT *
            FROM media_quarantine
            WHERE id = ?
        """, (item_id,)).fetchone()
    if not item:
        return False, "Quarantine item not found."
    if item["status"] != "quarantined":
        return False, "That quarantine item is already resolved."
    if not can_admin_access_guild(item["guild_id"], load_config()):
        abort(403)

    quarantine_path = Path(item["quarantine_path"])
    original_path = Path(item["original_path"])
    now = utc_now_iso()
    if action == "restore":
        if not quarantine_path.is_file():
            return False, "Quarantined file is missing."
        try:
            restored_path = move_path_with_parents(quarantine_path, original_path)
        except OSError as error:
            return False, f"Restore failed: {error}"
        new_status = "restored"
        details = f"Restored quarantined media to {restored_path}."
        with database() as connection:
            connection.execute(
                "UPDATE submissions SET status = 'posted' WHERE id = ?",
                (item["submission_id"],),
            )
    elif action == "delete":
        try:
            if quarantine_path.is_file():
                quarantine_path.unlink()
        except OSError as error:
            return False, f"Delete failed: {error}"
        new_status = "deleted"
        details = "Deleted quarantined media file."
    else:
        return False, "Unknown quarantine action."

    with database() as connection:
        connection.execute("""
            UPDATE media_quarantine
            SET status = ?, resolved_at = ?
            WHERE id = ?
        """, (new_status, now, item_id))
        add_admin_audit_log(
            connection,
            item["guild_id"],
            f"quarantine_{new_status}",
            actor_id,
            actor_name,
            "media_quarantine",
            item_id,
            details,
        )
    PUBLIC_PAGE_CACHE.clear()
    return True, details


def remove_submission_from_dashboard(submission_id, actor_id, actor_name):
    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if not row:
        return False, "Submission not found."

    for channel_id, message_id in (
        (row["repost_channel_id"], row["repost_message_id"]),
        (row["approval_channel_id"], row["approval_message_id"]),
    ):
        deleted, error_message = delete_discord_message(channel_id, message_id)
        if not deleted:
            send_admin_notification(
                "repost_delete_failed",
                (
                    f"Could not delete Discord message `{message_id}` in "
                    f"channel `{channel_id}` for submission `{row['id']}`: "
                    f"`{error_message}`"
                ),
                guild_id=row["guild_id"],
                throttle_key=f"repost_delete_failed:{row['id']}:{message_id}",
                throttle_seconds=900,
            )
            return False, error_message

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
            actor_name,
            "Removed from dashboard",
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            row["guild_id"],
            "remove_submission_dashboard",
            actor_id,
            actor_name,
            "submission",
            row["id"],
            "Removed from dashboard",
        )
        connection.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
        connection.execute(
            "DELETE FROM media_fingerprints WHERE submission_id = ?",
            (submission_id,),
        )
    delete_local_media(row)
    PUBLIC_PAGE_CACHE.clear()
    return True, "Submission removed from the website and Discord."


def optimize_database():
    if using_postgres():
        return False, "Database optimize is currently only available for SQLite."
    if not DB_FILE.exists():
        return False, "SQLite database file was not found."
    backup_path, _created, backup_message = create_database_backup("pre-optimize")
    before_size = DB_FILE.stat().st_size
    connection = sqlite3.connect(DB_FILE)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("ANALYZE")
        connection.commit()
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()
    after_size = DB_FILE.stat().st_size
    return True, (
        f"Optimized SQLite database. Size {format_bytes(before_size)} -> "
        f"{format_bytes(after_size)}. Backup: {backup_path.name}. {backup_message}"
    )


def two_admin_approval_enabled(config_data=None):
    config_data = config_data or load_config()
    return bool(
        (config_data.get("limits") or {}).get("two_admin_approval_enabled", False)
    )


def create_pending_admin_action(
    action_type,
    target_type,
    target_id,
    payload,
    actor_id,
    actor_name,
    guild_id=None,
):
    with database() as connection:
        cursor = connection.execute("""
            INSERT INTO pending_admin_actions (
                guild_id, action_type, target_type, target_id, payload_json,
                requested_by, requested_by_name, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            str(guild_id) if guild_id is not None else None,
            action_type,
            target_type,
            str(target_id or ""),
            json.dumps(payload or {}, separators=(",", ":")),
            str(actor_id or ""),
            str(actor_name or ""),
            utc_now_iso(),
        ))
        action_id = cursor.lastrowid
        add_admin_audit_log(
            connection,
            guild_id,
            "pending_admin_action_created",
            actor_id,
            actor_name,
            "pending_admin_action",
            action_id,
            f"Requested approval for {action_type}.",
        )
    return action_id


def approval_required_redirect(
    action_type,
    target_type,
    target_id,
    payload,
    actor_id,
    actor_name,
    guild_id=None,
    endpoint="admin_approvals",
    route_values=None,
):
    action_id = create_pending_admin_action(
        action_type,
        target_type,
        target_id,
        payload,
        actor_id,
        actor_name,
        guild_id,
    )
    values = {"key": ADMIN_KEY, **(route_values or {})}
    values["notice"] = (
        f"Created pending approval #{action_id}. A second admin must approve it."
    )
    return redirect(url_for(endpoint, **values))


def pending_admin_action_rows(status="pending", limit=100):
    where = []
    params = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    scope_sql, scope_params = admin_scope_filter("guild_id", load_config(), include_global=True)
    if scope_sql:
        where.append(scope_sql)
        params.extend(scope_params)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT *
            FROM pending_admin_actions
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, params + [int(limit)]).fetchall()
    actions = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload_json") or "{}")
        except (TypeError, ValueError):
            item["payload"] = {}
        actions.append(item)
    return actions


def execute_pending_admin_action(row, actor_id, actor_name):
    payload = json.loads(row["payload_json"] or "{}")
    action_type = row["action_type"]
    if action_type == "delete_submission":
        return remove_submission_from_dashboard(
            int(payload.get("submission_id") or row["target_id"] or 0),
            actor_id,
            actor_name,
        )
    if action_type == "privacy_delete_user_data":
        details = delete_user_privacy_data(
            payload.get("guild_id") or row["guild_id"],
            payload.get("user_id") or row["target_id"],
            actor_id,
            actor_name,
        )
        return True, f"Deleted privacy data: {details}"
    if action_type == "delete_orphans":
        deleted = delete_orphaned_media_files()
        return True, f"Deleted {deleted} orphaned media file(s)."
    if action_type == "prune_backed_up_originals":
        job_id = queue_background_job(
            "prune_backed_up_originals",
            guild_id=payload.get("guild_id"),
            payload={"guild_id": payload.get("guild_id")},
            actor_id=actor_id,
            actor_name=actor_name,
        )
        return True, f"Queued backed-up original pruning as job #{job_id}."
    if action_type == "rollback_latest_snapshot":
        job_id = queue_background_job(
            "rollback_latest_snapshot",
            actor_id=actor_id,
            actor_name=actor_name,
        )
        return True, f"Queued rollback as background job #{job_id}."
    if action_type == "quarantine_submission":
        return quarantine_submission_media(
            int(payload.get("submission_id") or row["target_id"] or 0),
            payload.get("reason") or "Approved admin quarantine",
            actor_id,
            actor_name,
        )
    return False, f"Unknown pending action type: {action_type}"


def resolve_pending_admin_action(action_id, decision, actor_id, actor_name):
    with closing(connect_db()) as connection:
        row = connection.execute("""
            SELECT *
            FROM pending_admin_actions
            WHERE id = ?
        """, (action_id,)).fetchone()
    if not row:
        return False, "Pending action not found."
    if row["status"] != "pending":
        return False, "Pending action is already resolved."
    if str(row["requested_by"] or "") == str(actor_id or ""):
        return False, "A second admin must approve this action."
    if not can_admin_access_guild(row["guild_id"], load_config()):
        abort(403)

    now = utc_now_iso()
    if decision == "deny":
        ok = True
        message = "Pending action denied."
        status = "denied"
    else:
        ok, message = execute_pending_admin_action(row, actor_id, actor_name)
        status = "complete" if ok else "failed"
    with database() as connection:
        connection.execute("""
            UPDATE pending_admin_actions
            SET status = ?, approved_by = ?, approved_by_name = ?,
                approved_at = ?, completed_at = ?, result_text = ?
            WHERE id = ?
        """, (
            status,
            str(actor_id or ""),
            str(actor_name or ""),
            now,
            now,
            message,
            action_id,
        ))
        add_admin_audit_log(
            connection,
            row["guild_id"],
            f"pending_admin_action_{status}",
            actor_id,
            actor_name,
            "pending_admin_action",
            action_id,
            message,
        )
    return ok, message


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


def normalize_role(role):
    role = str(role or "").strip().lower()
    return role if role in ROLE_LEVELS else "moderator"


def is_admin_logged_in():
    return bool(session.get("sdac_admin"))


def current_admin_username():
    return session.get("sdac_admin_username") or "web-admin"


def current_admin_role():
    return normalize_role(session.get("sdac_admin_role") or "moderator")


def has_admin_role(required_role):
    return ROLE_LEVELS[current_admin_role()] >= ROLE_LEVELS[normalize_role(required_role)]


def parse_guild_scope(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple, set)):
        return [
            str(item).strip()
            for item in raw_value
            if str(item).strip()
        ]
    text = str(raw_value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parse_guild_scope(parsed)
    except json.JSONDecodeError:
        pass
    return [
        item.strip()
        for item in re.split(r"[\s,]+", text)
        if item.strip()
    ]


def current_admin_allowed_guild_ids(config_data=None):
    config_data = config_data or load_config()
    all_ids = {
        str(guild_id)
        for guild_id in (config_data.get("guilds") or {})
    }
    if current_admin_role() == "owner":
        return all_ids
    scoped_ids = set(parse_guild_scope(session.get("sdac_admin_guild_ids", [])))
    if not scoped_ids:
        return all_ids
    return all_ids & scoped_ids


def can_admin_access_guild(guild_id, config_data=None):
    if not has_request_context():
        return True
    if current_admin_role() == "owner":
        return True
    return str(guild_id) in current_admin_allowed_guild_ids(config_data)


def dashboard_user(username):
    username = str(username or "").strip().casefold()
    if not username:
        return None
    with closing(connect_db()) as connection:
        return connection.execute("""
            SELECT username, password_hash, role, disabled, guild_ids_json
            FROM dashboard_admin_users
            WHERE username = ?
            LIMIT 1
        """, (username,)).fetchone()


def dashboard_user_count():
    with closing(connect_db()) as connection:
        return connection.execute("""
            SELECT COUNT(*)
            FROM dashboard_admin_users
            WHERE disabled = 0
        """).fetchone()[0]


def dashboard_users():
    with closing(connect_db()) as connection:
        return connection.execute("""
            SELECT username, role, disabled, guild_ids_json,
                   created_at, updated_at, last_login_at
            FROM dashboard_admin_users
            ORDER BY disabled ASC, role DESC, username ASC
        """).fetchall()


def notification_routes(config_data=None):
    config_data = config_data or load_config()
    guild_names = guild_name_map(config_data)
    scope_sql, scope_params = admin_scope_filter("guild_id", config_data)
    where_sql = f"WHERE {scope_sql}" if scope_sql else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT guild_id, event_key, channel_id, enabled, updated_at
            FROM admin_notifications
            {where_sql}
            ORDER BY guild_id, event_key
        """, scope_params).fetchall()
    return [
        {
            "guild_id": row["guild_id"],
            "guild_name": guild_names.get(row["guild_id"], row["guild_id"]),
            "event_key": row["event_key"],
            "event_label": NOTIFICATION_EVENT_LABELS.get(
                row["event_key"],
                row["event_key"],
            ),
            "channel_id": row["channel_id"],
            "enabled": bool(row["enabled"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def admin_url(endpoint, **values):
    values.setdefault("key", ADMIN_KEY)
    return url_for(endpoint, **values)


def require_admin_key():
    if not has_valid_key():
        abort(403)


def require_admin_login(required_role="moderator"):
    require_admin_key()
    if not is_admin_logged_in():
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))
    if not has_admin_role(required_role):
        abort(403)
    return None


def positive_page(raw_value):
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 1


def web_actor():
    remote_addr = request.remote_addr or "unknown"
    username = current_admin_username()
    role = current_admin_role()
    return username, f"{username} ({role})@{remote_addr}"


def recent_database_backups():
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    rows = []
    integrity = {}
    try:
        with closing(connect_db()) as connection:
            integrity = {
                row["backup_name"]: row
                for row in connection.execute("""
                    SELECT backup_name, sha256, restore_status,
                           restore_details, checked_at
                    FROM backup_integrity
                """).fetchall()
            }
    except sqlite3.Error:
        integrity = {}
    for backup_path in backups[:10]:
        stat = backup_path.stat()
        integrity_row = integrity.get(backup_path.name)
        rows.append({
            "name": backup_path.name,
            "size": format_bytes(stat.st_size),
            "modified": datetime.fromtimestamp(
                stat.st_mtime,
                timezone.utc,
            ).strftime("%Y-%m-%d %H:%M UTC"),
            "sha256": (
                integrity_row["sha256"] if integrity_row else ""
            ),
            "restore_status": (
                integrity_row["restore_status"] if integrity_row else ""
            ),
            "restore_details": (
                integrity_row["restore_details"] if integrity_row else ""
            ),
            "checked_at": (
                integrity_row["checked_at"] if integrity_row else ""
            ),
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
        "original_repo": ORIGINAL_REPO,
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


def oauth_enabled():
    return bool(DISCORD_OAUTH_CLIENT_ID and DISCORD_OAUTH_CLIENT_SECRET)


def oauth_redirect_uri():
    if DISCORD_OAUTH_REDIRECT_URI:
        return DISCORD_OAUTH_REDIRECT_URI
    return url_for("admin_oauth_callback", key=ADMIN_KEY, _external=True)


def discord_json_request(url, token, token_type="Bearer"):
    headers = {
        "Accept": "application/json",
        "User-Agent": "SDAC-Dashboard/2.7",
        "Authorization": f"{token_type} {token}",
    }
    api_request = Request(url, headers=headers)
    with urlopen(api_request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_discord_oauth_code(code):
    payload = urlencode({
        "client_id": DISCORD_OAUTH_CLIENT_ID,
        "client_secret": DISCORD_OAUTH_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": oauth_redirect_uri(),
    }).encode("utf-8")
    api_request = Request(
        "https://discord.com/api/oauth2/token",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "SDAC-Dashboard/2.7",
        },
    )
    with urlopen(api_request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def discord_user_guilds(access_token):
    return discord_json_request(
        "https://discord.com/api/users/@me/guilds",
        access_token,
    )


def discord_current_user(access_token):
    return discord_json_request(
        "https://discord.com/api/users/@me",
        access_token,
    )


def discord_member_role_ids(guild_id, user_id):
    if not TOKEN:
        return []
    try:
        member = discord_json_request(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
            TOKEN,
            token_type="Bot",
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    return [str(role_id) for role_id in member.get("roles") or []]


def oauth_allowed_guild_ids(access_token, user_id, config_data):
    configured = config_data.get("guilds") or {}
    try:
        guilds = discord_user_guilds(access_token)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    allowed = []
    for guild in guilds:
        guild_id = str(guild.get("id") or "")
        guild_config = configured.get(guild_id)
        if not guild_config:
            continue
        try:
            permissions = int(guild.get("permissions") or 0)
        except (TypeError, ValueError):
            permissions = 0
        if permissions & DISCORD_ADMINISTRATOR_PERMISSION:
            allowed.append(guild_id)
            continue
        admin_roles = {
            str(role_id)
            for role_id in guild_config.get("admin_role_ids", [])
        }
        if admin_roles and admin_roles.intersection(
            discord_member_role_ids(guild_id, user_id)
        ):
            allowed.append(guild_id)
    return sorted(set(allowed))


@app.route("/admin/oauth/start")
def admin_oauth_start():
    if not oauth_enabled():
        abort(404)
    if not has_valid_key():
        abort(403)
    state = secrets.token_urlsafe(24)
    session["sdac_oauth_state"] = state
    session["sdac_oauth_next"] = request.args.get("next") or url_for(
        "index",
        key=ADMIN_KEY,
    )
    authorize_url = (
        "https://discord.com/api/oauth2/authorize?"
        + urlencode({
            "client_id": DISCORD_OAUTH_CLIENT_ID,
            "redirect_uri": oauth_redirect_uri(),
            "response_type": "code",
            "scope": "identify guilds",
            "state": state,
            "prompt": "none",
        })
    )
    return redirect(authorize_url)


@app.route("/admin/oauth/callback")
def admin_oauth_callback():
    if not oauth_enabled():
        abort(404)
    if not has_valid_key():
        abort(403)
    state = request.args.get("state", "")
    code = request.args.get("code", "")
    if not code or state != session.get("sdac_oauth_state"):
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            error="Discord login state did not match. Try again.",
        ))
    try:
        token_payload = exchange_discord_oauth_code(code)
        access_token = token_payload.get("access_token") or ""
        user = discord_current_user(access_token)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            error=f"Discord login failed: {error}",
        ))
    user_id = str(user.get("id") or "")
    username = (
        user.get("global_name")
        or user.get("username")
        or f"discord-{user_id}"
    )
    allowed_guilds = oauth_allowed_guild_ids(
        access_token,
        user_id,
        load_config(),
    )
    if not allowed_guilds:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            error="Discord login succeeded, but you are not an SDAC admin in any configured server.",
        ))

    session["sdac_admin"] = True
    session["sdac_admin_username"] = username
    session["sdac_admin_role"] = "admin"
    session["sdac_admin_auth"] = "discord"
    session["sdac_admin_guild_ids"] = allowed_guilds
    session["sdac_discord_user_id"] = user_id
    session.pop("sdac_oauth_state", None)
    next_url = session.pop("sdac_oauth_next", None) or url_for(
        "index",
        key=ADMIN_KEY,
    )
    with database() as connection:
        add_admin_audit_log(
            connection,
            None,
            "dashboard_discord_oauth_login_success",
            user_id,
            username,
            "dashboard",
            "admin_oauth",
            "Discord OAuth admin login succeeded.",
        )
    return redirect(next_url)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not has_valid_key():
        abort(403)

    next_url = request.values.get("next") or url_for(
        "index",
        key=ADMIN_KEY,
    )
    error = request.args.get("error", "")
    username = request.values.get("username", "owner").strip() or "owner"

    if request.method == "POST":
        require_csrf_token()
        username = request.form.get("username", "owner").strip().casefold() or "owner"
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
        else:
            user = dashboard_user(username)
            role = ""
            login_ok = False
            if user and not int(user["disabled"] or 0):
                login_ok = check_password_hash(user["password_hash"], password)
                role = normalize_role(user["role"])
            elif username in {"owner", "admin", "web-admin"}:
                login_ok = secrets.compare_digest(password, ADMIN_PASSWORD)
                role = "owner"

            if login_ok:
                clear_login_failures(remote_key)
                session["sdac_admin"] = True
                session["sdac_admin_username"] = username
                session["sdac_admin_role"] = role
                session["sdac_admin_auth"] = "password"
                session["sdac_admin_guild_ids"] = (
                    parse_guild_scope(user["guild_ids_json"])
                    if user
                    else []
                )
                if user:
                    with database() as connection:
                        connection.execute("""
                            UPDATE dashboard_admin_users
                            SET last_login_at = ?
                            WHERE username = ?
                        """, (utc_now_iso(), username))
                with database() as connection:
                    add_admin_audit_log(
                        connection,
                        None,
                        "dashboard_login_success",
                        username,
                        f"{username} ({role})",
                        "dashboard",
                        "admin_login",
                        "Admin login succeeded.",
                    )
                return redirect(next_url)

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
                    f"Invalid password for {username}.",
                )
            error = "Invalid admin username or password."

    return render_template_string(
        LOGIN_HTML,
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        error=error,
        next_url=next_url,
        oauth_enabled=oauth_enabled(),
        username=username,
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
    session.pop("sdac_admin_username", None)
    session.pop("sdac_admin_role", None)
    session.pop("sdac_admin_auth", None)
    session.pop("sdac_admin_guild_ids", None)
    session.pop("sdac_discord_user_id", None)
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
    login_response = require_admin_login("admin")
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
    if current_admin_role() != "owner" and not selected_server_id and options:
        selected_server_id = options[0]["id"]

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

            if action == "update_item":
                item_id = int(request.form.get("item_id", "0") or 0)
                with database() as connection:
                    existing_item = connection.execute("""
                        SELECT *
                        FROM guess_library_items
                        WHERE id = ?
                    """, (item_id,)).fetchone()
                    if not existing_item:
                        raise ValueError("Library item was not found.")
                    if not can_admin_access_guild(
                        existing_item["guild_id"],
                        config_data,
                    ):
                        abort(403)
                    answer_aliases = parse_answer_aliases(
                        request.form.get("answer", "")
                )
                if not answer_aliases:
                    raise ValueError("Answer is required.")
                answer_display = answer_aliases[0]["display"]
                normalized_answer = answer_aliases[0]["normalized"]
                title = request.form.get("title", "").strip()[:120]
                max_text_length = int(
                    config_data.get("limits", {}).get(
                        "max_text_length",
                        DEFAULT_LIMITS["max_text_length"],
                    )
                )
                prompt_text = request.form.get("prompt_text", "").strip()
                if len(prompt_text) > max_text_length:
                    raise ValueError(
                        f"Prompt text is limited to {max_text_length} characters."
                    )
                hint_text = request.form.get("hint_text", "").strip()
                if len(hint_text) > 500:
                    raise ValueError("Hints are limited to 500 characters.")
                category = request.form.get("category", "").strip()[:80]
                try:
                    auto_hint_minutes = int(
                        request.form.get("auto_hint_minutes", "0") or 0
                    )
                except ValueError as form_error:
                    raise ValueError(
                        "Automatic hint minutes must be a number."
                    ) from form_error
                auto_hint_minutes = max(0, min(1440, auto_hint_minutes))
                new_status = request.form.get("status", "draft").strip()
                if new_status not in {"draft", "active", "disabled"}:
                    raise ValueError("Invalid library item status.")

                media_info = None
                upload = request.files.get("media")
                if upload is not None and upload.filename:
                    media_info = save_guess_library_upload(
                        existing_item["guild_id"],
                        upload,
                        config_data.get("limits", {}),
                    )
                has_media = bool(
                    media_info
                    or (
                        existing_item["media_path"]
                        and Path(existing_item["media_path"]).exists()
                    )
                )
                if new_status == "active" and not has_media:
                    raise ValueError("Active library items must have media attached.")

                old_media_path = existing_item["media_path"] if media_info else ""
                try:
                    with database() as connection:
                        connection.execute("""
                            UPDATE guess_library_items
                            SET title = ?,
                                answer = ?,
                                answer_display = ?,
                                answer_aliases_json = ?,
                                prompt_text = ?,
                                category = ?,
                                hint_text = ?,
                                auto_hint_minutes = ?,
                                media_path = ?,
                                media_name = ?,
                                media_type = ?,
                                media_size = ?,
                                media_metadata_json = ?,
                                status = ?,
                                updated_at = ?
                            WHERE id = ?
                        """, (
                            title or answer_display,
                            normalized_answer,
                            answer_display,
                            json.dumps(answer_aliases, separators=(",", ":")),
                            prompt_text,
                            category,
                            hint_text,
                            auto_hint_minutes,
                            media_info["path"] if media_info else existing_item["media_path"],
                            media_info["name"] if media_info else existing_item["media_name"],
                            media_info["type"] if media_info else existing_item["media_type"],
                            int(media_info["size"] or 0) if media_info else int(existing_item["media_size"] or 0),
                            (
                                json.dumps(
                                    media_info["metadata"],
                                    separators=(",", ":"),
                                )
                                if media_info
                                else existing_item["media_metadata_json"]
                            ),
                            new_status,
                            utc_now_iso(),
                            item_id,
                        ))
                        add_admin_audit_log(
                            connection,
                            existing_item["guild_id"],
                            "dashboard_update_guess_library_item",
                            actor_id,
                            actor_name,
                            "guess_library_item",
                            item_id,
                            f"Updated website game-library item {item_id}.",
                        )
                except Exception:
                    if media_info:
                        delete_guess_library_media(media_info["path"])
                    raise
                if old_media_path:
                    delete_guess_library_media(old_media_path)
                return game_library_redirect(
                    f"Library item {item_id} updated.",
                    guild_id=redirect_guild_id,
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
                    if not can_admin_access_guild(item["guild_id"], config_data):
                        abort(403)
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
                    if not can_admin_access_guild(item["guild_id"], config_data):
                        abort(403)
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
            media_url(relative_path, item.get("guild_id"))
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
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"

    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        actor_id, actor_name = web_actor()
        if action in {
            "create_dashboard_user",
            "update_dashboard_user",
            "disable_dashboard_user",
        }:
            if not has_admin_role("owner"):
                abort(403)
            username = request.form.get("username", "").strip().casefold()
            role = normalize_role(request.form.get("role", "moderator"))
            password = request.form.get("password", "")
            guild_scope = parse_guild_scope(request.form.get("guild_ids", ""))
            guild_scope_json = json.dumps(guild_scope, separators=(",", ":"))
            if not username or not re.match(r"^[a-z0-9_.-]{3,40}$", username):
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice="Dashboard username must be 3-40 letters, numbers, dots, dashes, or underscores.",
                    error=1,
                ))
            now = utc_now_iso()
            with database() as connection:
                if action == "create_dashboard_user":
                    if not password:
                        return redirect(url_for(
                            "admin_settings",
                            key=ADMIN_KEY,
                            notice="Password is required for new dashboard users.",
                            error=1,
                        ))
                    connection.execute("""
                        INSERT INTO dashboard_admin_users (
                            username, password_hash, role, disabled,
                            created_at, updated_at, guild_ids_json
                        )
                        VALUES (?, ?, ?, 0, ?, ?, ?)
                        ON CONFLICT(username) DO UPDATE SET
                            password_hash = excluded.password_hash,
                            role = excluded.role,
                            disabled = 0,
                            guild_ids_json = excluded.guild_ids_json,
                            updated_at = excluded.updated_at
                    """, (
                        username,
                        generate_password_hash(password),
                        role,
                        now,
                        now,
                        guild_scope_json,
                    ))
                    message = f"Dashboard user {username} saved as {role}."
                elif action == "update_dashboard_user":
                    user = connection.execute("""
                        SELECT username
                        FROM dashboard_admin_users
                        WHERE username = ?
                    """, (username,)).fetchone()
                    if not user:
                        return redirect(url_for(
                            "admin_settings",
                            key=ADMIN_KEY,
                            notice="Dashboard user was not found.",
                            error=1,
                        ))
                    if password:
                        connection.execute("""
                            UPDATE dashboard_admin_users
                            SET password_hash = ?, role = ?, guild_ids_json = ?,
                                disabled = 0,
                                updated_at = ?
                            WHERE username = ?
                        """, (
                            generate_password_hash(password),
                            role,
                            guild_scope_json,
                            now,
                            username,
                        ))
                    else:
                        connection.execute("""
                            UPDATE dashboard_admin_users
                            SET role = ?, guild_ids_json = ?, disabled = 0,
                                updated_at = ?
                            WHERE username = ?
                        """, (role, guild_scope_json, now, username))
                    message = f"Dashboard user {username} updated."
                else:
                    connection.execute("""
                        UPDATE dashboard_admin_users
                        SET disabled = 1, updated_at = ?
                        WHERE username = ?
                    """, (now, username))
                    message = f"Dashboard user {username} disabled."
                add_admin_audit_log(
                    connection,
                    None,
                    f"dashboard_{action}",
                    actor_id,
                    actor_name,
                    "dashboard_user",
                    username,
                    message,
                )
            return redirect(url_for(
                "admin_settings",
                key=ADMIN_KEY,
                notice=message,
            ))
        if action == "set_notification_route":
            config_data = load_config()
            guild_id = request.form.get("guild_id", "").strip()
            if guild_id not in (config_data.get("guilds") or {}):
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice="Unknown guild for notification route.",
                    error=1,
                ))
            if not can_admin_access_guild(guild_id, config_data):
                abort(403)
            event_key = request.form.get("event_key", "").strip()
            if event_key not in NOTIFICATION_EVENT_LABELS:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice="Unknown notification event.",
                    error=1,
                ))
            try:
                channel_id = nullable_channel_id(request.form.get("channel_id"))
            except ValueError as form_error:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice=str(form_error),
                    error=1,
                ))
            enabled = request.form.get("enabled") == "1"
            if enabled and channel_id is None:
                return redirect(url_for(
                    "admin_settings",
                    key=ADMIN_KEY,
                    notice="Enabled notification routes need a channel ID.",
                    error=1,
                ))
            now = utc_now_iso()
            with database() as connection:
                connection.execute("""
                    INSERT INTO admin_notifications (
                        guild_id, event_key, channel_id, enabled,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, event_key) DO UPDATE SET
                        channel_id = excluded.channel_id,
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                """, (
                    guild_id,
                    event_key,
                    str(channel_id) if channel_id is not None else "",
                    1 if enabled else 0,
                    now,
                    now,
                ))
                add_admin_audit_log(
                    connection,
                    guild_id,
                    "dashboard_set_notification_route",
                    actor_id,
                    actor_name,
                    "admin_notification",
                    event_key,
                    (
                        f"Set {NOTIFICATION_EVENT_LABELS[event_key]} route to "
                        f"{channel_id or 'disabled'}."
                    ),
                )
            return redirect(url_for(
                "admin_settings",
                key=ADMIN_KEY,
                notice="Notification route saved.",
            ))
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
            if not created and message != "Backup already exists.":
                send_admin_notification(
                    "backup_failed",
                    f"Manual dashboard backup failed: `{message}`",
                    throttle_key="dashboard_backup_failed",
                    throttle_seconds=900,
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
                    "monthly_submission_limit_per_guild",
                    "active_game_limit_per_guild",
                    "guild_storage_limit_bytes",
                    "offsite_backup_warning_hours",
                    "local_original_retention_days",
                    "thumbnail_max_dimension",
                    "image_compression_quality",
                    "archive_full_history_after_months",
                    "spam_review_threshold",
                    "spam_burst_count",
                    "spam_burst_window_minutes",
                ):
                    value = int(request.form.get(field, "0"))
                    if value < 0:
                        raise ValueError("Limits cannot be negative.")
                    limits[field] = value
                if limits["thumbnail_max_dimension"] and not (
                    160 <= limits["thumbnail_max_dimension"] <= 2048
                ):
                    raise ValueError(
                        "Thumbnail max dimension must be between 160 and 2048."
                    )
                if limits["image_compression_quality"] and not (
                    40 <= limits["image_compression_quality"] <= 95
                ):
                    raise ValueError(
                        "Image compression quality must be between 40 and 95."
                    )
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
                limits["restore_drill_enabled"] = (
                    request.form.get("restore_drill_enabled") == "1"
                )
                limits["monthly_digest_enabled"] = (
                    request.form.get("monthly_digest_enabled") == "1"
                )
                limits["two_admin_approval_enabled"] = (
                    request.form.get("two_admin_approval_enabled") == "1"
                )
                limits["orphan_media_cleanup_enabled"] = (
                    request.form.get("orphan_media_cleanup_enabled") == "1"
                )
                limits["image_compression_enabled"] = (
                    request.form.get("image_compression_enabled") == "1"
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
            if not can_admin_access_guild(guild_id, config_data):
                abort(403)
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
                    guild_config["emergency_paused"] = (
                        request.form.get("emergency_paused") == "1"
                    )
                    guild_config["emergency_reason"] = request.form.get(
                        "emergency_reason",
                        "",
                    ).strip()[:300]
                    if not guild_config["emergency_paused"]:
                        guild_config["emergency_reason"] = ""
                    guild_config["game_summary_channel"] = nullable_channel_id(
                        request.form.get("game_summary_channel")
                    )
                    guild_config["error_channel"] = nullable_channel_id(
                        request.form.get("error_channel")
                    )
                    guild_config["admin_role_ids"] = role_id_list(
                        request.form.get("admin_role_ids")
                    )
                    guild_config["public_stats_enabled"] = (
                        request.form.get("public_stats_enabled") == "1"
                    )
                    backup_remote = request.form.get(
                        "external_backup_remote",
                        "",
                    ).strip()[:300]
                    if any(character in backup_remote for character in "\r\n"):
                        raise ValueError(
                            "External backup remote cannot contain line breaks."
                        )
                    backup_public_base = request.form.get(
                        "external_backup_public_base_url",
                        "",
                    ).strip().rstrip("/")[:300]
                    if backup_public_base and not backup_public_base.startswith(
                        ("https://", "http://")
                    ):
                        raise ValueError(
                            "External backup public media URL must start with http:// or https://."
                        )
                    include_media = (
                        request.form.get("external_backup_include_media") == "1"
                    )
                    delete_local_media = (
                        request.form.get(
                            "external_backup_delete_local_media_after_success"
                        ) == "1"
                    )
                    if delete_local_media and not include_media:
                        raise ValueError(
                            "Local media cleanup requires media backup to be enabled."
                        )
                    backup_enabled = (
                        request.form.get("external_backup_enabled") == "1"
                    )
                    if backup_enabled and not backup_remote:
                        raise ValueError(
                            "External backup remote is required when backups are enabled."
                        )
                    existing_backup = guild_config.get("external_backup") or {}
                    guild_config["external_backup"] = {
                        **DEFAULT_GUILD_FIELDS["external_backup"],
                        **existing_backup,
                        "enabled": backup_enabled,
                        "provider": "rclone",
                        "remote": backup_remote,
                        "public_base_url": backup_public_base,
                        "include_media": include_media,
                        "include_database_export": (
                            request.form.get(
                                "external_backup_include_database_export"
                            ) == "1"
                        ),
                        "delete_local_media_after_success": delete_local_media,
                    }
                    guild_limits = guild_config.setdefault("limits", {})
                    for field, form_name in (
                        ("max_file_bytes", "guild_max_file_bytes"),
                        ("max_total_bytes", "guild_max_total_bytes"),
                        ("monthly_submission_limit", "guild_monthly_submission_limit"),
                        ("active_game_limit", "guild_active_game_limit"),
                        ("storage_limit_bytes", "guild_storage_limit_bytes"),
                    ):
                        value = int(request.form.get(form_name, "0") or 0)
                        if value < 0:
                            raise ValueError("Guild limits cannot be negative.")
                        guild_limits[field] = value
                    media_types = [
                        item.strip().casefold()
                        for item in request.form.get(
                            "allowed_media_types",
                            "image,video,audio",
                        ).split(",")
                        if item.strip()
                    ]
                    invalid_types = sorted(
                        set(media_types) - {"image", "video", "audio"}
                    )
                    if invalid_types:
                        raise ValueError(
                            "Allowed media types can only include image, video, and audio."
                        )
                    new_user_days = int(request.form.get("new_user_days", "7") or 7)
                    if new_user_days < 0 or new_user_days > 365:
                        raise ValueError("New-user days must be 0-365.")
                    spam_burst_count = int(
                        request.form.get("spam_burst_count", "5") or 0
                    )
                    spam_burst_window = int(
                        request.form.get("spam_burst_window_minutes", "10") or 0
                    )
                    spam_review_threshold = int(
                        request.form.get("spam_review_threshold", "40") or 0
                    )
                    if spam_burst_count < 0 or spam_burst_count > 100:
                        raise ValueError("Spam burst count must be 0-100.")
                    if spam_burst_window < 0 or spam_burst_window > 1440:
                        raise ValueError("Spam burst window must be 0-1440 minutes.")
                    if spam_review_threshold < 0 or spam_review_threshold > 1000:
                        raise ValueError("Spam review threshold must be 0-1000.")
                    moderation_config = guild_config.setdefault("moderation", {})
                    moderation_config.update({
                        "blocked_words": [
                            item.strip()
                            for item in request.form.get("blocked_words", "").split(",")
                            if item.strip()
                        ][:100],
                        "allowed_media_types": media_types or ["image", "video", "audio"],
                        "require_approval_for_new_users": (
                            request.form.get("require_approval_for_new_users") == "1"
                        ),
                        "new_user_days": new_user_days,
                        "spoiler_requires_approval": (
                            request.form.get("spoiler_requires_approval") == "1"
                        ),
                        "duplicate_requires_approval": (
                            request.form.get("duplicate_requires_approval") == "1"
                        ),
                        "spam_burst_count": spam_burst_count,
                        "spam_burst_window_minutes": spam_burst_window,
                        "spam_review_threshold": spam_review_threshold,
                    })
                    reuse_days = int(request.form.get("reuse_cooldown_days", "30") or 0)
                    auto_hint = int(request.form.get("default_auto_hint_minutes", "0") or 0)
                    if reuse_days < 0 or reuse_days > 3650:
                        raise ValueError("Reuse cooldown must be 0-3650 days.")
                    if auto_hint < 0 or auto_hint > 1440:
                        raise ValueError("Auto-hint minutes must be 0-1440.")
                    guild_config["game_settings"] = {
                        "reuse_cooldown_days": reuse_days,
                        "default_auto_hint_minutes": auto_hint,
                        "default_difficulty": request.form.get(
                            "default_difficulty",
                            "normal",
                        ).strip()[:40] or "normal",
                    }
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
    allowed_settings_ids = {option["id"] for option in guild_options(config_data)}
    for guild_id, guild_config in sorted(
        (config_data.get("guilds") or {}).items()
    ):
        if str(guild_id) not in allowed_settings_ids:
            continue
        features = guild_config.get("features") or {}
        guild_limits = guild_config.get("limits") or {}
        moderation = guild_config.get("moderation") or {}
        game_settings = guild_config.get("game_settings") or {}
        external_backup = {
            **DEFAULT_GUILD_FIELDS["external_backup"],
            **(guild_config.get("external_backup") or {}),
        }
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
            "emergency_paused": guild_config.get("emergency_paused", False),
            "emergency_reason": guild_config.get("emergency_reason") or "",
            "limits": {
                **DEFAULT_GUILD_FIELDS["limits"],
                **guild_limits,
            },
            "moderation": {
                **DEFAULT_GUILD_FIELDS["moderation"],
                **moderation,
            },
            "game_settings": {
                **DEFAULT_GUILD_FIELDS["game_settings"],
                **game_settings,
            },
            "public_stats_enabled": guild_config.get("public_stats_enabled", True),
            "external_backup": external_backup,
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

    scope_sql, scope_params = guild_id_filter("guild_id", allowed_settings_ids)
    with closing(connect_db()) as connection:
        stats = {
            "submissions": connection.execute(
                f"SELECT COUNT(*) FROM submissions WHERE {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "active_games": connection.execute(f"""
                SELECT COUNT(*)
                FROM guess_games
                WHERE status = 'active'
                  AND {scope_sql}
            """, scope_params).fetchone()[0],
            "audit_entries": connection.execute(f"""
                SELECT
                    (SELECT COUNT(*) FROM admin_audit_log WHERE {scope_sql})
                    + (SELECT COUNT(*) FROM moderation_history WHERE {scope_sql})
            """, scope_params + scope_params).fetchone()[0],
            "rate_limit_events": connection.execute(f"""
                SELECT COUNT(*)
                FROM rate_limit_events
                WHERE {scope_sql}
            """, scope_params).fetchone()[0],
            "media_size": format_bytes(media_directory_size()),
        }
        active_games = connection.execute(f"""
            SELECT id, guild_id, channel_id, starter_username,
                   media_name, started_at
            FROM guess_games
            WHERE status = 'active'
              AND {scope_sql}
            ORDER BY started_at DESC, id DESC
        """, scope_params).fetchall()

    db_size = format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B"
    return render_template_string(
        SETTINGS_HTML,
        active_games=active_games,
        admin_key=ADMIN_KEY,
        backups=recent_database_backups(),
        can_manage_users=has_admin_role("owner"),
        csrf_token=get_csrf_token(),
        current_admin_role=current_admin_role(),
        current_admin_username=current_admin_username(),
        dashboard_users=dashboard_users() if has_admin_role("owner") else [],
        db_file=DB_FILE,
        db_size=db_size,
        error=error,
        guilds=guilds,
        limits=limits,
        notice=notice,
        notification_event_labels=NOTIFICATION_EVENT_LABELS,
        notification_routes=notification_routes(config_data),
        parse_guild_scope=parse_guild_scope,
        role_labels=ROLE_LABELS,
        security_warnings=warnings,
        stats=stats,
        weekdays=WEEKDAYS,
    )


@app.route("/admin/maintenance", methods=["GET", "POST"])
def admin_maintenance():
    login_response = require_admin_login("admin")
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
            if not created and message != "Backup already exists.":
                send_admin_notification(
                    "backup_failed",
                    f"Manual maintenance backup failed: `{message}`",
                    throttle_key="maintenance_backup_failed",
                    throttle_seconds=900,
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
            if not passed:
                send_admin_notification(
                    "restore_test_failed",
                    f"Manual restore test failed: `{message}`",
                    throttle_key="maintenance_restore_test_failed",
                    throttle_seconds=900,
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
        if action in {"archive_history", "archive_history_delete"}:
            delete_exported = action == "archive_history_delete"
            job_id = queue_background_job(
                "archive_history",
                payload={"delete_exported": delete_exported},
                actor_id=actor_id,
                actor_name=actor_name,
            )
            message = f"Queued history archive as background job #{job_id}."
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=message,
                error=0,
            ))
        if action == "rollback_latest_snapshot":
            if two_admin_approval_enabled(load_config()):
                return approval_required_redirect(
                    "rollback_latest_snapshot",
                    "deploy_snapshot",
                    "latest",
                    {},
                    actor_id,
                    actor_name,
                    endpoint="admin_maintenance",
                )
            job_id = queue_background_job(
                "rollback_latest_snapshot",
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=(
                    f"Queued rollback to the latest deploy snapshot as "
                    f"background job #{job_id}. Watch the Jobs page; the "
                    "dashboard may briefly restart if rollback succeeds."
                ),
                error=0,
            ))
        if action == "optimize_database":
            job_id = queue_background_job(
                "optimize_database",
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_maintenance",
                key=ADMIN_KEY,
                notice=f"Queued database optimize as background job #{job_id}.",
                error=0,
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

    bot_status = read_bot_status()
    maybe_notify_stale_bot(bot_status)
    allowed_guild_ids = current_admin_allowed_guild_ids(config_data)
    guild_backup_rows = []
    for guild_id, guild_config in sorted((config_data.get("guilds") or {}).items()):
        if allowed_guild_ids is not None and str(guild_id) not in allowed_guild_ids:
            continue
        backup = {
            **DEFAULT_GUILD_FIELDS["external_backup"],
            **(guild_config.get("external_backup") or {}),
        }
        if not (
            backup.get("enabled")
            or backup.get("remote")
            or backup.get("last_status")
            or backup.get("public_base_url")
        ):
            continue
        guild_backup_rows.append({
            "guild_id": guild_id,
            "name": (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or f"Discord {guild_id}"
            ),
            **backup,
        })

    return render_template_string(
        MAINTENANCE_HTML,
        admin_key=ADMIN_KEY,
        bot_status=bot_status,
        backups=recent_database_backups(),
        cache_entries=len(PUBLIC_PAGE_CACHE),
        config_backups=recent_config_backups(),
        csrf_token=get_csrf_token(),
        dashboard_instance_id=DASHBOARD_INSTANCE_ID,
        db_file=DB_FILE,
        db_size=format_bytes(DB_FILE.stat().st_size) if DB_FILE.exists() else "0 B",
        error=error,
        guild_backup_rows=guild_backup_rows,
        media_files=media_stats["files"],
        media_size=format_bytes(media_stats["bytes"]),
        notice=notice,
        offsite_backup=config_data.get("offsite_backup") or {},
        release=os.getenv("SDAC_RELEASE") or "development",
        release_status=release_status(),
        restore_runs=restore_runs,
        server_name=os.getenv("SDAC_SERVER_NAME") or "local",
        started_at=APP_STARTED_AT.strftime("%Y-%m-%d %H:%M UTC"),
        storage_forecasts=storage_forecast_rows(config_data),
        uptime=f"{days}d {hours}h {minutes}m",
        warnings=security_warnings() + storage_warnings(config_data),
    )


@app.route("/admin/media", methods=["GET", "POST"])
def admin_media_cleanup():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    actor_id, actor_name = web_actor()
    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        config_data = load_config()
        if action == "delete_orphans":
            if two_admin_approval_enabled(config_data):
                return approval_required_redirect(
                    "delete_orphans",
                    "media",
                    "orphans",
                    {},
                    actor_id,
                    actor_name,
                    endpoint="admin_media_cleanup",
                )
            deleted = delete_orphaned_media_files()
            with database() as connection:
                add_admin_audit_log(
                    connection,
                    None,
                    "dashboard_delete_orphaned_media",
                    actor_id,
                    actor_name,
                    "media",
                    "",
                    f"Deleted {deleted} orphaned media file(s).",
                )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=f"Deleted {deleted} orphaned media file(s).",
            ))
        if action == "generate_thumbnails":
            job_id = queue_background_job(
                "generate_thumbnails",
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=f"Queued thumbnail generation as job #{job_id}.",
            ))
        if action == "rebuild_media_fingerprints":
            job_id = queue_background_job(
                "rebuild_media_fingerprints",
                payload={"limit": 10000},
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=f"Queued media fingerprint rebuild as job #{job_id}.",
            ))
        if action in {"prune_backed_up_originals", "prune_guild_originals"}:
            guild_id = (
                request.form.get("guild_id", "").strip()
                if action == "prune_guild_originals"
                else None
            )
            if two_admin_approval_enabled(config_data):
                return approval_required_redirect(
                    "prune_backed_up_originals",
                    "guild",
                    guild_id or "all",
                    {"guild_id": guild_id},
                    actor_id,
                    actor_name,
                    guild_id=guild_id,
                    endpoint="admin_media_cleanup",
                )
            job_id = queue_background_job(
                "prune_backed_up_originals",
                guild_id=guild_id,
                payload={"guild_id": guild_id},
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=f"Queued backed-up original pruning as job #{job_id}.",
            ))
        if action == "restore_guild_media":
            guild_id = request.form.get("guild_id", "").strip()
            job_id = queue_background_job(
                "restore_guild_media",
                guild_id=guild_id,
                payload={"guild_id": guild_id},
                actor_id=actor_id,
                actor_name=actor_name,
            )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=f"Queued media restore as job #{job_id}.",
            ))
        if action in {"restore_quarantine", "delete_quarantine"}:
            quarantine_id = int(request.form.get("quarantine_id", "0") or 0)
            ok, message = resolve_quarantine_item(
                quarantine_id,
                "restore" if action == "restore_quarantine" else "delete",
                actor_id,
                actor_name,
            )
            return redirect(url_for(
                "admin_media_cleanup",
                key=ADMIN_KEY,
                notice=message,
                error=0 if ok else 1,
            ))

    config_data = load_config()
    return render_template_string(
        MEDIA_CLEANUP_HTML,
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        guild_storage_rows=guild_storage_rows(config_data),
        notice=notice,
        quarantine_items=quarantine_items(),
        report=media_cleanup_report(),
    )


@app.route("/admin/jobs")
def admin_jobs():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    resume_queued_background_jobs()
    config_data = load_config()
    options = guild_options(config_data)
    selected_server_id = selected_guild_id(options)
    return render_template_string(
        JOBS_HTML,
        admin_key=ADMIN_KEY,
        jobs=recent_background_jobs(
            limit=75,
            guild_id=selected_server_id,
        ),
    )


@app.route("/admin/install-doctor")
def admin_install_doctor():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    return render_template_string(
        INSTALL_DOCTOR_HTML,
        admin_key=ADMIN_KEY,
        report=install_doctor_report(),
    )


@app.route("/admin/approvals", methods=["GET", "POST"])
def admin_approvals():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    selected_status = request.args.get("status", "pending").strip() or "pending"
    if selected_status not in {"pending", "complete", "denied", "failed", "all"}:
        selected_status = "pending"
    actor_id, actor_name = web_actor()
    if request.method == "POST":
        require_csrf_token()
        action_id = int(request.form.get("action_id", "0") or 0)
        decision = request.form.get("decision", "approve")
        if decision not in {"approve", "deny"}:
            abort(400)
        ok, message = resolve_pending_admin_action(
            action_id,
            decision,
            actor_id,
            actor_name,
        )
        return redirect(url_for(
            "admin_approvals",
            key=ADMIN_KEY,
            status=selected_status,
            notice=message,
            error=0 if ok else 1,
        ))
    return render_template_string(
        APPROVALS_HTML,
        actions=pending_admin_action_rows(selected_status),
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        error=error,
        notice=notice,
        selected_status=selected_status,
    )


@app.route("/admin/privacy", methods=["GET", "POST"])
def admin_privacy():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    error = request.args.get("error") == "1"
    config_data = load_config()
    options = guild_options(config_data)
    valid_guild_ids = {option["id"] for option in options}
    actor_id, actor_name = web_actor()

    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        guild_id = request.form.get("guild_id", "").strip()
        user_id = request.form.get("user_id", "").strip()
        if guild_id not in valid_guild_ids or not user_id:
            abort(400)
        if action == "export":
            payload = user_privacy_export_payload(guild_id, user_id)
            with database() as connection:
                connection.execute("""
                    INSERT INTO privacy_actions (
                        guild_id, user_id, action, actor_user_id,
                        actor_username, details_json, created_at
                    )
                    VALUES (?, ?, 'export_user_data', ?, ?, ?, ?)
                """, (
                    guild_id,
                    user_id,
                    actor_id,
                    actor_name,
                    json.dumps({
                        "submissions": len(payload["submissions"]),
                        "guess_points": len(payload["guess_points"]),
                    }, separators=(",", ":")),
                    utc_now_iso(),
                ))
                add_admin_audit_log(
                    connection,
                    guild_id,
                    "privacy_export_user_data",
                    actor_id,
                    actor_name,
                    "user",
                    user_id,
                    "Exported user privacy data.",
                )
            return Response(
                json.dumps(payload, indent=2),
                mimetype="application/json",
                headers={
                    "Content-Disposition": (
                        f"attachment; filename=sdac-user-{guild_id}-{user_id}.json"
                    )
                },
            )
        if action == "delete":
            if request.form.get("confirm_delete", "").strip() != "DELETE":
                return redirect(url_for(
                    "admin_privacy",
                    key=ADMIN_KEY,
                    notice="Type DELETE before deleting user data.",
                    error=1,
                ))
            if two_admin_approval_enabled(config_data):
                return approval_required_redirect(
                    "privacy_delete_user_data",
                    "user",
                    user_id,
                    {"guild_id": guild_id, "user_id": user_id},
                    actor_id,
                    actor_name,
                    guild_id=guild_id,
                    endpoint="admin_privacy",
                )
            details = delete_user_privacy_data(
                guild_id,
                user_id,
                actor_id,
                actor_name,
            )
            return redirect(url_for(
                "admin_privacy",
                key=ADMIN_KEY,
                notice=(
                    f"Deleted {details['submissions_deleted']} submission(s) "
                    f"and {details['discord_messages_deleted']} Discord message(s)."
                ),
            ))

    with closing(connect_db()) as connection:
        actions = connection.execute("""
            SELECT *
            FROM privacy_actions
            ORDER BY created_at DESC, id DESC
            LIMIT 50
        """).fetchall()
    return render_template_string(
        PRIVACY_HTML,
        actions=actions,
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        error=error,
        guild_options=options,
        notice=notice,
    )


@app.get("/admin/guild/<guild_id>/config.json")
def admin_export_guild_config(guild_id):
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    config_data = load_config()
    if not can_admin_access_guild(guild_id, config_data):
        abort(403)
    payload = exportable_guild_config(config_data, guild_id)
    return Response(
        json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": (
                f"attachment; filename=sdac-guild-config-{guild_id}.json"
            )
        },
    )


@app.post("/admin/guild-config/import")
def admin_import_guild_config():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    require_csrf_token()
    guild_id = request.form.get("guild_id", "").strip()
    if not guild_id:
        abort(400)
    config_data = load_config()
    if not can_admin_access_guild(guild_id, config_data):
        abort(403)
    raw_config = request.form.get("config_json", "").strip()
    try:
        payload = json.loads(raw_config)
        guild_config = normalize_imported_guild_config(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as import_error:
        return redirect(url_for(
            "admin_settings",
            key=ADMIN_KEY,
            notice=f"Config import failed: {import_error}",
            error=1,
        ))
    if request.form.get("confirm_import") != "1":
        current_config = (config_data.get("guilds") or {}).get(str(guild_id)) or {}
        guild_names = {
            option["id"]: option["name"]
            for option in guild_options(config_data)
        }
        normalized_json = json.dumps({
            "format": "sdac-guild-config-v1",
            "guild_id": payload.get("guild_id") or guild_id,
            "guild_config": guild_config,
        }, indent=2, sort_keys=True)
        return render_template_string(
            CONFIG_DIFF_HTML,
            admin_key=ADMIN_KEY,
            csrf_token=get_csrf_token(),
            diff_rows=guild_config_diff(current_config, guild_config),
            guild_id=str(guild_id),
            guild_name=guild_names.get(str(guild_id), f"Discord {guild_id}"),
            normalized_json=normalized_json,
            source_guild_id=payload.get("guild_id") or "",
        )
    actor_id, actor_name = web_actor()
    config_data.setdefault("guilds", {})[str(guild_id)] = guild_config
    save_config(config_data)
    with database() as connection:
        add_admin_audit_log(
            connection,
            guild_id,
            "import_guild_config",
            actor_id,
            actor_name,
            "guild_config",
            guild_id,
            "Imported guild configuration from dashboard.",
        )
    return redirect(url_for(
        "admin_settings",
        key=ADMIN_KEY,
        notice=f"Imported config for guild {guild_id}.",
    ))


@app.route("/admin/analytics")
def admin_analytics():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    config_data = load_config()
    options = guild_options(config_data)
    selected_server_id = selected_guild_id(options)
    allowed_ids = (
        {selected_server_id}
        if selected_server_id
        else current_admin_allowed_guild_ids(config_data)
    )
    scope_sql, scope_params = guild_id_filter("guild_id", allowed_ids)
    with closing(connect_db()) as connection:
        totals = {
            "Submissions": connection.execute(
                f"SELECT COUNT(*) FROM submissions WHERE {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "Posted Submissions": connection.execute(
                f"SELECT COUNT(*) FROM submissions WHERE status = 'posted' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "Active Games": connection.execute(
                f"SELECT COUNT(*) FROM guess_games WHERE status = 'active' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "Recorded Answers": connection.execute(
                f"SELECT COUNT(*) FROM guess_answer_history WHERE {scope_sql}",
                scope_params,
            ).fetchone()[0],
        }
        submissions_by_month = connection.execute(f"""
            SELECT substr(COALESCE(created_at, submitted_at, ''), 1, 7) AS month,
                   COUNT(*) AS count
            FROM submissions
            WHERE {scope_sql}
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """, scope_params).fetchall()
        top_categories = connection.execute(f"""
            SELECT category, COUNT(*) AS count
            FROM submissions
            WHERE {scope_sql}
            GROUP BY category
            ORDER BY count DESC, category ASC
            LIMIT 10
        """, scope_params).fetchall()
        top_submitters = connection.execute(f"""
            SELECT username, COUNT(*) AS count
            FROM submissions
            WHERE {scope_sql}
            GROUP BY user_id, username
            ORDER BY count DESC, username ASC
            LIMIT 10
        """, scope_params).fetchall()
        answer_history = connection.execute(f"""
            SELECT answer_display, category, source, created_at
            FROM guess_answer_history
            WHERE {scope_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT 25
        """, scope_params).fetchall()

    return render_template_string(
        ANALYTICS_HTML,
        admin_key=ADMIN_KEY,
        answer_history=answer_history,
        guild_options=options,
        selected_guild_id=selected_server_id,
        submissions_by_month=submissions_by_month,
        top_categories=top_categories,
        top_submitters=top_submitters,
        totals=totals,
    )


@app.route("/admin/monthly-report")
def admin_monthly_report():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    config_data = load_config()
    options = guild_options(config_data)
    selected_server_id = selected_guild_id(options)
    month = request.args.get("month", current_month_key()).strip()
    if not re.match(r"^\d{4}-\d{2}$", month):
        month = current_month_key()
    report = monthly_report_data(month, selected_server_id)
    return render_template_string(
        MONTHLY_REPORT_HTML,
        activity=report["activity"],
        admin_key=ADMIN_KEY,
        guild_names=guild_name_map(config_data),
        guild_options=options,
        month=report["month"],
        selected_guild_id=selected_server_id,
        top_guessers=report["top_guessers"],
        top_submissions=report["top_submissions"],
        totals=report["totals"],
    )


@app.route("/admin/releases")
def admin_releases():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    return render_template_string(
        RELEASES_HTML,
        admin_key=ADMIN_KEY,
        release_status=release_status(),
        snapshots=latest_deploy_snapshots(),
    )


@app.route("/admin/production-health")
def admin_production_health():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    report = production_health_report(load_config())
    return render_template_string(
        PRODUCTION_HEALTH_HTML,
        admin_key=ADMIN_KEY,
        checks=report["checks"],
        free_backup_options=free_offsite_backup_options(),
        max_score=report["max_score"],
        score=report["score"],
    )


@app.route("/admin/moderation", methods=["GET", "POST"])
def admin_moderation():
    login_response = require_admin_login()
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    config_data = load_config()
    guild_names = guild_name_map(config_data)
    allowed_moderation_ids = current_admin_allowed_guild_ids(config_data)
    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        actor_id, actor_name = web_actor()
        if action == "bulk_resolve_reports":
            report_ids = [
                int(report_id)
                for report_id in request.form.getlist("report_ids")
                if str(report_id).isdigit()
            ]
            admin_notes = request.form.get("admin_notes", "").strip()[:500]
            if not report_ids:
                return redirect(url_for(
                    "admin_moderation",
                    key=ADMIN_KEY,
                    notice="Choose at least one report.",
                ))
            placeholders = ", ".join("?" for _ in report_ids)
            scope_sql, scope_params = guild_id_filter(
                "guild_id",
                allowed_moderation_ids,
            )
            with database() as connection:
                connection.execute(f"""
                    UPDATE submission_reports
                    SET status = 'resolved',
                        admin_notes = ?,
                        resolved_at = ?
                    WHERE id IN ({placeholders})
                      AND {scope_sql}
                """, [admin_notes, utc_now_iso()] + report_ids + scope_params)
                add_admin_audit_log(
                    connection,
                    None,
                    "dashboard_bulk_resolve_reports",
                    actor_id,
                    actor_name,
                    "submission_report",
                    ",".join(str(report_id) for report_id in report_ids),
                    f"Resolved {len(report_ids)} report(s).",
                )
            return redirect(url_for(
                "admin_moderation",
                key=ADMIN_KEY,
                notice=f"Resolved {len(report_ids)} report(s).",
            ))
        if action == "resolve_report":
            report_id = request.form.get("report_id", "").strip()
            admin_notes = request.form.get("admin_notes", "").strip()[:500]
            with database() as connection:
                report = connection.execute("""
                    SELECT *
                    FROM submission_reports
                    WHERE id = ?
                """, (report_id,)).fetchone()
                if report and not can_admin_access_guild(
                    report["guild_id"],
                    config_data,
                ):
                    abort(403)
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
        scope_sql, scope_params = guild_id_filter(
            "reports.guild_id",
            allowed_moderation_ids,
        )
        reports = connection.execute(f"""
            SELECT reports.id, reports.submission_id, reports.guild_id,
                   reports.reporter_name, reports.reason, reports.created_at
            FROM submission_reports AS reports
            WHERE reports.status = 'open'
              AND {scope_sql}
            ORDER BY reports.created_at DESC, reports.id DESC
            LIMIT 50
        """, scope_params).fetchall()
        scope_sql, scope_params = guild_id_filter(
            "guild_id",
            allowed_moderation_ids,
        )
        pending_rows = connection.execute(f"""
            SELECT *
            FROM submissions
            WHERE status = 'pending'
              AND {scope_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT 50
        """, scope_params).fetchall()
        history = connection.execute(f"""
            SELECT guild_id, submission_id, action, actor_username,
                   details, created_at
            FROM moderation_history
            WHERE {scope_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT 50
        """, scope_params).fetchall()
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
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    config_data = load_config()
    return render_template_string(
        ONBOARDING_HTML,
        admin_key=ADMIN_KEY,
        invite_url=bot_invite_url(),
        servers=build_onboarding_rows(config_data),
        setup_templates=SETUP_TEMPLATE_ROWS,
    )


@app.route("/admin/owner-portal")
def admin_owner_portal():
    login_response = require_admin_login("moderator")
    if login_response:
        return login_response
    return render_template_string(
        OWNER_PORTAL_HTML,
        admin_key=ADMIN_KEY,
        servers=owner_portal_rows(),
    )


@app.route("/admin/seasons", methods=["GET", "POST"])
def admin_seasons():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    notice = request.args.get("notice", "")
    config_data = load_config()
    options = guild_options(config_data)
    valid_guild_ids = {option["id"] for option in options}
    actor_id, actor_name = web_actor()

    if request.method == "POST":
        require_csrf_token()
        action = request.form.get("action", "")
        if action == "create_season":
            guild_id = request.form.get("guild_id", "").strip()
            if guild_id not in valid_guild_ids:
                abort(400)
            name = request.form.get("name", "").strip()[:120]
            starts_at = request.form.get("starts_at", "").strip()
            ends_at = request.form.get("ends_at", "").strip()
            if not name or not starts_at or not ends_at:
                return redirect(url_for(
                    "admin_seasons",
                    key=ADMIN_KEY,
                    notice="Name, start date, and end date are required.",
                ))
            if len(starts_at) == 10:
                starts_at = starts_at + "T00:00:00+00:00"
            if len(ends_at) == 10:
                ends_at = ends_at + "T23:59:59+00:00"
            now = utc_now_iso()
            with database() as connection:
                cursor = connection.execute("""
                    INSERT INTO game_seasons (
                        guild_id, name, starts_at, ends_at, status,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, 'active', ?, ?)
                """, (guild_id, name, starts_at, ends_at, now, now))
                season_id = cursor.lastrowid
                add_admin_audit_log(
                    connection,
                    guild_id,
                    "dashboard_create_game_season",
                    actor_id,
                    actor_name,
                    "game_season",
                    season_id,
                    f"Created season {name}.",
                )
            return redirect(url_for(
                "admin_seasons",
                key=ADMIN_KEY,
                notice=f"Season {name} created.",
            ))

        if action == "close_season":
            season_id = int(request.form.get("season_id", "0") or 0)
            with database() as connection:
                season = connection.execute("""
                    SELECT *
                    FROM game_seasons
                    WHERE id = ?
                """, (season_id,)).fetchone()
                if not season:
                    abort(404)
                leaderboard = season_leaderboard(connection, season, limit=1)
                winner = leaderboard[0] if leaderboard else None
                connection.execute("""
                    UPDATE game_seasons
                    SET status = 'closed',
                        winner_user_id = ?,
                        winner_username = ?,
                        winner_points = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    winner["user_id"] if winner else "",
                    winner["username"] if winner else "",
                    int(winner["points"] or 0) if winner else 0,
                    utc_now_iso(),
                    season_id,
                ))
                add_admin_audit_log(
                    connection,
                    season["guild_id"],
                    "dashboard_close_game_season",
                    actor_id,
                    actor_name,
                    "game_season",
                    season_id,
                    "Closed season and archived winner.",
                )
            return redirect(url_for(
                "admin_seasons",
                key=ADMIN_KEY,
                notice="Season closed and winner archived.",
            ))

    guild_names = guild_name_map(config_data)
    allowed_season_ids = {option["id"] for option in options}
    with closing(connect_db()) as connection:
        where_sql = ""
        parameters = []
        if current_admin_role() != "owner":
            filter_sql, parameters = guild_id_filter("guild_id", allowed_season_ids)
            where_sql = "WHERE " + filter_sql
        rows = connection.execute(f"""
            SELECT *
            FROM game_seasons
            {where_sql}
            ORDER BY starts_at DESC, id DESC
            LIMIT 100
        """, parameters).fetchall()
        seasons = []
        for row in rows:
            season = dict(row)
            season["guild_name"] = guild_names.get(
                season.get("guild_id"),
                season.get("guild_id") or "Unknown",
            )
            season["leaderboard"] = season_leaderboard(connection, row, limit=10)
            seasons.append(season)

    return render_template_string(
        SEASONS_HTML,
        admin_key=ADMIN_KEY,
        csrf_token=get_csrf_token(),
        guild_options=options,
        notice=notice,
        seasons=seasons,
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
                        NULL AS media_hashes,
                        0 AS spam_score,
                        '[]' AS spam_reasons_json,
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
            elif selected_status in {"posted", "pending", "needs_review", "removed"}:
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


@app.route("/about")
def about():
    return render_template_string(
        ABOUT_HTML,
        invite_url=bot_invite_url(),
    )


@app.route("/setup-guide")
def setup_guide():
    return render_template_string(
        SETUP_GUIDE_HTML,
        invite_url=bot_invite_url(),
    )


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


@app.route("/my-submissions")
@app.route("/me")
def my_submissions():
    config_data = load_config()
    has_key = request.args.get("key") == ADMIN_KEY
    is_admin = has_key and is_admin_logged_in()
    if has_key and not is_admin:
        return redirect(url_for(
            "admin_login",
            key=ADMIN_KEY,
            next=request.full_path,
        ))

    search_query = (
        request.args.get("q", "").strip()
        or session.get("sdac_discord_user_id", "")
    )
    server_options = guild_options(config_data, public_only=not is_admin)
    guild_names = guild_name_map(config_data)
    selected_server_id = selected_guild_id(server_options)
    visible_guild_ids = {option["id"] for option in server_options}
    rows = []

    if search_query:
        where = []
        parameters = []
        if search_query.isdigit():
            where.append("user_id = ?")
            parameters.append(search_query)
        else:
            where.append("username LIKE ?")
            parameters.append(f"%{search_query}%")
        if not is_admin:
            where.append("status = 'posted'")
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

        with closing(connect_db()) as connection:
            rows = connection.execute(f"""
                SELECT id, guild_id, user_id, username, category, stars,
                       status, created_at, submitted_at
                FROM submissions
                WHERE {" AND ".join(where)}
                ORDER BY created_at DESC, id DESC
                LIMIT 100
            """, parameters).fetchall()

    return render_template_string(
        MY_SUBMISSIONS_HTML,
        admin_key=ADMIN_KEY,
        guild_names=guild_names,
        guild_options=server_options,
        is_admin=is_admin,
        rows=rows,
        search_query=search_query,
        selected_guild_id=selected_server_id,
    )


@app.route("/audit")
@app.route("/admin/audit")
def audit_log():
    login_response = require_admin_login()
    if login_response:
        return login_response

    page = positive_page(request.args.get("page"))
    config_data = load_config()
    server_options = guild_options(config_data)
    selected_server_id = selected_guild_id(server_options)
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


@app.route("/stats")
def public_stats():
    config_data = load_config()
    public_guilds = {
        option["id"]: option["name"]
        for option in guild_options(config_data, public_only=True)
        if (config_data.get("guilds") or {})
        .get(option["id"], {})
        .get("public_stats_enabled", True)
    }
    visible_ids = set(public_guilds)
    scope_sql, scope_params = guild_id_filter("guild_id", visible_ids)
    with closing(connect_db()) as connection:
        totals = {
            "Servers": len(public_guilds),
            "Submissions": connection.execute(
                f"SELECT COUNT(*) FROM submissions WHERE status = 'posted' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "Guess Points": connection.execute(
                f"SELECT COALESCE(SUM(points), 0) FROM guess_points WHERE {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "Active Games": connection.execute(
                f"SELECT COUNT(*) FROM guess_games WHERE status = 'active' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
        }
        servers_rows = []
        for guild_id, name in public_guilds.items():
            servers_rows.append({
                "id": guild_id,
                "name": name,
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
            })
        servers_rows.sort(
            key=lambda row: (row["submissions"], row["guess_points"]),
            reverse=True,
        )
        winners = connection.execute(f"""
            SELECT month, username, SUM(points) AS points
            FROM guess_points
            WHERE {scope_sql}
            GROUP BY month, user_id, username
            ORDER BY month DESC, points DESC, username ASC
            LIMIT 20
        """, scope_params).fetchall()
    return render_template_string(
        PUBLIC_STATS_HTML,
        servers=servers_rows[:10],
        totals=totals,
        winners=winners,
    )


@app.route("/api/stats")
def api_stats():
    config_data = load_config()
    public_guilds = {
        option["id"]: option["name"]
        for option in guild_options(config_data, public_only=True)
        if (config_data.get("guilds") or {})
        .get(option["id"], {})
        .get("public_stats_enabled", True)
    }
    scope_sql, scope_params = guild_id_filter("guild_id", set(public_guilds))
    with closing(connect_db()) as connection:
        payload = {
            "servers": len(public_guilds),
            "submissions": connection.execute(
                f"SELECT COUNT(*) FROM submissions WHERE status = 'posted' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "guess_points": connection.execute(
                f"SELECT COALESCE(SUM(points), 0) FROM guess_points WHERE {scope_sql}",
                scope_params,
            ).fetchone()[0],
            "active_games": connection.execute(
                f"SELECT COUNT(*) FROM guess_games WHERE status = 'active' AND {scope_sql}",
                scope_params,
            ).fetchone()[0],
        }
    return jsonify(payload)


@app.route("/api/servers")
def api_servers():
    config_data = load_config()
    rows = []
    with closing(connect_db()) as connection:
        for option in guild_options(config_data, public_only=True):
            guild_config = (config_data.get("guilds") or {}).get(option["id"], {})
            if not guild_config.get("public_stats_enabled", True):
                continue
            rows.append({
                "id": option["id"],
                "name": option["name"],
                "submissions": connection.execute("""
                    SELECT COUNT(*)
                    FROM submissions
                    WHERE guild_id = ? AND status = 'posted'
                """, (option["id"],)).fetchone()[0],
                "guess_points": connection.execute("""
                    SELECT COALESCE(SUM(points), 0)
                    FROM guess_points
                    WHERE guild_id = ?
                """, (option["id"],)).fetchone()[0],
            })
    return jsonify({"servers": rows})


@app.route("/api/leaderboard")
def api_leaderboard():
    config_data = load_config()
    visible_ids = {
        option["id"]
        for option in guild_options(config_data, public_only=True)
        if (config_data.get("guilds") or {})
        .get(option["id"], {})
        .get("public_stats_enabled", True)
    }
    month = request.args.get("month", current_month_key()).strip()
    if not re.match(r"^\d{4}-\d{2}$", month):
        month = current_month_key()
    scope_sql, scope_params = guild_id_filter("guild_id", visible_ids)
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT guild_id, user_id, username, SUM(points) AS points
            FROM guess_points
            WHERE {scope_sql}
              AND month = ?
            GROUP BY guild_id, user_id, username
            ORDER BY points DESC, username ASC
            LIMIT 25
        """, scope_params + [month]).fetchall()
    return jsonify({
        "month": month,
        "leaderboard": rows_as_dicts(rows),
    })


@app.route("/api/server/<guild_id>")
def api_server(guild_id):
    config_data = load_config()
    guild_config = (config_data.get("guilds") or {}).get(str(guild_id))
    if not guild_config or not feature_enabled(guild_config, "public_gallery"):
        abort(404)
    if not guild_config.get("public_stats_enabled", True):
        abort(404)
    with closing(connect_db()) as connection:
        recent = connection.execute("""
            SELECT id, username, category, stars, created_at
            FROM submissions
            WHERE guild_id = ?
              AND status = 'posted'
            ORDER BY created_at DESC, id DESC
            LIMIT 20
        """, (str(guild_id),)).fetchall()
        totals = {
            "submissions": connection.execute("""
                SELECT COUNT(*)
                FROM submissions
                WHERE guild_id = ? AND status = 'posted'
            """, (str(guild_id),)).fetchone()[0],
            "guess_points": connection.execute("""
                SELECT COALESCE(SUM(points), 0)
                FROM guess_points
                WHERE guild_id = ?
            """, (str(guild_id),)).fetchone()[0],
        }
    return jsonify({
        "id": str(guild_id),
        "name": (
            guild_config.get("brand_name")
            or guild_config.get("guild_name")
            or f"Discord {guild_id}"
        ),
        "totals": totals,
        "recent_submissions": rows_as_dicts(recent),
    })


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
        "dashboard_instance_id": DASHBOARD_INSTANCE_ID,
        "bot_heartbeat_fresh": bool(bot_status.get("fresh")),
    })


@app.route("/admin/health")
def admin_health():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    media_stats = media_directory_stats()
    config_data = load_config()
    setup_rows = build_onboarding_rows(config_data)
    production_health = production_health_report(config_data)
    bot_status = read_bot_status()
    maybe_notify_stale_bot(bot_status)
    with closing(connect_db()) as connection:
        schema_row = connection.execute("""
            SELECT version, updated_at
            FROM schema_version
            WHERE id = 1
        """).fetchone()
        payload = {
            "ok": True,
            "service": "sdac-dashboard",
            "dashboard_instance_id": DASHBOARD_INSTANCE_ID,
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
            "storage_forecast": [
                {
                    "guild_id": row["guild_id"],
                    "current": row["current"],
                    "limit": row["limit"],
                    "average": row["average"],
                    "forecast": row["forecast"],
                }
                for row in storage_forecast_rows(config_data)
            ],
            "release_status": release_status(),
            "production_health": {
                "score": production_health["score"],
                "max_score": production_health["max_score"],
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
    config_data = load_config()
    scope_sql, scope_params = admin_scope_filter("guild_id", config_data)
    where_sql = f"WHERE {scope_sql}" if scope_sql else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT id, guild_id, user_id, username, category, stars,
                   status, media_sizes, media_metadata_json,
                   created_at, submitted_at
            FROM submissions
            {where_sql}
            ORDER BY created_at DESC, id DESC
        """, scope_params).fetchall()
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
    config_data = load_config()
    scope_sql, scope_params = admin_scope_filter("guild_id", config_data)
    where_sql = f"WHERE {scope_sql}" if scope_sql else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
            SELECT guild_id, channel_id, user_id, username, month, points,
                   updated_at
            FROM guess_points
            {where_sql}
            ORDER BY month DESC, points DESC
        """, scope_params).fetchall()
    return csv_response(
        "sdac-guessing.csv",
        rows,
        ["guild_id", "channel_id", "user_id", "username", "month", "points", "updated_at"],
    )


@app.route("/export/monthly-report.csv")
def export_monthly_report():
    login_response = require_admin_login("admin")
    if login_response:
        return login_response

    config_data = load_config()
    options = guild_options(config_data)
    valid_ids = {option["id"] for option in options}
    requested_guild_id = request.args.get("guild_id", "").strip()
    guild_id = requested_guild_id if requested_guild_id in valid_ids else None
    month = request.args.get("month", current_month_key()).strip()
    report = monthly_report_data(month, guild_id)
    rows = []
    for label, value in report["totals"].items():
        rows.append({
            "section": "summary",
            "rank": "",
            "guild_id": guild_id or "all",
            "label": label,
            "user": "",
            "category": "",
            "value": value,
            "submission_id": "",
            "month": report["month"],
        })
    for rank, row in enumerate(report["top_submissions"], start=1):
        rows.append({
            "section": "top_submission",
            "rank": rank,
            "guild_id": row["guild_id"],
            "label": "votes",
            "user": row["username"],
            "category": row["category"] or "Uncategorized",
            "value": row["stars"],
            "submission_id": row["id"],
            "month": report["month"],
        })
    for rank, row in enumerate(report["top_guessers"], start=1):
        rows.append({
            "section": "top_guesser",
            "rank": rank,
            "guild_id": row["guild_id"],
            "label": "points",
            "user": row["username"],
            "category": "",
            "value": row["points"],
            "submission_id": "",
            "month": report["month"],
        })
    return csv_response(
        f"sdac-monthly-report-{report['month']}.csv",
        rows,
        [
            "section",
            "rank",
            "guild_id",
            "label",
            "user",
            "category",
            "value",
            "submission_id",
            "month",
        ],
    )


@app.route("/export/audit.csv")
def export_audit():
    login_response = require_admin_login()
    if login_response:
        return login_response
    config_data = load_config()
    scope_sql, scope_params = admin_scope_filter(
        "guild_id",
        config_data,
        include_global=True,
    )
    where_sql = f"WHERE {scope_sql}" if scope_sql else ""
    with closing(connect_db()) as connection:
        rows = connection.execute(f"""
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
            {where_sql}
            ORDER BY created_at DESC, sort_id DESC
        """, scope_params).fetchall()
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


@app.post("/admin/submission/<int:submission_id>/status")
def set_submission_status(submission_id):
    login_response = require_admin_login()
    if login_response:
        return login_response
    require_csrf_token()

    new_status = request.form.get("new_status", "").strip()
    if new_status not in {"posted", "needs_review"}:
        abort(400)

    selected_category = request.args.get("category", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_server_id = request.args.get("guild_id", "all").strip()
    page = positive_page(request.args.get("page"))
    redirect_values = {
        "key": ADMIN_KEY,
        "category": selected_category,
        "guild_id": selected_server_id or "all",
        "status": selected_status,
        "page": page,
    }

    actor_id, actor = web_actor()
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
        if not row:
            return redirect(url_for(
                "index",
                notice="Submission not found.",
                error=1,
                **redirect_values,
            ))
        connection.execute("""
            UPDATE submissions
            SET status = ?
            WHERE id = ?
        """, (new_status, submission_id))
        connection.execute("""
            INSERT INTO moderation_history (
                guild_id, submission_id, action, actor_user_id,
                actor_username, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["guild_id"],
            row["id"],
            "status",
            actor_id,
            actor,
            f"Set status to {new_status}",
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            row["guild_id"],
            "set_submission_status_dashboard",
            actor_id,
            actor,
            "submission",
            row["id"],
            f"Set status to {new_status}.",
        )
    PUBLIC_PAGE_CACHE.clear()
    return redirect(url_for(
        "index",
        notice=f"Submission marked {new_status}.",
        **redirect_values,
    ))


@app.post("/admin/submission/<int:submission_id>/quarantine")
def quarantine_submission(submission_id):
    login_response = require_admin_login("admin")
    if login_response:
        return login_response
    require_csrf_token()

    redirect_values = {
        "key": ADMIN_KEY,
        "category": request.args.get("category", "").strip(),
        "guild_id": request.args.get("guild_id", "all").strip() or "all",
        "status": request.args.get("status", "").strip(),
        "q": request.args.get("q", "").strip(),
        "page": positive_page(request.args.get("page")),
    }
    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT guild_id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if not row:
        return redirect(url_for(
            "index",
            notice="Submission not found.",
            error=1,
            **redirect_values,
        ))
    actor_id, actor_name = web_actor()
    reason = request.form.get("reason", "Manual dashboard quarantine")
    if two_admin_approval_enabled(load_config()):
        return approval_required_redirect(
            "quarantine_submission",
            "submission",
            submission_id,
            {"submission_id": submission_id, "reason": reason},
            actor_id,
            actor_name,
            guild_id=row["guild_id"],
            endpoint="admin_approvals",
        )
    ok, message = quarantine_submission_media(
        submission_id,
        reason,
        actor_id,
        actor_name,
    )
    return redirect(url_for(
        "index",
        notice=message,
        error=0 if ok else 1,
        **redirect_values,
    ))


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
    actor_id, actor = web_actor()
    if two_admin_approval_enabled(load_config()):
        return approval_required_redirect(
            "delete_submission",
            "submission",
            submission_id,
            {"submission_id": submission_id},
            actor_id,
            actor,
            guild_id=row["guild_id"],
            endpoint="index",
            route_values=redirect_values,
        )

    ok, message = remove_submission_from_dashboard(submission_id, actor_id, actor)
    return redirect(url_for(
        "index",
        notice=message,
        error=0 if ok else 1,
        **redirect_values,
    ))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
