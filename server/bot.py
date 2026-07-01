import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import traceback
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import TOKEN
from database_backend import connect_database, using_postgres
from database_migrations import DATABASE_SCHEMA_VERSION, apply_database_migrations
from observability import capture_exception, init_sentry


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = Path(os.getenv("SDAC_CONFIG_FILE", BASE_DIR / "config.json"))
DB_FILE = Path(os.getenv("SDAC_DB_FILE", BASE_DIR / "sdac.db"))
MEDIA_DIR = Path(os.getenv("SDAC_MEDIA_DIR", BASE_DIR / "media"))
BACKUP_DIR = Path(os.getenv("SDAC_BACKUP_DIR", BASE_DIR / "backups"))
BOT_STATUS_FILE = Path(os.getenv("SDAC_BOT_STATUS_FILE", BASE_DIR / "bot_status.json"))
ORIGINAL_REPO = os.getenv("SDAC_UPSTREAM_GITHUB_REPO", "BaytaeTistear/SDAC-Bot")
RELEASE_REPO = os.getenv("SDAC_GITHUB_REPO", ORIGINAL_REPO)
BOT_INSTANCE_ID = (
    os.getenv("SDAC_INSTANCE_ID")
    or f"{socket.gethostname()}:{hashlib.sha1(str(BASE_DIR).encode('utf-8')).hexdigest()[:8]}"
)
BACKUP_KEEP_COUNT = 30
SCHEMA_VERSION = DATABASE_SCHEMA_VERSION
OWNER_OVERRIDE_USERNAME = "baytae"

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".mov", ".webm", ".mkv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a",
}

USER_COOLDOWN_SECONDS = 30
CATEGORY_COOLDOWN_SECONDS = 5
PUBLIC_CACHE_SECONDS = 45
WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
WEEKDAY_CHOICES = [
    app_commands.Choice(name=name.title(), value=name)
    for name in WEEKDAY_NAMES
]

init_sentry("sdac-bot")

DEFAULT_CONFIG = {
    "guilds": {},
    "limits": {
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
    },
    "offsite_backup": {
        "provider": "",
        "remote": "",
        "last_success_at": "",
        "last_status": "",
        "last_details": "",
    },
}

DEFAULT_FEATURES = {
    "submissions": True,
    "approval_queue": True,
    "guessing_games": True,
    "weekly_posts": True,
    "public_gallery": True,
    "cross_server_leaderboard": True,
    "cross_server_gallery": True,
}

DEFAULT_GUILD_EXTERNAL_BACKUP = {
    "enabled": False,
    "provider": "rclone",
    "remote": "",
    "public_base_url": "",
    "include_media": True,
    "include_database_export": True,
    "zip_backups": True,
    "delete_local_media_after_success": False,
    "last_success_at": "",
    "last_status": "",
    "last_details": "",
    "last_archive_path": "",
}

DEFAULT_GUILD_CONFIG = {
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
    "notification_digest": {
        "enabled": False,
        "frequency": "weekly",
        "channel_id": None,
    },
    "categories": {},
    "features": DEFAULT_FEATURES,
}

FEATURE_LABELS = {
    "submissions": "Submissions",
    "approval_queue": "Approval Queue",
    "guessing_games": "Guessing Games",
    "weekly_posts": "Weekly Posts",
    "public_gallery": "Public Gallery",
    "cross_server_leaderboard": "Cross-Server Leaderboard",
    "cross_server_gallery": "Cross-Server Gallery Visibility",
}

FEATURE_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in FEATURE_LABELS.items()
]

LIMIT_LABELS = {
    "max_file_mb": "Max File MB",
    "max_total_mb": "Max Submission Total MB",
    "monthly_submissions": "Monthly Submissions",
    "active_games": "Active Games",
    "storage_mb": "Storage MB",
}

LIMIT_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in LIMIT_LABELS.items()
]

SETUP_PRESETS = {
    "simple": {
        "label": "Simple Gallery",
        "description": "Submissions, public gallery, weekly posts, and games.",
        "approval_enabled": False,
        "features": {
            "submissions": True,
            "approval_queue": False,
            "guessing_games": True,
            "weekly_posts": True,
            "public_gallery": True,
            "cross_server_leaderboard": True,
        },
    },
    "approval": {
        "label": "Approval Queue",
        "description": "Submissions with admin approval before public posting.",
        "approval_enabled": True,
        "features": {
            "submissions": True,
            "approval_queue": True,
            "guessing_games": True,
            "weekly_posts": True,
            "public_gallery": True,
            "cross_server_leaderboard": True,
        },
    },
    "game_only": {
        "label": "Guessing Games Only",
        "description": "Disable submissions and focus on media guessing games.",
        "approval_enabled": False,
        "features": {
            "submissions": False,
            "approval_queue": False,
            "guessing_games": True,
            "weekly_posts": False,
            "public_gallery": False,
            "cross_server_leaderboard": True,
        },
    },
}

REQUIRED_TABLES = {
    "submissions",
    "category_history",
    "moderation_history",
    "admin_audit_log",
    "admin_notifications",
    "background_jobs",
    "backup_integrity",
    "daily_runs",
    "dashboard_admin_users",
    "game_seasons",
    "guess_games",
    "guess_library_items",
    "guess_points",
    "guess_correct_guesses",
    "guess_answer_history",
    "guess_cooldowns",
    "monthly_guess_runs",
    "daily_guess_runs",
    "monthly_submission_top",
    "schema_version",
    "rate_limit_events",
    "restore_test_runs",
    "submission_reports",
    "setup_test_runs",
    "support_bundles",
    "content_moderation_events",
    "offsite_backup_runs",
    "privacy_actions",
    "media_fingerprints",
    "pending_admin_actions",
    "media_quarantine",
    "monthly_digest_runs",
    "scheduled_games",
    "user_streaks",
    "user_achievements",
    "backup_archives",
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

NOTIFICATION_EVENT_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in NOTIFICATION_EVENT_LABELS.items()
]

USER_COMMAND_HELP = [
    ("/commands", "Show the public SDAC command list."),
    ("/submit", "Start a guided media submission."),
    ("/categories", "Show configured categories and basic server setup."),
    ("/guess guess", "Guess the active game answer in the current channel."),
    ("/hint", "Show this channel's revealed game hint."),
]

USER_COMMAND_GROUPS = {
    "All User Commands": USER_COMMAND_HELP,
    "Submissions": [
        ("/submit", "Start a guided media submission."),
        ("/categories", "Show configured categories and basic server setup."),
    ],
    "Guessing Games": [
        ("/guess guess", "Guess the active game answer in the current channel."),
        ("/hint", "Show this channel's revealed game hint."),
    ],
}

ADMIN_COMMAND_HELP = [
    ("/admincommands", "Show this admin command list."),
    ("/setup", "Open the guided Discord setup wizard."),
    ("/setupstatus", "Show setup progress."),
    ("/setupchecklist", "Show the admin setup and production checklist."),
    ("/setuptest", "Run setup checks."),
    ("/diagnose", "Run setup and runtime diagnostics."),
    ("/repository", "Show the configured user/fork repo and original repo."),
    ("/settings", "Show SDAC bot settings."),
    ("/setsubmit #channel", "Set the submission channel."),
    ("/clearsubmit", "Clear the submission channel."),
    ("/setcategory category #channel", "Create or update a repost category."),
    ("/editcategory oldname newname #channel", "Rename or move a category."),
    ("/deletecategory category", "Delete a category."),
    ("/setfeature feature enabled", "Enable or disable a feature."),
    ("/checkpermissions", "Check bot permissions in configured channels."),
    ("/repairpermissions", "Show missing permissions and the repair invite."),
    ("/setbranding name accent logo_url", "Set dashboard branding."),
    ("/setapproval enabled #channel", "Configure approval-before-repost."),
    ("/setadminrole @role", "Allow a role to manage SDAC."),
    ("/removeadminrole @role", "Remove an SDAC admin role."),
    ("/setweeklychannel #channel", "Set weekly top channel."),
    ("/clearweeklychannel", "Clear weekly top channel."),
    ("/setweeklyday day", "Set weekly top posting day."),
    ("/setweeklytime hour minute", "Set weekly top posting time."),
    ("/settimezone timezone", "Set this server's timezone."),
    ("/setguesstimeout minutes", "Set wrong-guess cooldown."),
    ("/setgamesummarychannel #channel", "Set game summary channel."),
    ("/cleargamesummarychannel", "Use game channel for summaries."),
    ("/seterrorchannel #channel", "Set error notification channel."),
    ("/clearerrorchannel", "Clear error notification channel."),
    ("/setnotification event #channel enabled", "Route admin alerts."),
    ("/setlimit limit value", "Set a safety limit."),
    ("/setmoderation ...", "Set moderation controls."),
    ("/setgamesettings ...", "Set default guessing-game controls."),
    ("/setserverbackup ...", "Set per-server external backup target."),
    ("/serverbackupstatus", "Show this server's backup settings."),
    ("/backupguide provider", "Show setup steps for a backup provider."),
    ("/backupsetup provider remote ...", "Configure backups from Discord."),
    ("/backupnow upload", "Create a zip backup and optionally upload it."),
    ("/backupstatus", "Show backup settings and prerequisites."),
    ("/setdigest enabled frequency #channel", "Configure admin notification digest."),
    ("/supportbundle", "Create a small diagnostic bundle."),
    ("/sdacpanic paused reason", "Pause or resume SDAC activity."),
    ("/schedulegame #channel start_time ...", "Schedule a saved library game."),
    ("/scheduledgames", "List queued and running scheduled games."),
    ("/cancelscheduledgame id", "Cancel a queued scheduled game."),
    ("/reasonpresets", "Show standard admin action reasons."),
    ("/startgame #channel answer media text category hint auto_hint_minutes", "Start a guessing game."),
    ("/startlibrarygame #channel item_id category random_item", "Start a saved library game."),
    ("/activegame", "Show active game details including the answer."),
    ("/correct", "Reveal and close the active game."),
    ("/cancelgame", "Cancel the active game."),
    ("/sethint hint", "Reveal a manual hint."),
    ("/revealhint", "Reveal the next generated hint."),
    ("/removesubmission id reason_preset reason", "Remove a submission with an audit reason."),
    ("/submissioninfo id", "Show submission details."),
]

ADMIN_COMMAND_GROUPS = {
    "All Admin Commands": ADMIN_COMMAND_HELP,
    "Setup": [
        ("/setup", "Open the guided Discord setup wizard."),
        ("/setupstatus", "Show setup progress."),
        ("/setupchecklist", "Show the admin setup and production checklist."),
        ("/setuptest", "Run setup checks."),
        ("/diagnose", "Run setup and runtime diagnostics."),
        ("/repository", "Show the configured user/fork repo and original repo."),
        ("/settings", "Show SDAC bot settings."),
        ("/setfeature feature enabled", "Enable or disable a feature."),
    ],
    "Channels": [
        ("/setsubmit #channel", "Set the submission channel."),
        ("/clearsubmit", "Clear the submission channel."),
        ("/setcategory category #channel", "Create or update a repost category."),
        ("/editcategory oldname newname #channel", "Rename or move a category."),
        ("/deletecategory category", "Delete a category."),
        ("/setweeklychannel #channel", "Set weekly top channel."),
        ("/clearweeklychannel", "Clear weekly top channel."),
        ("/setgamesummarychannel #channel", "Set game summary channel."),
        ("/seterrorchannel #channel", "Set error notification channel."),
    ],
    "Permissions": [
        ("/checkpermissions", "Check bot permissions in configured channels."),
        ("/repairpermissions", "Show missing permissions and the repair invite."),
        ("/setadminrole @role", "Allow a role to manage SDAC."),
        ("/removeadminrole @role", "Remove an SDAC admin role."),
    ],
    "Games": [
        ("/startgame #channel answer media text category hint auto_hint_minutes", "Start a guessing game."),
        ("/startlibrarygame #channel item_id category random_item", "Start a saved library game."),
        ("/schedulegame #channel start_time ...", "Schedule a saved library game."),
        ("/scheduledgames", "List queued and running scheduled games."),
        ("/cancelscheduledgame id", "Cancel a queued scheduled game."),
        ("/activegame", "Show active game details including the answer."),
        ("/correct", "Reveal and close the active game."),
        ("/cancelgame", "Cancel the active game."),
        ("/sethint hint", "Reveal a manual hint."),
        ("/revealhint", "Reveal the next generated hint."),
        ("/setgamesettings ...", "Set default guessing-game controls."),
    ],
    "Moderation": [
        ("/setmoderation ...", "Set moderation controls."),
        ("/removesubmission id reason_preset reason", "Remove a submission with an audit reason."),
        ("/submissioninfo id", "Show submission details."),
        ("/reasonpresets", "Show standard admin action reasons."),
        ("/sdacpanic paused reason", "Pause or resume SDAC activity."),
    ],
    "Backups": [
        ("/backupguide provider", "Show setup steps for a backup provider."),
        ("/backupsetup provider remote ...", "Configure backups from Discord."),
        ("/backupnow upload", "Create a zip backup and optionally upload it."),
        ("/backupstatus", "Show backup settings and prerequisites."),
        ("/setserverbackup ...", "Set per-server external backup target."),
        ("/serverbackupstatus", "Show this server's backup settings."),
        ("/supportbundle", "Create a small diagnostic bundle."),
    ],
    "Notifications": [
        ("/setnotification event #channel enabled", "Route admin alerts."),
        ("/setdigest enabled frequency #channel", "Configure admin notification digest."),
        ("/setweeklyday day", "Set weekly top posting day."),
        ("/setweeklytime hour minute", "Set weekly top posting time."),
        ("/settimezone timezone", "Set this server's timezone."),
        ("/setbranding name accent logo_url", "Set dashboard branding."),
    ],
}

BACKUP_PROVIDER_GUIDES = {
    "google_drive": {
        "label": "Google Drive",
        "remote_hint": "drive:sdac-backups/server-name",
        "steps": "Run `rclone config`, choose Google Drive, then use the remote path from `/backupsetup`.",
    },
    "onedrive": {
        "label": "Microsoft OneDrive",
        "remote_hint": "onedrive:SDAC/server-name",
        "steps": "Run `rclone config`, choose OneDrive, sign in, then use the remote path from `/backupsetup`.",
    },
    "dropbox": {
        "label": "Dropbox",
        "remote_hint": "dropbox:sdac/server-name",
        "steps": "Run `rclone config`, choose Dropbox, sign in, then use the remote path from `/backupsetup`.",
    },
    "mega": {
        "label": "Mega",
        "remote_hint": "mega:sdac/server-name",
        "steps": "Run `rclone config`, choose Mega, enter the account credentials, then use the remote path.",
    },
    "s3": {
        "label": "Amazon S3 compatible",
        "remote_hint": "s3:bucket/sdac/server-name",
        "steps": "Run `rclone config`, choose S3, enter keys/region/bucket provider, then use the remote path.",
    },
    "b2": {
        "label": "Backblaze B2",
        "remote_hint": "b2:bucket/sdac/server-name",
        "steps": "Run `rclone config`, choose Backblaze B2, enter key ID/application key, then use the remote path.",
    },
    "box": {
        "label": "Box",
        "remote_hint": "box:SDAC/server-name",
        "steps": "Run `rclone config`, choose Box, sign in, then use the remote path from `/backupsetup`.",
    },
    "sftp": {
        "label": "SFTP / another VPS",
        "remote_hint": "sftp:sdac/server-name",
        "steps": "Run `rclone config`, choose SFTP, enter SSH host/user/key settings, then use the remote path.",
    },
}

BACKUP_PROVIDER_CHOICES = [
    app_commands.Choice(name=guide["label"], value=key)
    for key, guide in BACKUP_PROVIDER_GUIDES.items()
]

MODERATION_REASON_PRESETS = {
    "spam": "Spam or automated abuse",
    "wrong_category": "Wrong category",
    "duplicate": "Duplicate submission",
    "unsafe_media": "Unsafe or disallowed media",
    "user_request": "Removed by user request",
    "copyright": "Copyright or ownership concern",
    "other": "Other admin decision",
}

REASON_PRESET_CHOICES = [
    app_commands.Choice(name=label, value=key)
    for key, label in MODERATION_REASON_PRESETS.items()
]


def command_help_chunks(title, commands, intro=""):
    lines = [f"**{title}**"]
    if intro:
        lines.append(intro)
    for command, description in commands:
        lines.append(f"- `{command}` - {description}")
    chunks = []
    current = ""
    for line in lines:
        next_value = f"{current}\n{line}" if current else line
        if len(next_value) > 1900 and current:
            chunks.append(current)
            current = line
        else:
            current = next_value
    if current:
        chunks.append(current)
    return chunks


async def send_command_help(interaction, title, commands, intro=""):
    chunks = command_help_chunks(title, commands, intro)
    if not chunks:
        chunks = [f"**{title}**\nNo commands are listed."]
    await interaction.response.send_message(chunks[0], ephemeral=True)
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)


class CommandHelpSelect(discord.ui.Select):
    def __init__(self, groups):
        self.groups = groups
        options = [
            discord.SelectOption(label=label[:100], value=label)
            for label in groups
        ]
        super().__init__(
            placeholder="Choose a command category",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction):
        label = self.values[0]
        commands = self.groups.get(label, [])
        chunks = command_help_chunks(label, commands)
        await interaction.response.edit_message(content=chunks[0], view=self.view)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)


class CommandHelpView(discord.ui.View):
    def __init__(self, groups):
        super().__init__(timeout=300)
        self.add_item(CommandHelpSelect(groups))


async def send_command_help_menu(interaction, title, groups, intro=""):
    first_label = next(iter(groups))
    chunks = command_help_chunks(title, groups[first_label], intro)
    await interaction.response.send_message(
        chunks[0],
        view=CommandHelpView(groups),
        ephemeral=True,
    )
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk, ephemeral=True)


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


def cleanup_old_config_backups():
    if not BACKUP_DIR.exists():
        return
    backups = sorted(
        BACKUP_DIR.glob("config-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for backup_path in backups[BACKUP_KEEP_COUNT:]:
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


def load_config():
    if not CONFIG_FILE.exists():
        data = json.loads(json.dumps(DEFAULT_CONFIG))
        save_config(data)
        return data

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    changed = False
    if "guilds" not in data:
        legacy_config = {
            "submit_channel": data.get("submit_channel"),
            "daily_top_channel": data.get("daily_top_channel"),
            "daily_top_time_utc": data.get(
                "daily_top_time_utc",
                "00:00",
            ),
            "guild_name": data.get("guild_name", ""),
            "admin_role_ids": data.get("admin_role_ids") or [],
            "weekly_top_day": data.get("weekly_top_day", "sunday"),
            "game_summary_channel": data.get("game_summary_channel"),
            "error_channel": data.get("error_channel"),
            "approval_enabled": data.get("approval_enabled", False),
            "approval_channel": data.get("approval_channel"),
            "categories": data.get("categories") or {},
        }
        if any([
            legacy_config["submit_channel"],
            legacy_config["daily_top_channel"],
            legacy_config["approval_channel"],
            legacy_config["categories"],
        ]):
            data["legacy_guild_config"] = legacy_config
        data["guilds"] = {}
        changed = True
    if "limits" not in data:
        data["limits"] = dict(DEFAULT_CONFIG["limits"])
        changed = True
    if "offsite_backup" not in data:
        data["offsite_backup"] = dict(DEFAULT_CONFIG["offsite_backup"])
        changed = True

    for key, value in DEFAULT_CONFIG["limits"].items():
        if key not in data["limits"]:
            data["limits"][key] = value
            changed = True
    if fill_nested_defaults(
        data.setdefault("offsite_backup", {}),
        DEFAULT_CONFIG["offsite_backup"],
    ):
        changed = True

    if changed:
        save_config(data)
    return data


config = load_config()


def migrate_legacy_config():
    legacy_config = config.get("legacy_guild_config")
    if not legacy_config:
        return
    if len(bot.guilds) != 1:
        print(
            "Legacy configuration needs exactly one connected guild "
            "before it can be migrated."
        )
        return

    guild = bot.guilds[0]
    guild_config = get_guild_config(guild.id)
    guild_config.update(legacy_config)
    config.pop("legacy_guild_config", None)
    for key in (
        "guild_name",
        "admin_role_ids",
        "submit_channel",
        "daily_top_channel",
        "daily_top_time_utc",
        "weekly_top_day",
        "game_summary_channel",
        "error_channel",
        "timezone",
        "approval_enabled",
        "approval_channel",
        "categories",
    ):
        config.pop(key, None)
    save_config(config)

    with database() as connection:
        connection.execute("""
            UPDATE submissions
            SET guild_id = ?
            WHERE guild_id IS NULL OR guild_id = ''
        """, (str(guild.id),))
        connection.execute("""
            UPDATE category_history
            SET guild_id = ?
            WHERE guild_id IS NULL OR guild_id = ''
        """, (str(guild.id),))
    print(f"Migrated legacy configuration to guild {guild.id}.")


def get_guild_config(guild_id, create=True):
    if guild_id is None:
        return None

    guilds = config.setdefault("guilds", {})
    key = str(guild_id)
    if key not in guilds:
        if not create:
            return dict(DEFAULT_GUILD_CONFIG)
        guilds[key] = json.loads(json.dumps(DEFAULT_GUILD_CONFIG))
        save_config(config)

    guild_config = guilds[key]
    changed = False
    for setting, default in DEFAULT_GUILD_CONFIG.items():
        if setting not in guild_config:
            guild_config[setting] = json.loads(json.dumps(default))
            changed = True
        elif isinstance(default, dict) and isinstance(guild_config.get(setting), dict):
            if fill_nested_defaults(guild_config[setting], default):
                changed = True
    features = guild_config.setdefault("features", {})
    for feature, default in DEFAULT_FEATURES.items():
        if feature not in features:
            features[feature] = default
            changed = True
    if changed:
        save_config(config)
    return guild_config


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


def active_user_restriction(connection, guild_id, user_id, scope):
    lock_column = "lock_games" if scope == "games" else "lock_submissions"
    return connection.execute(f"""
        SELECT *
        FROM user_restrictions
        WHERE active = 1
          AND user_id = ?
          AND (guild_id = '' OR guild_id = ?)
          AND {lock_column} = 1
        ORDER BY CASE WHEN guild_id = ? THEN 0 ELSE 1 END, updated_at DESC
        LIMIT 1
    """, (str(user_id), str(guild_id), str(guild_id))).fetchone()


def user_lockout_message(row, scope):
    label = "guessing games" if scope == "games" else "submissions"
    reason = (row["reason"] or "").strip() if row else ""
    if reason:
        return f"You are locked out of SDAC {label}: {reason}"
    return f"You are locked out of SDAC {label}."


def ensure_column(connection, table, column, definition):
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


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
            CREATE TABLE IF NOT EXISTS category_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                category TEXT,
                channel_id TEXT,
                admin_user_id TEXT,
                admin_username TEXT,
                created_at TEXT
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
                email TEXT,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'moderator',
                disabled INTEGER DEFAULT 0,
                email_verified INTEGER DEFAULT 0,
                discord_user_id TEXT,
                created_ip TEXT,
                approved_by TEXT,
                approved_at TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_login_at TEXT,
                guild_ids_json TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_user_server_access (
                username TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                source TEXT DEFAULT 'manual',
                verified_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (username, guild_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_bot_owners (
                username TEXT PRIMARY KEY,
                source TEXT DEFAULT 'manual',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT DEFAULT '',
                user_id TEXT NOT NULL,
                username TEXT,
                lock_games INTEGER DEFAULT 0,
                lock_submissions INTEGER DEFAULT 0,
                reason TEXT,
                active INTEGER DEFAULT 1,
                created_by TEXT,
                created_by_name TEXT,
                created_at TEXT,
                updated_at TEXT
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
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                message_id TEXT,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_by_name TEXT,
                created_at TEXT,
                closes_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS poll_votes (
                poll_id INTEGER,
                user_id TEXT,
                username TEXT,
                option_index INTEGER,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (poll_id, user_id)
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
            CREATE TABLE IF NOT EXISTS daily_runs (
                guild_id TEXT,
                run_date TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, run_date)
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
                tags_json TEXT,
                pack_name TEXT,
                enabled INTEGER DEFAULT 1,
                notes TEXT,
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
            CREATE TABLE IF NOT EXISTS scheduled_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                library_item_id INTEGER DEFAULT 0,
                category TEXT,
                random_item INTEGER DEFAULT 0,
                starts_at TEXT,
                close_after_minutes INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                game_id INTEGER,
                created_by TEXT,
                created_by_name TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_error TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_streaks (
                guild_id TEXT,
                user_id TEXT,
                username TEXT,
                current_guess_streak INTEGER DEFAULT 0,
                best_guess_streak INTEGER DEFAULT 0,
                last_correct_game_id INTEGER,
                updated_at TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                user_id TEXT,
                username TEXT,
                achievement_key TEXT,
                label TEXT,
                details TEXT,
                month TEXT,
                awarded_at TEXT,
                UNIQUE (guild_id, user_id, achievement_key, month)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS backup_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                archive_type TEXT,
                file_path TEXT,
                size_bytes INTEGER DEFAULT 0,
                sha256 TEXT,
                destination TEXT,
                status TEXT DEFAULT 'created',
                details TEXT,
                created_by TEXT,
                created_by_name TEXT,
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

        submission_columns = {
            "guild_id": "TEXT",
            "original_message_id": "TEXT",
            "repost_message_id": "TEXT",
            "repost_channel_id": "TEXT",
            "approval_message_id": "TEXT",
            "approval_channel_id": "TEXT",
            "user_id": "TEXT",
            "username": "TEXT",
            "category": "TEXT",
            "message_text": "TEXT",
            "file_paths": "TEXT",
            "media_paths": "TEXT",
            "media_names": "TEXT",
            "media_types": "TEXT",
            "media_sizes": "TEXT",
            "media_metadata_json": "TEXT",
            "media_hashes": "TEXT",
            "spam_score": "INTEGER DEFAULT 0",
            "spam_reasons_json": "TEXT",
            "stars": "INTEGER DEFAULT 0",
            "voters": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'posted'",
            "submitted_at": "TEXT",
            "created_at": "TEXT",
            "approved_at": "TEXT",
            "daily_posted_at": "TEXT",
        }
        for column, definition in submission_columns.items():
            ensure_column(
                connection, "submissions", column, definition
            )

        for column, definition in {
            "guild_id": "TEXT",
            "action": "TEXT",
            "category": "TEXT",
            "channel_id": "TEXT",
            "admin_user_id": "TEXT",
            "admin_username": "TEXT",
            "created_at": "TEXT",
        }.items():
            ensure_column(
                connection, "category_history", column, definition
            )

        for column, definition in {
            "guild_id": "TEXT",
            "channel_id": "TEXT",
            "message_id": "TEXT",
            "starter_user_id": "TEXT",
            "starter_username": "TEXT",
            "answer": "TEXT",
            "answer_display": "TEXT",
            "prompt_text": "TEXT",
            "media_path": "TEXT",
            "media_name": "TEXT",
            "media_type": "TEXT",
            "media_size": "INTEGER DEFAULT 0",
            "media_metadata_json": "TEXT",
            "hint_text": "TEXT",
            "hint_revealed_at": "TEXT",
            "answer_aliases_json": "TEXT",
            "hints_json": "TEXT",
            "hint_level": "INTEGER DEFAULT 0",
            "next_hint_at": "TEXT",
            "auto_hint_minutes": "INTEGER DEFAULT 0",
            "hint_category": "TEXT",
            "library_item_id": "INTEGER",
            "status": "TEXT DEFAULT 'active'",
            "winner_user_id": "TEXT",
            "winner_username": "TEXT",
            "started_at": "TEXT",
            "solved_at": "TEXT",
        }.items():
            ensure_column(
                connection, "guess_games", column, definition
            )

        for column, definition in {
            "tags_json": "TEXT",
            "pack_name": "TEXT",
            "enabled": "INTEGER DEFAULT 1",
            "notes": "TEXT",
        }.items():
            ensure_column(
                connection, "guess_library_items", column, definition
            )

        ensure_column(
            connection,
            "dashboard_admin_users",
            "guild_ids_json",
            "TEXT",
        )
        for column, definition in {
            "email": "TEXT",
            "display_name": "TEXT",
            "email_verified": "INTEGER DEFAULT 0",
            "discord_user_id": "TEXT",
            "created_ip": "TEXT",
            "approved_by": "TEXT",
            "approved_at": "TEXT",
            "notes": "TEXT",
        }.items():
            ensure_column(
                connection,
                "dashboard_admin_users",
                column,
                definition,
            )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT DEFAULT '',
                user_id TEXT NOT NULL,
                username TEXT,
                lock_games INTEGER DEFAULT 0,
                lock_submissions INTEGER DEFAULT 0,
                reason TEXT,
                active INTEGER DEFAULT 1,
                created_by TEXT,
                created_by_name TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        connection.execute("""
            UPDATE submissions
            SET status = 'posted'
            WHERE status IS NULL OR status = ''
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_guild_category
            ON submissions (guild_id, category, status)
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
            CREATE INDEX IF NOT EXISTS idx_submissions_repost
            ON submissions (repost_message_id)
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
            CREATE INDEX IF NOT EXISTS idx_scheduled_games_due
            ON scheduled_games (status, starts_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_games_guild_status
            ON scheduled_games (guild_id, status, starts_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_streaks_best
            ON user_streaks (guild_id, best_guess_streak)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_achievements_user
            ON user_achievements (guild_id, user_id, awarded_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_achievements_key
            ON user_achievements (guild_id, achievement_key, month)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_backup_archives_created
            ON backup_archives (guild_id, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_backup_archives_status
            ON backup_archives (status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_games_active
            ON guess_games (guild_id, channel_id, status)
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
            CREATE INDEX IF NOT EXISTS idx_guess_points_month
            ON guess_points (guild_id, channel_id, month, points)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_points_global_month
            ON guess_points (month, user_id, points)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_guess_cooldowns_timeout
            ON guess_cooldowns (timeout_until)
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
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_role
            ON dashboard_admin_users (role, disabled)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_email
            ON dashboard_admin_users (email, disabled)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_admin_users_discord_id
            ON dashboard_admin_users (discord_user_id, disabled)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_dashboard_user_server_access_guild
            ON dashboard_user_server_access (guild_id, role)
        """)
        now = datetime.now(timezone.utc).isoformat()
        connection.execute("""
            INSERT OR IGNORE INTO dashboard_bot_owners (
                username, source, created_at, updated_at
            )
            VALUES (?, 'bootstrap', ?, ?)
        """, (OWNER_OVERRIDE_USERNAME, now, now))
        connection.execute("""
            INSERT OR IGNORE INTO dashboard_user_server_access (
                username, guild_id, role, source, verified_at, updated_at
            )
            SELECT users.username, json_each.value,
                   CASE WHEN users.username = ? THEN 'bot_owner' ELSE users.role END,
                   'legacy', users.updated_at, users.updated_at
            FROM dashboard_admin_users AS users, json_each(COALESCE(NULLIF(users.guild_ids_json, ''), '[]'))
            WHERE json_valid(COALESCE(NULLIF(users.guild_ids_json, ''), '[]'))
        """, (OWNER_OVERRIDE_USERNAME,))
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_restrictions_guild_user
            ON user_restrictions (guild_id, user_id)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_restrictions_active_scope
            ON user_restrictions (active, guild_id, user_id)
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
            CREATE INDEX IF NOT EXISTS idx_polls_guild_status
            ON polls (guild_id, status, created_at)
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_poll_votes_poll
            ON poll_votes (poll_id, option_index)
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
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def ensure_directory_writable(path):
    path.mkdir(parents=True, exist_ok=True)
    probe_path = path / ".sdac-write-test"
    probe_path.write_text("ok", encoding="utf-8")
    try:
        probe_path.unlink()
    except OSError:
        pass


def startup_health_check():
    issues = []

    if not TOKEN:
        issues.append("DISCORD_TOKEN is missing.")
    if not CONFIG_FILE.is_file():
        issues.append(f"{CONFIG_FILE} is missing.")

    for directory in (MEDIA_DIR, BACKUP_DIR):
        try:
            ensure_directory_writable(directory)
        except OSError as error:
            issues.append(f"{directory} is not writable: {error}")

    try:
        with database() as connection:
            table_names = {
                row["name"]
                for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
            }
            missing_tables = sorted(REQUIRED_TABLES - table_names)
            if missing_tables:
                issues.append(
                    "Database is missing tables: "
                    + ", ".join(missing_tables)
                )
            version_row = connection.execute("""
                SELECT version
                FROM schema_version
                WHERE id = 1
            """).fetchone()
            if not version_row or version_row["version"] < SCHEMA_VERSION:
                issues.append(
                    f"Database schema version is below {SCHEMA_VERSION}."
                )
    except sqlite3.Error as error:
        issues.append(f"Database check failed: {error}")

    if issues:
        raise RuntimeError(
            "Startup health check failed: " + " ".join(issues)
        )

    print(
        "Startup health check passed: "
        f"schema v{SCHEMA_VERSION}, database={DB_FILE}, media={MEDIA_DIR}",
        flush=True,
    )


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_now_display():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def clean_category_name(category):
    return category.lower().strip().replace(" ", "")


def normalize_guess(value):
    cleaned = re.sub(r"[^\w\s]", " ", value.casefold())
    cleaned = re.sub(r"[_\s]+", " ", cleaned)
    return cleaned.strip()


def feature_enabled(guild_config, feature):
    features = (guild_config or {}).get("features") or {}
    return bool(features.get(feature, DEFAULT_FEATURES.get(feature, True)))


def emergency_pause_message(guild_config):
    if not (guild_config or {}).get("emergency_paused"):
        return ""
    reason = (guild_config or {}).get("emergency_reason") or "No reason provided."
    return f"SDAC is paused for this server. Reason: {reason}"


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


def record_guess_answer_history(
    connection,
    guild_id,
    channel_id,
    game_id,
    library_item_id,
    normalized_answer,
    answer_display,
    category,
    source,
    started_by,
):
    connection.execute("""
        INSERT INTO guess_answer_history (
            guild_id, channel_id, game_id, library_item_id, answer,
            answer_display, category, source, started_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(guild_id),
        str(channel_id),
        game_id,
        library_item_id,
        normalized_answer,
        answer_display,
        category or "",
        source,
        str(started_by),
        utc_now_iso(),
    ))


def answer_alias_matches(game, normalized_guess):
    aliases = []
    try:
        aliases = json.loads(game["answer_aliases_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        aliases = []
    valid_answers = {
        alias.get("normalized", "")
        for alias in aliases
        if alias.get("normalized")
    }
    if game["answer"]:
        valid_answers.add(game["answer"])
    return normalized_guess in valid_answers


def answer_words(answer):
    return re.findall(r"[\w]+", answer or "")


def first_answer_letter(answer):
    for character in answer or "":
        if character.isalnum():
            return character.upper()
    return "?"


def build_game_hints(answer, category="", custom_hint=""):
    hints = []
    category = (category or "").strip()
    if category:
        hints.append(f"Category: {category}")
    words = answer_words(answer)
    if words:
        hints.append(f"Word count: {len(words)}")
    hints.append(f"First letter: {first_answer_letter(answer)}")
    custom_hint = (custom_hint or "").strip()
    if custom_hint:
        hints.append(f"Admin hint: {custom_hint}")

    deduped = []
    seen = set()
    for hint in hints:
        key = hint.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hint)
    return deduped


def next_hint_time(minutes):
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        minutes = 0
    if minutes <= 0:
        return None
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def append_hint_text(existing_text, hint):
    existing_text = (existing_text or "").strip()
    if not existing_text:
        return hint
    return existing_text + "\n" + hint


def reveal_next_hint_for_game(connection, game):
    try:
        hints = json.loads(game["hints_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        hints = []
    hint_level = int(game["hint_level"] or 0)
    if hint_level >= len(hints):
        return None

    hint = str(hints[hint_level]).strip()
    if not hint:
        return None

    new_level = hint_level + 1
    auto_minutes = int(game["auto_hint_minutes"] or 0)
    next_at = None
    if auto_minutes > 0 and new_level < len(hints):
        next_at = (
            datetime.now(timezone.utc) + timedelta(minutes=auto_minutes)
        ).isoformat()

    connection.execute("""
        UPDATE guess_games
        SET hint_text = ?,
            hint_revealed_at = COALESCE(hint_revealed_at, ?),
            hint_level = ?,
            next_hint_at = ?
        WHERE id = ?
    """, (
        append_hint_text(game["hint_text"], hint),
        utc_now_iso(),
        new_level,
        next_at,
        game["id"],
    ))
    return hint


def get_guild_timezone(guild_config):
    timezone_name = (
        (guild_config or {}).get("timezone")
        or DEFAULT_GUILD_CONFIG["timezone"]
    )
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_GUILD_CONFIG["timezone"])


def guild_now(guild_config):
    return datetime.now(get_guild_timezone(guild_config))


def parse_database_datetime(value):
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def current_month_key(guild_config=None):
    return guild_now(guild_config).strftime("%Y-%m")


def previous_month_key(now=None):
    now = now or datetime.now(timezone.utc)
    first_of_month = now.replace(day=1)
    previous_month = first_of_month - timedelta(days=1)
    return previous_month.strftime("%Y-%m")


def normalize_weekday(value):
    value = (value or "").casefold().strip()
    if value in WEEKDAY_NAMES:
        return value
    return None


def weekly_top_day_index(guild_config):
    day = normalize_weekday(guild_config.get("weekly_top_day"))
    if day is None:
        day = DEFAULT_GUILD_CONFIG["weekly_top_day"]
    return WEEKDAY_NAMES.index(day)


def weekly_run_key(now):
    return f"weekly:{now.strftime('%G-W%V')}"


def safe_backup_label(label):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "backup"


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


def latest_database_backup():
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(
        BACKUP_DIR.glob("sdac-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


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


def restore_test_has_run(run_key):
    with database() as connection:
        row = connection.execute("""
            SELECT 1
            FROM restore_test_runs
            WHERE run_key = ?
            LIMIT 1
        """, (run_key,)).fetchone()
    return row is not None


def run_restore_test(run_key):
    backup_path = latest_database_backup()
    passed, details = validate_database_backup(backup_path)
    status = "passed" if passed else "failed"
    record_restore_test_run(run_key, backup_path, status, details)
    return passed, backup_path, details


def create_daily_database_backup():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        backup_path, created, message = create_database_backup(f"daily-{today}")
    except (OSError, sqlite3.Error) as error:
        print(f"Daily database backup failed: {error}", flush=True)
        return None, False, str(error)
    if created:
        with database() as connection:
            add_admin_audit_log(
                connection,
                None,
                "database_backup_daily",
                "system",
                "system",
                "backup",
                backup_path.name,
                message,
            )
    return backup_path, created, message


BACKUP_EXPORT_TABLES = (
    "submissions",
    "monthly_submission_top",
    "category_history",
    "moderation_history",
    "admin_audit_log",
    "admin_notifications",
    "game_seasons",
    "guess_games",
    "guess_library_items",
    "guess_answer_history",
    "guess_points",
    "guess_correct_guesses",
    "guess_cooldowns",
    "monthly_guess_runs",
    "daily_guess_runs",
    "rate_limit_events",
    "submission_reports",
    "setup_test_runs",
    "support_bundles",
    "content_moderation_events",
    "privacy_actions",
    "scheduled_games",
    "user_streaks",
    "user_achievements",
    "backup_archives",
)


def table_has_column(connection, table_name, column_name):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        return False
    return column_name in {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def rows_for_guild_export(connection, table_name, guild_id):
    if not table_has_column(connection, table_name, "guild_id"):
        return []
    columns = [
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    ]
    order_column = "id" if "id" in columns else columns[0]
    rows = connection.execute(
        f'SELECT * FROM "{table_name}" WHERE guild_id = ? ORDER BY "{order_column}"',
        (str(guild_id),),
    ).fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def create_guild_backup_archive(guild_id, actor_id="", actor_name=""):
    guild_id = str(guild_id)
    guild_config = get_guild_config(guild_id, create=False)
    backup = {
        **DEFAULT_GUILD_EXTERNAL_BACKUP,
        **(guild_config.get("external_backup") or {}),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_dir = BACKUP_DIR / "archives" / guild_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"sdac-guild-{guild_id}-{stamp}.zip"
    manifest = {
        "guild_id": guild_id,
        "guild_name": guild_config.get("guild_name", ""),
        "created_at": utc_now_iso(),
        "created_by": str(actor_id or ""),
        "created_by_name": str(actor_name or ""),
        "include_media": bool(backup.get("include_media", True)),
        "include_database_export": bool(
            backup.get("include_database_export", True)
        ),
        "tables": {},
        "media_files": 0,
    }
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        archive.writestr(
            "guild-config.json",
            json.dumps({
                "format": "sdac-guild-config-v1",
                "guild_id": guild_id,
                "guild_config": guild_config,
            }, indent=2) + "\n",
        )
        if backup.get("include_database_export", True):
            export = {}
            with database() as connection:
                for table_name in BACKUP_EXPORT_TABLES:
                    rows = rows_for_guild_export(connection, table_name, guild_id)
                    if rows:
                        export[table_name] = rows
                        manifest["tables"][table_name] = len(rows)
            archive.writestr(
                "database-guild-export.json",
                json.dumps(export, indent=2, default=str) + "\n",
            )
        if backup.get("include_media", True):
            media_root = MEDIA_DIR.resolve()
            guild_media_dir = (media_root / guild_id).resolve()
            try:
                guild_media_dir.relative_to(media_root)
            except ValueError:
                guild_media_dir = media_root / "__invalid__"
            if guild_media_dir.is_dir():
                for media_path in guild_media_dir.rglob("*"):
                    if not media_path.is_file():
                        continue
                    try:
                        relative = media_path.resolve().relative_to(media_root)
                    except (OSError, ValueError):
                        continue
                    archive.write(media_path, f"media/{relative.as_posix()}")
                    manifest["media_files"] += 1
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")

    sha256 = file_sha256(archive_path)
    size_bytes = archive_path.stat().st_size
    with database() as connection:
        cursor = connection.execute("""
            INSERT INTO backup_archives (
                guild_id, archive_type, file_path, size_bytes, sha256,
                destination, status, details, created_by, created_by_name,
                created_at
            )
            VALUES (?, 'guild_zip', ?, ?, ?, ?, 'created', ?, ?, ?, ?)
        """, (
            guild_id,
            str(archive_path),
            int(size_bytes),
            sha256,
            backup.get("remote") or "",
            f"Created zip archive with {manifest['media_files']} media file(s).",
            str(actor_id or ""),
            str(actor_name or ""),
            utc_now_iso(),
        ))
        archive_id = cursor.lastrowid
    return {
        "id": archive_id,
        "path": archive_path,
        "sha256": sha256,
        "size": size_bytes,
        "manifest": manifest,
    }


async def upload_archive_with_rclone(archive_info, remote):
    remote = (remote or "").strip().rstrip("/")
    if not remote:
        return False, "No rclone remote is configured."
    if shutil.which("rclone") is None:
        return False, (
            "rclone is not installed. Run "
            "`sudo bash scripts/install_backup_prereqs.sh` on the server."
        )
    archive_path = Path(archive_info["path"])
    destination = f"{remote}/archives"
    process = await asyncio.create_subprocess_exec(
        "rclone",
        "copy",
        str(archive_path),
        destination,
        "--transfers",
        os.getenv("SDAC_RCLONE_TRANSFERS", "4"),
        "--checkers",
        os.getenv("SDAC_RCLONE_CHECKERS", "8"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = (stderr or stdout or b"").decode("utf-8", errors="replace").strip()
    guild_id = str(archive_info["manifest"]["guild_id"])
    status = "uploaded" if process.returncode == 0 else "failed"
    details = (
        f"Uploaded archive to {destination}."
        if process.returncode == 0
        else f"rclone failed: {output[-500:]}"
    )
    with database() as connection:
        connection.execute("""
            UPDATE backup_archives
            SET status = ?, destination = ?, details = ?
            WHERE id = ?
        """, (status, destination, details, archive_info["id"]))
        connection.execute("""
            INSERT INTO offsite_backup_runs (
                provider, destination, status, details, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            "rclone",
            f"guild:{guild_id}:{destination}",
            "success" if process.returncode == 0 else "failed",
            details,
            utc_now_iso(),
        ))
    return process.returncode == 0, details


def referenced_media_paths(connection):
    paths = set()
    for row in connection.execute("""
        SELECT media_paths, file_paths
        FROM submissions
    """):
        for value in split_values(row["media_paths"] or row["file_paths"]):
            try:
                paths.add(Path(value).resolve())
            except OSError:
                pass
    for row in connection.execute("""
        SELECT media_path
        FROM guess_games
        WHERE media_path IS NOT NULL AND media_path != ''
    """):
        try:
            paths.add(Path(row["media_path"]).resolve())
        except OSError:
            pass
    for row in connection.execute("""
        SELECT media_path
        FROM guess_library_items
        WHERE media_path IS NOT NULL AND media_path != ''
    """):
        try:
            paths.add(Path(row["media_path"]).resolve())
        except OSError:
            pass
    return paths


def cleanup_orphaned_media(connection):
    if not config["limits"].get("orphan_media_cleanup_enabled", True):
        return 0
    if not MEDIA_DIR.exists():
        return 0
    media_root = MEDIA_DIR.resolve()
    referenced = referenced_media_paths(connection)
    removed = 0
    for file_path in media_root.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            resolved = file_path.resolve()
            resolved.relative_to(media_root)
        except (OSError, ValueError):
            continue
        if resolved in referenced:
            continue
        try:
            resolved.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def guild_backup_safe_for_pruning(guild_config):
    backup = guild_config.get("external_backup") or {}
    return bool(
        backup.get("enabled")
        and backup.get("remote")
        and backup.get("public_base_url")
        and backup.get("last_status") == "success"
        and backup.get("last_success_at")
    )


def delete_original_files_keep_thumbnails(paths):
    removed = 0
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
                removed += 1
            except OSError:
                pass
    return removed


def cleanup_old_local_originals(connection):
    retention_days = configured_limit("local_original_retention_days", 30)
    if retention_days <= 0:
        return 0
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=retention_days)
    ).isoformat()
    removed = 0
    guilds = config.get("guilds") or {}
    for guild_id, guild_config in guilds.items():
        if not guild_backup_safe_for_pruning(guild_config):
            continue
        rows = connection.execute("""
            SELECT id, media_paths, file_paths
            FROM submissions
            WHERE guild_id = ?
              AND status IN ('posted', 'removed')
              AND COALESCE(created_at, submitted_at, '') < ?
        """, (str(guild_id), cutoff)).fetchall()
        for row in rows:
            removed += delete_original_files_keep_thumbnails(
                split_values(row["media_paths"] or row["file_paths"])
            )
        game_rows = connection.execute("""
            SELECT media_path
            FROM guess_games
            WHERE guild_id = ?
              AND status != 'active'
              AND COALESCE(started_at, '') < ?
        """, (str(guild_id), cutoff)).fetchall()
        for row in game_rows:
            removed += delete_original_files_keep_thumbnails([row["media_path"]])
    return removed


def cleanup_background_data():
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    pending_hours = config["limits"].get(
        "pending_submission_retention_hours",
        48,
    )
    audit_days = config["limits"].get("audit_retention_days", 365)
    rate_limit_days = config["limits"].get("rate_limit_retention_days", 30)
    pending_cutoff = (now - timedelta(hours=pending_hours)).isoformat()
    audit_cutoff = (now - timedelta(days=audit_days)).isoformat()
    rate_limit_cutoff = (now - timedelta(days=rate_limit_days)).isoformat()

    with database() as connection:
        pending_rows = connection.execute("""
            SELECT *
            FROM submissions
            WHERE status = 'pending'
              AND COALESCE(created_at, submitted_at, '') < ?
        """, (pending_cutoff,)).fetchall()
        for row in pending_rows:
            cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
            connection.execute(
                "DELETE FROM submissions WHERE id = ?",
                (row["id"],),
            )
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE timeout_until IS NOT NULL AND timeout_until < ?
        """, (now_iso,))
        if audit_days:
            connection.execute("""
                DELETE FROM admin_audit_log
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (audit_cutoff,))
            connection.execute("""
                DELETE FROM moderation_history
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (audit_cutoff,))
        if rate_limit_days:
            connection.execute("""
                DELETE FROM rate_limit_events
                WHERE created_at IS NOT NULL AND created_at < ?
            """, (rate_limit_cutoff,))
        removed_media = cleanup_orphaned_media(connection)
        removed_originals = cleanup_old_local_originals(connection)
        if pending_rows or removed_media or removed_originals:
            add_admin_audit_log(
                connection,
                None,
                "background_cleanup",
                "system",
                "system",
                "cleanup",
                "",
                (
                    f"Removed {len(pending_rows)} stale pending submission(s) "
                    f"{removed_media} orphan media file(s), and "
                    f"{removed_originals} backed-up local original(s)."
                ),
            )


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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def is_allowed_file(filename):
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_media_type(filename):
    extension = Path(filename).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if extension in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if extension in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
        return "audio"
    return "unknown"


def lifecycle_limit(name, default):
    return configured_limit(name, default)


def thumbnail_path_for_media(path):
    try:
        relative_path = Path(path).resolve().relative_to(MEDIA_DIR.resolve())
    except (OSError, ValueError):
        return None
    if relative_path.parts and relative_path.parts[0] == "_thumbs":
        return None
    return (MEDIA_DIR / "_thumbs" / relative_path).with_suffix(".webp")


def maybe_compress_image(path, filename):
    if not config["limits"].get("image_compression_enabled", False):
        return False
    if get_media_type(filename) != "image":
        return False
    if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return False
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    quality = max(40, min(95, lifecycle_limit("image_compression_quality", 85)))
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


def create_media_thumbnail(path, filename):
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
    max_dimension = max(160, min(2048, lifecycle_limit("thumbnail_max_dimension", 640)))
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


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def directory_size(path):
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        try:
            total += item.stat().st_size
        except OSError:
            pass
    return total


def storage_warning_lines():
    lines = []
    media_limit = configured_limit("media_warning_bytes", 0)
    database_limit = configured_limit("database_warning_bytes", 0)
    media_size = directory_size(MEDIA_DIR)
    database_size = DB_FILE.stat().st_size if DB_FILE.exists() else 0

    if media_limit and media_size >= media_limit:
        lines.append(
            f"Media folder is {format_bytes(media_size)} "
            f"(warning at {format_bytes(media_limit)})."
        )
    if database_limit and database_size >= database_limit:
        lines.append(
            f"Database is {format_bytes(database_size)} "
            f"(warning at {format_bytes(database_limit)})."
        )
    for guild_id, guild_config in sorted((config.get("guilds") or {}).items()):
        limit = guild_storage_limit(guild_config)
        if not limit:
            limit = configured_limit("guild_storage_limit_bytes", 0)
        if not limit:
            continue
        used = guild_media_size(guild_id)
        if used >= limit * 0.8:
            guild_name = (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or f"Discord {guild_id}"
            )
            lines.append(
                f"{guild_name} media storage is {format_bytes(used)} / "
                f"{format_bytes(limit)} ({(used / limit) * 100:.1f}%)."
            )
    return lines


def probe_media_duration(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    if duration <= 0:
        return None
    return round(duration, 2)


def attachment_metadata(attachment, path):
    media_type = get_media_type(attachment.filename)
    try:
        size = Path(path).stat().st_size
    except OSError:
        size = int(attachment.size or 0)
    metadata = {
        "filename": attachment.filename,
        "media_type": media_type,
        "size": int(size or 0),
        "size_label": format_bytes(int(size or 0)),
        "content_type": getattr(attachment, "content_type", "") or "",
        "duration_seconds": None,
        "thumbnail_path": create_media_thumbnail(path, attachment.filename),
    }
    if media_type in {"audio", "video"}:
        metadata["duration_seconds"] = probe_media_duration(path)
    return metadata


def stored_media_metadata(filename, path, content_type=""):
    try:
        size = Path(path).stat().st_size
    except OSError:
        size = 0
    media_type = get_media_type(filename)
    metadata = {
        "filename": filename,
        "media_type": media_type,
        "size": int(size or 0),
        "size_label": format_bytes(int(size or 0)),
        "content_type": content_type or "",
        "duration_seconds": None,
        "thumbnail_path": create_media_thumbnail(path, filename),
    }
    if media_type in {"audio", "video"}:
        metadata["duration_seconds"] = probe_media_duration(path)
    return metadata


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


def file_sha256(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def dynamic_placeholders(values):
    return ",".join("?" for _ in values)


def configured_moderation_int(guild_config, key, fallback):
    moderation = guild_config.get("moderation") or {}
    limits = config.get("limits") or {}
    try:
        value = moderation.get(key, limits.get(key, fallback))
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def submission_spam_signal(connection, guild_id, user_id, guild_config, media_hashes, source_message):
    moderation = guild_config.get("moderation") or {}
    unique_hashes = sorted({item for item in media_hashes if item})
    score = 0
    reasons = []

    if unique_hashes and moderation.get("duplicate_requires_approval", True):
        placeholders = dynamic_placeholders(unique_hashes)
        duplicate_rows = connection.execute(f"""
            SELECT media_hash, submission_id, media_name
            FROM media_fingerprints
            WHERE guild_id = ?
              AND media_hash IN ({placeholders})
            LIMIT 5
        """, [str(guild_id)] + unique_hashes).fetchall()
        if duplicate_rows:
            score += 40
            duplicate_ids = sorted({
                str(row["submission_id"])
                for row in duplicate_rows
                if row["submission_id"] is not None
            })
            if duplicate_ids:
                reasons.append(
                    "duplicate media seen in submission(s) "
                    + ", ".join(duplicate_ids[:3])
                )
            else:
                reasons.append("duplicate media fingerprint")

    burst_count = configured_moderation_int(
        guild_config,
        "spam_burst_count",
        5,
    )
    burst_window = configured_moderation_int(
        guild_config,
        "spam_burst_window_minutes",
        10,
    )
    if burst_count > 0 and burst_window > 0:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=burst_window)
        ).isoformat()
        recent_count = connection.execute("""
            SELECT COUNT(*)
            FROM submissions
            WHERE guild_id = ?
              AND user_id = ?
              AND COALESCE(created_at, submitted_at, '') >= ?
              AND status != 'removed'
        """, (str(guild_id), str(user_id), cutoff)).fetchone()[0]
        if recent_count >= burst_count:
            score += 25
            reasons.append(
                f"{recent_count} recent submission(s) in {burst_window} minutes"
            )

    created_at = getattr(source_message.author, "created_at", None)
    if created_at and moderation.get("require_approval_for_new_users"):
        account_age = datetime.now(timezone.utc) - created_at
        new_user_days = configured_moderation_int(
            guild_config,
            "new_user_days",
            7,
        )
        if account_age < timedelta(days=max(1, new_user_days)):
            score += 15
            reasons.append(f"account newer than {new_user_days} day(s)")

    return score, reasons


def register_media_fingerprints(connection, guild_id, submission_id, paths, names, hashes, sizes):
    now = utc_now_iso()
    for index, media_hash in enumerate(hashes):
        if not media_hash:
            continue
        try:
            size_bytes = int(sizes[index]) if index < len(sizes) else 0
        except (TypeError, ValueError):
            size_bytes = 0
        connection.execute("""
            INSERT INTO media_fingerprints (
                media_hash, guild_id, submission_id, media_path,
                media_name, size_bytes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            media_hash,
            str(guild_id),
            submission_id,
            paths[index] if index < len(paths) else "",
            names[index] if index < len(names) else "",
            size_bytes,
            now,
        ))


def get_voters(raw_value):
    if not raw_value:
        return set()
    return {value for value in raw_value.split(",") if value}


def save_voters(voters):
    return ",".join(sorted(voters))


def cleanup_files(paths):
    for raw_path in paths:
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            resolved.relative_to(MEDIA_DIR.resolve())
            if resolved.is_file():
                resolved.unlink()
            thumb_path = thumbnail_path_for_media(resolved)
            if thumb_path and thumb_path.is_file():
                thumb_path.unlink()
        except (OSError, ValueError):
            continue


def make_discord_files(row):
    paths = split_values(row["media_paths"] or row["file_paths"])
    names = split_values(row["media_names"])
    files = []
    for index, raw_path in enumerate(paths):
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"Missing media file: {path.name}")
        filename = names[index] if index < len(names) else path.name
        files.append(discord.File(path, filename=filename))
    return files


async def send_submission_message(channel, content, row, view):
    files = make_discord_files(row)
    try:
        return await channel.send(
            content=content,
            files=files,
            view=view,
        )
    finally:
        for file in files:
            file.close()


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


def log_admin_action(
    guild_id,
    action,
    actor_user_id,
    actor_username,
    target_type="",
    target_id="",
    details="",
):
    with database() as connection:
        add_admin_audit_log(
            connection,
            guild_id,
            action,
            actor_user_id,
            actor_username,
            target_type,
            target_id,
            details,
        )


def audit_interaction(
    interaction,
    action,
    target_type="",
    target_id="",
    details="",
):
    log_admin_action(
        interaction.guild_id,
        action,
        interaction.user.id,
        interaction.user,
        target_type,
        target_id,
        details,
    )


def record_rate_limit_event(
    guild_id,
    user_id,
    username,
    bucket,
    action,
    retry_after_seconds,
    details="",
):
    with database() as connection:
        connection.execute("""
            INSERT INTO rate_limit_events (
                guild_id, user_id, username, bucket, action,
                retry_after_seconds, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(guild_id) if guild_id is not None else "",
            str(user_id) if user_id is not None else "",
            str(username) if username is not None else "",
            bucket,
            action,
            int(retry_after_seconds),
            details,
            utc_now_iso(),
        ))


def record_content_moderation_event(
    guild_id,
    user_id,
    username,
    category,
    reason,
    action,
    details="",
):
    with database() as connection:
        connection.execute("""
            INSERT INTO content_moderation_events (
                guild_id, user_id, username, category, reason, action,
                details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(guild_id) if guild_id is not None else "",
            str(user_id) if user_id is not None else "",
            str(username) if username is not None else "",
            category or "",
            reason,
            action,
            details,
            utc_now_iso(),
        ))


def guild_limits(guild_config):
    return (guild_config or {}).get("limits") or {}


def guild_moderation(guild_config):
    return (guild_config or {}).get("moderation") or {}


def guild_game_settings(guild_config):
    return (guild_config or {}).get("game_settings") or {}


def configured_guild_limit(guild_config, guild_key, global_key, default=0):
    try:
        guild_value = int(guild_limits(guild_config).get(guild_key) or 0)
    except (TypeError, ValueError):
        guild_value = 0
    if guild_value > 0:
        return guild_value
    return configured_limit(global_key, default)


def guild_monthly_submission_limit(guild_config):
    return configured_guild_limit(
        guild_config,
        "monthly_submission_limit",
        "monthly_submission_limit_per_guild",
        0,
    )


def guild_active_game_limit(guild_config):
    return configured_guild_limit(
        guild_config,
        "active_game_limit",
        "active_game_limit_per_guild",
        0,
    )


def guild_storage_limit(guild_config):
    return configured_guild_limit(
        guild_config,
        "storage_limit_bytes",
        "guild_storage_limit_bytes",
        0,
    )


def guild_max_file_bytes(guild_config):
    return configured_guild_limit(
        guild_config,
        "max_file_bytes",
        "max_file_bytes",
        25 * 1024 * 1024,
    )


def guild_max_total_bytes(guild_config):
    return configured_guild_limit(
        guild_config,
        "max_total_bytes",
        "max_total_bytes",
        50 * 1024 * 1024,
    )


def guild_media_size(guild_id):
    root = MEDIA_DIR / str(guild_id)
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            total += path.stat().st_size
        except OSError:
            pass
    return total


def submission_guidance_lines(guild_id, guild_config):
    moderation = guild_moderation(guild_config)
    allowed_types = moderation.get("allowed_media_types") or [
        "image",
        "video",
        "audio",
    ]
    storage_limit = guild_storage_limit(guild_config)
    storage_used = guild_media_size(guild_id)
    lines = [
        f"Accepted media: `{', '.join(allowed_types)}`.",
        f"Max per file: `{format_bytes(guild_max_file_bytes(guild_config))}`.",
        f"Max per submission: `{format_bytes(guild_max_total_bytes(guild_config))}`.",
        "Files per submission: `1-5`.",
    ]
    if storage_limit:
        remaining = max(0, storage_limit - storage_used)
        percent = (storage_used / storage_limit) * 100 if storage_limit else 0
        lines.append(
            f"Server storage: `{format_bytes(storage_used)} / "
            f"{format_bytes(storage_limit)}` ({percent:.1f}%, "
            f"{format_bytes(remaining)} free)."
        )
    if config["limits"].get("image_compression_enabled", False):
        lines.append(
            "Large JPEG/PNG/WebP images may be compressed after upload."
        )
    retention_days = configured_limit("local_original_retention_days", 30)
    if retention_days > 0 and guild_backup_safe_for_pruning(guild_config):
        lines.append(
            f"Older originals may move to remote storage after {retention_days} day(s)."
        )
    return lines


def current_month_submission_count(connection, guild_id, guild_config):
    month = current_month_key(guild_config)
    row = connection.execute("""
        SELECT COUNT(*)
        FROM submissions
        WHERE guild_id = ?
          AND substr(COALESCE(created_at, submitted_at, ''), 1, 7) = ?
    """, (str(guild_id), month)).fetchone()
    return int(row[0] or 0)


def active_game_count(connection, guild_id):
    row = connection.execute("""
        SELECT COUNT(*)
        FROM guess_games
        WHERE guild_id = ? AND status = 'active'
    """, (str(guild_id),)).fetchone()
    return int(row[0] or 0)


def parse_scheduled_start_time(raw_value, guild_config):
    value = (raw_value or "").strip()
    if not value:
        raise ValueError("Start time is required.")
    timezone_info = get_guild_timezone(guild_config)
    for candidate in (value, value.replace(" ", "T", 1)):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone_info)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M%p", "%Y-%m-%d %I:%M %p"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=timezone_info).astimezone(timezone.utc)
        except ValueError:
            pass
    raise ValueError(
        "Use `YYYY-MM-DD HH:MM` in the server timezone or an ISO timestamp."
    )


def select_library_item_for_game(
    connection,
    guild_id,
    item_id=0,
    category="",
    random_item=False,
    reuse_cooldown_days=0,
):
    guild_id = str(guild_id)
    if int(item_id or 0) > 0:
        return connection.execute("""
            SELECT *
            FROM guess_library_items
            WHERE id = ?
              AND guild_id = ?
              AND status = 'active'
              AND (enabled IS NULL OR enabled != 0)
            LIMIT 1
        """, (int(item_id), guild_id)).fetchone()

    where = [
        "guild_id = ?",
        "status = 'active'",
        "(enabled IS NULL OR enabled != 0)",
        "media_path IS NOT NULL",
        "media_path != ''",
    ]
    parameters = [guild_id]
    category_filter = (category or "").strip()
    if category_filter:
        where.append("LOWER(category) = LOWER(?)")
        parameters.append(category_filter)
    if reuse_cooldown_days > 0:
        where.append("(last_used_at IS NULL OR last_used_at = '' OR last_used_at < ?)")
        parameters.append(
            (
                datetime.now(timezone.utc) - timedelta(days=reuse_cooldown_days)
            ).isoformat()
        )
    order_sql = (
        "RANDOM()"
        if random_item
        else """
            CASE WHEN last_used_at IS NULL OR last_used_at = '' THEN 0 ELSE 1 END,
            last_used_at ASC,
            id ASC
        """
    )
    return connection.execute(f"""
        SELECT *
        FROM guess_library_items
        WHERE {" AND ".join(where)}
        ORDER BY {order_sql}
        LIMIT 1
    """, parameters).fetchone()


async def start_library_game_item(
    guild,
    channel,
    item,
    starter_user_id,
    starter_username,
    source="library",
    scheduled_id=None,
):
    guild_config = get_guild_config(guild.id, create=False)
    if emergency_pause_message(guild_config):
        raise RuntimeError("SDAC is paused for this server.")
    if not feature_enabled(guild_config, "guessing_games"):
        raise RuntimeError("Guessing games are disabled for this server.")

    bot_member = guild.me
    if bot_member is None and bot.user is not None:
        bot_member = guild.get_member(bot.user.id)
    if bot_member is None:
        raise RuntimeError("The bot could not verify its channel permissions.")
    permissions = channel.permissions_for(bot_member)
    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.attach_files
    ):
        raise RuntimeError(
            "The bot needs View Channel, Send Messages, and Attach Files."
        )

    try:
        answer_aliases = json.loads(item["answer_aliases_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        answer_aliases = []
    if not answer_aliases:
        answer_aliases = parse_answer_aliases(
            item["answer_display"] or item["answer"]
        )
    if not answer_aliases:
        raise RuntimeError(f"Library item {item['id']} does not have an answer.")

    answer_display = item["answer_display"] or answer_aliases[0]["display"]
    normalized_answer = item["answer"] or answer_aliases[0]["normalized"]
    media_name = item["media_name"] or Path(item["media_path"] or "").name
    if not media_name or not is_allowed_file(media_name):
        raise RuntimeError(f"Library item {item['id']} does not have valid media.")

    source_path = Path(item["media_path"] or "")
    if not source_path.is_absolute():
        source_path = BASE_DIR / source_path
    source_path = source_path.resolve()
    source_path.relative_to(MEDIA_DIR.resolve())
    if not source_path.is_file():
        raise RuntimeError(f"Library item {item['id']} is missing its media file.")

    media_size = source_path.stat().st_size
    if media_size > guild_max_file_bytes(guild_config):
        raise RuntimeError(f"Library item {item['id']} exceeds the file limit.")
    storage_limit = guild_storage_limit(guild_config)
    if storage_limit and guild_media_size(guild.id) + media_size > storage_limit:
        raise RuntimeError("This server has reached its media storage limit.")

    game_settings = guild_game_settings(guild_config)
    with database() as connection:
        limit = guild_active_game_limit(guild_config)
        active_same_channel = connection.execute("""
            SELECT 1
            FROM guess_games
            WHERE guild_id = ? AND channel_id = ? AND status = 'active'
            LIMIT 1
        """, (str(guild.id), str(channel.id))).fetchone()
        if limit and active_game_count(connection, guild.id) >= limit and not active_same_channel:
            raise RuntimeError("This server has reached its active game limit.")
        recent_answer = answer_recently_used(
            connection,
            guild.id,
            normalized_answer,
            int(game_settings.get("reuse_cooldown_days") or 0),
        )
        if recent_answer:
            raise RuntimeError(
                f"That answer was used recently ({recent_answer['created_at']})."
            )

    replaced_game = await close_active_guess_game(guild.id, channel.id, "replaced")
    game_folder = MEDIA_DIR / str(guild.id) / "guess_games" / str(channel.id)
    game_folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(media_name).name.replace("\\", "_")
    unique_token = scheduled_id or int(time.time())
    media_path = game_folder / f"{int(time.time())}_{unique_token}_{safe_name}"
    discord_file = None
    game_message = None
    game_id = None

    try:
        shutil.copy2(source_path, media_path)
        maybe_compress_image(media_path, media_name)
        try:
            stored_metadata = json.loads(item["media_metadata_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            stored_metadata = {}
        media_metadata = stored_media_metadata(
            media_name,
            media_path,
            stored_metadata.get("content_type", ""),
        )
        discord_file = discord.File(media_path, filename=media_name)
        auto_hint_minutes = int(item["auto_hint_minutes"] or 0)
        if auto_hint_minutes == 0:
            auto_hint_minutes = int(
                game_settings.get("default_auto_hint_minutes") or 0
            )
        game_lines = ["**Guessing Game Started**"]
        prompt_text = (item["prompt_text"] or "").strip()
        if prompt_text:
            game_lines.append(prompt_text)
        if scheduled_id:
            game_lines.append(f"Scheduled game `{scheduled_id}` is now live.")
        if auto_hint_minutes > 0:
            game_lines.append(
                f"Automatic hints are enabled every {auto_hint_minutes} minute(s)."
            )
        game_lines.append("Use `/guess <guess>` in this channel.")
        generated_hints = build_game_hints(
            answer_display,
            item["category"] or "",
            item["hint_text"] or "",
        )
        game_message = await channel.send(
            content="\n\n".join(game_lines),
            file=discord_file,
        )
        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO guess_games (
                    guild_id, channel_id, message_id, starter_user_id,
                    starter_username, answer, answer_display, prompt_text,
                    media_path, media_name, media_type, media_size,
                    media_metadata_json, answer_aliases_json, hints_json,
                    hint_level, next_hint_at, auto_hint_minutes,
                    hint_category, library_item_id, status, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'active', ?)
            """, (
                str(guild.id),
                str(channel.id),
                str(game_message.id),
                str(starter_user_id),
                str(starter_username),
                normalized_answer,
                answer_display,
                prompt_text,
                str(media_path),
                media_name,
                get_media_type(media_name),
                int(media_metadata.get("size") or media_size),
                json.dumps(media_metadata, separators=(",", ":")),
                json.dumps(answer_aliases, separators=(",", ":")),
                json.dumps(generated_hints, separators=(",", ":")),
                next_hint_time(auto_hint_minutes),
                auto_hint_minutes,
                item["category"] or "",
                item["id"],
                utc_now_iso(),
            ))
            game_id = cursor.lastrowid
            record_guess_answer_history(
                connection,
                guild.id,
                channel.id,
                game_id,
                item["id"],
                normalized_answer,
                answer_display,
                item["category"] or "",
                source,
                starter_username,
            )
            connection.execute("""
                UPDATE guess_library_items
                SET times_used = COALESCE(times_used, 0) + 1,
                    last_used_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (utc_now_iso(), utc_now_iso(), item["id"]))
            add_admin_audit_log(
                connection,
                guild.id,
                "start_scheduled_library_game" if scheduled_id else "start_library_guess_game",
                starter_user_id,
                starter_username,
                "game",
                game_id,
                (
                    f"Channel {channel.id}; library item {item['id']}; "
                    f"scheduled={scheduled_id or 'no'}; replaced={bool(replaced_game)}."
                ),
            )
        return game_id, replaced_game
    except Exception:
        if game_message is not None:
            try:
                await game_message.delete()
            except discord.HTTPException:
                pass
        if game_id is not None:
            with database() as connection:
                connection.execute("DELETE FROM guess_games WHERE id = ?", (game_id,))
        cleanup_files([str(media_path)])
        raise
    finally:
        if discord_file is not None:
            discord_file.close()


def award_user_achievement(
    connection,
    guild_id,
    user_id,
    username,
    key,
    label,
    details,
    month="",
):
    existing = connection.execute("""
        SELECT 1
        FROM user_achievements
        WHERE guild_id = ?
          AND user_id = ?
          AND achievement_key = ?
          AND month = ?
        LIMIT 1
    """, (str(guild_id), str(user_id), key, month or "")).fetchone()
    if existing:
        return ""
    connection.execute("""
        INSERT INTO user_achievements (
            guild_id, user_id, username, achievement_key, label,
            details, month, awarded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(guild_id),
        str(user_id),
        str(username),
        key,
        label,
        details,
        month or "",
        utc_now_iso(),
    ))
    return label


def record_guess_success_achievements(
    connection,
    guild_id,
    user_id,
    username,
    game_id,
    month,
):
    row = connection.execute("""
        SELECT *
        FROM user_streaks
        WHERE guild_id = ? AND user_id = ?
    """, (str(guild_id), str(user_id))).fetchone()
    if row and str(row["last_correct_game_id"] or "") == str(game_id):
        current_streak = int(row["current_guess_streak"] or 1)
        best_streak = int(row["best_guess_streak"] or current_streak)
    else:
        current_streak = int(row["current_guess_streak"] or 0) + 1 if row else 1
        best_streak = max(current_streak, int(row["best_guess_streak"] or 0) if row else 0)
    connection.execute("""
        INSERT INTO user_streaks (
            guild_id, user_id, username, current_guess_streak,
            best_guess_streak, last_correct_game_id, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET
            username = excluded.username,
            current_guess_streak = excluded.current_guess_streak,
            best_guess_streak = excluded.best_guess_streak,
            last_correct_game_id = excluded.last_correct_game_id,
            updated_at = excluded.updated_at
    """, (
        str(guild_id),
        str(user_id),
        str(username),
        current_streak,
        best_streak,
        int(game_id),
        utc_now_iso(),
    ))

    labels = []
    for key, label, details, award_month in (
        ("first_correct", "First Correct Guess", "Guessed a game correctly.", ""),
        ("streak_3", "Three-Guess Streak", "Reached a 3 correct-guess streak.", ""),
        ("streak_5", "Five-Guess Streak", "Reached a 5 correct-guess streak.", ""),
        ("streak_10", "Ten-Guess Streak", "Reached a 10 correct-guess streak.", ""),
    ):
        if key == "streak_3" and best_streak < 3:
            continue
        if key == "streak_5" and best_streak < 5:
            continue
        if key == "streak_10" and best_streak < 10:
            continue
        awarded = award_user_achievement(
            connection,
            guild_id,
            user_id,
            username,
            key,
            label,
            details,
            award_month,
        )
        if awarded:
            labels.append(awarded)

    total_points = connection.execute("""
        SELECT COALESCE(SUM(points), 0)
        FROM guess_points
        WHERE guild_id = ? AND user_id = ? AND month = ?
    """, (str(guild_id), str(user_id), month)).fetchone()[0]
    if int(total_points or 0) >= 10:
        awarded = award_user_achievement(
            connection,
            guild_id,
            user_id,
            username,
            "monthly_10_points",
            "Monthly 10 Points",
            f"Earned at least 10 guessing points in {month}.",
            month,
        )
        if awarded:
            labels.append(awarded)
    return labels


def blocked_word_match(text, blocked_words):
    normalized_text = (text or "").casefold()
    for word in blocked_words or []:
        word = str(word or "").strip().casefold()
        if word and word in normalized_text:
            return word
    return ""


def moderation_rejection(guild_config, message, category):
    moderation = guild_moderation(guild_config)
    blocked = blocked_word_match(
        message.content,
        moderation.get("blocked_words") or [],
    )
    if blocked:
        record_content_moderation_event(
            message.guild.id,
            message.author.id,
            message.author,
            category,
            "blocked_word",
            "rejected",
            f"Matched `{blocked}`.",
        )
        return "This submission contains a blocked word."

    allowed_types = set(moderation.get("allowed_media_types") or [])
    if allowed_types:
        bad_types = [
            attachment.filename
            for attachment in message.attachments
            if get_media_type(attachment.filename) not in allowed_types
        ]
        if bad_types:
            record_content_moderation_event(
                message.guild.id,
                message.author.id,
                message.author,
                category,
                "blocked_media_type",
                "rejected",
                ", ".join(bad_types),
            )
            return "One or more attachment media types are not allowed here."
    return ""


def submission_needs_moderation_approval(guild_config, message):
    moderation = guild_moderation(guild_config)
    if moderation.get("spoiler_requires_approval"):
        if any(str(attachment.filename or "").startswith("SPOILER_") for attachment in message.attachments):
            return True, "Spoiler media requires approval."
    if moderation.get("require_approval_for_new_users"):
        try:
            new_user_days = int(moderation.get("new_user_days") or 7)
        except (TypeError, ValueError):
            new_user_days = 7
        created_at = getattr(message.author, "created_at", None)
        if created_at:
            age = datetime.now(timezone.utc) - created_at
            if age.days < new_user_days:
                return True, f"Account is newer than {new_user_days} day(s)."
    return False, ""


def answer_recently_used(connection, guild_id, normalized_answer, cooldown_days):
    try:
        cooldown_days = int(cooldown_days or 0)
    except (TypeError, ValueError):
        cooldown_days = 0
    if cooldown_days <= 0:
        return None
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cooldown_days)).isoformat()
    return connection.execute("""
        SELECT answer_display, category, created_at
        FROM guess_answer_history
        WHERE guild_id = ?
          AND answer = ?
          AND created_at >= ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """, (str(guild_id), normalized_answer, cutoff)).fetchone()


def support_bundle_payload(guild_id=None):
    config_guilds = config.get("guilds", {})
    selected_guild = config_guilds.get(str(guild_id), {}) if guild_id else None
    with database() as connection:
        payload = {
            "created_at": utc_now_iso(),
            "schema_version": SCHEMA_VERSION,
            "database_backend": "postgresql" if using_postgres() else "sqlite",
            "db_file": str(DB_FILE),
            "media_dir": str(MEDIA_DIR),
            "guild_count": len(config_guilds),
            "selected_guild_id": str(guild_id) if guild_id else "",
            "selected_guild_configured": bool(selected_guild),
            "submissions": connection.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0],
            "active_games": connection.execute("""
                SELECT COUNT(*)
                FROM guess_games
                WHERE status = 'active'
            """).fetchone()[0],
            "rate_limit_events": connection.execute(
                "SELECT COUNT(*) FROM rate_limit_events"
            ).fetchone()[0],
        }
    if selected_guild:
        payload["selected_guild"] = {
            "name": selected_guild.get("guild_name") or selected_guild.get("brand_name") or "",
            "categories": len(selected_guild.get("categories") or {}),
            "features": selected_guild.get("features") or {},
            "limits": selected_guild.get("limits") or {},
            "public_stats_enabled": selected_guild.get("public_stats_enabled", True),
        }
    return payload


def configured_limit(name, default):
    try:
        value = int(config["limits"].get(name, default))
    except (TypeError, ValueError):
        return default
    return max(0, value)


def command_cooldown_message(bucket, guild_id, user_id, seconds):
    if seconds <= 0:
        return None, 0
    now = time.time()
    key = f"{bucket}:{guild_id}:{user_id}"
    last_seen = command_cooldowns.get(key, 0)
    elapsed = now - last_seen
    if elapsed < seconds:
        remaining = max(1, int(seconds - elapsed))
        return f"Slow down a little. Try again in {remaining}s.", remaining
    command_cooldowns[key] = now
    return None, 0


def add_moderation_history(
    connection,
    row,
    action,
    actor_user_id,
    actor_username,
    details="",
):
    connection.execute("""
        INSERT INTO moderation_history (
            guild_id, submission_id, action, actor_user_id,
            actor_username, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        row["guild_id"],
        row["id"],
        action,
        str(actor_user_id),
        str(actor_username),
        details,
        utc_now_iso(),
    ))


def parse_poll_options(raw_value):
    parts = [
        part.strip()
        for part in re.split(r"[\n|]+", str(raw_value or ""))
        if part.strip()
    ]
    if len(parts) < 2:
        raise ValueError("Polls need at least two options separated by | or new lines.")
    if len(parts) > 10:
        raise ValueError("Polls can have at most 10 options.")
    return [part[:120] for part in parts]


def poll_vote_counts(connection, poll_id):
    rows = connection.execute("""
        SELECT option_index, COUNT(*) AS total
        FROM poll_votes
        WHERE poll_id = ?
        GROUP BY option_index
    """, (poll_id,)).fetchall()
    return {int(row["option_index"]): int(row["total"] or 0) for row in rows}


def poll_results_text(options, counts):
    total = sum(counts.values())
    lines = []
    for index, option in enumerate(options):
        votes = counts.get(index, 0)
        percent = round((votes / total) * 100) if total else 0
        lines.append(f"{index + 1}. {option} - {votes} vote(s), {percent}%")
    lines.append(f"Total votes: {total}")
    return "\n".join(lines)


def poll_embed(poll_id, question, options, counts=None, status="active"):
    counts = counts or {}
    embed = discord.Embed(
        title=f"Poll #{poll_id}: {question}",
        description=(
            "Vote with `/votepoll poll_id option_number`.\n\n"
            + poll_results_text(options, counts)
        ),
        color=0x5865F2 if status == "active" else 0x6B7280,
    )
    embed.set_footer(text=f"Status: {status}")
    return embed


def admin_only(interaction):
    if not interaction.guild:
        return False
    if interaction.user.guild_permissions.administrator:
        return True

    guild_config = get_guild_config(interaction.guild_id, create=False)
    allowed_role_ids = {
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id).strip()
    }
    if not allowed_role_ids:
        return False
    return any(str(role.id) in allowed_role_ids for role in interaction.user.roles)


async def require_admin(interaction):
    if admin_only(interaction):
        seconds = configured_limit("admin_action_cooldown_seconds", 1)
        message, remaining = command_cooldown_message(
            "admin_action",
            interaction.guild_id,
            interaction.user.id,
            seconds,
        )
        if message:
            record_rate_limit_event(
                interaction.guild_id,
                interaction.user.id,
                interaction.user,
                "admin_action",
                (
                    interaction.command.name
                    if getattr(interaction, "command", None)
                    else "unknown"
                ),
                remaining,
                "Admin command cooldown.",
            )
            await interaction.response.send_message(message, ephemeral=True)
            return False
        return True
    command_name = (
        interaction.command.name
        if getattr(interaction, "command", None)
        else "unknown"
    )
    log_admin_action(
        interaction.guild_id,
        "admin_command_denied",
        interaction.user.id,
        interaction.user,
        "command",
        command_name,
        "Non-admin attempted an admin-only command.",
    )
    await interaction.response.send_message(
        "Only admins can use this command.",
        ephemeral=True,
    )
    return False


async def category_autocomplete(interaction, current):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    categories = guild_config.get("categories", {}) if guild_config else {}
    current = clean_category_name(current)
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(categories)
        if current in name
    ][:25]


def channel_display(channel_id):
    return f"<#{channel_id}>" if channel_id else "Not set"


def bot_invite_url():
    client_id = (
        os.getenv("SDAC_BOT_CLIENT_ID")
        or os.getenv("DISCORD_CLIENT_ID")
        or (str(bot.user.id) if bot.user else "")
    )
    if not client_id:
        return ""
    permissions = os.getenv("SDAC_BOT_PERMISSIONS", "274878221376")
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}"
        f"&permissions={permissions}"
        "&scope=bot%20applications.commands"
    )


def settings_lines(guild_config):
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    timeout_seconds = config["limits"].get("wrong_guess_timeout_seconds", 600)
    timeout_minutes = max(1, round(timeout_seconds / 60))
    weekly_day = guild_config.get(
        "weekly_top_day",
        DEFAULT_GUILD_CONFIG["weekly_top_day"],
    ).title()
    brand_name = guild_config.get("brand_name") or guild_config.get("guild_name") or "SDAC"
    setup_preset = guild_config.get("setup_preset") or "custom"
    lines = [
        "**SDAC Settings**",
        f"Brand name: `{brand_name}`",
        f"Brand accent: `{guild_config.get('brand_accent') or '#7c9cff'}`",
        f"Setup preset: `{setup_preset}`",
        f"Submit channel: {channel_display(guild_config.get('submit_channel'))}",
        f"Weekly top channel: {channel_display(guild_config.get('daily_top_channel'))}",
        f"Weekly top day: `{weekly_day}`",
        f"Weekly top time: `{guild_config['daily_top_time_utc']}` `{timezone_name}`",
        f"Timezone: `{timezone_name}`",
        f"Approval: {'Enabled' if guild_config['approval_enabled'] else 'Disabled'}",
        f"Approval channel: {channel_display(guild_config.get('approval_channel'))}",
        f"Game summary channel: {channel_display(guild_config.get('game_summary_channel'))}",
        f"Error channel: {channel_display(guild_config.get('error_channel'))}",
        f"Admin roles: `{len(guild_config.get('admin_role_ids', []))}`",
        (
            "Emergency pause: `Enabled`"
            if guild_config.get("emergency_paused")
            else "Emergency pause: `Disabled`"
        ),
        f"Wrong guess timeout: `{timeout_minutes}` minute(s)",
        f"Categories: `{len(guild_config.get('categories', {}))}`",
        "",
        "**Features:**",
    ]
    features = guild_config.get("features") or {}
    for feature, label in FEATURE_LABELS.items():
        enabled = features.get(feature, DEFAULT_FEATURES[feature])
        lines.append(f"- {label}: `{'Enabled' if enabled else 'Disabled'}`")
    lines.append("")
    categories = guild_config.get("categories", {})
    if not categories:
        lines.append("No categories are set.")
    else:
        lines.append("**Categories:**")
        for category, channel_id in sorted(categories.items()):
            lines.append(f"- `{category}` -> {channel_display(channel_id)}")
    return lines


def submission_content(row):
    return (
        f"Category: **{row['category'].upper()}**\n"
        f"Submitted by: <@{row['user_id']}>\n"
        f"Submitted: {utc_now_display()}\n\n"
        f"{row['message_text'] or ''}"
    )


REQUIRED_BOT_PERMISSIONS = (
    ("view_channel", "View Channel"),
    ("send_messages", "Send Messages"),
    ("attach_files", "Attach Files"),
    ("read_message_history", "Read Message History"),
)
OPTIONAL_BOT_PERMISSIONS = (
    ("manage_messages", "Manage Messages"),
)


def configured_channel_ids(guild_config):
    channel_ids = []
    for key in (
        "submit_channel",
        "daily_top_channel",
        "game_summary_channel",
        "error_channel",
        "approval_channel",
    ):
        channel_id = guild_config.get(key)
        if channel_id:
            channel_ids.append(channel_id)
    channel_ids.extend((guild_config.get("categories") or {}).values())

    deduped = []
    seen = set()
    for channel_id in channel_ids:
        if str(channel_id) in seen:
            continue
        seen.add(str(channel_id))
        deduped.append(channel_id)
    return deduped


async def resolve_guild_channel(guild, channel_id):
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None
    channel = guild.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        channel = await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        return None
    if getattr(channel, "guild", None) and channel.guild.id == guild.id:
        return channel
    return None


def bot_permission_summary(guild, channel):
    bot_member = guild.me
    if bot_member is None and bot.user is not None:
        bot_member = guild.get_member(bot.user.id)
    if bot_member is None:
        return "Bot member was not found in this server."

    permissions = channel.permissions_for(bot_member)
    missing_required = [
        label
        for attribute, label in REQUIRED_BOT_PERMISSIONS
        if not getattr(permissions, attribute, False)
    ]
    missing_optional = [
        label
        for attribute, label in OPTIONAL_BOT_PERMISSIONS
        if not getattr(permissions, attribute, False)
    ]
    if missing_required:
        return "Missing required: " + ", ".join(missing_required)
    if missing_optional:
        return "Usable, recommended: " + ", ".join(missing_optional)
    return "OK"


async def permission_drift_lines_for_guild(guild, guild_config):
    lines = []
    seen = set()
    for channel_id in configured_channel_ids(guild_config):
        channel_key = str(channel_id)
        if channel_key in seen:
            continue
        seen.add(channel_key)
        channel = await resolve_guild_channel(guild, channel_id)
        if channel is None:
            lines.append(f"`{channel_id}`: channel not visible to the bot.")
            continue
        summary = bot_permission_summary(guild, channel)
        if summary != "OK":
            lines.append(f"{channel.mention}: {summary}")
    return lines


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!sdac ", intents=intents)
tree = bot.tree
user_cooldowns = {}
category_cooldowns = {}
command_cooldowns = {}
active_submission_sessions = set()
slash_commands_synced = False
persistent_views_registered = False
last_backup_date = None
last_storage_warning_date = None
last_permission_drift_date = {}


def refresh_known_guilds():
    changed = False
    for guild in bot.guilds:
        guild_config = get_guild_config(guild.id)
        if guild_config.get("guild_name") != guild.name:
            guild_config["guild_name"] = guild.name
            changed = True
    if changed:
        save_config(config)


def write_bot_status(event="heartbeat"):
    payload = {
        "event": event,
        "updated_at": utc_now_iso(),
        "release": os.getenv("SDAC_RELEASE") or "development",
        "instance_id": BOT_INSTANCE_ID,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "base_dir": str(BASE_DIR),
        "bot_user": str(bot.user) if bot.user else "",
        "bot_id": str(bot.user.id) if bot.user else "",
        "guild_count": len(bot.guilds),
        "slash_commands_synced": slash_commands_synced,
        "guilds": [
            {
                "id": str(guild.id),
                "name": guild.name,
                "member_count": guild.member_count,
            }
            for guild in bot.guilds
        ],
    }
    try:
        BOT_STATUS_FILE.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        print(f"Could not write bot status file: {error}", flush=True)


async def delete_discord_message(channel_id, message_id):
    if not channel_id or not message_id:
        return True, ""
    try:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            channel = await bot.fetch_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        await message.delete()
        return True, ""
    except discord.NotFound:
        return True, ""
    except discord.Forbidden:
        return False, "The bot does not have permission to delete the Discord message."
    except discord.HTTPException as error:
        return False, f"Discord deletion failed: {error}"


async def delete_guess_game_message(row):
    deleted, message = await delete_discord_message(
        row["channel_id"],
        row["message_id"],
    )
    if not deleted:
        print(f"Could not delete old guessing game message: {message}", flush=True)
    cleanup_files([row["media_path"]])


async def close_active_guess_game(guild_id, channel_id, status):
    with database() as connection:
        row = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(guild_id), str(channel_id))).fetchone()
        if row:
            connection.execute("""
                UPDATE guess_games
                SET status = ?,
                    solved_at = COALESCE(solved_at, ?)
                WHERE id = ?
            """, (status, utc_now_iso(), row["id"]))
            connection.execute("""
                DELETE FROM guess_cooldowns
                WHERE guild_id = ? AND channel_id = ?
            """, (str(guild_id), str(channel_id)))

    if row:
        await delete_guess_game_message(row)
    return row


def guess_leaderboard_lines(connection, guild_id, channel_id, month, limit=10):
    rows = connection.execute("""
        SELECT username, points
        FROM guess_points
        WHERE guild_id = ?
          AND channel_id = ?
          AND month = ?
        ORDER BY points DESC, username ASC
        LIMIT ?
    """, (str(guild_id), str(channel_id), month, limit)).fetchall()

    if not rows:
        return ["No points yet."]

    return [
        f"{index}. {row['username']} - {row['points']} point(s)"
        for index, row in enumerate(rows, start=1)
    ]


async def configured_summary_channel(game, fallback_channel):
    guild_config = get_guild_config(game["guild_id"], create=False)
    channel_id = guild_config.get("game_summary_channel")
    if not channel_id:
        return fallback_channel
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            channel = None
    return channel or fallback_channel


def configured_notification_channel_id(guild_id, event_key):
    if not event_key:
        return None
    with database() as connection:
        row = connection.execute("""
            SELECT channel_id
            FROM admin_notifications
            WHERE guild_id = ?
              AND event_key = ?
              AND enabled = 1
            LIMIT 1
        """, (str(guild_id), event_key)).fetchone()
    return row["channel_id"] if row else None


async def send_error_notification(guild_id, message, event_key="system_errors"):
    guild_config = get_guild_config(guild_id, create=False)
    try:
        channel_id = configured_notification_channel_id(guild_id, event_key)
    except sqlite3.Error:
        channel_id = None
    channel_id = channel_id or guild_config.get("error_channel")
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except discord.HTTPException:
            channel = None
    if channel is not None:
        try:
            event_label = NOTIFICATION_EVENT_LABELS.get(event_key, "System Error")
            await channel.send(f"**SDAC {event_label}**\n{message}")
        except discord.HTTPException:
            pass


async def send_system_error_notification(message, event_key="system_errors"):
    sent_guilds = set()
    for guild_id in config.get("guilds", {}):
        if guild_id in sent_guilds:
            continue
        sent_guilds.add(guild_id)
        await send_error_notification(guild_id, message, event_key)


async def report_background_error(name, error):
    capture_exception(error)
    print(f"{name} failed: {error}", flush=True)
    await send_system_error_notification(
        f"`{name}` failed: `{error}`",
        "system_errors",
    )


async def announce_guess_summary(channel, game, reason):
    guild_config = get_guild_config(game["guild_id"], create=False)
    target_channel = await configured_summary_channel(game, channel)
    if target_channel is None:
        return
    with database() as connection:
        correct_rows = connection.execute("""
            SELECT username
            FROM guess_correct_guesses
            WHERE game_id = ?
            ORDER BY guessed_at ASC
        """, (game["id"],)).fetchall()
        leaderboard = guess_leaderboard_lines(
            connection,
            game["guild_id"],
            game["channel_id"],
            current_month_key(guild_config),
            limit=10,
        )

    correct_names = (
        ", ".join(row["username"] for row in correct_rows)
        if correct_rows
        else "Nobody"
    )
    await target_channel.send(
        f"**Guessing Game Summary ({reason})**\n"
        f"Answer: **{game['answer_display']}**\n"
        f"Correct guessers: {correct_names}\n\n"
        "**Top 10 This Month**\n"
        + "\n".join(leaderboard)
    )


async def remove_submission_record(
    submission_id,
    actor_user_id,
    actor_username,
    reason,
):
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()

    if not row:
        return False, "Submission not found."

    deleted, message = await delete_discord_message(
        row["repost_channel_id"],
        row["repost_message_id"],
    )
    if not deleted:
        return False, message

    await delete_discord_message(
        row["approval_channel_id"],
        row["approval_message_id"],
    )

    with database() as connection:
        add_moderation_history(
            connection,
            row,
            "remove",
            actor_user_id,
            actor_username,
            reason,
        )
        add_admin_audit_log(
            connection,
            row["guild_id"],
            "remove_submission",
            actor_user_id,
            actor_username,
            "submission",
            row["id"],
            reason,
        )
        connection.execute(
            "DELETE FROM submissions WHERE id = ?",
            (submission_id,),
        )

    cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
    return True, "Submission removed from Discord and the database."


class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Vote",
        style=discord.ButtonStyle.secondary,
        custom_id="sdac_star_vote",
    )
    async def star_vote(self, interaction, button):
        repost_message_id = str(interaction.message.id)
        user_id = str(interaction.user.id)

        with database() as connection:
            row = connection.execute("""
                SELECT id, voters
                FROM submissions
                WHERE repost_message_id = ? AND status = 'posted'
            """, (repost_message_id,)).fetchone()

            if not row:
                await interaction.response.send_message(
                    "This post is not registered in the SDAC database.",
                    ephemeral=True,
                )
                return

            voters = get_voters(row["voters"])
            if user_id in voters:
                await interaction.response.send_message(
                    "You already voted for this post.",
                    ephemeral=True,
                )
                return

            voters.add(user_id)
            connection.execute("""
                UPDATE submissions
                SET stars = stars + 1, voters = ?
                WHERE id = ?
            """, (save_voters(voters), row["id"]))

        await interaction.response.send_message(
            "Vote added.",
            ephemeral=True,
        )


class ApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_pending_row(self, interaction):
        with database() as connection:
            return connection.execute("""
                SELECT *
                FROM submissions
                WHERE approval_message_id = ? AND status = 'pending'
            """, (str(interaction.message.id),)).fetchone()

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="sdac_approve_submission",
    )
    async def approve(self, interaction, button):
        if not admin_only(interaction):
            log_admin_action(
                interaction.guild_id,
                "admin_button_denied",
                interaction.user.id,
                interaction.user,
                "button",
                "approve_submission",
                "Non-admin attempted to approve a submission.",
            )
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        row = await self.get_pending_row(interaction)
        if not row:
            await interaction.followup.send(
                "This submission is no longer pending.",
                ephemeral=True,
            )
            return

        target_channel = bot.get_channel(int(row["repost_channel_id"]))
        if target_channel is None:
            try:
                target_channel = await bot.fetch_channel(
                    int(row["repost_channel_id"])
                )
            except discord.HTTPException:
                target_channel = None
        if target_channel is None:
            await interaction.followup.send(
                "The target category channel could not be found.",
                ephemeral=True,
            )
            return

        try:
            repost = await send_submission_message(
                target_channel,
                submission_content(row),
                row,
                VoteView(),
            )
        except (discord.HTTPException, OSError) as error:
            await interaction.followup.send(
                f"Approval failed: `{error}`",
                ephemeral=True,
            )
            return

        with database() as connection:
            connection.execute("""
                UPDATE submissions
                SET status = 'posted',
                    repost_message_id = ?,
                    repost_channel_id = ?,
                    approved_at = ?
                WHERE id = ? AND status = 'pending'
            """, (
                str(repost.id),
                str(target_channel.id),
                utc_now_iso(),
                row["id"],
            ))
            add_moderation_history(
                connection,
                row,
                "approve",
                interaction.user.id,
                interaction.user,
            )
            add_admin_audit_log(
                connection,
                row["guild_id"],
                "approve_submission",
                interaction.user.id,
                interaction.user,
                "submission",
                row["id"],
                f"Posted to channel {target_channel.id}.",
            )

        await interaction.message.edit(
            content=interaction.message.content + "\n\nApproved.",
            view=None,
        )
        await interaction.followup.send(
            f"Submission `{row['id']}` approved.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="sdac_reject_submission",
    )
    async def reject(self, interaction, button):
        if not admin_only(interaction):
            log_admin_action(
                interaction.guild_id,
                "admin_button_denied",
                interaction.user.id,
                interaction.user,
                "button",
                "reject_submission",
                "Non-admin attempted to reject a submission.",
            )
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return

        row = await self.get_pending_row(interaction)
        if not row:
            await interaction.response.send_message(
                "This submission is no longer pending.",
                ephemeral=True,
            )
            return

        with database() as connection:
            add_moderation_history(
                connection,
                row,
                "reject",
                interaction.user.id,
                interaction.user,
            )
            add_admin_audit_log(
                connection,
                row["guild_id"],
                "reject_submission",
                interaction.user.id,
                interaction.user,
                "submission",
                row["id"],
                "Rejected from approval queue.",
            )
            connection.execute(
                "DELETE FROM submissions WHERE id = ?",
                (row["id"],),
            )

        cleanup_files(split_values(row["media_paths"] or row["file_paths"]))
        await interaction.message.edit(
            content=interaction.message.content + "\n\nRejected.",
            attachments=[],
            view=None,
        )
        await interaction.response.send_message(
            f"Submission `{row['id']}` rejected.",
            ephemeral=True,
        )


def setup_status_rows(guild_config):
    categories = guild_config.get("categories") or {}
    admin_roles = [
        role_id
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id).strip()
    ]
    rows = [
        {
            "label": "Admin role",
            "ok": bool(admin_roles),
            "value": (
                ", ".join(f"<@&{role_id}>" for role_id in admin_roles)
                if admin_roles
                else "Not set",
            ),
            "required": True,
        },
        {
            "label": "Submit channel",
            "ok": bool(guild_config.get("submit_channel")),
            "value": channel_display(guild_config.get("submit_channel")),
            "required": True,
        },
        {
            "label": "Submission categories",
            "ok": bool(categories),
            "value": (
                ", ".join(
                    f"`{name}` -> {channel_display(channel_id)}"
                    for name, channel_id in sorted(categories.items())
                )
                if categories
                else "Not set",
            ),
            "required": True,
        },
        {
            "label": "Branding",
            "ok": bool(guild_config.get("brand_name")),
            "value": (
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or "Default SDAC"
            ),
            "required": False,
        },
        {
            "label": "Approval queue",
            "ok": (
                not guild_config.get("approval_enabled")
                or bool(guild_config.get("approval_channel"))
            ),
            "value": (
                f"Enabled in {channel_display(guild_config.get('approval_channel'))}"
                if guild_config.get("approval_enabled")
                else "Disabled",
            ),
            "required": False,
        },
        {
            "label": "Weekly top posts",
            "ok": bool(guild_config.get("daily_top_channel")),
            "value": (
                f"{channel_display(guild_config.get('daily_top_channel'))} "
                f"on {guild_config.get('weekly_top_day', 'sunday').title()} "
                f"at {guild_config.get('daily_top_time_utc', '00:00')}"
            ),
            "required": False,
        },
        {
            "label": "Timezone",
            "ok": bool(guild_config.get("timezone")),
            "value": guild_config.get("timezone", "UTC"),
            "required": False,
        },
        {
            "label": "Game summary channel",
            "ok": bool(guild_config.get("game_summary_channel")),
            "value": channel_display(guild_config.get("game_summary_channel")),
            "required": False,
        },
        {
            "label": "Error channel",
            "ok": bool(guild_config.get("error_channel")),
            "value": channel_display(guild_config.get("error_channel")),
            "required": False,
        },
    ]
    return rows


def setup_wizard_content(guild_config, page=1, notice=""):
    rows = setup_status_rows(guild_config)
    required_rows = [row for row in rows if row["required"]]
    complete_required = sum(1 for row in required_rows if row["ok"])
    page_titles = {
        1: "Basics",
        2: "Channels And Schedule",
        3: "Features And Finish",
    }
    lines = [
        "**SDAC Setup Wizard**",
        f"Page {page} of 3: {page_titles.get(page, 'Setup')}",
        f"Required progress: `{complete_required}/{len(required_rows)}`",
    ]
    if notice:
        lines.extend(["", notice])

    lines.append("")
    lines.append("**Required Setup**")
    for row in required_rows:
        status = "[OK]" if row["ok"] else "[MISSING]"
        lines.append(f"{status} {row['label']}: {row['value']}")

    lines.append("")
    lines.append("**Recommended Setup**")
    for row in rows:
        if row["required"]:
            continue
        status = "[OK]" if row["ok"] else "[OPTIONAL]"
        lines.append(f"{status} {row['label']}: {row['value']}")

    lines.append("")
    if page == 1:
        lines.append(
            "Use the controls below to set an admin role, submit channel, "
            "categories, and approval queue."
        )
    elif page == 2:
        lines.append(
            "Use the controls below to set weekly posts, game summaries, "
            "error notifications, timezone, and weekly schedule."
        )
    else:
        lines.append(
            "Use the controls below to choose enabled features and run a "
            "setup test."
        )
    return "\n".join(lines)[:1900]


def setup_modal_allowed(interaction, owner_id, guild_id):
    return (
        interaction.guild is not None
        and str(interaction.guild_id) == str(guild_id)
        and interaction.user.id == owner_id
        and admin_only(interaction)
    )


async def setup_test_lines(guild, guild_config):
    rows = setup_status_rows(guild_config)
    required_rows = [row for row in rows if row["required"]]
    missing_required = [row["label"] for row in required_rows if not row["ok"]]
    lines = ["**SDAC Setup Test**"]
    if missing_required:
        lines.append("[MISSING] Required setup: " + ", ".join(missing_required))
    else:
        lines.append("[OK] Required setup is complete.")

    try:
        with database() as connection:
            table_names = {
                row["name"]
                for row in connection.execute("""
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                """).fetchall()
            }
            missing_tables = sorted(REQUIRED_TABLES - table_names)
        if missing_tables:
            lines.append("[MISSING] Database tables: " + ", ".join(missing_tables))
        else:
            lines.append(f"[OK] Database schema v{SCHEMA_VERSION} is ready.")
    except sqlite3.Error as error:
        lines.append(f"[MISSING] Database check failed: {error}")

    for directory in (MEDIA_DIR, BACKUP_DIR):
        try:
            ensure_directory_writable(directory)
            lines.append(f"[OK] Writable: `{directory.name}/`")
        except OSError as error:
            lines.append(f"[MISSING] `{directory.name}/` is not writable: {error}")

    channel_ids = configured_channel_ids(guild_config)
    if not channel_ids:
        lines.append("[MISSING] No configured channels were found.")
    seen = set()
    for channel_id in channel_ids:
        channel_key = str(channel_id)
        if channel_key in seen:
            continue
        seen.add(channel_key)
        guild_channel = await resolve_guild_channel(guild, channel_id)
        if guild_channel is None:
            lines.append(f"[MISSING] `{channel_id}` was not found or visible.")
            continue
        summary = bot_permission_summary(guild, guild_channel)
        status = "[MISSING]" if summary.startswith("Missing required") else "[OK]"
        lines.append(f"{status} {guild_channel.mention}: {summary}")

    lines.append(
        "[OK] Slash commands synced."
        if slash_commands_synced
        else "[MISSING] Slash commands have not synced in this process yet."
    )
    public_url = os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN") or ""
    if public_url:
        lines.append(f"[OK] Public URL/domain configured: `{public_url}`")
    else:
        lines.append("[OPTIONAL] Set `SDAC_PUBLIC_URL` or `SDAC_DOMAIN` for links.")
    return lines


def save_setup_test_run(interaction, lines):
    missing_count = sum(1 for line in lines if line.startswith("[MISSING]"))
    status = "passed" if missing_count == 0 else "needs_attention"
    summary = f"{status.replace('_', ' ').title()}; {missing_count} issue(s)."
    with database() as connection:
        connection.execute("""
            INSERT INTO setup_test_runs (
                guild_id, actor_user_id, actor_username, status,
                summary, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            str(interaction.user.id),
            str(interaction.user),
            status,
            summary,
            json.dumps({"lines": lines}, separators=(",", ":")),
            utc_now_iso(),
        ))
    return status, summary


async def diagnostic_lines(interaction):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    lines = await setup_test_lines(interaction.guild, guild_config)
    lines.extend([
        "",
        "**Runtime Diagnostics**",
        f"[OK] Bot user: `{bot.user}`",
        f"[OK] Connected guilds: `{len(bot.guilds)}`",
        f"[OK] Database path: `{DB_FILE}`",
        f"[OK] Config path: `{CONFIG_FILE}`",
        f"[OK] Release: `{os.getenv('SDAC_RELEASE') or 'development'}`",
        (
            "[OK] Discord token is loaded."
            if bool(TOKEN)
            else "[MISSING] Discord token is missing."
        ),
        (
            "[OK] Public URL/domain configured."
            if (os.getenv("SDAC_PUBLIC_URL") or os.getenv("SDAC_DOMAIN"))
            else "[OPTIONAL] Public URL/domain is not configured."
        ),
    ])
    return lines


class SetupCategoryModal(discord.ui.Modal):
    def __init__(self, owner_id, guild_id, channel_id, channel_mention):
        super().__init__(title="Add Setup Category")
        self.owner_id = owner_id
        self.guild_id = str(guild_id)
        self.channel_id = int(channel_id)
        self.channel_mention = channel_mention
        self.category_input = discord.ui.TextInput(
            label="Category name",
            placeholder="screenshots, clips, memes",
            max_length=50,
        )
        self.add_item(self.category_input)

    async def on_submit(self, interaction):
        if not setup_modal_allowed(interaction, self.owner_id, self.guild_id):
            await interaction.response.send_message(
                "Only the admin who opened this setup wizard can use this modal.",
                ephemeral=True,
            )
            return

        category = clean_category_name(str(self.category_input.value))
        if not category:
            await interaction.response.send_message(
                "Category name cannot be empty.",
                ephemeral=True,
            )
            return

        guild_config = get_guild_config(interaction.guild_id)
        guild_config.setdefault("categories", {})[category] = self.channel_id
        save_config(config)
        with database() as connection:
            connection.execute("""
                INSERT INTO category_history (
                    guild_id, action, category, channel_id,
                    admin_user_id, admin_username, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(interaction.guild_id),
                "setup:set",
                category,
                str(self.channel_id),
                str(interaction.user.id),
                str(interaction.user),
                utc_now_iso(),
            ))
            add_admin_audit_log(
                connection,
                interaction.guild_id,
                "setup_set_category",
                interaction.user.id,
                interaction.user,
                "category",
                category,
                f"Channel {self.channel_id}.",
            )
        await interaction.response.send_message(
            setup_wizard_content(
                guild_config,
                page=1,
                notice=(
                    f"Category `{category}` now posts to "
                    f"{self.channel_mention}."
                ),
            ),
            view=SetupWizardView(interaction.user.id, interaction.guild_id, 1),
            ephemeral=True,
        )


class SetupScheduleModal(discord.ui.Modal):
    def __init__(self, owner_id, guild_id):
        super().__init__(title="Weekly Schedule")
        self.owner_id = owner_id
        self.guild_id = str(guild_id)
        self.weekday_input = discord.ui.TextInput(
            label="Weekly day",
            placeholder="sunday",
            default="sunday",
            max_length=20,
        )
        self.time_input = discord.ui.TextInput(
            label="Weekly time",
            placeholder="00:00",
            default="00:00",
            max_length=5,
        )
        self.add_item(self.weekday_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction):
        if not setup_modal_allowed(interaction, self.owner_id, self.guild_id):
            await interaction.response.send_message(
                "Only the admin who opened this setup wizard can use this modal.",
                ephemeral=True,
            )
            return

        day = normalize_weekday(str(self.weekday_input.value))
        if day is None:
            await interaction.response.send_message(
                "Choose a valid weekday, like `sunday` or `monday`.",
                ephemeral=True,
            )
            return
        raw_time = str(self.time_input.value or "").strip()
        if not re.match(r"^\d{2}:\d{2}$", raw_time):
            await interaction.response.send_message(
                "Time must be in `HH:MM` format.",
                ephemeral=True,
            )
            return
        hour, minute = [int(part) for part in raw_time.split(":")]
        if hour > 23 or minute > 59:
            await interaction.response.send_message(
                "Time must be between `00:00` and `23:59`.",
                ephemeral=True,
            )
            return

        guild_config = get_guild_config(interaction.guild_id)
        guild_config["weekly_top_day"] = day
        guild_config["daily_top_time_utc"] = raw_time
        save_config(config)
        audit_interaction(
            interaction,
            "setup_set_weekly_schedule",
            "schedule",
            raw_time,
            f"Weekly top set to {day} {raw_time}.",
        )
        await interaction.response.send_message(
            setup_wizard_content(
                guild_config,
                page=2,
                notice=f"Weekly schedule set to `{day.title()}` at `{raw_time}`.",
            ),
            view=SetupWizardView(interaction.user.id, interaction.guild_id, 2),
            ephemeral=True,
        )


class SetupTimezoneModal(discord.ui.Modal):
    def __init__(self, owner_id, guild_id):
        super().__init__(title="Server Timezone")
        self.owner_id = owner_id
        self.guild_id = str(guild_id)
        self.timezone_input = discord.ui.TextInput(
            label="IANA timezone",
            placeholder="America/New_York",
            default="UTC",
            max_length=80,
        )
        self.add_item(self.timezone_input)

    async def on_submit(self, interaction):
        if not setup_modal_allowed(interaction, self.owner_id, self.guild_id):
            await interaction.response.send_message(
                "Only the admin who opened this setup wizard can use this modal.",
                ephemeral=True,
            )
            return

        timezone_name = str(self.timezone_input.value or "").strip()
        try:
            selected_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            await interaction.response.send_message(
                "That timezone was not found. Use an IANA name like "
                "`America/Los_Angeles`, `America/New_York`, or `UTC`.",
                ephemeral=True,
            )
            return

        guild_config = get_guild_config(interaction.guild_id)
        guild_config["timezone"] = timezone_name
        save_config(config)
        current_time = datetime.now(selected_timezone).strftime("%Y-%m-%d %H:%M")
        audit_interaction(
            interaction,
            "setup_set_timezone",
            "timezone",
            timezone_name,
            f"Current configured local time was {current_time}.",
        )
        await interaction.response.send_message(
            setup_wizard_content(
                guild_config,
                page=2,
                notice=(
                    f"Timezone set to `{timezone_name}`. Current time there "
                    f"is `{current_time}`."
                ),
            ),
            view=SetupWizardView(interaction.user.id, interaction.guild_id, 2),
            ephemeral=True,
        )


class SetupBrandingModal(discord.ui.Modal):
    def __init__(self, owner_id, guild_id):
        super().__init__(title="Server Branding")
        self.owner_id = owner_id
        self.guild_id = str(guild_id)
        guild_config = get_guild_config(guild_id, create=False)
        self.name_input = discord.ui.TextInput(
            label="Display name",
            placeholder="SDAC, Free The Fishies, etc.",
            default=(
                guild_config.get("brand_name")
                or guild_config.get("guild_name")
                or ""
            )[:80],
            max_length=80,
            required=False,
        )
        self.accent_input = discord.ui.TextInput(
            label="Accent color",
            placeholder="#7c9cff",
            default=(guild_config.get("brand_accent") or "#7c9cff")[:16],
            max_length=16,
            required=False,
        )
        self.logo_input = discord.ui.TextInput(
            label="Logo URL",
            placeholder="https://example.com/logo.png",
            default=(guild_config.get("brand_logo_url") or "")[:200],
            max_length=200,
            required=False,
        )
        self.add_item(self.name_input)
        self.add_item(self.accent_input)
        self.add_item(self.logo_input)

    async def on_submit(self, interaction):
        if not setup_modal_allowed(interaction, self.owner_id, self.guild_id):
            await interaction.response.send_message(
                "Only the admin who opened this setup wizard can use this modal.",
                ephemeral=True,
            )
            return

        accent = str(self.accent_input.value or "").strip() or "#7c9cff"
        if not re.match(r"^#[0-9A-Fa-f]{6}$", accent):
            await interaction.response.send_message(
                "Accent color must be a hex color like `#7c9cff`.",
                ephemeral=True,
            )
            return

        guild_config = get_guild_config(interaction.guild_id)
        guild_config["brand_name"] = str(self.name_input.value or "").strip()[:80]
        guild_config["brand_accent"] = accent
        guild_config["brand_logo_url"] = str(self.logo_input.value or "").strip()[:200]
        save_config(config)
        audit_interaction(
            interaction,
            "setup_set_branding",
            "guild",
            interaction.guild_id,
            "Updated server branding from Discord setup wizard.",
        )
        await interaction.response.send_message(
            setup_wizard_content(
                guild_config,
                page=3,
                notice="Server branding saved.",
            ),
            view=SetupWizardView(interaction.user.id, interaction.guild_id, 3),
            ephemeral=True,
        )


class SetupRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Step 1: choose an SDAC admin role",
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction):
        if not await self.view.ensure_allowed(interaction):
            return
        role = self.values[0]
        guild_config = get_guild_config(interaction.guild_id)
        role_ids = {
            str(role_id)
            for role_id in guild_config.get("admin_role_ids", [])
            if str(role_id).strip()
        }
        role_ids.add(str(role.id))
        guild_config["admin_role_ids"] = sorted(role_ids)
        save_config(config)
        audit_interaction(
            interaction,
            "setup_set_admin_role",
            "role",
            role.id,
            f"Added SDAC admin role {role.name}.",
        )
        await self.view.refresh(
            interaction,
            f"{role.mention} can now manage SDAC.",
        )


class SetupChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup_action, placeholder, row):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            row=row,
        )
        self.setup_action = setup_action

    async def callback(self, interaction):
        if not await self.view.ensure_allowed(interaction):
            return
        channel = self.values[0]
        guild_config = get_guild_config(interaction.guild_id)

        if self.setup_action == "category":
            await interaction.response.send_modal(
                SetupCategoryModal(
                    interaction.user.id,
                    interaction.guild_id,
                    channel.id,
                    channel.mention,
                )
            )
            return

        updates = {
            "submit": ("submit_channel", "setup_set_submit_channel"),
            "approval": ("approval_channel", "setup_set_approval_channel"),
            "weekly": ("daily_top_channel", "setup_set_weekly_channel"),
            "summary": ("game_summary_channel", "setup_set_game_summary_channel"),
            "error": ("error_channel", "setup_set_error_channel"),
        }
        config_key, audit_action = updates[self.setup_action]
        guild_config[config_key] = channel.id
        if self.setup_action == "approval":
            guild_config["approval_enabled"] = True
        save_config(config)
        audit_interaction(
            interaction,
            audit_action,
            "channel",
            channel.id,
            f"Set by Discord setup wizard.",
        )
        await self.view.refresh(
            interaction,
            f"{channel.mention} saved for `{config_key}`.",
        )


class SetupFeatureSelect(discord.ui.Select):
    def __init__(self, guild_config):
        features = guild_config.get("features") or {}
        options = [
            discord.SelectOption(
                label=label,
                value=key,
                default=features.get(key, DEFAULT_FEATURES[key]),
            )
            for key, label in FEATURE_LABELS.items()
        ]
        super().__init__(
            placeholder="Select features that should be enabled",
            min_values=0,
            max_values=len(options),
            options=options,
            row=0,
        )

    async def callback(self, interaction):
        if not await self.view.ensure_allowed(interaction):
            return
        enabled_features = set(self.values)
        guild_config = get_guild_config(interaction.guild_id)
        features = guild_config.setdefault("features", {})
        for feature_key in DEFAULT_FEATURES:
            features[feature_key] = feature_key in enabled_features
        save_config(config)
        audit_interaction(
            interaction,
            "setup_set_features",
            "features",
            "",
            "Updated feature toggles from Discord setup wizard.",
        )
        await self.view.refresh(interaction, "Feature toggles saved.")


class SetupPresetSelect(discord.ui.Select):
    def __init__(self, guild_config):
        options = []
        selected_preset = guild_config.get("setup_preset") or ""
        for preset_key, preset in SETUP_PRESETS.items():
            options.append(discord.SelectOption(
                label=preset["label"],
                value=preset_key,
                description=preset["description"],
                default=selected_preset == preset_key,
            ))
        super().__init__(
            placeholder="Apply a setup preset",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction):
        if not await self.view.ensure_allowed(interaction):
            return
        preset_key = self.values[0]
        preset = SETUP_PRESETS.get(preset_key)
        if not preset:
            await interaction.response.send_message(
                "Unknown setup preset.",
                ephemeral=True,
            )
            return
        guild_config = get_guild_config(interaction.guild_id)
        guild_config["setup_preset"] = preset_key
        guild_config["approval_enabled"] = bool(preset["approval_enabled"])
        features = guild_config.setdefault("features", {})
        for feature_key in DEFAULT_FEATURES:
            features[feature_key] = bool(
                preset["features"].get(feature_key, DEFAULT_FEATURES[feature_key])
            )
        save_config(config)
        audit_interaction(
            interaction,
            "setup_apply_preset",
            "preset",
            preset_key,
            f"Applied setup preset {preset['label']}.",
        )
        await self.view.refresh(
            interaction,
            f"`{preset['label']}` preset applied. Review channels before finishing.",
        )


class SetupButton(discord.ui.Button):
    def __init__(self, label, setup_action, style=discord.ButtonStyle.secondary, row=4):
        super().__init__(label=label, style=style, row=row)
        self.setup_action = setup_action

    async def callback(self, interaction):
        if not await self.view.ensure_allowed(interaction):
            return
        await self.view.handle_button(interaction, self.setup_action)


class SetupWizardView(discord.ui.View):
    def __init__(self, owner_id, guild_id, page=1):
        super().__init__(timeout=900)
        self.owner_id = int(owner_id)
        self.guild_id = str(guild_id)
        self.page = max(1, min(3, int(page or 1)))
        guild_config = get_guild_config(guild_id, create=False)

        if self.page == 1:
            self.add_item(SetupRoleSelect())
            self.add_item(SetupChannelSelect(
                "submit",
                "Step 2: choose the submission channel",
                1,
            ))
            self.add_item(SetupChannelSelect(
                "category",
                "Step 3: choose a category repost channel",
                2,
            ))
            self.add_item(SetupChannelSelect(
                "approval",
                "Optional: choose approval channel and enable approval",
                3,
            ))
            self.add_item(SetupButton("Disable Approval", "disable_approval", row=4))
            self.add_item(SetupButton("Next", "next", discord.ButtonStyle.primary, 4))
        elif self.page == 2:
            self.add_item(SetupChannelSelect(
                "weekly",
                "Optional: choose weekly top channel",
                0,
            ))
            self.add_item(SetupChannelSelect(
                "summary",
                "Optional: choose guessing game summary channel",
                1,
            ))
            self.add_item(SetupChannelSelect(
                "error",
                "Optional: choose error notification channel",
                2,
            ))
            self.add_item(SetupButton("Weekly Schedule", "weekly_schedule", row=3))
            self.add_item(SetupButton("Timezone", "timezone", row=3))
            self.add_item(SetupButton("Back", "back", row=4))
            self.add_item(SetupButton("Next", "next", discord.ButtonStyle.primary, 4))
        else:
            self.add_item(SetupFeatureSelect(guild_config))
            self.add_item(SetupPresetSelect(guild_config))
            self.add_item(SetupButton("Branding", "branding", row=2))
            self.add_item(SetupButton("Permission Check", "permission_check", row=2))
            self.add_item(SetupButton("Full Setup Test", "setup_test", row=3))
            self.add_item(SetupButton("Refresh", "refresh", row=3))
            self.add_item(SetupButton("Back", "back", row=4))
            self.add_item(SetupButton("Finish", "finish", discord.ButtonStyle.success, 4))

    async def ensure_allowed(self, interaction):
        if not interaction.guild or str(interaction.guild_id) != self.guild_id:
            await interaction.response.send_message(
                "This setup wizard belongs to another server.",
                ephemeral=True,
            )
            return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the admin who opened this setup wizard can use these controls.",
                ephemeral=True,
            )
            return False
        if not admin_only(interaction):
            await interaction.response.send_message(
                "Only admins can use this setup wizard.",
                ephemeral=True,
            )
            return False
        return True

    async def refresh(self, interaction, notice=""):
        guild_config = get_guild_config(interaction.guild_id, create=False)
        await interaction.response.edit_message(
            content=setup_wizard_content(guild_config, self.page, notice),
            view=SetupWizardView(self.owner_id, self.guild_id, self.page),
        )

    async def handle_button(self, interaction, action):
        if action == "next":
            page = min(3, self.page + 1)
            guild_config = get_guild_config(interaction.guild_id, create=False)
            await interaction.response.edit_message(
                content=setup_wizard_content(guild_config, page),
                view=SetupWizardView(self.owner_id, self.guild_id, page),
            )
            return
        if action == "back":
            page = max(1, self.page - 1)
            guild_config = get_guild_config(interaction.guild_id, create=False)
            await interaction.response.edit_message(
                content=setup_wizard_content(guild_config, page),
                view=SetupWizardView(self.owner_id, self.guild_id, page),
            )
            return
        if action == "refresh":
            await self.refresh(interaction, "Setup status refreshed.")
            return
        if action == "disable_approval":
            guild_config = get_guild_config(interaction.guild_id)
            guild_config["approval_enabled"] = False
            save_config(config)
            audit_interaction(
                interaction,
                "setup_disable_approval",
                "approval",
                "disabled",
                "Disabled from Discord setup wizard.",
            )
            await self.refresh(interaction, "Approval queue disabled.")
            return
        if action == "weekly_schedule":
            await interaction.response.send_modal(
                SetupScheduleModal(interaction.user.id, interaction.guild_id)
            )
            return
        if action == "timezone":
            await interaction.response.send_modal(
                SetupTimezoneModal(interaction.user.id, interaction.guild_id)
            )
            return
        if action == "branding":
            await interaction.response.send_modal(
                SetupBrandingModal(interaction.user.id, interaction.guild_id)
            )
            return
        if action == "permission_check":
            await self.send_permission_check(interaction)
            return
        if action == "setup_test":
            await self.send_setup_test(interaction)
            return
        if action == "finish":
            guild_config = get_guild_config(interaction.guild_id, create=False)
            await interaction.response.edit_message(
                content=(
                    setup_wizard_content(
                        guild_config,
                        self.page,
                        "Setup wizard closed. Run `/setup` any time to reopen it.",
                    )
                ),
                view=None,
            )

    async def send_permission_check(self, interaction):
        guild_config = get_guild_config(interaction.guild_id, create=False)
        channel_ids = configured_channel_ids(guild_config)
        if not channel_ids and isinstance(interaction.channel, discord.TextChannel):
            channel_ids.append(interaction.channel.id)

        lines = ["**SDAC Permission Check**"]
        if not channel_ids:
            lines.append("No configured text channels were found.")

        seen = set()
        for channel_id in channel_ids:
            if str(channel_id) in seen:
                continue
            seen.add(str(channel_id))
            guild_channel = await resolve_guild_channel(
                interaction.guild,
                channel_id,
            )
            if guild_channel is None:
                lines.append(
                    f"- `{channel_id}`: channel was not found or is not visible."
                )
                continue
            summary = bot_permission_summary(interaction.guild, guild_channel)
            lines.append(f"- {guild_channel.mention}: {summary}")

        audit_interaction(
            interaction,
            "setup_check_permissions",
            "guild",
            interaction.guild_id,
            f"Checked {len(seen)} channel(s).",
        )
        await interaction.response.send_message(
            "\n".join(lines)[:1900],
            ephemeral=True,
        )

    async def send_setup_test(self, interaction):
        guild_config = get_guild_config(interaction.guild_id, create=False)
        lines = await setup_test_lines(interaction.guild, guild_config)
        status, summary = save_setup_test_run(interaction, lines)
        audit_interaction(
            interaction,
            "setup_full_test",
            "guild",
            interaction.guild_id,
            f"Ran full setup test from Discord setup wizard: {summary}",
        )
        lines.insert(1, f"Saved result: `{status}`.")
        await interaction.response.send_message(
            "\n".join(lines)[:1900],
            ephemeral=True,
        )


@tree.command(name="commands", description="Show SDAC user commands")
@app_commands.guild_only()
async def commands_list(interaction):
    await send_command_help_menu(
        interaction,
        "SDAC User Commands",
        USER_COMMAND_GROUPS,
        "These commands are available to regular users. Use the menu to switch sections.",
    )


@tree.command(name="admincommands", description="Show SDAC admin commands")
@app_commands.guild_only()
async def admincommands(interaction):
    if not await require_admin(interaction):
        return
    await send_command_help_menu(
        interaction,
        "SDAC Admin Commands",
        ADMIN_COMMAND_GROUPS,
        "These commands require SDAC admin access. Use the menu to switch sections.",
    )


@tree.command(name="setup", description="Open the guided SDAC setup wizard")
@app_commands.guild_only()
async def setup(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    audit_interaction(
        interaction,
        "open_setup_wizard",
        "guild",
        interaction.guild_id,
        "Opened Discord setup wizard.",
    )
    await interaction.response.send_message(
        setup_wizard_content(guild_config, page=1),
        view=SetupWizardView(interaction.user.id, interaction.guild_id, 1),
        ephemeral=True,
    )


@tree.command(name="setupstatus", description="Show SDAC setup progress")
@app_commands.guild_only()
async def setupstatus(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    await interaction.response.send_message(
        setup_wizard_content(
            guild_config,
            page=1,
            notice="Run `/setup` to change these settings with the wizard.",
        ),
        ephemeral=True,
    )


@tree.command(name="setupchecklist", description="Show SDAC setup and production checklist")
@app_commands.guild_only()
async def setupchecklist(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    lines = await setup_test_lines(interaction.guild, guild_config)
    backup = {
        **DEFAULT_GUILD_EXTERNAL_BACKUP,
        **(guild_config.get("external_backup") or {}),
    }
    digest = guild_config.get("notification_digest") or {}
    lines.extend([
        "",
        "**Production Extras**",
        (
            "OK: Per-server backup remote configured."
            if backup.get("enabled") and backup.get("remote")
            else "WARN: No per-server backup remote configured. Run `/backupguide` and `/backupsetup`."
        ),
        (
            "OK: Backup zip archives are enabled."
            if backup.get("zip_backups", True)
            else "WARN: Backup zip archives are disabled."
        ),
        (
            "OK: Admin notification digest configured."
            if digest.get("enabled") and digest.get("channel_id")
            else "WARN: Admin notification digest is not configured. Run `/setdigest`."
        ),
        f"Release: `{os.getenv('SDAC_RELEASE') or 'development'}`",
        f"Update channel: `{os.getenv('SDAC_RELEASE_TAG') or 'latest-official'}`",
    ])
    status, summary = save_setup_test_run(interaction, lines)
    audit_interaction(
        interaction,
        "run_setup_checklist",
        "guild",
        interaction.guild_id,
        f"Ran setup checklist: {summary}",
    )
    lines.insert(1, f"Saved checklist result: `{status}`.")
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="setuptest", description="Run a full SDAC setup test")
@app_commands.guild_only()
async def setuptest(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    lines = await setup_test_lines(interaction.guild, guild_config)
    status, summary = save_setup_test_run(interaction, lines)
    audit_interaction(
        interaction,
        "run_setup_test",
        "guild",
        interaction.guild_id,
        f"Ran full setup test from slash command: {summary}",
    )
    lines.insert(1, f"Saved result: `{status}`.")
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="diagnose", description="Run SDAC setup and runtime diagnostics")
@app_commands.guild_only()
async def diagnose(interaction):
    if not await require_admin(interaction):
        return
    lines = await diagnostic_lines(interaction)
    status, summary = save_setup_test_run(interaction, lines)
    audit_interaction(
        interaction,
        "run_diagnostics",
        "guild",
        interaction.guild_id,
        f"Ran diagnostics: {summary}",
    )
    lines.insert(1, f"Saved diagnostic result: `{status}`.")
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="repository", description="Show the SDAC GitHub repositories")
@app_commands.guild_only()
async def repository(interaction):
    if not await require_admin(interaction):
        return
    configured_repo = RELEASE_REPO
    original_repo = ORIGINAL_REPO
    lines = [
        "**SDAC Repositories**",
        f"User/fork repository: https://github.com/{configured_repo}",
        f"Original repository: https://github.com/{original_repo}",
        f"Current update channel: `{os.getenv('SDAC_RELEASE_TAG') or 'latest-official'}`",
        f"Current release: `{os.getenv('SDAC_RELEASE') or 'development'}`",
    ]
    if configured_repo == original_repo:
        lines.append("This install is using the original repository directly.")
    else:
        lines.append("This install is configured to update from a fork.")
    audit_interaction(
        interaction,
        "show_repository",
        "guild",
        interaction.guild_id,
        f"Displayed repositories: user={configured_repo}; original={original_repo}.",
    )
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="setbranding", description="Set this server's SDAC branding")
@app_commands.guild_only()
@app_commands.describe(
    name="Display name for this server on the dashboard",
    accent="#RRGGBB accent color",
    logo_url="Optional logo URL",
)
async def setbranding(
    interaction,
    name: str,
    accent: str = "#7c9cff",
    logo_url: str = "",
):
    if not await require_admin(interaction):
        return
    accent = (accent or "#7c9cff").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", accent):
        await interaction.response.send_message(
            "Accent color must be a hex color like `#7c9cff`.",
            ephemeral=True,
        )
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["brand_name"] = (name or "").strip()[:80]
    guild_config["brand_accent"] = accent
    guild_config["brand_logo_url"] = (logo_url or "").strip()[:200]
    save_config(config)
    audit_interaction(
        interaction,
        "set_branding",
        "guild",
        interaction.guild_id,
        "Updated per-server branding.",
    )
    await interaction.response.send_message(
        f"Branding saved as `{guild_config['brand_name']}` with `{accent}`.",
        ephemeral=True,
    )


@tree.command(name="setnotification", description="Route SDAC admin alerts to a channel")
@app_commands.guild_only()
@app_commands.describe(
    event="Alert type to route",
    channel="Channel that should receive this alert type",
    enabled="Disable to pause this alert route",
)
@app_commands.choices(event=NOTIFICATION_EVENT_CHOICES)
async def setnotification(
    interaction,
    event: app_commands.Choice[str],
    channel: Optional[discord.TextChannel] = None,
    enabled: bool = True,
):
    if not await require_admin(interaction):
        return
    if enabled and channel is None:
        await interaction.response.send_message(
            "Choose a channel when enabling a notification route.",
            ephemeral=True,
        )
        return
    now = utc_now_iso()
    with database() as connection:
        connection.execute("""
            INSERT INTO admin_notifications (
                guild_id, event_key, channel_id, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, event_key) DO UPDATE SET
                channel_id = excluded.channel_id,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
        """, (
            str(interaction.guild_id),
            event.value,
            str(channel.id) if channel else "",
            1 if enabled else 0,
            now,
            now,
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "set_notification_route",
            interaction.user.id,
            interaction.user,
            "notification",
            event.value,
            (
                f"{event.value} -> {channel.id if channel else 'disabled'}; "
                f"enabled={enabled}."
            ),
        )
    if enabled:
        message = (
            f"`{event.name}` notifications will go to {channel.mention}."
        )
    else:
        message = f"`{event.name}` notifications are disabled."
    await interaction.response.send_message(message, ephemeral=True)


@tree.command(name="setsubmit", description="Set the SDAC submission channel")
@app_commands.guild_only()
@app_commands.describe(channel="Channel where users can submit")
async def setsubmit(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["submit_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_submit_channel",
        "channel",
        channel.id,
        f"Submit channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Submit channel set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearsubmit", description="Clear the SDAC submission channel")
@app_commands.guild_only()
async def clearsubmit(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["submit_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_submit_channel",
        "channel",
        "",
        "Submit channel cleared.",
    )
    await interaction.response.send_message(
        "Submit channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setcategory", description="Create or update an SDAC category")
@app_commands.guild_only()
@app_commands.describe(category="Category name", channel="Category repost channel")
async def setcategory(
    interaction,
    category: str,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return
    category = clean_category_name(category)
    if not category:
        await interaction.response.send_message(
            "Category name cannot be empty.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["categories"][category] = channel.id
    save_config(config)

    with database() as connection:
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            "set",
            category,
            str(channel.id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "set_category",
            interaction.user.id,
            interaction.user,
            "category",
            category,
            f"Channel {channel.id}.",
        )

    await interaction.response.send_message(
        f"Category `{category}` set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="editcategory", description="Rename or move an SDAC category")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
@app_commands.describe(
    category="Existing category",
    new_name="New category name",
    channel="Optional new repost channel",
)
async def editcategory(
    interaction,
    category: str,
    new_name: str,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return

    category = clean_category_name(category)
    new_name = clean_category_name(new_name)
    guild_config = get_guild_config(interaction.guild_id)
    categories = guild_config["categories"]
    if category not in categories:
        await interaction.response.send_message(
            f"Category `{category}` does not exist.",
            ephemeral=True,
        )
        return
    if not new_name:
        await interaction.response.send_message(
            "New category name cannot be empty.",
            ephemeral=True,
        )
        return
    if new_name != category and new_name in categories:
        await interaction.response.send_message(
            f"Category `{new_name}` already exists.",
            ephemeral=True,
        )
        return

    channel_id = channel.id if channel else categories[category]
    categories.pop(category)
    categories[new_name] = channel_id
    save_config(config)

    with database() as connection:
        connection.execute("""
            UPDATE submissions
            SET category = ?
            WHERE guild_id = ? AND category = ?
        """, (new_name, str(interaction.guild_id), category))
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            f"edit:{category}",
            new_name,
            str(channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "edit_category",
            interaction.user.id,
            interaction.user,
            "category",
            new_name,
            f"Renamed from {category}; channel {channel_id}.",
        )

    await interaction.response.send_message(
        f"Category `{category}` changed to `{new_name}`.",
        ephemeral=True,
    )


@tree.command(name="deletecategory", description="Delete an SDAC category")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
async def deletecategory(interaction, category: str):
    if not await require_admin(interaction):
        return
    category = clean_category_name(category)
    guild_config = get_guild_config(interaction.guild_id)
    if category not in guild_config["categories"]:
        await interaction.response.send_message(
            f"Category `{category}` does not exist.",
            ephemeral=True,
        )
        return

    old_channel_id = guild_config["categories"].pop(category)
    save_config(config)
    with database() as connection:
        connection.execute("""
            INSERT INTO category_history (
                guild_id, action, category, channel_id,
                admin_user_id, admin_username, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            "delete",
            category,
            str(old_channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "delete_category",
            interaction.user.id,
            interaction.user,
            "category",
            category,
            f"Removed channel {old_channel_id}.",
        )

    await interaction.response.send_message(
        f"Deleted category `{category}`. Existing submissions remain.",
        ephemeral=True,
    )


@tree.command(name="categories", description="List SDAC configuration")
@app_commands.guild_only()
async def categories(interaction):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    submit_channel_id = guild_config.get("submit_channel")
    submit_channel = (
        bot.get_channel(submit_channel_id) if submit_channel_id else None
    )
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    lines = [
        "**SDAC Configuration**",
        f"Submit channel: {submit_channel.mention if submit_channel else 'Not set'}",
        f"Timezone: `{timezone_name}`",
        f"Weekly day: {guild_config.get('weekly_top_day', 'sunday').title()}",
        f"Weekly time: {guild_config['daily_top_time_utc']} {timezone_name}",
        f"Approval: {'Enabled' if guild_config['approval_enabled'] else 'Disabled'}",
        "",
    ]
    if not guild_config["categories"]:
        lines.append("No categories are set.")
    else:
        lines.append("**Categories:**")
        for category, channel_id in sorted(
            guild_config["categories"].items()
        ):
            channel = bot.get_channel(channel_id)
            destination = (
                channel.mention
                if channel
                else f"Unknown channel `{channel_id}`"
            )
            lines.append(f"- `{category}` -> {destination}")
    await interaction.response.send_message(
        "\n".join(lines),
        ephemeral=True,
    )


@tree.command(name="settings", description="Show SDAC bot settings")
@app_commands.guild_only()
async def settings(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    await interaction.response.send_message(
        "\n".join(settings_lines(guild_config)),
        ephemeral=True,
    )


@tree.command(name="setfeature", description="Enable or disable an SDAC feature")
@app_commands.guild_only()
@app_commands.choices(feature=FEATURE_CHOICES)
@app_commands.describe(
    feature="Feature to change for this Discord server",
    enabled="Whether the feature should be enabled",
)
async def setfeature(
    interaction,
    feature: app_commands.Choice[str],
    enabled: bool,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config.setdefault("features", {})[feature.value] = enabled
    save_config(config)
    audit_interaction(
        interaction,
        "set_feature",
        "feature",
        feature.value,
        f"{feature.name} set to {'enabled' if enabled else 'disabled'}.",
    )
    await interaction.response.send_message(
        f"{feature.name} is now {'enabled' if enabled else 'disabled'}.",
        ephemeral=True,
    )


@tree.command(name="sdacpanic", description="Pause or resume SDAC activity in this server")
@app_commands.guild_only()
@app_commands.describe(
    paused="True pauses submissions, games, and guesses. False resumes them.",
    reason="Optional reason shown to users while paused",
)
async def sdacpanic(
    interaction,
    paused: bool = True,
    reason: str = "",
):
    if not await require_admin(interaction):
        return
    reason = (reason or "").strip()[:300]
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["emergency_paused"] = bool(paused)
    guild_config["emergency_reason"] = reason if paused else ""
    save_config(config)
    audit_interaction(
        interaction,
        "sdac_panic_pause" if paused else "sdac_panic_resume",
        "guild",
        interaction.guild_id,
        reason or ("Paused SDAC." if paused else "Resumed SDAC."),
    )
    await interaction.response.send_message(
        (
            f"SDAC is now paused for this server. Reason: {reason or 'No reason provided.'}"
            if paused
            else "SDAC is resumed for this server."
        ),
        ephemeral=True,
    )


@tree.command(name="checkpermissions", description="Check SDAC bot channel permissions")
@app_commands.guild_only()
@app_commands.describe(channel="Optional channel to check")
async def checkpermissions(
    interaction,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id, create=False)
    channel_ids = configured_channel_ids(guild_config)
    if channel is not None:
        channel_ids.insert(0, channel.id)
    if not channel_ids and isinstance(interaction.channel, discord.TextChannel):
        channel_ids.append(interaction.channel.id)

    lines = ["**SDAC Permission Check**"]
    if not channel_ids:
        lines.append("No configured text channels were found.")

    seen = set()
    for channel_id in channel_ids:
        if str(channel_id) in seen:
            continue
        seen.add(str(channel_id))
        guild_channel = await resolve_guild_channel(
            interaction.guild,
            channel_id,
        )
        if guild_channel is None:
            lines.append(
                f"- `{channel_id}`: channel was not found or is not visible."
            )
            continue
        summary = bot_permission_summary(interaction.guild, guild_channel)
        lines.append(f"- {guild_channel.mention}: {summary}")

    audit_interaction(
        interaction,
        "check_permissions",
        "guild",
        interaction.guild_id,
        f"Checked {len(seen)} channel(s).",
    )
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="repairpermissions", description="Show missing SDAC bot permissions and repair link")
@app_commands.guild_only()
async def repairpermissions(interaction):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id, create=False)
    channel_ids = configured_channel_ids(guild_config)
    if not channel_ids and isinstance(interaction.channel, discord.TextChannel):
        channel_ids.append(interaction.channel.id)

    required_permission_integer = os.getenv("SDAC_BOT_PERMISSIONS", "274878221376")
    lines = [
        "**SDAC Permission Repair Preview**",
        "This command does not change permissions by itself. It previews what SDAC needs.",
        f"Invite scopes: `bot applications.commands`",
        f"Permissions integer: `{required_permission_integer}`",
        "",
        "**Channel Checks**",
    ]
    missing_count = 0
    if not channel_ids:
        lines.append("No configured channels are set yet. Run `/setup` first.")

    seen = set()
    for channel_id in channel_ids:
        if str(channel_id) in seen:
            continue
        seen.add(str(channel_id))
        guild_channel = await resolve_guild_channel(
            interaction.guild,
            channel_id,
        )
        if guild_channel is None:
            missing_count += 1
            lines.append(
                f"- `{channel_id}`: I cannot see this channel. Check View Channel."
            )
            continue
        summary = bot_permission_summary(interaction.guild, guild_channel)
        if summary != "OK":
            missing_count += 1
        lines.append(f"- {guild_channel.mention}: {summary}")

    invite_url = bot_invite_url()
    lines.append("")
    if missing_count:
        lines.append(
            "Recommended fix: edit the channel/role overwrite for the bot, "
            "then rerun `/repairpermissions`. If guild-level permissions are "
            "missing, re-authorize the bot with the link below."
        )
    else:
        lines.append("No missing SDAC channel permissions were found.")
    if invite_url:
        lines.append(f"Re-authorize link: {invite_url}")

    audit_interaction(
        interaction,
        "repair_permissions",
        "guild",
        interaction.guild_id,
        f"Checked {len(seen)} channel(s); {missing_count} issue(s).",
    )
    await interaction.response.send_message(
        "\n".join(lines)[:1900],
        ephemeral=True,
    )


@tree.command(name="setweeklychannel", description="Set weekly top channel")
@app_commands.guild_only()
async def setweeklychannel(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_weekly_channel",
        "channel",
        channel.id,
        f"Weekly top channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Weekly top channel set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearweeklychannel", description="Clear weekly top channel")
@app_commands.guild_only()
async def clearweeklychannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_weekly_channel",
        "channel",
        "",
        "Weekly top channel cleared.",
    )
    await interaction.response.send_message(
        "Weekly top channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setweeklytime", description="Set weekly top posting time")
@app_commands.guild_only()
@app_commands.describe(
    hour="Hour from 0 to 23 in the configured timezone",
    minute="Minute from 0 to 59 in the configured timezone",
)
async def setweeklytime(interaction, hour: app_commands.Range[int, 0, 23], minute: app_commands.Range[int, 0, 59] = 0):
    if not await require_admin(interaction):
        return
    value = f"{hour:02d}:{minute:02d}"
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_time_utc"] = value
    save_config(config)
    timezone_name = guild_config.get("timezone", DEFAULT_GUILD_CONFIG["timezone"])
    audit_interaction(
        interaction,
        "set_weekly_time",
        "schedule",
        value,
        f"Weekly top time set in {timezone_name}.",
    )
    await interaction.response.send_message(
        f"Weekly top time set to `{value}` in `{timezone_name}`.",
        ephemeral=True,
    )


@tree.command(name="setweeklyday", description="Set weekly top posting day")
@app_commands.guild_only()
@app_commands.choices(day=WEEKDAY_CHOICES)
@app_commands.describe(day="Day of the week for weekly top posts")
async def setweeklyday(interaction, day: str):
    if not await require_admin(interaction):
        return
    day = normalize_weekday(day)
    if day is None:
        await interaction.response.send_message(
            "Choose a valid weekday.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["weekly_top_day"] = day
    save_config(config)
    audit_interaction(
        interaction,
        "set_weekly_day",
        "schedule",
        day,
        f"Weekly top day set to {day}.",
    )
    await interaction.response.send_message(
        f"Weekly top day set to `{day.title()}`.",
        ephemeral=True,
    )


@tree.command(name="settimezone", description="Set the SDAC server timezone")
@app_commands.guild_only()
@app_commands.describe(
    timezone_name="IANA timezone name, for example America/New_York",
)
async def settimezone(interaction, timezone_name: str):
    if not await require_admin(interaction):
        return

    timezone_name = timezone_name.strip()
    try:
        selected_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        await interaction.response.send_message(
            "That timezone was not found. Use an IANA name like "
            "`America/Los_Angeles`, `America/New_York`, or `UTC`.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    guild_config["timezone"] = timezone_name
    save_config(config)
    current_time = datetime.now(selected_timezone).strftime("%Y-%m-%d %H:%M")
    audit_interaction(
        interaction,
        "set_timezone",
        "timezone",
        timezone_name,
        f"Current configured local time was {current_time}.",
    )
    await interaction.response.send_message(
        f"Timezone set to `{timezone_name}`. Current server time there is "
        f"`{current_time}`.",
        ephemeral=True,
    )


@tree.command(name="setguesstimeout", description="Set wrong-guess cooldown")
@app_commands.guild_only()
@app_commands.describe(minutes="Cooldown minutes after a wrong guess")
async def setguesstimeout(
    interaction,
    minutes: app_commands.Range[int, 1, 1440],
):
    if not await require_admin(interaction):
        return
    seconds = int(minutes) * 60
    config["limits"]["wrong_guess_timeout_seconds"] = seconds
    save_config(config)
    audit_interaction(
        interaction,
        "set_guess_timeout",
        "limit",
        "wrong_guess_timeout_seconds",
        f"Set to {minutes} minute(s).",
    )
    await interaction.response.send_message(
        f"Wrong-guess cooldown set to `{minutes}` minute(s).",
        ephemeral=True,
    )


@tree.command(name="createpoll", description="Create an SDAC poll")
@app_commands.guild_only()
@app_commands.describe(
    question="Poll question",
    options="Options separated with |, for example: Red | Blue | Green",
    channel="Optional channel to post the poll in",
)
async def createpoll(
    interaction,
    question: str,
    options: str,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return
    try:
        poll_options = parse_poll_options(options)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    target_channel = channel or interaction.channel
    now = utc_now_iso()
    with database() as connection:
        cursor = connection.execute("""
            INSERT INTO polls (
                guild_id, channel_id, message_id, question, options_json,
                status, created_by, created_by_name, created_at, closes_at
            )
            VALUES (?, ?, '', ?, ?, 'active', ?, ?, ?, '')
        """, (
            str(interaction.guild_id),
            str(target_channel.id),
            question[:240],
            json.dumps(poll_options, separators=(",", ":")),
            str(interaction.user.id),
            str(interaction.user),
            now,
        ))
        poll_id = cursor.lastrowid
    message = await target_channel.send(
        embed=poll_embed(poll_id, question[:240], poll_options, {}, "active")
    )
    with database() as connection:
        connection.execute(
            "UPDATE polls SET message_id = ? WHERE id = ?",
            (str(message.id), poll_id),
        )
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "discord_create_poll",
            interaction.user.id,
            interaction.user,
            "poll",
            poll_id,
            f"Created poll: {question[:240]}",
        )
    await interaction.response.send_message(
        f"Poll `{poll_id}` created in {target_channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="polls", description="List active SDAC polls")
@app_commands.guild_only()
async def polls(interaction):
    with closing(connect_db()) as connection:
        rows = connection.execute("""
            SELECT id, question, options_json, status
            FROM polls
            WHERE guild_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 10
        """, (str(interaction.guild_id),)).fetchall()
    if not rows:
        await interaction.response.send_message("No polls found.", ephemeral=True)
        return
    lines = []
    for row in rows:
        status = row["status"] or "active"
        lines.append(f"`{row['id']}` [{status}] {row['question']}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@tree.command(name="votepoll", description="Vote in an SDAC poll")
@app_commands.guild_only()
@app_commands.describe(poll_id="Poll ID", option_number="Option number from the poll")
async def votepoll(
    interaction,
    poll_id: int,
    option_number: app_commands.Range[int, 1, 10],
):
    with database() as connection:
        poll = connection.execute("""
            SELECT *
            FROM polls
            WHERE id = ? AND guild_id = ?
            LIMIT 1
        """, (poll_id, str(interaction.guild_id))).fetchone()
        if not poll:
            await interaction.response.send_message("Poll not found on this server.", ephemeral=True)
            return
        if (poll["status"] or "active") != "active":
            await interaction.response.send_message("That poll is closed.", ephemeral=True)
            return
        options = json.loads(poll["options_json"] or "[]")
        option_index = int(option_number) - 1
        if option_index < 0 or option_index >= len(options):
            await interaction.response.send_message("That option number is not valid for this poll.", ephemeral=True)
            return
        now = utc_now_iso()
        connection.execute("""
            INSERT INTO poll_votes (
                poll_id, user_id, username, option_index, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(poll_id, user_id) DO UPDATE SET
                username = excluded.username,
                option_index = excluded.option_index,
                updated_at = excluded.updated_at
        """, (
            poll_id,
            str(interaction.user.id),
            str(interaction.user),
            option_index,
            now,
            now,
        ))
        counts = poll_vote_counts(connection, poll_id)
    await interaction.response.send_message(
        f"Vote saved for poll `{poll_id}`: **{options[option_index]}**",
        ephemeral=True,
    )
    if poll["channel_id"] and poll["message_id"]:
        try:
            channel = bot.get_channel(int(poll["channel_id"])) or await bot.fetch_channel(int(poll["channel_id"]))
            message = await channel.fetch_message(int(poll["message_id"]))
            await message.edit(embed=poll_embed(poll_id, poll["question"], options, counts, poll["status"] or "active"))
        except (discord.DiscordException, ValueError):
            pass


@tree.command(name="closepoll", description="Close an SDAC poll")
@app_commands.guild_only()
@app_commands.describe(poll_id="Poll ID to close")
async def closepoll(interaction, poll_id: int):
    if not await require_admin(interaction):
        return
    with database() as connection:
        poll = connection.execute("""
            SELECT *
            FROM polls
            WHERE id = ? AND guild_id = ?
            LIMIT 1
        """, (poll_id, str(interaction.guild_id))).fetchone()
        if not poll:
            await interaction.response.send_message("Poll not found on this server.", ephemeral=True)
            return
        connection.execute(
            "UPDATE polls SET status = 'closed' WHERE id = ?",
            (poll_id,),
        )
        options = json.loads(poll["options_json"] or "[]")
        counts = poll_vote_counts(connection, poll_id)
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "discord_close_poll",
            interaction.user.id,
            interaction.user,
            "poll",
            poll_id,
            "Closed poll.",
        )
    await interaction.response.send_message(
        f"Poll `{poll_id}` closed.\n{poll_results_text(options, counts)}",
        ephemeral=True,
    )



@tree.command(name="setadminrole", description="Allow a role to manage SDAC")
@app_commands.guild_only()
@app_commands.describe(role="Role that can manage SDAC without Administrator")
async def setadminrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    role_ids = {
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id).strip()
    }
    role_ids.add(str(role.id))
    guild_config["admin_role_ids"] = sorted(role_ids)
    save_config(config)
    audit_interaction(
        interaction,
        "set_admin_role",
        "role",
        role.id,
        f"Added SDAC admin role {role.name}.",
    )
    await interaction.response.send_message(
        f"{role.mention} can now manage SDAC.",
        ephemeral=True,
    )


@tree.command(name="removeadminrole", description="Remove an SDAC admin role")
@app_commands.guild_only()
@app_commands.describe(role="Role to remove from SDAC admin access")
async def removeadminrole(interaction, role: discord.Role):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    role_ids = [
        str(role_id)
        for role_id in guild_config.get("admin_role_ids", [])
        if str(role_id) != str(role.id)
    ]
    guild_config["admin_role_ids"] = role_ids
    save_config(config)
    audit_interaction(
        interaction,
        "remove_admin_role",
        "role",
        role.id,
        f"Removed SDAC admin role {role.name}.",
    )
    await interaction.response.send_message(
        f"{role.mention} can no longer manage SDAC through its role.",
        ephemeral=True,
    )


@tree.command(name="setgamesummarychannel", description="Set guessing game summary channel")
@app_commands.guild_only()
async def setgamesummarychannel(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["game_summary_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_game_summary_channel",
        "channel",
        channel.id,
        f"Game summaries set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"Guessing game summaries will post in {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="cleargamesummarychannel", description="Use game channel for summaries")
@app_commands.guild_only()
async def cleargamesummarychannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["game_summary_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_game_summary_channel",
        "channel",
        "",
        "Game summaries will post in the game channel.",
    )
    await interaction.response.send_message(
        "Guessing game summaries will post in the game channel.",
        ephemeral=True,
    )


@tree.command(name="seterrorchannel", description="Set SDAC error notification channel")
@app_commands.guild_only()
async def seterrorchannel(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["error_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_error_channel",
        "channel",
        channel.id,
        f"Error channel set to {channel.id}.",
    )
    await interaction.response.send_message(
        f"SDAC error notifications will use {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="clearerrorchannel", description="Clear SDAC error notification channel")
@app_commands.guild_only()
async def clearerrorchannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["error_channel"] = None
    save_config(config)
    audit_interaction(
        interaction,
        "clear_error_channel",
        "channel",
        "",
        "Error channel cleared.",
    )
    await interaction.response.send_message(
        "SDAC error channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setapproval", description="Configure approval-before-repost")
@app_commands.guild_only()
@app_commands.describe(
    enabled="Whether submissions require admin approval",
    channel="Channel where pending submissions are reviewed",
)
async def setapproval(
    interaction,
    enabled: bool,
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    if enabled and channel is None and not guild_config["approval_channel"]:
        await interaction.response.send_message(
            "Choose an approval channel when enabling approval.",
            ephemeral=True,
        )
        return
    guild_config["approval_enabled"] = enabled
    if channel is not None:
        guild_config["approval_channel"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_approval",
        "approval",
        "enabled" if enabled else "disabled",
        (
            f"Approval channel {channel.id}."
            if channel is not None
            else "Approval channel unchanged."
        ),
    )
    await interaction.response.send_message(
        f"Approval is now {'enabled' if enabled else 'disabled'}.",
        ephemeral=True,
    )


@tree.command(name="setlimit", description="Set a per-server SDAC safety limit")
@app_commands.guild_only()
@app_commands.choices(limit=LIMIT_CHOICES)
@app_commands.describe(
    limit="Limit to update",
    value="Use 0 to inherit the global/default limit",
)
async def setlimit(interaction, limit: app_commands.Choice[str], value: int):
    if not await require_admin(interaction):
        return
    if value < 0:
        await interaction.response.send_message(
            "Limits cannot be negative.",
            ephemeral=True,
        )
        return
    guild_config = get_guild_config(interaction.guild_id)
    limits = guild_config.setdefault("limits", {})
    if limit.value == "max_file_mb":
        limits["max_file_bytes"] = value * 1024 * 1024
    elif limit.value == "max_total_mb":
        limits["max_total_bytes"] = value * 1024 * 1024
    elif limit.value == "monthly_submissions":
        limits["monthly_submission_limit"] = value
    elif limit.value == "active_games":
        limits["active_game_limit"] = value
    elif limit.value == "storage_mb":
        limits["storage_limit_bytes"] = value * 1024 * 1024
    save_config(config)
    audit_interaction(
        interaction,
        "set_guild_limit",
        "limit",
        limit.value,
        f"Set {limit.value} to {value}.",
    )
    await interaction.response.send_message(
        f"{limit.name} set to `{value}` for this server.",
        ephemeral=True,
    )


@tree.command(name="setmoderation", description="Set content moderation controls")
@app_commands.guild_only()
@app_commands.describe(
    blocked_words="Comma-separated blocked words. Use blank to clear.",
    allowed_media_types="Comma-separated: image, video, audio. Use blank for all.",
    require_approval_for_new_users="Require approval for new Discord accounts",
    new_user_days="Account age threshold for new-user approval",
    spoiler_requires_approval="Require approval for SPOILER_ files",
)
async def setmoderation(
    interaction,
    blocked_words: str = "",
    allowed_media_types: str = "image,video,audio",
    require_approval_for_new_users: bool = False,
    new_user_days: int = 7,
    spoiler_requires_approval: bool = False,
):
    if not await require_admin(interaction):
        return
    media_types = [
        item.strip().casefold()
        for item in allowed_media_types.split(",")
        if item.strip()
    ]
    invalid_types = sorted(set(media_types) - {"image", "video", "audio"})
    if invalid_types:
        await interaction.response.send_message(
            "Allowed media types can only include image, video, and audio.",
            ephemeral=True,
        )
        return
    if new_user_days < 0 or new_user_days > 365:
        await interaction.response.send_message(
            "New-user days must be between 0 and 365.",
            ephemeral=True,
        )
        return
    words = [
        item.strip()
        for item in blocked_words.split(",")
        if item.strip()
    ][:100]
    guild_config = get_guild_config(interaction.guild_id)
    moderation = guild_config.setdefault("moderation", {})
    moderation.update({
        "blocked_words": words,
        "allowed_media_types": media_types or ["image", "video", "audio"],
        "require_approval_for_new_users": bool(require_approval_for_new_users),
        "new_user_days": int(new_user_days),
        "spoiler_requires_approval": bool(spoiler_requires_approval),
    })
    save_config(config)
    audit_interaction(
        interaction,
        "set_moderation",
        "guild",
        interaction.guild_id,
        f"{len(words)} blocked words; media={','.join(media_types) or 'all'}.",
    )
    await interaction.response.send_message(
        "Moderation settings saved for this server.",
        ephemeral=True,
    )


@tree.command(name="setgamesettings", description="Set default guessing-game controls")
@app_commands.guild_only()
@app_commands.describe(
    reuse_cooldown_days="Do not reuse the same answer this many days",
    default_auto_hint_minutes="Default auto-hint minutes when a game uses 0",
    default_difficulty="Difficulty label stored with future library items",
)
async def setgamesettings(
    interaction,
    reuse_cooldown_days: int = 30,
    default_auto_hint_minutes: int = 0,
    default_difficulty: str = "normal",
):
    if not await require_admin(interaction):
        return
    if reuse_cooldown_days < 0 or reuse_cooldown_days > 3650:
        await interaction.response.send_message(
            "Reuse cooldown must be between 0 and 3650 days.",
            ephemeral=True,
        )
        return
    if default_auto_hint_minutes < 0 or default_auto_hint_minutes > 1440:
        await interaction.response.send_message(
            "Default auto-hint minutes must be between 0 and 1440.",
            ephemeral=True,
        )
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["game_settings"] = {
        "reuse_cooldown_days": int(reuse_cooldown_days),
        "default_auto_hint_minutes": int(default_auto_hint_minutes),
        "default_difficulty": (default_difficulty or "normal").strip()[:40],
    }
    save_config(config)
    audit_interaction(
        interaction,
        "set_game_settings",
        "guild",
        interaction.guild_id,
        (
            f"reuse={reuse_cooldown_days}; "
            f"auto_hint={default_auto_hint_minutes}; "
            f"difficulty={default_difficulty}"
        ),
    )
    await interaction.response.send_message(
        "Guessing-game defaults saved.",
        ephemeral=True,
    )


@tree.command(name="setserverbackup", description="Set this server's external backup target")
@app_commands.guild_only()
@app_commands.describe(
    enabled="Whether per-server offsite backups are enabled",
    remote="rclone destination, like drive:sdac/server-name. Blank keeps current.",
    public_base_url="Optional public media URL prefix. Use clear to remove.",
    include_media="Include this server's media folder in the backup job",
    include_database_export="Include this server's database rows as JSON",
    zip_backups="Create a local zip archive when backups run",
    delete_local_media_after_success="Advanced: delete local guild media after a successful copy",
)
async def setserverbackup(
    interaction,
    enabled: bool,
    remote: str = "",
    public_base_url: str = "",
    include_media: bool = True,
    include_database_export: bool = True,
    zip_backups: bool = True,
    delete_local_media_after_success: bool = False,
):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id)
    backup = guild_config.setdefault(
        "external_backup",
        json.loads(json.dumps(DEFAULT_GUILD_EXTERNAL_BACKUP)),
    )

    remote_value = (remote or "").strip()
    public_base_value = (public_base_url or "").strip()
    if remote_value.casefold() in {"clear", "none", "-"}:
        backup["remote"] = ""
    elif remote_value:
        if any(character in remote_value for character in "\r\n"):
            await interaction.response.send_message(
                "The backup remote cannot contain line breaks.",
                ephemeral=True,
            )
            return
        backup["remote"] = remote_value[:300]

    if public_base_value.casefold() in {"clear", "none", "-"}:
        backup["public_base_url"] = ""
    elif public_base_value:
        if not public_base_value.startswith(("https://", "http://")):
            await interaction.response.send_message(
                "Public media base URL must start with http:// or https://.",
                ephemeral=True,
            )
            return
        backup["public_base_url"] = public_base_value.rstrip("/")[:300]

    if enabled and not backup.get("remote"):
        await interaction.response.send_message(
            "Set a backup remote before enabling per-server backups.",
            ephemeral=True,
        )
        return
    if delete_local_media_after_success and not include_media:
        await interaction.response.send_message(
            "Local media can only be deleted after a media backup is included.",
            ephemeral=True,
        )
        return

    backup["enabled"] = bool(enabled)
    backup["provider"] = "rclone"
    backup["include_media"] = bool(include_media)
    backup["include_database_export"] = bool(include_database_export)
    backup["zip_backups"] = bool(zip_backups)
    backup["delete_local_media_after_success"] = bool(
        delete_local_media_after_success
    )
    save_config(config)

    audit_interaction(
        interaction,
        "set_server_backup",
        "guild",
        interaction.guild_id,
        (
            f"enabled={enabled}; remote={backup.get('remote') or 'unset'}; "
            f"include_media={include_media}; "
            f"zip_backups={zip_backups}; "
            f"delete_local={delete_local_media_after_success}"
        ),
    )

    command = (
        "SDAC_GUILD_ID="
        f"{interaction.guild_id} bash scripts/backup_guild_offsite.sh"
    )
    warnings = []
    if backup.get("delete_local_media_after_success"):
        warnings.append(
            "Advanced cleanup is enabled: local media for this guild is removed "
            "only after rclone reports a successful copy."
        )
    if backup.get("public_base_url"):
        warnings.append(
            "Dashboard media links can use this guild's public media URL."
        )
    await interaction.response.send_message(
        "\n".join([
            f"Per-server backup is now {'enabled' if enabled else 'disabled'}.",
            f"Remote: `{backup.get('remote') or 'Not set'}`",
            f"Zip archives: `{backup.get('zip_backups')}`",
            f"Run on the host with: `{command}`",
            *warnings,
        ]),
        ephemeral=True,
    )


@tree.command(name="serverbackupstatus", description="Show this server's backup settings")
@app_commands.guild_only()
async def serverbackupstatus(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    backup = {
        **DEFAULT_GUILD_EXTERNAL_BACKUP,
        **(guild_config.get("external_backup") or {}),
    }
    command = (
        "SDAC_GUILD_ID="
        f"{interaction.guild_id} bash scripts/backup_guild_offsite.sh"
    )
    await interaction.response.send_message(
        "\n".join([
            f"Enabled: `{backup.get('enabled')}`",
            f"Provider: `{backup.get('provider') or 'rclone'}`",
            f"Remote: `{backup.get('remote') or 'Not set'}`",
            f"Public media URL: `{backup.get('public_base_url') or 'Not set'}`",
            f"Include media: `{backup.get('include_media')}`",
            f"Include DB export: `{backup.get('include_database_export')}`",
            f"Zip archives: `{backup.get('zip_backups', True)}`",
            (
                "Delete local media after success: "
                f"`{backup.get('delete_local_media_after_success')}`"
            ),
            f"Last archive: `{backup.get('last_archive_path') or 'Never'}`",
            f"Last success: `{backup.get('last_success_at') or 'Never'}`",
            f"Last status: `{backup.get('last_status') or 'Unknown'}`",
            f"Details: `{backup.get('last_details') or ''}`",
            f"Host command: `{command}`",
        ]),
        ephemeral=True,
    )


@tree.command(name="backupguide", description="Show backup provider setup steps")
@app_commands.guild_only()
@app_commands.choices(provider=BACKUP_PROVIDER_CHOICES)
async def backupguide(interaction, provider: app_commands.Choice[str]):
    if not await require_admin(interaction):
        return
    guide = BACKUP_PROVIDER_GUIDES[provider.value]
    await interaction.response.send_message(
        "\n".join([
            f"**Backup Setup: {guide['label']}**",
            "Prerequisites on Ubuntu:",
            "`sudo bash scripts/install_backup_prereqs.sh`",
            "",
            "Configure rclone on the server:",
            "`rclone config`",
            "",
            guide["steps"],
            f"Example remote: `{guide['remote_hint']}`",
            "",
            "Then save it in Discord:",
            f"`/backupsetup provider:{guide['label']} remote:{guide['remote_hint']}`",
            "",
            "Create and upload a zip backup any time with `/backupnow upload:true`.",
        ]),
        ephemeral=True,
    )


@tree.command(name="backupsetup", description="Configure this server's backups from Discord")
@app_commands.guild_only()
@app_commands.choices(provider=BACKUP_PROVIDER_CHOICES)
@app_commands.describe(
    remote="rclone destination, for example drive:sdac/server-name",
    public_base_url="Optional public media URL prefix. Use clear to remove.",
    include_media="Include this server's media folder in backups",
    include_database_export="Include this server's database rows as JSON",
    zip_backups="Create local zip archives for backups",
    delete_local_media_after_success="Advanced: delete local guild media after a successful copy",
)
async def backupsetup(
    interaction,
    provider: app_commands.Choice[str],
    remote: str,
    public_base_url: str = "",
    include_media: bool = True,
    include_database_export: bool = True,
    zip_backups: bool = True,
    delete_local_media_after_success: bool = False,
):
    if not await require_admin(interaction):
        return
    remote_value = (remote or "").strip()
    if not remote_value or any(character in remote_value for character in "\r\n"):
        await interaction.response.send_message(
            "Remote is required and cannot contain line breaks.",
            ephemeral=True,
        )
        return
    public_base_value = (public_base_url or "").strip()
    if public_base_value.casefold() in {"clear", "none", "-"}:
        public_base_value = ""
    if public_base_value and not public_base_value.startswith(("https://", "http://")):
        await interaction.response.send_message(
            "Public media base URL must start with http:// or https://.",
            ephemeral=True,
        )
        return
    if delete_local_media_after_success and not include_media:
        await interaction.response.send_message(
            "Local media can only be deleted after media is included in backups.",
            ephemeral=True,
        )
        return

    guild_config = get_guild_config(interaction.guild_id)
    backup = guild_config.setdefault(
        "external_backup",
        json.loads(json.dumps(DEFAULT_GUILD_EXTERNAL_BACKUP)),
    )
    backup.update({
        "enabled": True,
        "provider": provider.value,
        "remote": remote_value[:300],
        "public_base_url": public_base_value.rstrip("/")[:300],
        "include_media": bool(include_media),
        "include_database_export": bool(include_database_export),
        "zip_backups": bool(zip_backups),
        "delete_local_media_after_success": bool(
            delete_local_media_after_success
        ),
    })
    save_config(config)
    audit_interaction(
        interaction,
        "backup_setup",
        "guild",
        interaction.guild_id,
        f"provider={provider.value}; remote={remote_value}; zip={zip_backups}.",
    )
    await interaction.response.send_message(
        "\n".join([
            "Backup settings saved.",
            f"Provider: `{BACKUP_PROVIDER_GUIDES[provider.value]['label']}`",
            f"Remote: `{remote_value}`",
            f"Zip archives: `{zip_backups}`",
            "Use `/backupnow upload:true` to create and upload a zip backup.",
        ]),
        ephemeral=True,
    )


@tree.command(name="backupnow", description="Create a zip backup and optionally upload it")
@app_commands.guild_only()
@app_commands.describe(upload="Upload the zip to the configured rclone remote")
async def backupnow(interaction, upload: bool = True):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    backup = {
        **DEFAULT_GUILD_EXTERNAL_BACKUP,
        **(guild_config.get("external_backup") or {}),
    }
    if not backup.get("zip_backups", True):
        await interaction.response.send_message(
            "Zip backups are disabled. Enable them with `/backupsetup`.",
            ephemeral=True,
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        archive_info = await asyncio.to_thread(
            create_guild_backup_archive,
            interaction.guild_id,
            interaction.user.id,
            interaction.user,
        )
        guild_config = get_guild_config(interaction.guild_id)
        guild_config.setdefault("external_backup", {})["last_archive_path"] = str(
            archive_info["path"]
        )
        save_config(config)
    except Exception as error:
        capture_exception(error)
        await interaction.followup.send(
            f"Backup zip creation failed: `{error}`",
            ephemeral=True,
        )
        return

    upload_message = "Upload skipped."
    if upload:
        ok, upload_message = await upload_archive_with_rclone(
            archive_info,
            backup.get("remote") or "",
        )
        if ok:
            guild_config = get_guild_config(interaction.guild_id)
            backup_config = guild_config.setdefault("external_backup", {})
            backup_config["last_status"] = "success"
            backup_config["last_success_at"] = utc_now_iso()
            backup_config["last_details"] = upload_message
            save_config(config)

    await interaction.followup.send(
        "\n".join([
            "Backup zip created.",
            f"Archive: `{archive_info['path'].name}`",
            f"Size: `{format_bytes(archive_info['size'])}`",
            f"SHA-256: `{archive_info['sha256']}`",
            f"Media files: `{archive_info['manifest']['media_files']}`",
            upload_message,
        ])[:1900],
        ephemeral=True,
    )


@tree.command(name="backupstatus", description="Show this server's backup status")
@app_commands.guild_only()
async def backupstatus(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    backup = {
        **DEFAULT_GUILD_EXTERNAL_BACKUP,
        **(guild_config.get("external_backup") or {}),
    }
    prereqs = [
        "OK: Python zipfile is built in.",
        (
            "OK: rclone found."
            if shutil.which("rclone")
            else "WARN: rclone not found. Run `sudo bash scripts/install_backup_prereqs.sh`."
        ),
    ]
    await interaction.response.send_message(
        "\n".join([
            "**SDAC Backup Status**",
            f"Enabled: `{backup.get('enabled')}`",
            f"Provider: `{backup.get('provider') or 'rclone'}`",
            f"Remote: `{backup.get('remote') or 'Not set'}`",
            f"Zip archives: `{backup.get('zip_backups', True)}`",
            f"Include media: `{backup.get('include_media')}`",
            f"Include DB export: `{backup.get('include_database_export')}`",
            f"Last archive: `{backup.get('last_archive_path') or 'Never'}`",
            f"Last success: `{backup.get('last_success_at') or 'Never'}`",
            f"Last status: `{backup.get('last_status') or 'Unknown'}`",
            *prereqs,
        ]),
        ephemeral=True,
    )


@tree.command(name="setdigest", description="Configure the admin notification digest")
@app_commands.guild_only()
@app_commands.describe(
    enabled="Whether digest posts are enabled",
    frequency="daily or weekly",
    channel="Channel where the digest should post",
)
async def setdigest(
    interaction,
    enabled: bool,
    frequency: str = "weekly",
    channel: Optional[discord.TextChannel] = None,
):
    if not await require_admin(interaction):
        return
    frequency = (frequency or "weekly").strip().casefold()
    if frequency not in {"daily", "weekly"}:
        await interaction.response.send_message(
            "Digest frequency must be `daily` or `weekly`.",
            ephemeral=True,
        )
        return
    guild_config = get_guild_config(interaction.guild_id)
    digest = guild_config.setdefault("notification_digest", {})
    if enabled and channel is None and not digest.get("channel_id"):
        await interaction.response.send_message(
            "Choose a digest channel the first time you enable admin digests.",
            ephemeral=True,
        )
        return
    digest["enabled"] = bool(enabled)
    digest["frequency"] = frequency
    if channel is not None:
        digest["channel_id"] = channel.id
    save_config(config)
    audit_interaction(
        interaction,
        "set_notification_digest",
        "guild",
        interaction.guild_id,
        f"enabled={enabled}; frequency={frequency}; channel={digest.get('channel_id')}",
    )
    await interaction.response.send_message(
        "\n".join([
            f"Notification digest is now {'enabled' if enabled else 'disabled'}.",
            f"Frequency: `{frequency}`",
            f"Channel: {channel.mention if channel else channel_display(digest.get('channel_id'))}",
        ]),
        ephemeral=True,
    )


@tree.command(name="reasonpresets", description="Show standard SDAC admin action reasons")
@app_commands.guild_only()
async def reasonpresets(interaction):
    if not await require_admin(interaction):
        return
    await interaction.response.send_message(
        "\n".join(
            ["**SDAC Reason Presets**"]
            + [
                f"- `{key}` - {label}"
                for key, label in MODERATION_REASON_PRESETS.items()
            ]
        ),
        ephemeral=True,
    )


@tree.command(name="supportbundle", description="Create a small SDAC diagnostic bundle")
@app_commands.guild_only()
async def supportbundle(interaction):
    if not await require_admin(interaction):
        return
    payload = support_bundle_payload(interaction.guild_id)
    summary = (
        f"backend={payload['database_backend']}; "
        f"schema={payload['schema_version']}; "
        f"submissions={payload['submissions']}; "
        f"active_games={payload['active_games']}"
    )
    with database() as connection:
        cursor = connection.execute("""
            INSERT INTO support_bundles (
                guild_id, actor_user_id, actor_username, summary,
                details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            str(interaction.user.id),
            str(interaction.user),
            summary,
            json.dumps(payload, indent=2),
            utc_now_iso(),
        ))
        bundle_id = cursor.lastrowid
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "create_support_bundle",
            interaction.user.id,
            interaction.user,
            "support_bundle",
            bundle_id,
            summary,
        )
    await interaction.response.send_message(
        f"Support bundle `{bundle_id}` created.\n`{summary}`",
        ephemeral=True,
    )


def submission_cooldown_message(guild_id, user_id, category):
    now = time.time()
    user_key = f"{guild_id}:{user_id}"
    category_key = f"{guild_id}:{category}"
    user_seconds = configured_limit(
        "submission_user_cooldown_seconds",
        USER_COOLDOWN_SECONDS,
    )
    category_seconds = configured_limit(
        "submission_category_cooldown_seconds",
        CATEGORY_COOLDOWN_SECONDS,
    )
    last_user = user_cooldowns.get(user_key, 0)
    if user_seconds and now - last_user < user_seconds:
        remaining = max(1, int(user_seconds - (now - last_user)))
        return f"Wait {remaining}s before submitting again.", remaining, "user"

    last_category = category_cooldowns.get(category_key, 0)
    if category_seconds and now - last_category < category_seconds:
        remaining = max(
            1,
            int(category_seconds - (now - last_category)),
        )
        return (
            f"Category `{category}` is cooling down for {remaining}s.",
            remaining,
            "category",
        )
    return None, 0, ""


def validate_submission_message(message, guild_config=None, category=""):
    text = message.content.strip()
    attachments = list(message.attachments)
    guild_config = guild_config or {}
    moderation_error = moderation_rejection(guild_config, message, category)
    if moderation_error:
        return moderation_error

    if not attachments:
        return "A submission must include at least one image, audio, or video file."
    max_text_length = configured_limit("max_text_length", 1500)
    if len(text) > max_text_length:
        return f"Text is limited to {max_text_length} characters."
    if len(attachments) > 5:
        return "A submission can contain at most 5 media files."

    bad_files = [
        attachment.filename
        for attachment in attachments
        if not is_allowed_file(attachment.filename)
    ]
    if bad_files:
        return "Unsupported file type: " + ", ".join(bad_files)

    oversized = [
        attachment.filename
        for attachment in attachments
        if attachment.size > guild_max_file_bytes(guild_config)
    ]
    if oversized:
        return "Files exceed the per-file limit: " + ", ".join(oversized)

    total_size = sum(attachment.size for attachment in attachments)
    if total_size > guild_max_total_bytes(guild_config):
        return "The combined upload exceeds the total submission limit."
    return None


def submission_preview(category, message):
    text = message.content.strip() or "(no text)"
    file_lines = [
        f"- `{attachment.filename}` ({attachment.size / 1024 / 1024:.2f} MB)"
        for attachment in message.attachments
    ]
    files = "\n".join(file_lines) if file_lines else "(no media)"
    return (
        "**Step 3 of 3: Confirm your submission**\n"
        f"Category: `{category}`\n\n"
        f"Text:\n{text}\n\n"
        f"Media:\n{files}\n\n"
        "Choose **Confirm** to submit or **Cancel** to discard it."
    )


def submission_preview_embeds(message):
    embeds = []
    for attachment in message.attachments:
        if get_media_type(attachment.filename) != "image":
            continue
        embed = discord.Embed(title=attachment.filename)
        embed.set_image(url=attachment.url)
        embeds.append(embed)
    return embeds


async def delete_source_message(message):
    try:
        await message.delete()
        return True, ""
    except discord.NotFound:
        return True, ""
    except discord.Forbidden:
        return (
            False,
            "The bot needs the **Manage Messages** permission in the submit channel.",
        )
    except discord.HTTPException:
        try:
            fresh_message = await message.channel.fetch_message(message.id)
            await fresh_message.delete()
            return True, ""
        except discord.NotFound:
            return True, ""
        except discord.Forbidden:
            return (
                False,
                "The bot needs the **Manage Messages** permission in the submit channel.",
            )
        except discord.HTTPException as error:
            return False, f"The source message could not be deleted: {error}"


async def create_submission(source_message, category):
    guild_config = get_guild_config(source_message.guild.id, create=False)
    validation_error = validate_submission_message(
        source_message,
        guild_config,
        category,
    )
    if validation_error:
        return False, validation_error
    categories_config = guild_config.get("categories", {})
    target_channel_id = categories_config.get(category)
    target_channel = bot.get_channel(target_channel_id)
    if target_channel is None and target_channel_id:
        try:
            target_channel = await bot.fetch_channel(int(target_channel_id))
        except (TypeError, ValueError, discord.HTTPException):
            target_channel = None
    if target_channel is None:
        return False, "The category channel could not be found."

    approval_channel = None
    moderation_approval, moderation_reason = submission_needs_moderation_approval(
        guild_config,
        source_message,
    )
    if (
        (guild_config["approval_enabled"] or moderation_approval)
        and feature_enabled(
            guild_config,
            "approval_queue",
        )
    ):
        approval_channel_id = guild_config.get("approval_channel")
        approval_channel = (
            bot.get_channel(approval_channel_id)
            if approval_channel_id
            else None
        )
        if approval_channel is None:
            return False, "Approval is enabled, but its channel is unavailable."

    cooldown_message, retry_after, bucket = submission_cooldown_message(
        source_message.guild.id,
        source_message.author.id,
        category,
    )
    if cooldown_message:
        record_rate_limit_event(
            source_message.guild.id,
            source_message.author.id,
            source_message.author,
            f"submission_{bucket}",
            "create_submission",
            retry_after,
            f"Category {category}.",
        )
        return False, cooldown_message

    text = source_message.content.strip()
    attachments = list(source_message.attachments)
    total_size = sum(int(attachment.size or 0) for attachment in attachments)
    with database() as connection:
        monthly_limit = guild_monthly_submission_limit(guild_config)
        if monthly_limit:
            current_count = current_month_submission_count(
                connection,
                source_message.guild.id,
                guild_config,
            )
            if current_count >= monthly_limit:
                return (
                    False,
                    "This server has reached its monthly submission limit.",
                )
        storage_limit = guild_storage_limit(guild_config)
        if (
            storage_limit
            and guild_media_size(source_message.guild.id) + total_size
            > storage_limit
        ):
            return (
                False,
                "This server has reached its configured media storage limit.",
            )

    user_folder = (
        MEDIA_DIR
        / str(source_message.guild.id)
        / category
        / str(source_message.author.id)
    )
    user_folder.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    media_names = []
    media_types = []
    media_sizes = []
    media_metadata = []
    media_hashes = []
    created_message = None
    submission_id = None

    try:
        for attachment in attachments:
            safe_name = Path(attachment.filename).name.replace("\\", "_")
            filename = (
                f"{int(time.time())}_{source_message.id}_{safe_name}"
            )
            path = user_folder / filename
            await attachment.save(path)
            maybe_compress_image(path, attachment.filename)
            try:
                stored_size = path.stat().st_size
            except OSError:
                stored_size = int(attachment.size or 0)
            saved_paths.append(str(path))
            media_names.append(attachment.filename)
            media_types.append(get_media_type(attachment.filename))
            media_sizes.append(str(int(stored_size or 0)))
            metadata = attachment_metadata(attachment, path)
            media_hash = file_sha256(path)
            if media_hash:
                metadata["sha256"] = media_hash
            media_hashes.append(media_hash)
            media_metadata.append(metadata)

        status = "pending" if approval_channel else "posted"
        spam_score = 0
        spam_reasons = []
        with database() as connection:
            spam_score, spam_reasons = submission_spam_signal(
                connection,
                source_message.guild.id,
                source_message.author.id,
                guild_config,
                media_hashes,
                source_message,
            )
            spam_threshold = configured_moderation_int(
                guild_config,
                "spam_review_threshold",
                40,
            )
            if spam_score >= spam_threshold:
                moderation_approval = True
                moderation_reason = "; ".join(spam_reasons[:3])
                if approval_channel is None and feature_enabled(
                    guild_config,
                    "approval_queue",
                ):
                    approval_channel_id = guild_config.get("approval_channel")
                    approval_channel = (
                        bot.get_channel(approval_channel_id)
                        if approval_channel_id
                        else None
                    )
                status = "pending" if approval_channel else "posted"
            cursor = connection.execute("""
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_channel_id,
                    user_id, username, category, message_text,
                    file_paths, media_paths, media_names, media_types,
                    media_sizes, media_metadata_json, media_hashes,
                    spam_score, spam_reasons_json,
                    stars, voters, status, submitted_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?)
            """, (
                str(source_message.guild.id),
                str(source_message.id),
                str(target_channel.id),
                str(source_message.author.id),
                str(source_message.author),
                category,
                text,
                ";".join(saved_paths),
                ";".join(saved_paths),
                ";".join(media_names),
                ";".join(media_types),
                ";".join(media_sizes),
                json.dumps(media_metadata, separators=(",", ":")),
                ";".join(media_hashes),
                int(spam_score),
                json.dumps(spam_reasons, separators=(",", ":")),
                status,
                utc_now_iso(),
                utc_now_iso(),
            ))
            submission_id = cursor.lastrowid
            register_media_fingerprints(
                connection,
                source_message.guild.id,
                submission_id,
                saved_paths,
                media_names,
                media_hashes,
                media_sizes,
            )
            row = connection.execute(
                "SELECT * FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()

        if approval_channel:
            created_message = await send_submission_message(
                approval_channel,
                (
                    f"Pending submission `{submission_id}`\n\n"
                    + submission_content(row)
                ),
                row,
                ApprovalView(),
            )
            with database() as connection:
                connection.execute("""
                    UPDATE submissions
                    SET approval_message_id = ?, approval_channel_id = ?
                    WHERE id = ?
                """, (
                    str(created_message.id),
                    str(approval_channel.id),
                    submission_id,
                ))
            response_text = (
                f"Submission `{submission_id}` is awaiting approval."
            )
            if moderation_reason:
                response_text += f" Reason: {moderation_reason}"
        else:
            created_message = await send_submission_message(
                target_channel,
                submission_content(row),
                row,
                VoteView(),
            )
            with database() as connection:
                connection.execute("""
                    UPDATE submissions
                    SET repost_message_id = ?, approved_at = ?
                    WHERE id = ?
                """, (
                    str(created_message.id),
                    utc_now_iso(),
                    submission_id,
                ))
            response_text = (
                f"Submitted to `{category}` as `{submission_id}`."
            )

        now = time.time()
        user_cooldowns[
            f"{source_message.guild.id}:{source_message.author.id}"
        ] = now
        category_cooldowns[
            f"{source_message.guild.id}:{category}"
        ] = now
        deleted, delete_error = await delete_source_message(source_message)
        if not deleted:
            response_text += (
                "\n\nWarning: the submission was posted, but the bot could not "
                f"delete the original message. {delete_error}"
            )
            await send_error_notification(
                source_message.guild.id,
                (
                    f"Submission `{submission_id}` was posted, but source "
                    f"message cleanup failed: `{delete_error}`"
                ),
                "repost_delete_failed",
            )
        return True, response_text
    except Exception as error:
        capture_exception(error)
        if created_message is not None:
            try:
                await created_message.delete()
            except discord.HTTPException:
                pass
        if submission_id is not None:
            with database() as connection:
                connection.execute(
                    "DELETE FROM submissions WHERE id = ?",
                    (submission_id,),
                )
                connection.execute(
                    "DELETE FROM media_fingerprints WHERE submission_id = ?",
                    (submission_id,),
                )
        cleanup_files(saved_paths)
        return False, f"Submission failed: `{error}`"


class SubmissionConfirmView(discord.ui.View):
    def __init__(self, source_message, category, session_key):
        super().__init__(timeout=300)
        self.source_message = source_message
        self.category = category
        self.session_key = session_key
        self.finished = False
        self.preview_message = None

    async def interaction_check(self, interaction):
        if interaction.user.id == self.source_message.author.id:
            return True
        await interaction.response.send_message(
            "Only the person who started this submission can use these buttons.",
            ephemeral=True,
        )
        return False

    async def finish(self, content):
        active_submission_sessions.discard(self.session_key)
        self.stop()
        if self.preview_message is not None:
            try:
                await self.preview_message.edit(
                    content=content,
                    embeds=[],
                    view=None,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.success,
    )
    async def confirm(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(
                "This submission has already been handled.",
                ephemeral=True,
            )
            return
        self.finished = True
        await interaction.response.defer()
        success, message = await create_submission(
            self.source_message,
            self.category,
        )
        if not success:
            self.finished = False
            await interaction.followup.send(message, ephemeral=True)
            return
        await self.finish(f"**Submission complete**\n{message}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
    )
    async def cancel(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(
                "This submission has already been handled.",
                ephemeral=True,
            )
            return
        self.finished = True
        await interaction.response.defer()
        deleted, delete_error = await delete_source_message(
            self.source_message
        )
        if deleted:
            await self.finish("Submission cancelled.")
        else:
            await self.finish(
                f"Submission cancelled, but {delete_error}"
            )

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        deleted, delete_error = await delete_source_message(
            self.source_message
        )
        message = "Submission timed out. Run `/submit` to start again."
        if not deleted:
            message += f"\n{delete_error}"
        await self.finish(message)


class SubmissionCategorySelect(discord.ui.Select):
    def __init__(self, categories):
        options = [
            discord.SelectOption(
                label=category[:100],
                value=category,
                description="Submit to this category",
            )
            for category in categories[:25]
        ]
        super().__init__(
            placeholder="Choose a submission category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        view = self.view
        if view is None:
            await interaction.response.send_message(
                "This submission menu is no longer available.",
                ephemeral=True,
            )
            return
        await view.start_content_step(interaction, self.values[0])


class SubmissionCategoryView(discord.ui.View):
    def __init__(self, author_id, guild_config):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild_config = guild_config
        self.message = None
        categories = sorted(guild_config.get("categories", {}).keys())
        self.add_item(SubmissionCategorySelect(categories))

    async def interaction_check(self, interaction):
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "Only the person who started this submission can use this menu.",
            ephemeral=True,
        )
        return False

    async def start_content_step(self, interaction, category):
        category = clean_category_name(category)
        if category not in self.guild_config.get("categories", {}):
            await interaction.response.send_message(
                f"Invalid category `{category}`.",
                ephemeral=True,
            )
            return

        session_key = f"{interaction.guild_id}:{interaction.user.id}"
        if session_key in active_submission_sessions:
            await interaction.response.send_message(
                "You already have an active submission. Finish or cancel it first.",
                ephemeral=True,
            )
            return

        cooldown_message, retry_after, bucket = submission_cooldown_message(
            interaction.guild_id,
            interaction.user.id,
            category,
        )
        if cooldown_message:
            record_rate_limit_event(
                interaction.guild_id,
                interaction.user.id,
                interaction.user,
                f"submission_{bucket}",
                "submit",
                retry_after,
                f"Category {category}.",
            )
            await interaction.response.send_message(
                cooldown_message,
                ephemeral=True,
            )
            return

        active_submission_sessions.add(session_key)
        self.stop()
        for item in self.children:
            item.disabled = True

        guidance = "\n".join(
            f"- {line}"
            for line in submission_guidance_lines(
                interaction.guild_id,
                self.guild_config,
            )
        )
        await interaction.response.edit_message(
            content=(
                f"**Step 2 of 3: Add media/text for `{category}`**\n"
                "Send one normal message in this channel with at least one "
                "image, audio, or video attachment. Text is optional. You can "
                "attach up to 5 files.\n\n"
                f"{guidance}\n\n"
                "You have 5 minutes."
            ),
            view=None,
        )

        def message_check(message):
            return (
                message.guild
                and message.guild.id == interaction.guild_id
                and message.channel.id == interaction.channel_id
                and message.author.id == interaction.user.id
                and not message.author.bot
            )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + 300
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                source_message = await bot.wait_for(
                    "message",
                    timeout=remaining,
                    check=message_check,
                )
                validation_error = validate_submission_message(
                    source_message,
                    self.guild_config,
                    category,
                )
                if not validation_error:
                    break
                await delete_source_message(source_message)
                await interaction.edit_original_response(
                    content=(
                        f"**Step 2 of 3: Try again for `{category}`**\n"
                        f"{validation_error}\n\n"
                        "Media is required. Send another normal message with "
                        "at least one image, audio, or video attachment. Text "
                        "can be included with the media.\n\n"
                        f"{guidance}"
                    )
                )
        except asyncio.TimeoutError:
            active_submission_sessions.discard(session_key)
            await interaction.edit_original_response(
                content="Submission timed out. Run `/submit` to start again.",
                view=None,
            )
            return

        view = SubmissionConfirmView(source_message, category, session_key)
        preview_message = await interaction.edit_original_response(
            content=submission_preview(category, source_message),
            embeds=submission_preview_embeds(source_message),
            view=view,
        )
        view.preview_message = preview_message

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(
                    content="Submission timed out. Run `/submit` to start again.",
                    view=None,
                )
            except discord.HTTPException:
                pass


@tree.command(name="submit", description="Start a guided SDAC submission")
@app_commands.guild_only()
async def submit(interaction):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    paused = emergency_pause_message(guild_config)
    if paused:
        await interaction.response.send_message(paused, ephemeral=True)
        return
    if not feature_enabled(guild_config, "submissions"):
        await interaction.response.send_message(
            "Submissions are currently disabled for this server.",
            ephemeral=True,
        )
        return
    with database() as connection:
        restriction = active_user_restriction(
            connection,
            interaction.guild_id,
            interaction.user.id,
            "submissions",
        )
    if restriction:
        await interaction.response.send_message(
            user_lockout_message(restriction, "submissions"),
            ephemeral=True,
        )
        return
    submit_channel_id = guild_config.get("submit_channel")
    if not submit_channel_id:
        await interaction.response.send_message(
            "The submit channel is not configured.",
            ephemeral=True,
        )
        return
    if interaction.channel_id != submit_channel_id:
        channel = bot.get_channel(submit_channel_id)
        await interaction.response.send_message(
            f"Please submit in {channel.mention if channel else 'the configured channel'}.",
            ephemeral=True,
        )
        return

    categories = sorted(guild_config.get("categories", {}).keys())
    if not categories:
        await interaction.response.send_message(
            "No submission categories are configured yet.",
            ephemeral=True,
        )
        return

    session_key = f"{interaction.guild_id}:{interaction.user.id}"
    if session_key in active_submission_sessions:
        await interaction.response.send_message(
            "You already have an active submission. Finish or cancel it first.",
            ephemeral=True,
        )
        return

    view = SubmissionCategoryView(interaction.user.id, guild_config)
    extra = ""
    if len(categories) > 25:
        extra = "\n\nOnly the first 25 categories are shown because Discord limits select menus."
    await interaction.response.send_message(
        "**Step 1 of 3: Select a category**\n"
        "Choose where this submission should be posted. After that, I will "
        "ask you to send the media/text message in this channel."
        f"{extra}",
        view=view,
        ephemeral=True,
    )
    try:
        view.message = await interaction.original_response()
    except discord.HTTPException:
        view.message = None


@tree.command(name="schedulegame", description="Schedule a saved library guessing game")
@app_commands.guild_only()
@app_commands.describe(
    channel="Channel where the scheduled game should start",
    start_time="YYYY-MM-DD HH:MM in server timezone, or ISO time",
    item_id="Library item ID. Use 0 to choose by category/reuse rules.",
    category="Optional library category filter when item_id is 0",
    random_item="Pick a random matching library item",
    close_after_minutes="Automatically close the game after this many minutes",
)
async def schedulegame(
    interaction,
    channel: discord.TextChannel,
    start_time: str,
    item_id: int = 0,
    category: str = "",
    random_item: bool = True,
    close_after_minutes: int = 0,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return
    try:
        starts_at = parse_scheduled_start_time(start_time, guild_config)
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return
    if starts_at <= datetime.now(timezone.utc):
        await interaction.response.send_message(
            "Scheduled game time must be in the future.",
            ephemeral=True,
        )
        return
    if close_after_minutes < 0 or close_after_minutes > 10080:
        await interaction.response.send_message(
            "Auto-close minutes must be between 0 and 10080.",
            ephemeral=True,
        )
        return
    game_settings = guild_game_settings(guild_config)
    with database() as connection:
        item = select_library_item_for_game(
            connection,
            interaction.guild_id,
            item_id=item_id,
            category=category,
            random_item=random_item,
            reuse_cooldown_days=int(game_settings.get("reuse_cooldown_days") or 0),
        )
        if item is None:
            await interaction.response.send_message(
                "No active game-library item matched that schedule request.",
                ephemeral=True,
            )
            return
        cursor = connection.execute("""
            INSERT INTO scheduled_games (
                guild_id, channel_id, library_item_id, category, random_item,
                starts_at, close_after_minutes, status, created_by,
                created_by_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)
        """, (
            str(interaction.guild_id),
            str(channel.id),
            int(item_id or 0),
            (category or "").strip(),
            1 if random_item else 0,
            starts_at.isoformat(),
            int(close_after_minutes or 0),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
            utc_now_iso(),
        ))
        scheduled_id = cursor.lastrowid
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "schedule_guess_game",
            interaction.user.id,
            interaction.user,
            "scheduled_game",
            scheduled_id,
            f"Channel {channel.id}; starts {starts_at.isoformat()}; item {item['id']}.",
        )
    local_time = starts_at.astimezone(get_guild_timezone(guild_config))
    await interaction.response.send_message(
        "\n".join([
            f"Scheduled game `{scheduled_id}` for {channel.mention}.",
            f"Starts: `{local_time.strftime('%Y-%m-%d %H:%M %Z')}`",
            f"Selected item now: `{item['id']}` - `{item['title'] or item['answer_display']}`",
            (
                f"Auto-close: `{close_after_minutes}` minute(s)"
                if close_after_minutes
                else "Auto-close: `disabled`"
            ),
        ]),
        ephemeral=True,
    )


@tree.command(name="scheduledgames", description="List queued and running scheduled games")
@app_commands.guild_only()
async def scheduledgames(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    timezone_info = get_guild_timezone(guild_config)
    with database() as connection:
        rows = connection.execute("""
            SELECT *
            FROM scheduled_games
            WHERE guild_id = ?
              AND status IN ('queued', 'starting', 'running')
            ORDER BY starts_at ASC, id ASC
            LIMIT 15
        """, (str(interaction.guild_id),)).fetchall()
    lines = ["**Scheduled Games**"]
    if not rows:
        lines.append("No queued or running scheduled games.")
    for row in rows:
        starts_at = parse_database_datetime(row["starts_at"])
        if starts_at:
            starts_text = starts_at.astimezone(timezone_info).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            starts_text = row["starts_at"] or "unknown"
        lines.append(
            (
                f"- `{row['id']}` {channel_display(row['channel_id'])} "
                f"`{row['status']}` at `{starts_text}` "
                f"item `{row['library_item_id'] or 'auto'}` "
                f"category `{row['category'] or 'any'}`"
            )
        )
    await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)


@tree.command(name="cancelscheduledgame", description="Cancel a queued scheduled game")
@app_commands.guild_only()
@app_commands.describe(scheduled_id="Scheduled game ID from /scheduledgames")
async def cancelscheduledgame(interaction, scheduled_id: int):
    if not await require_admin(interaction):
        return
    with database() as connection:
        row = connection.execute("""
            SELECT *
            FROM scheduled_games
            WHERE id = ? AND guild_id = ?
        """, (scheduled_id, str(interaction.guild_id))).fetchone()
        if not row:
            await interaction.response.send_message(
                "Scheduled game not found.",
                ephemeral=True,
            )
            return
        if row["status"] not in {"queued", "starting"}:
            await interaction.response.send_message(
                f"Scheduled game `{scheduled_id}` is `{row['status']}` and cannot be cancelled here.",
                ephemeral=True,
            )
            return
        connection.execute("""
            UPDATE scheduled_games
            SET status = 'cancelled', updated_at = ?
            WHERE id = ?
        """, (utc_now_iso(), scheduled_id))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "cancel_scheduled_game",
            interaction.user.id,
            interaction.user,
            "scheduled_game",
            scheduled_id,
            "Cancelled scheduled game from Discord.",
        )
    await interaction.response.send_message(
        f"Cancelled scheduled game `{scheduled_id}`.",
        ephemeral=True,
    )


@tree.command(name="startgame", description="Start a guessing game in a channel")
@app_commands.guild_only()
@app_commands.describe(
    channel="Channel where users will guess",
    answer="Correct answer for the media. Use | to add aliases.",
    media="Image, video, or audio to guess",
    text="Optional prompt text",
    category="Optional hidden category for generated hints",
    hint="Optional custom hint to include with generated hints",
    auto_hint_minutes="Minutes between automatic hints. Use 0 to disable.",
)
async def startgame(
    interaction,
    channel: discord.TextChannel,
    answer: str,
    media: discord.Attachment,
    text: str = "",
    category: str = "",
    hint: str = "",
    auto_hint_minutes: int = 0,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    paused = emergency_pause_message(guild_config)
    if paused:
        await interaction.response.send_message(paused, ephemeral=True)
        return
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return

    answer = answer.strip()
    answer_aliases = parse_answer_aliases(answer)
    if not answer_aliases:
        await interaction.response.send_message(
            "The answer cannot be empty.",
            ephemeral=True,
        )
        return
    answer_display = answer_aliases[0]["display"]
    normalized_answer = answer_aliases[0]["normalized"]
    category = category.strip()
    hint = hint.strip()
    try:
        auto_hint_minutes = int(auto_hint_minutes or 0)
    except (TypeError, ValueError):
        auto_hint_minutes = 0
    game_settings = guild_game_settings(guild_config)
    if auto_hint_minutes == 0:
        try:
            auto_hint_minutes = int(
                game_settings.get("default_auto_hint_minutes") or 0
            )
        except (TypeError, ValueError):
            auto_hint_minutes = 0
    if auto_hint_minutes < 0 or auto_hint_minutes > 1440:
        await interaction.response.send_message(
            "Automatic hint minutes must be between 0 and 1440.",
            ephemeral=True,
        )
        return
    if len(text) > config["limits"]["max_text_length"]:
        await interaction.response.send_message(
            f"Text is limited to {config['limits']['max_text_length']} characters.",
            ephemeral=True,
        )
        return
    if len(hint) > 500:
        await interaction.response.send_message(
            "Hints are limited to 500 characters.",
            ephemeral=True,
        )
        return
    if not is_allowed_file(media.filename):
        await interaction.response.send_message(
            "The game media must be an image, video, or audio file.",
            ephemeral=True,
        )
        return
    if media.size > guild_max_file_bytes(guild_config):
        await interaction.response.send_message(
            "The game media exceeds the per-file size limit.",
            ephemeral=True,
        )
        return
    storage_limit = guild_storage_limit(guild_config)
    if storage_limit and guild_media_size(interaction.guild_id) + int(media.size or 0) > storage_limit:
        await interaction.response.send_message(
            "This server has reached its configured media storage limit.",
            ephemeral=True,
        )
        return

    with database() as connection:
        limit = guild_active_game_limit(guild_config)
        active_same_channel = connection.execute("""
            SELECT 1
            FROM guess_games
            WHERE guild_id = ? AND channel_id = ? AND status = 'active'
            LIMIT 1
        """, (str(interaction.guild_id), str(channel.id))).fetchone()
        if limit and active_game_count(connection, interaction.guild_id) >= limit and not active_same_channel:
            await interaction.response.send_message(
                "This server has reached its active game limit.",
                ephemeral=True,
            )
            return
        recent_answer = answer_recently_used(
            connection,
            interaction.guild_id,
            normalized_answer,
            game_settings.get("reuse_cooldown_days", 30),
        )
        if recent_answer:
            await interaction.response.send_message(
                (
                    "That answer was used recently "
                    f"({recent_answer['created_at']}). Pick another answer "
                    "or lower the reuse cooldown with `/setgamesettings`."
                ),
                ephemeral=True,
            )
            return

    bot_member = interaction.guild.me
    if bot_member is None and bot.user is not None:
        bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        await interaction.response.send_message(
            "The bot could not verify its permissions in that channel.",
            ephemeral=True,
        )
        return

    permissions = channel.permissions_for(bot_member)
    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.attach_files
    ):
        await interaction.response.send_message(
            "The bot needs View Channel, Send Messages, and Attach Files "
            f"in {channel.mention}.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    replaced_game = await close_active_guess_game(
        interaction.guild_id,
        channel.id,
        "replaced",
    )
    game_folder = (
        MEDIA_DIR
        / str(interaction.guild_id)
        / "guess_games"
        / str(channel.id)
    )
    game_folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(media.filename).name.replace("\\", "_")
    media_path = game_folder / f"{int(time.time())}_{interaction.id}_{safe_name}"
    discord_file = None
    game_message = None
    game_id = None

    try:
        await media.save(media_path)
        maybe_compress_image(media_path, media.filename)
        media_metadata = attachment_metadata(media, media_path)
        discord_file = discord.File(media_path, filename=media.filename)
        game_lines = ["**Guessing Game Started**"]
        prompt_text = text.strip()
        if prompt_text:
            game_lines.append(prompt_text)
        if auto_hint_minutes > 0:
            game_lines.append(
                f"Automatic hints are enabled every {auto_hint_minutes} minute(s)."
            )
        game_lines.append("Use `/guess <guess>` in this channel.")
        generated_hints = build_game_hints(answer_display, category, hint)
        game_message = await channel.send(
            content="\n\n".join(game_lines),
            file=discord_file,
        )

        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO guess_games (
                    guild_id, channel_id, message_id, starter_user_id,
                    starter_username, answer, answer_display, prompt_text,
                    media_path, media_name, media_type, media_size,
                    media_metadata_json, answer_aliases_json, hints_json,
                    hint_level, next_hint_at, auto_hint_minutes,
                    hint_category, library_item_id, status, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'active', ?)
            """, (
                str(interaction.guild_id),
                str(channel.id),
                str(game_message.id),
                str(interaction.user.id),
                str(interaction.user),
                normalized_answer,
                answer_display,
                prompt_text,
                str(media_path),
                media.filename,
                get_media_type(media.filename),
                int(media.size or 0),
                json.dumps(media_metadata, separators=(",", ":")),
                json.dumps(answer_aliases, separators=(",", ":")),
                json.dumps(generated_hints, separators=(",", ":")),
                next_hint_time(auto_hint_minutes),
                auto_hint_minutes,
                category,
                None,
                utc_now_iso(),
            ))
            game_id = cursor.lastrowid
            record_guess_answer_history(
                connection,
                interaction.guild_id,
                channel.id,
                game_id,
                None,
                normalized_answer,
                answer_display,
                category,
                "manual",
                interaction.user,
            )
            add_admin_audit_log(
                connection,
                interaction.guild_id,
                "start_guess_game",
                interaction.user.id,
                interaction.user,
                "game",
                game_id,
                (
                    f"Channel {channel.id}; media {media.filename}; "
                    f"aliases={len(answer_aliases)}; "
                    f"auto_hint_minutes={auto_hint_minutes}; "
                    f"replaced={bool(replaced_game)}."
                ),
            )

        await interaction.followup.send(
            (
                f"Guessing game `{game_id}` started in {channel.mention}."
                + (" Previous active game was removed." if replaced_game else "")
            ),
            ephemeral=True,
        )
    except Exception as error:
        capture_exception(error)
        if game_message is not None:
            try:
                await game_message.delete()
            except discord.HTTPException:
                pass
        if game_id is not None:
            with database() as connection:
                connection.execute(
                    "DELETE FROM guess_games WHERE id = ?",
                    (game_id,),
                )
        cleanup_files([str(media_path)])
        await interaction.followup.send(
            f"Game start failed: `{error}`",
            ephemeral=True,
        )
    finally:
        if discord_file is not None:
            discord_file.close()


@tree.command(
    name="startlibrarygame",
    description="Start a saved guessing game from the website library",
)
@app_commands.guild_only()
@app_commands.describe(
    channel="Channel where users will guess",
    item_id="Library item ID from the dashboard. Use 0 for next unused item.",
    category="Optional library category filter when item_id is 0",
    random_item="Pick a random matching library item",
)
async def startlibrarygame(
    interaction,
    channel: discord.TextChannel,
    item_id: int = 0,
    category: str = "",
    random_item: bool = False,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    paused = emergency_pause_message(guild_config)
    if paused:
        await interaction.response.send_message(paused, ephemeral=True)
        return
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return

    bot_member = interaction.guild.me
    if bot_member is None and bot.user is not None:
        bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        await interaction.response.send_message(
            "The bot could not verify its permissions in that channel.",
            ephemeral=True,
        )
        return

    permissions = channel.permissions_for(bot_member)
    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.attach_files
    ):
        await interaction.response.send_message(
            "The bot needs View Channel, Send Messages, and Attach Files "
            f"in {channel.mention}.",
            ephemeral=True,
        )
        return

    category_filter = (category or "").strip()
    game_settings = guild_game_settings(guild_config)
    try:
        reuse_cooldown_days = int(game_settings.get("reuse_cooldown_days") or 0)
    except (TypeError, ValueError):
        reuse_cooldown_days = 0

    with database() as connection:
        limit = guild_active_game_limit(guild_config)
        active_same_channel = connection.execute("""
            SELECT 1
            FROM guess_games
            WHERE guild_id = ? AND channel_id = ? AND status = 'active'
            LIMIT 1
        """, (str(interaction.guild_id), str(channel.id))).fetchone()
        if limit and active_game_count(connection, interaction.guild_id) >= limit and not active_same_channel:
            await interaction.response.send_message(
                "This server has reached its active game limit.",
                ephemeral=True,
            )
            return
        if item_id > 0:
            item = connection.execute("""
                SELECT *
                FROM guess_library_items
                WHERE id = ?
                  AND guild_id = ?
                  AND status = 'active'
                LIMIT 1
            """, (item_id, str(interaction.guild_id))).fetchone()
        else:
            where = [
                "guild_id = ?",
                "status = 'active'",
                "media_path IS NOT NULL",
                "media_path != ''",
            ]
            parameters = [str(interaction.guild_id)]
            if category_filter:
                where.append("LOWER(category) = LOWER(?)")
                parameters.append(category_filter)
            if reuse_cooldown_days > 0:
                where.append("(last_used_at IS NULL OR last_used_at = '' OR last_used_at < ?)")
                parameters.append(
                    (
                        datetime.now(timezone.utc)
                        - timedelta(days=reuse_cooldown_days)
                    ).isoformat()
                )
            order_sql = (
                "RANDOM()"
                if random_item
                else """
                    CASE WHEN last_used_at IS NULL OR last_used_at = '' THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    id ASC
                """
            )
            item = connection.execute(f"""
                SELECT *
                FROM guess_library_items
                WHERE {" AND ".join(where)}
                ORDER BY {order_sql}
                LIMIT 1
            """, parameters).fetchone()

    if not item:
        filter_text = f" in category `{category_filter}`" if category_filter else ""
        await interaction.response.send_message(
            (
                "No active website game-library item with media was found "
                f"for this server{filter_text}."
                if item_id <= 0
                else f"Active website game-library item `{item_id}` was not found for this server."
            ),
            ephemeral=True,
        )
        return

    try:
        answer_aliases = json.loads(item["answer_aliases_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        answer_aliases = []
    if not answer_aliases:
        answer_aliases = parse_answer_aliases(
            item["answer_display"] or item["answer"]
        )
    if not answer_aliases:
        await interaction.response.send_message(
            f"Library item `{item['id']}` does not have a usable answer.",
            ephemeral=True,
        )
        return

    answer_display = item["answer_display"] or answer_aliases[0]["display"]
    normalized_answer = item["answer"] or answer_aliases[0]["normalized"]
    with database() as connection:
        recent_answer = answer_recently_used(
            connection,
            interaction.guild_id,
            normalized_answer,
            reuse_cooldown_days,
        )
    if recent_answer:
        await interaction.response.send_message(
            (
                "That library answer was used recently "
                f"({recent_answer['created_at']}). Pick another item "
                "or lower the reuse cooldown with `/setgamesettings`."
            ),
            ephemeral=True,
        )
        return
    media_name = item["media_name"] or Path(item["media_path"] or "").name
    if not media_name or not is_allowed_file(media_name):
        await interaction.response.send_message(
            f"Library item `{item['id']}` does not have valid game media.",
            ephemeral=True,
        )
        return

    source_path = Path(item["media_path"] or "")
    if not source_path.is_absolute():
        source_path = BASE_DIR / source_path
    try:
        source_path = source_path.resolve()
        source_path.relative_to(MEDIA_DIR.resolve())
    except (OSError, ValueError):
        await interaction.response.send_message(
            f"Library item `{item['id']}` points to media outside the media folder.",
            ephemeral=True,
        )
        return
    if not source_path.is_file():
        await interaction.response.send_message(
            f"Library item `{item['id']}` is missing its media file.",
            ephemeral=True,
        )
        return

    media_size = source_path.stat().st_size
    if media_size > guild_max_file_bytes(guild_config):
        await interaction.response.send_message(
            f"Library item `{item['id']}` exceeds the per-file size limit.",
            ephemeral=True,
        )
        return
    storage_limit = guild_storage_limit(guild_config)
    if storage_limit and guild_media_size(interaction.guild_id) + media_size > storage_limit:
        await interaction.response.send_message(
            "This server has reached its configured media storage limit.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    replaced_game = await close_active_guess_game(
        interaction.guild_id,
        channel.id,
        "replaced",
    )
    game_folder = (
        MEDIA_DIR
        / str(interaction.guild_id)
        / "guess_games"
        / str(channel.id)
    )
    game_folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(media_name).name.replace("\\", "_")
    media_path = game_folder / f"{int(time.time())}_{interaction.id}_{safe_name}"
    discord_file = None
    game_message = None
    game_id = None

    try:
        shutil.copy2(source_path, media_path)
        maybe_compress_image(media_path, media_name)
        try:
            stored_metadata = json.loads(item["media_metadata_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            stored_metadata = {}
        media_metadata = stored_media_metadata(
            media_name,
            media_path,
            stored_metadata.get("content_type", ""),
        )
        discord_file = discord.File(media_path, filename=media_name)
        game_lines = ["**Guessing Game Started**"]
        prompt_text = (item["prompt_text"] or "").strip()
        if prompt_text:
            game_lines.append(prompt_text)
        auto_hint_minutes = int(item["auto_hint_minutes"] or 0)
        if auto_hint_minutes == 0:
            try:
                auto_hint_minutes = int(
                    game_settings.get("default_auto_hint_minutes") or 0
                )
            except (TypeError, ValueError):
                auto_hint_minutes = 0
        if auto_hint_minutes > 0:
            game_lines.append(
                f"Automatic hints are enabled every {auto_hint_minutes} minute(s)."
            )
        game_lines.append("Use `/guess <guess>` in this channel.")
        generated_hints = build_game_hints(
            answer_display,
            item["category"] or "",
            item["hint_text"] or "",
        )
        game_message = await channel.send(
            content="\n\n".join(game_lines),
            file=discord_file,
        )

        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO guess_games (
                    guild_id, channel_id, message_id, starter_user_id,
                    starter_username, answer, answer_display, prompt_text,
                    media_path, media_name, media_type, media_size,
                    media_metadata_json, answer_aliases_json, hints_json,
                    hint_level, next_hint_at, auto_hint_minutes,
                    hint_category, library_item_id, status, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'active', ?)
            """, (
                str(interaction.guild_id),
                str(channel.id),
                str(game_message.id),
                str(interaction.user.id),
                str(interaction.user),
                normalized_answer,
                answer_display,
                prompt_text,
                str(media_path),
                media_name,
                get_media_type(media_name),
                int(media_metadata.get("size") or media_size),
                json.dumps(media_metadata, separators=(",", ":")),
                json.dumps(answer_aliases, separators=(",", ":")),
                json.dumps(generated_hints, separators=(",", ":")),
                next_hint_time(auto_hint_minutes),
                auto_hint_minutes,
                item["category"] or "",
                item["id"],
                utc_now_iso(),
            ))
            game_id = cursor.lastrowid
            record_guess_answer_history(
                connection,
                interaction.guild_id,
                channel.id,
                game_id,
                item["id"],
                normalized_answer,
                answer_display,
                item["category"] or "",
                "library",
                interaction.user,
            )
            connection.execute("""
                UPDATE guess_library_items
                SET times_used = COALESCE(times_used, 0) + 1,
                    last_used_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (utc_now_iso(), utc_now_iso(), item["id"]))
            add_admin_audit_log(
                connection,
                interaction.guild_id,
                "start_library_guess_game",
                interaction.user.id,
                interaction.user,
                "game",
                game_id,
                (
                    f"Channel {channel.id}; library item {item['id']}; "
                    f"media {media_name}; aliases={len(answer_aliases)}; "
                    f"auto_hint_minutes={auto_hint_minutes}; "
                    f"replaced={bool(replaced_game)}."
                ),
            )

        await interaction.followup.send(
            (
                f"Guessing game `{game_id}` started in {channel.mention} "
                f"from library item `{item['id']}`."
                + (" Previous active game was removed." if replaced_game else "")
            ),
            ephemeral=True,
        )
    except Exception as error:
        capture_exception(error)
        if game_message is not None:
            try:
                await game_message.delete()
            except discord.HTTPException:
                pass
        if game_id is not None:
            with database() as connection:
                connection.execute(
                    "DELETE FROM guess_games WHERE id = ?",
                    (game_id,),
                )
        cleanup_files([str(media_path)])
        await interaction.followup.send(
            f"Library game start failed: `{error}`",
            ephemeral=True,
        )
    finally:
        if discord_file is not None:
            discord_file.close()


@tree.command(name="activegame", description="Show this channel's active guessing game")
@app_commands.guild_only()
async def activegame(interaction):
    if not await require_admin(interaction):
        return

    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return
    timezone_info = get_guild_timezone(guild_config)
    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()
        correct_rows = []
        if game:
            correct_rows = connection.execute("""
                SELECT username, guessed_at
                FROM guess_correct_guesses
                WHERE game_id = ?
                ORDER BY guessed_at ASC
            """, (game["id"],)).fetchall()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    started_at = parse_database_datetime(game["started_at"])
    started_display = started_at.astimezone(timezone_info).strftime(
        "%Y-%m-%d %H:%M"
    )
    correct_names = [row["username"] for row in correct_rows]
    correct_display = ", ".join(correct_names[:20]) if correct_names else "Nobody"
    if len(correct_names) > 20:
        correct_display += f" and {len(correct_names) - 20} more"
    try:
        aliases = json.loads(game["answer_aliases_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        aliases = []
    alias_display = ", ".join(
        alias.get("display", "")
        for alias in aliases[1:]
        if alias.get("display")
    ) or "(none)"
    try:
        hints = json.loads(game["hints_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        hints = []
    hint_level = int(game["hint_level"] or 0)

    await interaction.response.send_message(
        "\n".join([
            f"**Active Guessing Game {game['id']}**",
            f"Channel: {channel_display(game['channel_id'])}",
            f"Started by: {game['starter_username']}",
            f"Started: `{started_display}` `{guild_config.get('timezone', 'UTC')}`",
            f"Answer: `{game['answer_display']}`",
            f"Aliases: {alias_display}",
            f"Prompt: {game['prompt_text'] or '(none)'}",
            f"Hint category: {game['hint_category'] or '(none)'}",
            f"Hint: {game['hint_text'] or '(none)'}",
            f"Hints revealed: `{hint_level}` of `{len(hints)}`",
            f"Next auto hint: `{game['next_hint_at'] or 'disabled'}`",
            f"Media: `{game['media_name']}` ({game['media_type']})",
            f"Library item: `{game['library_item_id'] or 'none'}`",
            f"Correct guessers: {correct_display}",
        ]),
        ephemeral=True,
    )


@tree.command(name="cancelgame", description="Cancel this channel's active guessing game")
@app_commands.guild_only()
async def cancelgame(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    game = await close_active_guess_game(
        interaction.guild_id,
        interaction.channel_id,
        "cancelled",
    )
    if not game:
        await interaction.followup.send(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    audit_interaction(
        interaction,
        "cancel_guess_game",
        "game",
        game["id"],
        f"Cancelled in channel {interaction.channel_id}.",
    )
    await interaction.followup.send(
        f"Cancelled guessing game `{game['id']}` without revealing the answer.",
        ephemeral=True,
    )
    if interaction.channel is not None:
        await interaction.channel.send("The current guessing game was cancelled.")


@tree.command(name="sethint", description="Reveal a hint for this channel's game")
@app_commands.guild_only()
@app_commands.describe(hint="Hint to reveal for the active game")
async def sethint(interaction, hint: str):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return
    hint = hint.strip()
    if not hint:
        await interaction.response.send_message(
            "Hint cannot be empty.",
            ephemeral=True,
        )
        return

    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()
        if not game:
            await interaction.response.send_message(
                "There is no active guessing game in this channel.",
                ephemeral=True,
            )
            return
        new_hint_text = append_hint_text(game["hint_text"], hint)
        connection.execute("""
            UPDATE guess_games
            SET hint_text = ?,
                hint_revealed_at = COALESCE(hint_revealed_at, ?)
            WHERE id = ?
        """, (new_hint_text, utc_now_iso(), game["id"]))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "set_guess_hint",
            interaction.user.id,
            interaction.user,
            "game",
            game["id"],
            "Hint revealed for active guessing game.",
        )

    await interaction.response.send_message(
        "Hint revealed.",
        ephemeral=True,
    )
    await interaction.channel.send(
        f"**Guessing Game Hint**\n{hint}\n\n"
        "Correct guesses after a hint do not add leaderboard points."
    )


@tree.command(name="revealhint", description="Reveal the next generated hint")
@app_commands.guild_only()
async def revealhint(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return

    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()
        if not game:
            await interaction.response.send_message(
                "There is no active guessing game in this channel.",
                ephemeral=True,
            )
            return
        hint_text = reveal_next_hint_for_game(connection, game)
        if not hint_text:
            await interaction.response.send_message(
                "There are no generated hints left for this game.",
                ephemeral=True,
            )
            return
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "reveal_guess_hint",
            interaction.user.id,
            interaction.user,
            "game",
            game["id"],
            "Generated hint revealed for active guessing game.",
        )

    await interaction.response.send_message("Generated hint revealed.", ephemeral=True)
    await interaction.channel.send(
        f"**Guessing Game Hint**\n{hint_text}\n\n"
        "Correct guesses after a hint do not add leaderboard points."
    )


@tree.command(name="hint", description="Show this channel's game hint")
@app_commands.guild_only()
async def hint(interaction):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return
    with database() as connection:
        game = connection.execute("""
            SELECT hint_text, hint_revealed_at
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return
    if not game["hint_revealed_at"] or not game["hint_text"]:
        await interaction.response.send_message(
            "No hint has been revealed yet.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"**Hint:** {game['hint_text']}",
        ephemeral=True,
    )


@tree.command(name="guess", description="Guess the answer for this channel's game")
@app_commands.guild_only()
@app_commands.describe(guess="Your guess")
async def guess(interaction, guess: str):
    guild_config = get_guild_config(interaction.guild_id, create=False)
    paused = emergency_pause_message(guild_config)
    if paused:
        await interaction.response.send_message(paused, ephemeral=True)
        return
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return
    with database() as connection:
        restriction = active_user_restriction(
            connection,
            interaction.guild_id,
            interaction.user.id,
            "games",
        )
    if restriction:
        await interaction.response.send_message(
            user_lockout_message(restriction, "games"),
            ephemeral=True,
        )
        return
    normalized_guess = normalize_guess(guess)
    if not normalized_guess:
        await interaction.response.send_message(
            "Your guess cannot be empty.",
            ephemeral=True,
        )
        return

    message, retry_after = command_cooldown_message(
        "guess_command",
        interaction.guild_id,
        interaction.user.id,
        configured_limit("guess_command_cooldown_seconds", 2),
    )
    if message:
        record_rate_limit_event(
            interaction.guild_id,
            interaction.user.id,
            interaction.user,
            "guess_command",
            "guess",
            retry_after,
            "Slash command cooldown.",
        )
        await interaction.response.send_message(message, ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    channel = interaction.channel
    achievement_labels = []
    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

        if not game:
            await interaction.response.send_message(
                "There is no active guessing game in this channel.",
                ephemeral=True,
            )
            return

        cooldown = connection.execute("""
            SELECT timeout_until
            FROM guess_cooldowns
            WHERE guild_id = ?
              AND channel_id = ?
              AND user_id = ?
        """, (
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
        )).fetchone()

        if cooldown and cooldown["timeout_until"]:
            timeout_until = datetime.fromisoformat(cooldown["timeout_until"])
            if timeout_until > now:
                remaining = int((timeout_until - now).total_seconds()) + 1
                await interaction.response.send_message(
                    f"Wrong guess cooldown: try again in {remaining}s.",
                    ephemeral=True,
                )
                return

        if not answer_alias_matches(game, normalized_guess):
            seconds = config["limits"].get(
                "wrong_guess_timeout_seconds",
                600,
            )
            timeout_until = now + timedelta(seconds=seconds)
            connection.execute("""
                INSERT INTO guess_cooldowns (
                    guild_id, channel_id, user_id, timeout_until
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT (guild_id, channel_id, user_id)
                DO UPDATE SET timeout_until = excluded.timeout_until
            """, (
                str(interaction.guild_id),
                str(interaction.channel_id),
                str(interaction.user.id),
                timeout_until.isoformat(),
            ))
            connection.execute("""
                INSERT INTO rate_limit_events (
                    guild_id, user_id, username, bucket, action,
                    retry_after_seconds, details, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(interaction.guild_id),
                str(interaction.user.id),
                str(interaction.user),
                "wrong_guess",
                "guess",
                int(seconds),
                f"Game {game['id']}.",
                utc_now_iso(),
            ))
            await interaction.response.send_message(
                f"Incorrect. You can guess again in {seconds}s.",
                ephemeral=True,
            )
            return

        month = current_month_key(guild_config)
        points_awarded = 0 if game["hint_revealed_at"] else 1
        existing_correct = connection.execute("""
            SELECT 1
            FROM guess_correct_guesses
            WHERE game_id = ? AND user_id = ?
        """, (game["id"], str(interaction.user.id))).fetchone()
        if existing_correct:
            await interaction.response.send_message(
                "You already guessed this one correctly.",
                ephemeral=True,
            )
            return

        connection.execute("""
            INSERT INTO guess_correct_guesses (
                game_id, guild_id, channel_id, user_id, username, guessed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            game["id"],
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
            str(interaction.user),
            utc_now_iso(),
        ))
        connection.execute("""
            UPDATE guess_games
            SET winner_user_id = COALESCE(winner_user_id, ?),
                winner_username = COALESCE(winner_username, ?)
            WHERE id = ? AND status = 'active'
        """, (
            str(interaction.user.id),
            str(interaction.user),
            game["id"],
        ))
        if points_awarded:
            connection.execute("""
                INSERT INTO guess_points (
                    guild_id, channel_id, user_id, username,
                    month, points, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (guild_id, channel_id, user_id, month)
                DO UPDATE SET
                    points = points + excluded.points,
                    username = excluded.username,
                    updated_at = excluded.updated_at
            """, (
                str(interaction.guild_id),
                str(interaction.channel_id),
                str(interaction.user.id),
                str(interaction.user),
                month,
                points_awarded,
                utc_now_iso(),
            ))
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE guild_id = ?
              AND channel_id = ?
              AND user_id = ?
        """, (
            str(interaction.guild_id),
            str(interaction.channel_id),
            str(interaction.user.id),
        ))
        achievement_labels = record_guess_success_achievements(
            connection,
            interaction.guild_id,
            interaction.user.id,
            interaction.user,
            game["id"],
            month,
        )

    if points_awarded:
        response_text = f"Correct. You gained {points_awarded} point for `{month}`."
    else:
        response_text = (
            "Correct. This game already has a hint revealed, so no "
            "leaderboard point was added."
        )
    if achievement_labels:
        response_text += "\nNew achievement(s): " + ", ".join(
            f"`{label}`" for label in achievement_labels
        )
    await interaction.response.send_message(response_text, ephemeral=True)
    if channel is not None:
        await channel.send(
            f"{interaction.user.mention} guessed correctly."
        )


@tree.command(name="correct", description="Reveal and close this channel's guessing game")
@app_commands.guild_only()
async def correct(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id, create=False)
    if not feature_enabled(guild_config, "guessing_games"):
        await interaction.response.send_message(
            "Guessing games are currently disabled for this server.",
            ephemeral=True,
        )
        return

    with database() as connection:
        game = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE guild_id = ?
              AND channel_id = ?
              AND status = 'active'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """, (str(interaction.guild_id), str(interaction.channel_id))).fetchone()

    if not game:
        await interaction.response.send_message(
            "There is no active guessing game in this channel.",
            ephemeral=True,
        )
        return

    with database() as connection:
        connection.execute("""
            UPDATE guess_games
            SET status = 'closed',
                solved_at = ?
            WHERE id = ? AND status = 'active'
        """, (utc_now_iso(), game["id"]))
        connection.execute("""
            DELETE FROM guess_cooldowns
            WHERE guild_id = ? AND channel_id = ?
        """, (str(interaction.guild_id), str(interaction.channel_id)))
        add_admin_audit_log(
            connection,
            interaction.guild_id,
            "correct_guess_game",
            interaction.user.id,
            interaction.user,
            "game",
            game["id"],
            f"Closed and revealed in channel {interaction.channel_id}.",
        )

    await interaction.response.send_message(
        "Closing the current guessing game.",
        ephemeral=True,
    )
    await announce_guess_summary(interaction.channel, game, "manual close")


@tree.command(name="removesubmission", description="Remove a submission")
@app_commands.guild_only()
@app_commands.describe(
    submission_id="Dashboard submission ID",
    reason_preset="Standard reason preset",
    reason="Optional custom audit reason",
)
@app_commands.choices(reason_preset=REASON_PRESET_CHOICES)
async def removesubmission(
    interaction,
    submission_id: int,
    reason_preset: Optional[app_commands.Choice[str]] = None,
    reason: str = "",
):
    if not await require_admin(interaction):
        return
    final_reason = (reason or "").strip()
    if reason_preset is not None:
        preset_text = MODERATION_REASON_PRESETS.get(reason_preset.value, "")
        final_reason = (
            f"{preset_text}: {final_reason}"
            if final_reason
            else preset_text
        )
    if not final_reason:
        final_reason = "Removed by Discord admin"
    await interaction.response.defer(ephemeral=True, thinking=True)
    with database() as connection:
        row = connection.execute(
            "SELECT guild_id FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if row and row["guild_id"] and row["guild_id"] != str(interaction.guild_id):
        await interaction.followup.send(
            "That submission belongs to another server.",
            ephemeral=True,
        )
        return
    success, message = await remove_submission_record(
        submission_id,
        interaction.user.id,
        interaction.user,
        final_reason,
    )
    await interaction.followup.send(message, ephemeral=True)


@tree.command(name="submissioninfo", description="Show submission details")
@app_commands.guild_only()
async def submissioninfo(interaction, submission_id: int):
    if not await require_admin(interaction):
        return
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM submissions WHERE id = ?",
            (submission_id,),
        ).fetchone()
    if not row or (
        row["guild_id"]
        and row["guild_id"] != str(interaction.guild_id)
    ):
        await interaction.response.send_message(
            "Submission not found.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        "\n".join([
            f"**Submission {row['id']}**",
            f"Status: `{row['status']}`",
            f"Category: `{row['category']}`",
            f"User: {row['username']} (`{row['user_id']}`)",
            f"Stars: {row['stars'] or 0}",
            f"Created: {row['created_at'] or row['submitted_at']}",
            f"Text: {row['message_text'] or '(none)'}",
        ]),
        ephemeral=True,
    )


async def post_weekly_top(guild_id, guild_config, now):
    if not feature_enabled(guild_config, "weekly_posts"):
        return
    channel_id = guild_config.get("daily_top_channel")
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    week_key = weekly_run_key(now)
    with database() as connection:
        already_ran = connection.execute("""
            SELECT 1 FROM daily_runs
            WHERE guild_id = ? AND run_date = ?
        """, (str(guild_id), week_key)).fetchone()
        if already_ran:
            return

        rows = []
        for category in sorted(guild_config.get("categories", {})):
            row = connection.execute("""
                SELECT *
                FROM submissions
                WHERE guild_id = ?
                  AND category = ?
                  AND status = 'posted'
                  AND daily_posted_at IS NULL
                ORDER BY stars DESC, created_at DESC
                LIMIT 1
            """, (str(guild_id), category)).fetchone()
            if row:
                rows.append(row)

    if rows:
        lines = ["**SDAC Weekly Top Posts**"]
        for row in rows:
            link = (
                f"https://discord.com/channels/{guild_id}/"
                f"{row['repost_channel_id']}/{row['repost_message_id']}"
            )
            preview = (row["message_text"] or "").strip()[:100]
            lines.append(
                f"\n**{row['category']}** - {row['username']} - "
                f"{row['stars'] or 0} votes\n{preview}\n{link}"
            )
        await channel.send("\n".join(lines))

    with database() as connection:
        for row in rows:
            connection.execute(
                "UPDATE submissions SET daily_posted_at = ? WHERE id = ?",
                (utc_now_iso(), row["id"]),
            )
        connection.execute("""
            INSERT OR IGNORE INTO daily_runs (guild_id, run_date, created_at)
            VALUES (?, ?, ?)
        """, (str(guild_id), week_key, utc_now_iso()))


async def post_monthly_guess_leaderboards():
    with database() as connection:
        guild_rows = connection.execute("""
            SELECT DISTINCT guild_id
            FROM guess_points
            WHERE guild_id IS NOT NULL AND guild_id != ''
        """).fetchall()

    for guild_row in guild_rows:
        guild_id = guild_row["guild_id"]
        guild_config = get_guild_config(guild_id, create=False)
        if not feature_enabled(guild_config, "guessing_games"):
            continue
        now = guild_now(guild_config)
        if now.day != 1:
            continue

        month = previous_month_key(now)
        with database() as connection:
            preserve_monthly_submission_top(connection, month)
            channel_rows = connection.execute("""
                SELECT DISTINCT guild_id, channel_id
                FROM guess_points
                WHERE guild_id = ?
                  AND month = ?
            """, (guild_id, month)).fetchall()

        for channel_row in channel_rows:
            channel_id = channel_row["channel_id"]
            with database() as connection:
                already_posted = connection.execute("""
                    SELECT 1
                    FROM monthly_guess_runs
                    WHERE guild_id = ?
                      AND channel_id = ?
                      AND month = ?
                """, (guild_id, channel_id, month)).fetchone()
                if already_posted:
                    continue
                leaders = connection.execute("""
                    SELECT username, points
                    FROM guess_points
                    WHERE guild_id = ?
                      AND channel_id = ?
                      AND month = ?
                    ORDER BY points DESC, username ASC
                    LIMIT 3
                """, (guild_id, channel_id, month)).fetchall()

            if not leaders:
                continue

            channel = bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                except discord.HTTPException:
                    channel = None
            if channel is None:
                continue

            lines = [f"**Guessing Game Top 3 - {month}**"]
            for index, leader in enumerate(leaders, start=1):
                lines.append(
                    f"{index}. {leader['username']} - {leader['points']} point(s)"
                )
            await channel.send("\n".join(lines))

            with database() as connection:
                connection.execute("""
                    INSERT OR IGNORE INTO monthly_guess_runs (
                        guild_id, channel_id, month, created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (guild_id, channel_id, month, utc_now_iso()))


async def post_monthly_digests():
    if not config["limits"].get("monthly_digest_enabled", True):
        return
    for guild_id, guild_config in config.get("guilds", {}).items():
        now = guild_now(guild_config)
        if now.day != 1:
            continue
        month = previous_month_key(now)
        target_channel_id = (
            guild_config.get("daily_top_channel")
            or guild_config.get("game_summary_channel")
            or guild_config.get("error_channel")
        )
        if not target_channel_id:
            continue
        with database() as connection:
            already_posted = connection.execute("""
                SELECT 1
                FROM monthly_digest_runs
                WHERE guild_id = ?
                  AND month = ?
                  AND status = 'posted'
                LIMIT 1
            """, (str(guild_id), month)).fetchone()
            if already_posted:
                continue
            preserve_monthly_submission_top(connection, month)
            top_submissions = connection.execute("""
                SELECT username, category, stars
                FROM submissions
                WHERE guild_id = ?
                  AND status = 'posted'
                  AND substr(COALESCE(created_at, submitted_at), 1, 7) = ?
                ORDER BY stars DESC, created_at DESC, id DESC
                LIMIT 3
            """, (str(guild_id), month)).fetchall()
            top_guessers = connection.execute("""
                SELECT username, SUM(points) AS points
                FROM guess_points
                WHERE guild_id = ?
                  AND month = ?
                GROUP BY user_id, username
                ORDER BY points DESC, username ASC
                LIMIT 3
            """, (str(guild_id), month)).fetchall()
            totals = {
                "submissions": connection.execute("""
                    SELECT COUNT(*)
                    FROM submissions
                    WHERE guild_id = ?
                      AND status = 'posted'
                      AND substr(COALESCE(created_at, submitted_at), 1, 7) = ?
                """, (str(guild_id), month)).fetchone()[0],
                "reports": connection.execute("""
                    SELECT COUNT(*)
                    FROM submission_reports
                    WHERE guild_id = ?
                      AND substr(created_at, 1, 7) = ?
                """, (str(guild_id), month)).fetchone()[0],
            }

        channel = bot.get_channel(int(target_channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(target_channel_id))
            except discord.HTTPException:
                channel = None
        if channel is None:
            continue

        lines = [
            f"**SDAC Monthly Digest - {month}**",
            f"Submissions: `{totals['submissions']}`",
            f"Reports handled/opened: `{totals['reports']}`",
            "",
            "**Top Submissions**",
        ]
        if top_submissions:
            for index, row in enumerate(top_submissions, start=1):
                lines.append(
                    f"{index}. {row['username']} in {row['category'] or 'Uncategorized'} - {row['stars'] or 0} vote(s)"
                )
        else:
            lines.append("No submissions last month.")
        lines.extend(["", "**Top Guessers**"])
        if top_guessers:
            for index, row in enumerate(top_guessers, start=1):
                lines.append(
                    f"{index}. {row['username']} - {row['points'] or 0} point(s)"
                )
        else:
            lines.append("No guessing points last month.")
        try:
            await channel.send("\n".join(lines)[:1900])
            status = "posted"
            details = {"channel_id": str(target_channel_id), **totals}
        except discord.HTTPException as error:
            status = "failed"
            details = {"error": str(error), **totals}
        with database() as connection:
            connection.execute("""
                INSERT INTO monthly_digest_runs (
                    guild_id, month, status, details_json, posted_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(guild_id),
                month,
                status,
                json.dumps(details, separators=(",", ":")),
                utc_now_iso() if status == "posted" else "",
                utc_now_iso(),
            ))
        if status == "failed":
            await send_error_notification(
                guild_id,
                f"Monthly digest failed for `{month}`: `{details.get('error')}`",
                "monthly_digest",
            )


def notification_digest_run_key(frequency, now):
    if frequency == "daily":
        return f"admin-digest:daily:{now.date().isoformat()}"
    return f"admin-digest:weekly:{now.strftime('%G-W%V')}"


async def post_notification_digests():
    for guild_id, guild_config in config.get("guilds", {}).items():
        digest = guild_config.get("notification_digest") or {}
        if not digest.get("enabled"):
            continue
        target_channel_id = digest.get("channel_id")
        if not target_channel_id:
            continue
        frequency = str(digest.get("frequency") or "weekly").casefold()
        if frequency not in {"daily", "weekly"}:
            frequency = "weekly"

        now = guild_now(guild_config)
        if now.hour < 9:
            continue
        if frequency == "weekly" and now.weekday() != 0:
            continue
        run_key = notification_digest_run_key(frequency, now)
        since = (
            now - timedelta(days=1)
            if frequency == "daily"
            else now - timedelta(days=7)
        )
        since_iso = since.astimezone(timezone.utc).isoformat()

        with database() as connection:
            already_posted = connection.execute("""
                SELECT 1
                FROM daily_runs
                WHERE guild_id = ? AND run_date = ?
            """, (str(guild_id), run_key)).fetchone()
            if already_posted:
                continue
            totals = {
                "submissions": connection.execute("""
                    SELECT COUNT(*)
                    FROM submissions
                    WHERE guild_id = ?
                      AND COALESCE(created_at, submitted_at, '') >= ?
                """, (str(guild_id), since_iso)).fetchone()[0],
                "reports": connection.execute("""
                    SELECT COUNT(*)
                    FROM submission_reports
                    WHERE guild_id = ?
                      AND COALESCE(created_at, '') >= ?
                """, (str(guild_id), since_iso)).fetchone()[0],
                "active_games": connection.execute("""
                    SELECT COUNT(*)
                    FROM guess_games
                    WHERE guild_id = ?
                      AND status = 'active'
                """, (str(guild_id),)).fetchone()[0],
                "queued_scheduled_games": connection.execute("""
                    SELECT COUNT(*)
                    FROM scheduled_games
                    WHERE guild_id = ?
                      AND status IN ('queued', 'starting', 'running')
                """, (str(guild_id),)).fetchone()[0],
                "failed_scheduled_games": connection.execute("""
                    SELECT COUNT(*)
                    FROM scheduled_games
                    WHERE guild_id = ?
                      AND status = 'failed'
                      AND COALESCE(updated_at, created_at, '') >= ?
                """, (str(guild_id), since_iso)).fetchone()[0],
                "pending_approvals": connection.execute("""
                    SELECT COUNT(*)
                    FROM pending_admin_actions
                    WHERE (guild_id = ? OR guild_id IS NULL OR guild_id = '')
                      AND status = 'pending'
                """, (str(guild_id),)).fetchone()[0],
            }
            backup_row = connection.execute("""
                SELECT status, destination, size_bytes, created_at
                FROM backup_archives
                WHERE guild_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            """, (str(guild_id),)).fetchone()
            top_guessers = connection.execute("""
                SELECT username, SUM(points) AS points
                FROM guess_points
                WHERE guild_id = ?
                  AND month = ?
                GROUP BY user_id, username
                ORDER BY points DESC, username ASC
                LIMIT 3
            """, (str(guild_id), now.strftime("%Y-%m"))).fetchall()

        channel = bot.get_channel(int(target_channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(target_channel_id))
            except discord.HTTPException:
                channel = None
        if channel is None:
            continue

        lines = [
            f"**SDAC Admin Digest - {frequency.title()}**",
            f"Server: `{guild_config.get('guild_name') or guild_id}`",
            f"Window starts: `{since.strftime('%Y-%m-%d %H:%M %Z')}`",
            "",
            f"Submissions: `{totals['submissions']}`",
            f"Reports: `{totals['reports']}`",
            f"Active games: `{totals['active_games']}`",
            f"Queued/running scheduled games: `{totals['queued_scheduled_games']}`",
            f"Failed scheduled games: `{totals['failed_scheduled_games']}`",
            f"Pending admin approvals: `{totals['pending_approvals']}`",
        ]
        if backup_row:
            lines.extend([
                "",
                "**Latest Backup Archive**",
                f"Status: `{backup_row['status'] or 'unknown'}`",
                f"Destination: `{backup_row['destination'] or 'local only'}`",
                f"Size: `{format_bytes(int(backup_row['size_bytes'] or 0))}`",
                f"Created: `{backup_row['created_at'] or 'unknown'}`",
            ])
        else:
            lines.extend([
                "",
                "No zip backup archive has been recorded yet. Run `/backupnow`.",
            ])
        if top_guessers:
            lines.extend(["", "**Current Month Top Guessers**"])
            for index, row in enumerate(top_guessers, start=1):
                lines.append(
                    f"{index}. {row['username']} - {row['points'] or 0} point(s)"
                )
        try:
            await channel.send("\n".join(lines)[:1900])
        except discord.HTTPException as error:
            await send_error_notification(
                guild_id,
                f"Admin digest failed: `{error}`",
                "system_errors",
            )
            continue
        with database() as connection:
            connection.execute("""
                INSERT OR IGNORE INTO daily_runs (guild_id, run_date, created_at)
                VALUES (?, ?, ?)
            """, (str(guild_id), run_key, utc_now_iso()))


async def post_daily_guess_summaries():
    with database() as connection:
        games = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE status = 'active'
        """).fetchall()

    for game in games:
        guild_config = get_guild_config(game["guild_id"], create=False)
        if not feature_enabled(guild_config, "guessing_games"):
            continue
        timezone_info = get_guild_timezone(guild_config)
        now = datetime.now(timezone_info)
        today = now.date().isoformat()
        started_at = parse_database_datetime(game["started_at"])
        if started_at.astimezone(timezone_info).date() >= now.date():
            continue

        with database() as connection:
            already_posted = connection.execute("""
                SELECT 1
                FROM daily_guess_runs
                WHERE guild_id = ?
                  AND channel_id = ?
                  AND run_date = ?
            """, (game["guild_id"], game["channel_id"], today)).fetchone()
            if already_posted:
                continue
            connection.execute("""
                UPDATE guess_games
                SET status = 'closed',
                    solved_at = ?
                WHERE id = ? AND status = 'active'
            """, (utc_now_iso(), game["id"]))
            connection.execute("""
                DELETE FROM guess_cooldowns
                WHERE guild_id = ? AND channel_id = ?
            """, (game["guild_id"], game["channel_id"]))
            connection.execute("""
                INSERT OR IGNORE INTO daily_guess_runs (
                    guild_id, channel_id, run_date, created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                game["guild_id"],
                game["channel_id"],
                today,
                utc_now_iso(),
            ))

        channel = bot.get_channel(int(game["channel_id"]))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(game["channel_id"]))
            except discord.HTTPException:
                channel = None
        if channel is not None:
            await announce_guess_summary(channel, game, "end of day")


async def post_due_guess_hints():
    now = utc_now_iso()
    with database() as connection:
        games = connection.execute("""
            SELECT *
            FROM guess_games
            WHERE status = 'active'
              AND next_hint_at IS NOT NULL
              AND next_hint_at != ''
              AND next_hint_at <= ?
            ORDER BY next_hint_at ASC, id ASC
            LIMIT 25
        """, (now,)).fetchall()

    for game in games:
        guild_config = get_guild_config(game["guild_id"], create=False)
        if not feature_enabled(guild_config, "guessing_games"):
            continue

        with database() as connection:
            fresh_game = connection.execute("""
                SELECT *
                FROM guess_games
                WHERE id = ?
                  AND status = 'active'
                  AND next_hint_at IS NOT NULL
                  AND next_hint_at != ''
                  AND next_hint_at <= ?
            """, (game["id"], now)).fetchone()
            if not fresh_game:
                continue
            hint_text = reveal_next_hint_for_game(connection, fresh_game)
            if not hint_text:
                connection.execute("""
                    UPDATE guess_games
                    SET next_hint_at = NULL
                    WHERE id = ?
                """, (game["id"],))
                continue

        channel = bot.get_channel(int(game["channel_id"]))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(game["channel_id"]))
            except discord.HTTPException:
                channel = None
        if channel is not None:
            await channel.send(
                f"**Guessing Game Hint**\n{hint_text}\n\n"
                "Correct guesses after a hint do not add leaderboard points."
            )


@tasks.loop(minutes=1)
async def weekly_top_scheduler():
    try:
        for guild_id, guild_config in config.get("guilds", {}).items():
            now = guild_now(guild_config)
            current_time = now.strftime("%H:%M")
            if now.weekday() != weekly_top_day_index(guild_config):
                continue
            if guild_config.get("daily_top_time_utc", "00:00") == current_time:
                await post_weekly_top(guild_id, guild_config, now)
    except Exception as error:
        await report_background_error("weekly_top_scheduler", error)


@weekly_top_scheduler.before_loop
async def before_weekly_top_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def backup_scheduler():
    global last_backup_date
    try:
        backup_date = datetime.now(timezone.utc).date().isoformat()
        if last_backup_date != backup_date:
            _backup_path, created, message = create_daily_database_backup()
            if not created and message != "Backup already exists.":
                await send_system_error_notification(
                    f"Daily database backup failed: `{message}`",
                    "backup_failed",
                )
            last_backup_date = backup_date
    except Exception as error:
        await report_background_error("backup_scheduler", error)


@backup_scheduler.before_loop
async def before_backup_scheduler():
    await bot.wait_until_ready()


def restore_test_weekday_index():
    day = normalize_weekday(config["limits"].get("restore_test_weekday"))
    if day is None:
        day = DEFAULT_CONFIG["limits"]["restore_test_weekday"]
    return WEEKDAY_NAMES.index(day)


def restore_test_time_minutes():
    raw_value = str(
        config["limits"].get(
            "restore_test_time_utc",
            DEFAULT_CONFIG["limits"]["restore_test_time_utc"],
        )
    )
    if not re.match(r"^\d{2}:\d{2}$", raw_value):
        raw_value = DEFAULT_CONFIG["limits"]["restore_test_time_utc"]
    hour, minute = [int(part) for part in raw_value.split(":")]
    if hour > 23 or minute > 59:
        hour, minute = [int(part) for part in (
            DEFAULT_CONFIG["limits"]["restore_test_time_utc"].split(":")
        )]
    return hour * 60 + minute


@tasks.loop(minutes=30)
async def restore_test_scheduler():
    try:
        weekly_enabled = config["limits"].get("restore_test_enabled", True)
        drill_enabled = config["limits"].get("restore_drill_enabled", True)
        if not weekly_enabled and not drill_enabled:
            return
        now = datetime.now(timezone.utc)
        if now.weekday() != restore_test_weekday_index():
            return
        if now.hour * 60 + now.minute < restore_test_time_minutes():
            return
        if weekly_enabled:
            run_key = f"restore:{now.strftime('%G-W%V')}"
            if not restore_test_has_run(run_key):
                passed, backup_path, details = run_restore_test(run_key)
                if passed:
                    print(f"Restore test passed: {details}", flush=True)
                else:
                    target = backup_path.name if backup_path else "no backup"
                    await send_system_error_notification(
                        f"Weekly restore test failed for `{target}`: `{details}`",
                        "restore_test_failed",
                    )
        if drill_enabled:
            drill_key = f"restore-drill:{now.strftime('%Y-%m')}"
            if restore_test_has_run(drill_key):
                return
            drill_passed, drill_backup_path, drill_details = run_restore_test(
                drill_key
            )
            if drill_passed:
                print(f"Monthly restore drill passed: {drill_details}", flush=True)
            else:
                drill_target = (
                    drill_backup_path.name
                    if drill_backup_path
                    else "no backup"
                )
                await send_system_error_notification(
                    (
                        f"Monthly restore drill failed for `{drill_target}`: "
                        f"`{drill_details}`"
                    ),
                    "restore_drill_failed",
                )
    except Exception as error:
        await report_background_error("restore_test_scheduler", error)


@restore_test_scheduler.before_loop
async def before_restore_test_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=10)
async def guess_summary_scheduler():
    try:
        await post_daily_guess_summaries()
    except Exception as error:
        await report_background_error("guess_summary_scheduler", error)


@guess_summary_scheduler.before_loop
async def before_guess_summary_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def guess_hint_scheduler():
    try:
        await post_due_guess_hints()
    except Exception as error:
        await report_background_error("guess_hint_scheduler", error)


@guess_hint_scheduler.before_loop
async def before_guess_hint_scheduler():
    await bot.wait_until_ready()


async def start_due_scheduled_games():
    now = datetime.now(timezone.utc)
    with database() as connection:
        due_games = connection.execute("""
            SELECT *
            FROM scheduled_games
            WHERE status = 'queued'
              AND starts_at <= ?
            ORDER BY starts_at ASC, id ASC
            LIMIT 5
        """, (now.isoformat(),)).fetchall()
        for row in due_games:
            connection.execute("""
                UPDATE scheduled_games
                SET status = 'starting', updated_at = ?
                WHERE id = ? AND status = 'queued'
            """, (utc_now_iso(), row["id"]))

    for scheduled in due_games:
        try:
            guild = bot.get_guild(int(scheduled["guild_id"]))
            if guild is None:
                raise RuntimeError("Guild is not available to the bot.")
            channel = bot.get_channel(int(scheduled["channel_id"]))
            if channel is None:
                channel = await bot.fetch_channel(int(scheduled["channel_id"]))
            guild_config = get_guild_config(guild.id, create=False)
            game_settings = guild_game_settings(guild_config)
            with database() as connection:
                item = select_library_item_for_game(
                    connection,
                    guild.id,
                    item_id=int(scheduled["library_item_id"] or 0),
                    category=scheduled["category"] or "",
                    random_item=bool(scheduled["random_item"]),
                    reuse_cooldown_days=int(
                        game_settings.get("reuse_cooldown_days") or 0
                    ),
                )
            if item is None:
                raise RuntimeError("No active matching library item was found.")
            game_id, _replaced = await start_library_game_item(
                guild,
                channel,
                item,
                scheduled["created_by"] or "system",
                scheduled["created_by_name"] or "SDAC scheduler",
                source="scheduled",
                scheduled_id=scheduled["id"],
            )
            new_status = (
                "running"
                if int(scheduled["close_after_minutes"] or 0) > 0
                else "started"
            )
            with database() as connection:
                connection.execute("""
                    UPDATE scheduled_games
                    SET status = ?, game_id = ?, updated_at = ?, last_error = ''
                    WHERE id = ?
                """, (new_status, game_id, utc_now_iso(), scheduled["id"]))
        except Exception as error:
            capture_exception(error)
            with database() as connection:
                connection.execute("""
                    UPDATE scheduled_games
                    SET status = 'failed', updated_at = ?, last_error = ?
                    WHERE id = ?
                """, (utc_now_iso(), str(error)[:1000], scheduled["id"]))
            await send_error_notification(
                scheduled["guild_id"],
                f"Scheduled game `{scheduled['id']}` failed: `{error}`",
                "system_errors",
            )


async def close_due_scheduled_games():
    now = datetime.now(timezone.utc)
    with database() as connection:
        running = connection.execute("""
            SELECT *
            FROM scheduled_games
            WHERE status = 'running'
              AND close_after_minutes > 0
            ORDER BY starts_at ASC, id ASC
            LIMIT 10
        """).fetchall()
    for scheduled in running:
        starts_at = parse_database_datetime(scheduled["starts_at"])
        if starts_at is None:
            continue
        close_at = starts_at + timedelta(
            minutes=int(scheduled["close_after_minutes"] or 0)
        )
        if close_at > now:
            continue
        try:
            channel = bot.get_channel(int(scheduled["channel_id"]))
            if channel is None:
                channel = await bot.fetch_channel(int(scheduled["channel_id"]))
            game = await close_active_guess_game(
                scheduled["guild_id"],
                scheduled["channel_id"],
                "scheduled_closed",
            )
            if game:
                await announce_guess_summary(
                    channel,
                    game,
                    f"scheduled close from scheduled game {scheduled['id']}",
                )
            with database() as connection:
                connection.execute("""
                    UPDATE scheduled_games
                    SET status = 'completed', updated_at = ?
                    WHERE id = ?
                """, (utc_now_iso(), scheduled["id"]))
        except Exception as error:
            capture_exception(error)
            with database() as connection:
                connection.execute("""
                    UPDATE scheduled_games
                    SET last_error = ?, updated_at = ?
                    WHERE id = ?
                """, (str(error)[:1000], utc_now_iso(), scheduled["id"]))


@tasks.loop(minutes=1)
async def scheduled_games_scheduler():
    try:
        await start_due_scheduled_games()
        await close_due_scheduled_games()
    except Exception as error:
        await report_background_error("scheduled_games_scheduler", error)


@scheduled_games_scheduler.before_loop
async def before_scheduled_games_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=1)
async def monthly_leaderboard_scheduler():
    try:
        await post_monthly_guess_leaderboards()
        await post_monthly_digests()
        await post_notification_digests()
    except Exception as error:
        await report_background_error("monthly_leaderboard_scheduler", error)


@monthly_leaderboard_scheduler.before_loop
async def before_monthly_leaderboard_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=60)
async def cleanup_scheduler():
    try:
        cleanup_background_data()
    except Exception as error:
        await report_background_error("cleanup_scheduler", error)


@cleanup_scheduler.before_loop
async def before_cleanup_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=6)
async def storage_warning_scheduler():
    global last_storage_warning_date
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        if last_storage_warning_date == today:
            return
        warnings = storage_warning_lines()
        if not warnings:
            return
        last_storage_warning_date = today
        await send_system_error_notification(
            "Storage warning:\n" + "\n".join(f"- {line}" for line in warnings),
            "storage_warning",
        )
    except Exception as error:
        await report_background_error("storage_warning_scheduler", error)


@storage_warning_scheduler.before_loop
async def before_storage_warning_scheduler():
    await bot.wait_until_ready()


@tasks.loop(hours=6)
async def permission_drift_scheduler():
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        for guild_id, guild_config in config.get("guilds", {}).items():
            guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
            if guild is None:
                continue
            lines = await permission_drift_lines_for_guild(guild, guild_config)
            if not lines:
                continue
            if last_permission_drift_date.get(str(guild_id)) == today:
                continue
            last_permission_drift_date[str(guild_id)] = today
            await send_error_notification(
                guild_id,
                "Permission drift detected:\n" + "\n".join(
                    f"- {line}" for line in lines[:12]
                ) + "\nRun `/repairpermissions` for the full preview.",
                "permission_drift",
            )
    except Exception as error:
        await report_background_error("permission_drift_scheduler", error)


@permission_drift_scheduler.before_loop
async def before_permission_drift_scheduler():
    await bot.wait_until_ready()


@tasks.loop(minutes=5)
async def bot_status_scheduler():
    try:
        write_bot_status("heartbeat")
    except Exception as error:
        await report_background_error("bot_status_scheduler", error)


@bot_status_scheduler.before_loop
async def before_bot_status_scheduler():
    await bot.wait_until_ready()


async def sync_slash_commands():
    global slash_commands_synced
    if slash_commands_synced:
        print("Slash commands already synced for this process.", flush=True)
        return

    local_names = ", ".join(sorted(command.name for command in tree.get_commands()))
    print(f"Local slash commands registered: {local_names}", flush=True)

    synced_global = await tree.sync()
    command_names = ", ".join(sorted(command.name for command in synced_global))
    print(
        f"Synced {len(synced_global)} global slash commands: {command_names}",
        flush=True,
    )

    for guild in bot.guilds:
        discord_guild = discord.Object(id=guild.id)
        tree.copy_global_to(guild=discord_guild)
        synced_guild = await tree.sync(guild=discord_guild)
        guild_command_names = ", ".join(
            sorted(command.name for command in synced_guild)
        )
        print(
            f"Synced {len(synced_guild)} slash commands to "
            f"{guild.name} ({guild.id}): {guild_command_names}",
            flush=True,
        )
    slash_commands_synced = True
    write_bot_status("slash_sync")


@bot.event
async def on_ready():
    global persistent_views_registered
    print(f"on_ready fired for {bot.user}. Starting slash command sync.", flush=True)
    if not persistent_views_registered:
        bot.add_view(VoteView())
        bot.add_view(ApprovalView())
        persistent_views_registered = True
    migrate_legacy_config()
    refresh_known_guilds()
    try:
        await sync_slash_commands()
    except Exception as error:
        print(f"Slash command sync failed: {error}", flush=True)
        for guild in bot.guilds:
            await send_error_notification(
                guild.id,
                f"Slash command sync failed: `{error}`",
                "system_errors",
            )
    if not weekly_top_scheduler.is_running():
        weekly_top_scheduler.start()
    if not backup_scheduler.is_running():
        backup_scheduler.start()
    if not restore_test_scheduler.is_running():
        restore_test_scheduler.start()
    if not guess_summary_scheduler.is_running():
        guess_summary_scheduler.start()
    if not guess_hint_scheduler.is_running():
        guess_hint_scheduler.start()
    if not scheduled_games_scheduler.is_running():
        scheduled_games_scheduler.start()
    if not monthly_leaderboard_scheduler.is_running():
        monthly_leaderboard_scheduler.start()
    if not cleanup_scheduler.is_running():
        cleanup_scheduler.start()
    if not storage_warning_scheduler.is_running():
        storage_warning_scheduler.start()
    if not permission_drift_scheduler.is_running():
        permission_drift_scheduler.start()
    if not bot_status_scheduler.is_running():
        bot_status_scheduler.start()
    write_bot_status("ready")
    print(f"Logged in as {bot.user}", flush=True)
    print(f"Using database: {DB_FILE}", flush=True)
    print(f"Using config: {CONFIG_FILE}", flush=True)


@bot.event
async def on_error(event_method, *args, **kwargs):
    capture_exception(Exception(f"Unhandled bot event error: {event_method}"))
    formatted = traceback.format_exc().strip()
    message = formatted[-1500:] if formatted else "Unknown bot event error."
    print(f"Unhandled event error in {event_method}: {message}", flush=True)
    await send_system_error_notification(
        f"Unhandled event error in `{event_method}`:\n```{message}```",
        "system_errors",
    )


@bot.event
async def on_guild_join(guild):
    guild_config = get_guild_config(guild.id)
    guild_config["guild_name"] = guild.name
    save_config(config)
    log_admin_action(
        guild.id,
        "bot_joined_guild",
        "system",
        "system",
        "guild",
        guild.id,
        "Bot joined server and initialized default config.",
    )
    try:
        discord_guild = discord.Object(id=guild.id)
        tree.copy_global_to(guild=discord_guild)
        await tree.sync(guild=discord_guild)
    except Exception as error:
        capture_exception(error)
        print(f"Guild command sync failed for {guild.id}: {error}", flush=True)

    welcome = (
        "**SDAC is connected.**\n"
        "An administrator can run `/setup` to walk through channels, roles, "
        "features, timezone, branding, and the setup test from Discord."
    )
    candidate_channels = []
    if guild.system_channel is not None:
        candidate_channels.append(guild.system_channel)
    candidate_channels.extend(guild.text_channels)
    seen_channels = set()
    for channel in candidate_channels:
        if channel.id in seen_channels:
            continue
        seen_channels.add(channel.id)
        bot_member = guild.me
        if bot_member is None and bot.user is not None:
            bot_member = guild.get_member(bot.user.id)
        if bot_member is None:
            break
        permissions = channel.permissions_for(bot_member)
        if permissions.view_channel and permissions.send_messages:
            try:
                await channel.send(welcome)
                break
            except discord.HTTPException:
                continue
    write_bot_status("guild_join")


def main():
    startup_health_check()
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
