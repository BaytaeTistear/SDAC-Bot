import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import TOKEN


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE = BASE_DIR / "sdac.db"
MEDIA_DIR = BASE_DIR / "media"

ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".mov", ".webm", ".mkv",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a",
}

USER_COOLDOWN_SECONDS = 30
CATEGORY_COOLDOWN_SECONDS = 5

DEFAULT_CONFIG = {
    "guilds": {},
    "limits": {
        "max_file_bytes": 25 * 1024 * 1024,
        "max_total_bytes": 50 * 1024 * 1024,
        "max_text_length": 1500,
    },
}

DEFAULT_GUILD_CONFIG = {
    "submit_channel": None,
    "daily_top_channel": None,
    "daily_top_time_utc": "00:00",
    "approval_enabled": False,
    "approval_channel": None,
    "categories": {},
}


def save_config(data):
    with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=4)
        file.write("\n")


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

    for key, value in DEFAULT_CONFIG["limits"].items():
        if key not in data["limits"]:
            data["limits"][key] = value
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
        "submit_channel",
        "daily_top_channel",
        "daily_top_time_utc",
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
    if changed:
        save_config(config)
    return guild_config


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
            CREATE TABLE IF NOT EXISTS daily_runs (
                guild_id TEXT,
                run_date TEXT,
                created_at TEXT,
                PRIMARY KEY (guild_id, run_date)
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
            CREATE INDEX IF NOT EXISTS idx_submissions_repost
            ON submissions (repost_message_id)
        """)


initialize_database()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_now_display():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def clean_category_name(category):
    return category.lower().strip().replace(" ", "")


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


def split_values(raw_value):
    if not raw_value:
        return []
    return [value for value in raw_value.split(";") if value]


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


def admin_only(interaction):
    return bool(
        interaction.guild
        and interaction.user.guild_permissions.administrator
    )


async def require_admin(interaction):
    if admin_only(interaction):
        return True
    await interaction.response.send_message(
        "Administrator permission is required.",
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


def submission_content(row):
    return (
        f"Category: **{row['category'].upper()}**\n"
        f"Submitted by: <@{row['user_id']}>\n"
        f"Submitted: {utc_now_display()}\n\n"
        f"{row['message_text'] or ''}"
    )


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!sdac ", intents=intents)
tree = bot.tree
user_cooldowns = {}
category_cooldowns = {}


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
            repost = await target_channel.send(
                content=submission_content(row),
                files=make_discord_files(row),
                view=VoteView(),
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


@tree.command(name="setsubmit", description="Set the SDAC submission channel")
@app_commands.guild_only()
@app_commands.describe(channel="Channel where users can submit")
async def setsubmit(interaction, channel: discord.TextChannel):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["submit_channel"] = channel.id
    save_config(config)
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
    lines = [
        "**SDAC Configuration**",
        f"Submit channel: {submit_channel.mention if submit_channel else 'Not set'}",
        f"Daily time: {guild_config['daily_top_time_utc']} UTC",
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


@tree.command(name="setdailychannel", description="Set daily top channel")
@app_commands.guild_only()
async def setdailychannel(
    interaction,
    channel: discord.TextChannel,
):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = channel.id
    save_config(config)
    await interaction.response.send_message(
        f"Daily top channel set to {channel.mention}.",
        ephemeral=True,
    )


@tree.command(name="cleardailychannel", description="Clear daily top channel")
@app_commands.guild_only()
async def cleardailychannel(interaction):
    if not await require_admin(interaction):
        return
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_channel"] = None
    save_config(config)
    await interaction.response.send_message(
        "Daily top channel cleared.",
        ephemeral=True,
    )


@tree.command(name="setdailytime", description="Set daily top posting time in UTC")
@app_commands.guild_only()
@app_commands.describe(hour="UTC hour from 0 to 23", minute="UTC minute from 0 to 59")
async def setdailytime(interaction, hour: app_commands.Range[int, 0, 23], minute: app_commands.Range[int, 0, 59] = 0):
    if not await require_admin(interaction):
        return
    value = f"{hour:02d}:{minute:02d}"
    guild_config = get_guild_config(interaction.guild_id)
    guild_config["daily_top_time_utc"] = value
    save_config(config)
    await interaction.response.send_message(
        f"Daily top time set to `{value} UTC`.",
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
    await interaction.response.send_message(
        f"Approval is now {'enabled' if enabled else 'disabled'}.",
        ephemeral=True,
    )


@tree.command(name="submit", description="Submit media to SDAC")
@app_commands.guild_only()
@app_commands.autocomplete(category=category_autocomplete)
@app_commands.describe(
    category="Submission category",
    media1="Required image, video, or audio file",
    text="Optional message text",
    media2="Optional extra media file",
    media3="Optional extra media file",
    media4="Optional extra media file",
    media5="Optional extra media file",
)
async def submit(
    interaction,
    category: str,
    media1: discord.Attachment,
    text: str = "",
    media2: Optional[discord.Attachment] = None,
    media3: Optional[discord.Attachment] = None,
    media4: Optional[discord.Attachment] = None,
    media5: Optional[discord.Attachment] = None,
):
    guild_config = get_guild_config(interaction.guild_id, create=False)
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

    category = clean_category_name(category)
    categories_config = guild_config.get("categories", {})
    if category not in categories_config:
        await interaction.response.send_message(
            f"Invalid category `{category}`.",
            ephemeral=True,
        )
        return

    limits = config["limits"]
    if len(text) > limits["max_text_length"]:
        await interaction.response.send_message(
            f"Text is limited to {limits['max_text_length']} characters.",
            ephemeral=True,
        )
        return

    attachments = [
        attachment
        for attachment in [media1, media2, media3, media4, media5]
        if attachment is not None
    ]
    bad_files = [
        attachment.filename
        for attachment in attachments
        if not is_allowed_file(attachment.filename)
    ]
    if bad_files:
        await interaction.response.send_message(
            "Unsupported file type: " + ", ".join(bad_files),
            ephemeral=True,
        )
        return

    oversized = [
        attachment.filename
        for attachment in attachments
        if attachment.size > limits["max_file_bytes"]
    ]
    if oversized:
        await interaction.response.send_message(
            "Files exceed the per-file limit: " + ", ".join(oversized),
            ephemeral=True,
        )
        return
    if sum(attachment.size for attachment in attachments) > limits["max_total_bytes"]:
        await interaction.response.send_message(
            "The combined upload exceeds the total submission limit.",
            ephemeral=True,
        )
        return

    now = time.time()
    user_key = f"{interaction.guild_id}:{interaction.user.id}"
    category_key = f"{interaction.guild_id}:{category}"
    last_user = user_cooldowns.get(user_key, 0)
    if now - last_user < USER_COOLDOWN_SECONDS:
        remaining = max(1, int(USER_COOLDOWN_SECONDS - (now - last_user)))
        await interaction.response.send_message(
            f"Wait {remaining}s before submitting again.",
            ephemeral=True,
        )
        return
    last_category = category_cooldowns.get(category_key, 0)
    if now - last_category < CATEGORY_COOLDOWN_SECONDS:
        remaining = max(
            1,
            int(CATEGORY_COOLDOWN_SECONDS - (now - last_category)),
        )
        await interaction.response.send_message(
            f"Category `{category}` is cooling down for {remaining}s.",
            ephemeral=True,
        )
        return

    target_channel = bot.get_channel(categories_config[category])
    if target_channel is None:
        await interaction.response.send_message(
            "The category channel could not be found.",
            ephemeral=True,
        )
        return

    approval_channel = None
    if guild_config["approval_enabled"]:
        approval_channel_id = guild_config.get("approval_channel")
        approval_channel = (
            bot.get_channel(approval_channel_id)
            if approval_channel_id
            else None
        )
        if approval_channel is None:
            await interaction.response.send_message(
                "Approval is enabled, but its channel is unavailable.",
                ephemeral=True,
            )
            return

    await interaction.response.defer(ephemeral=True, thinking=True)
    user_folder = MEDIA_DIR / str(interaction.guild_id) / category / str(interaction.user.id)
    user_folder.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    media_names = []
    media_types = []
    created_message = None
    submission_id = None

    try:
        for attachment in attachments:
            safe_name = Path(attachment.filename).name.replace("\\", "_")
            filename = f"{int(time.time())}_{interaction.id}_{safe_name}"
            path = user_folder / filename
            await attachment.save(path)
            saved_paths.append(str(path))
            media_names.append(attachment.filename)
            media_types.append(get_media_type(attachment.filename))

        status = "pending" if approval_channel else "posted"
        with database() as connection:
            cursor = connection.execute("""
                INSERT INTO submissions (
                    guild_id, original_message_id, repost_channel_id,
                    user_id, username, category, message_text,
                    file_paths, media_paths, media_names, media_types,
                    stars, voters, status, submitted_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?)
            """, (
                str(interaction.guild_id),
                str(interaction.id),
                str(target_channel.id),
                str(interaction.user.id),
                str(interaction.user),
                category,
                text,
                ";".join(saved_paths),
                ";".join(saved_paths),
                ";".join(media_names),
                ";".join(media_types),
                status,
                utc_now_iso(),
                utc_now_iso(),
            ))
            submission_id = cursor.lastrowid
            row = connection.execute(
                "SELECT * FROM submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()

        if approval_channel:
            created_message = await approval_channel.send(
                content=(
                    f"Pending submission `{submission_id}`\n\n"
                    + submission_content(row)
                ),
                files=make_discord_files(row),
                view=ApprovalView(),
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
            response_text = f"Submission `{submission_id}` is awaiting approval."
        else:
            created_message = await target_channel.send(
                content=submission_content(row),
                files=make_discord_files(row),
                view=VoteView(),
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
            response_text = f"Submitted to `{category}` as `{submission_id}`."

        user_cooldowns[user_key] = now
        category_cooldowns[category_key] = now
        await interaction.followup.send(response_text, ephemeral=True)
    except Exception as error:
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
        cleanup_files(saved_paths)
        await interaction.followup.send(
            f"Submission failed: `{error}`",
            ephemeral=True,
        )


@tree.command(name="removesubmission", description="Remove a submission")
@app_commands.guild_only()
@app_commands.describe(submission_id="Dashboard submission ID", reason="Audit reason")
async def removesubmission(
    interaction,
    submission_id: int,
    reason: str = "Removed by Discord admin",
):
    if not await require_admin(interaction):
        return
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
        reason,
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


async def post_daily_top(guild_id, guild_config):
    channel_id = guild_config.get("daily_top_channel")
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    today = datetime.now(timezone.utc).date().isoformat()
    with database() as connection:
        already_ran = connection.execute("""
            SELECT 1 FROM daily_runs
            WHERE guild_id = ? AND run_date = ?
        """, (str(guild_id), today)).fetchone()
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
        lines = ["**SDAC Daily Top Posts**"]
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
        """, (str(guild_id), today, utc_now_iso()))


@tasks.loop(minutes=1)
async def daily_top_scheduler():
    now = datetime.now(timezone.utc)
    current_time = now.strftime("%H:%M")
    for guild_id, guild_config in config.get("guilds", {}).items():
        if guild_config.get("daily_top_time_utc", "00:00") == current_time:
            await post_daily_top(guild_id, guild_config)


@daily_top_scheduler.before_loop
async def before_daily_top_scheduler():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    bot.add_view(VoteView())
    bot.add_view(ApprovalView())
    migrate_legacy_config()
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as error:
        print(f"Slash command sync failed: {error}")
    if not daily_top_scheduler.is_running():
        daily_top_scheduler.start()
    print(f"Logged in as {bot.user}")
    print(f"Using database: {DB_FILE}")
    print(f"Using config: {CONFIG_FILE}")


def main():
    if not TOKEN:
        raise RuntimeError(
            "Set DISCORD_TOKEN in the Ubuntu service environment."
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
