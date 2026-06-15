import os
import json
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

try:
    from config import TOKEN
except Exception:
    TOKEN = os.getenv("DISCORD_TOKEN", "")

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
    "submit_channel": None,
    "daily_top_channel": None,
    "categories": {}
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in data:
            data[key] = value
            changed = True

    if data.get("categories") is None:
        data["categories"] = {}
        changed = True

    if changed:
        save_config(data)

    return data


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


config = load_config()

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_message_id TEXT,
    repost_message_id TEXT,
    repost_channel_id TEXT,
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
    submitted_at TEXT,
    created_at TEXT,
    daily_posted_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS category_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    category TEXT,
    channel_id TEXT,
    admin_user_id TEXT,
    admin_username TEXT,
    created_at TEXT
)
""")

db.commit()


def ensure_column(table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row["name"] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        db.commit()


for column, definition in {
    "original_message_id": "TEXT",
    "repost_message_id": "TEXT",
    "repost_channel_id": "TEXT",
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
    "submitted_at": "TEXT",
    "created_at": "TEXT",
    "daily_posted_at": "TEXT",
}.items():
    ensure_column("submissions", column, definition)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def utc_now_display():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def clean_category_name(category: str) -> str:
    return category.lower().strip().replace(" ", "")


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if ext in {".mp4", ".mov", ".webm", ".mkv"}:
        return "video"
    if ext in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
        return "audio"
    return "unknown"


def get_voters(raw: Optional[str]) -> set[str]:
    if not raw:
        return set()
    return {x for x in raw.split(",") if x}


def save_voters(voters: set[str]) -> str:
    return ",".join(sorted(voters))


def admin_only(interaction: discord.Interaction) -> bool:
    return bool(interaction.user.guild_permissions.administrator)


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!sdac ", intents=intents)
tree = bot.tree

MEDIA_DIR.mkdir(exist_ok=True)

user_cooldowns = {}
category_cooldowns = {}


class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⭐ Vote",
        style=discord.ButtonStyle.secondary,
        custom_id="sdac_star_vote"
    )
    async def star_vote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        repost_message_id = str(interaction.message.id)
        user_id = str(interaction.user.id)

        cursor.execute("""
        SELECT id, voters
        FROM submissions
        WHERE repost_message_id = ?
        """, (repost_message_id,))

        row = cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                "This post is not registered in the SDAC database.",
                ephemeral=True
            )
            return

        voters = get_voters(row["voters"])

        if user_id in voters:
            await interaction.response.send_message(
                "You already voted for this post.",
                ephemeral=True
            )
            return

        voters.add(user_id)

        cursor.execute("""
        UPDATE submissions
        SET stars = stars + 1,
            voters = ?
        WHERE id = ?
        """, (save_voters(voters), row["id"]))

        db.commit()

        await interaction.response.send_message("Vote added ⭐", ephemeral=True)


@tree.command(name="setsubmit", description="Set the SDAC submission channel")
@app_commands.describe(channel="Channel where users are allowed to submit")
async def setsubmit(interaction: discord.Interaction, channel: discord.TextChannel):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    config["submit_channel"] = channel.id
    save_config(config)

    await interaction.response.send_message(
        f"Submit channel set to {channel.mention}",
        ephemeral=True
    )


@tree.command(name="clearsubmit", description="Clear the SDAC submission channel")
async def clearsubmit(interaction: discord.Interaction):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    config["submit_channel"] = None
    save_config(config)

    await interaction.response.send_message(
        "Submit channel cleared. No submission channel is currently set.",
        ephemeral=True
    )


@tree.command(name="setcategory", description="Create or update an SDAC category")
@app_commands.describe(
    category="Category name, for example screenshot or guessanime",
    channel="Channel where this category should post"
)
async def setcategory(
    interaction: discord.Interaction,
    category: str,
    channel: discord.TextChannel
):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    category = clean_category_name(category)

    config.setdefault("categories", {})
    config["categories"][category] = channel.id
    save_config(config)

    cursor.execute("""
    INSERT INTO category_history (
        action, category, channel_id, admin_user_id, admin_username, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "set",
        category,
        str(channel.id),
        str(interaction.user.id),
        str(interaction.user),
        utc_now_iso()
    ))
    db.commit()

    await interaction.response.send_message(
        f"Category `{category}` set to {channel.mention}",
        ephemeral=True
    )


@tree.command(name="deletecategory", description="Delete an SDAC category")
@app_commands.describe(category="Category name to delete")
async def deletecategory(interaction: discord.Interaction, category: str):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    category = clean_category_name(category)

    if category not in config.get("categories", {}):
        await interaction.response.send_message(
            f"Category `{category}` does not exist.",
            ephemeral=True
        )
        return

    old_channel_id = config["categories"].pop(category)
    save_config(config)

    cursor.execute("""
    INSERT INTO category_history (
        action, category, channel_id, admin_user_id, admin_username, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "delete",
        category,
        str(old_channel_id),
        str(interaction.user.id),
        str(interaction.user),
        utc_now_iso()
    ))
    db.commit()

    await interaction.response.send_message(
        f"Deleted category `{category}`. Existing submissions remain in the database, but new submissions can no longer use that category.",
        ephemeral=True
    )


@tree.command(name="categories", description="List SDAC categories")
async def categories(interaction: discord.Interaction):
    cats = config.get("categories", {})

    submit_channel_id = config.get("submit_channel")
    submit_channel = bot.get_channel(submit_channel_id) if submit_channel_id else None

    lines = [
        "**SDAC Configuration**",
        f"Submit channel: {submit_channel.mention if submit_channel else 'Not set'}",
        ""
    ]

    if not cats:
        lines.append("No categories are set.")
    else:
        lines.append("**Categories:**")
        for category, channel_id in sorted(cats.items()):
            channel = bot.get_channel(channel_id)
            lines.append(
                f"- `{category}` → {channel.mention if channel else f'Unknown channel `{channel_id}`'}"
            )

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@tree.command(name="setdailychannel", description="Set the channel for daily top posts")
@app_commands.describe(channel="Channel where daily top summaries should be posted")
async def setdailychannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    config["daily_top_channel"] = channel.id
    save_config(config)

    await interaction.response.send_message(
        f"Daily top channel set to {channel.mention}",
        ephemeral=True
    )


@tree.command(name="cleardailychannel", description="Clear the channel for daily top posts")
async def cleardailychannel(interaction: discord.Interaction):
    if not admin_only(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    config["daily_top_channel"] = None
    save_config(config)

    await interaction.response.send_message("Daily top channel cleared.", ephemeral=True)


@tree.command(name="submit", description="Submit media to SDAC")
@app_commands.describe(
    category="Submission category",
    media1="Required image, video, or audio file",
    text="Optional message text",
    media2="Optional extra media file",
    media3="Optional extra media file",
    media4="Optional extra media file",
    media5="Optional extra media file"
)
async def submit(
    interaction: discord.Interaction,
    category: str,
    media1: discord.Attachment,
    text: str = "",
    media2: Optional[discord.Attachment] = None,
    media3: Optional[discord.Attachment] = None,
    media4: Optional[discord.Attachment] = None,
    media5: Optional[discord.Attachment] = None
):
    submit_channel_id = config.get("submit_channel")

    if not submit_channel_id:
        await interaction.response.send_message(
            "SDAC submit channel is not set yet. Ask an admin to use `/setsubmit`.",
            ephemeral=True
        )
        return

    if interaction.channel_id != submit_channel_id:
        channel = bot.get_channel(submit_channel_id)
        await interaction.response.send_message(
            f"Please submit in {channel.mention if channel else 'the configured submit channel'}.",
            ephemeral=True
        )
        return

    category = clean_category_name(category)
    categories_config = config.get("categories", {})

    if category not in categories_config:
        await interaction.response.send_message(
            f"Invalid category `{category}`. Use `/categories` to see available categories.",
            ephemeral=True
        )
        return

    now = time.time()
    uid = str(interaction.user.id)

    last_user = user_cooldowns.get(uid, 0)
    if now - last_user < USER_COOLDOWN_SECONDS:
        remaining = int(USER_COOLDOWN_SECONDS - (now - last_user))
        await interaction.response.send_message(
            f"You're on cooldown. Wait {remaining}s.",
            ephemeral=True
        )
        return

    last_category = category_cooldowns.get(category, 0)
    if now - last_category < CATEGORY_COOLDOWN_SECONDS:
        remaining = int(CATEGORY_COOLDOWN_SECONDS - (now - last_category))
        await interaction.response.send_message(
            f"Category `{category}` is cooling down. Wait {remaining}s.",
            ephemeral=True
        )
        return

    target_channel = bot.get_channel(categories_config[category])

    if not target_channel:
        await interaction.response.send_message(
            "The channel for this category could not be found. Ask an admin to set it again.",
            ephemeral=True
        )
        return

    attachments = [x for x in [media1, media2, media3, media4, media5] if x is not None]

    bad_files = [a.filename for a in attachments if not is_allowed_file(a.filename)]
    if bad_files:
        await interaction.response.send_message(
            "Unsupported file type: " + ", ".join(bad_files),
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    user_folder = MEDIA_DIR / category / str(interaction.user.id)
    user_folder.mkdir(parents=True, exist_ok=True)

    discord_files = []
    saved_paths = []
    media_names = []
    media_types = []

    try:
        for attachment in attachments:
            safe_name = attachment.filename.replace("/", "_").replace("\\", "_")
            filename = f"{int(time.time())}_{interaction.id}_{safe_name}"
            path = user_folder / filename

            await attachment.save(path)

            saved_paths.append(str(path))
            media_names.append(attachment.filename)
            media_types.append(get_media_type(attachment.filename))
            discord_files.append(await attachment.to_file())

        header = (
            f"📂 **{category.upper()}**\n"
            f"👤 {interaction.user.mention}\n"
            f"📅 {utc_now_display()}\n\n"
        )

        repost = await target_channel.send(
            content=header + (text or ""),
            files=discord_files,
            view=VoteView()
        )

        cursor.execute("""
        INSERT INTO submissions (
            original_message_id,
            repost_message_id,
            repost_channel_id,
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
            submitted_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(interaction.id),
            str(repost.id),
            str(target_channel.id),
            str(interaction.user.id),
            str(interaction.user),
            category,
            text or "",
            ";".join(saved_paths),
            ";".join(saved_paths),
            ";".join(media_names),
            ";".join(media_types),
            0,
            "",
            utc_now_iso(),
            utc_now_iso()
        ))

        db.commit()

        user_cooldowns[uid] = now
        category_cooldowns[category] = now

        await interaction.followup.send(f"Submitted to `{category}`.", ephemeral=True)

    except Exception as exc:
        await interaction.followup.send(f"Submission failed: `{exc}`", ephemeral=True)
        raise


@tasks.loop(hours=24)
async def daily_top():
    daily_channel_id = config.get("daily_top_channel")

    if not daily_channel_id:
        return

    daily_channel = bot.get_channel(daily_channel_id)
    if not daily_channel:
        return

    lines = ["🏆 **SDAC Daily Top Posts**"]
    found_any = False

    for category in sorted(config.get("categories", {}).keys()):
        cursor.execute("""
        SELECT *
        FROM submissions
        WHERE category = ?
          AND daily_posted_at IS NULL
        ORDER BY stars DESC, created_at DESC
        LIMIT 1
        """, (category,))

        row = cursor.fetchone()

        if not row:
            continue

        found_any = True
        link = f"https://discord.com/channels/{daily_channel.guild.id}/{row['repost_channel_id']}/{row['repost_message_id']}"
        preview = (row["message_text"] or "").strip()[:100]

        lines.append(
            f"\n**{category}** — {row['username']} — {row['stars']} ⭐\n"
            f"{preview}\n{link}"
        )

        cursor.execute(
            "UPDATE submissions SET daily_posted_at = ? WHERE id = ?",
            (utc_now_iso(), row["id"])
        )

    if found_any:
        db.commit()
        await daily_channel.send("\n".join(lines))


@daily_top.before_loop
async def before_daily_top():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    bot.add_view(VoteView())

    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as exc:
        print(f"Slash command sync failed: {exc}")

    if not daily_top.is_running():
        daily_top.start()

    print(f"Logged in as {bot.user}")
    print(f"Using database: {os.path.abspath(DB_FILE)}")
    print(f"Using config: {os.path.abspath(CONFIG_FILE)}")


if not TOKEN or TOKEN == "YOUR_NEW_TOKEN_HERE":
    raise RuntimeError("Set your NEW Discord bot token in config.py or DISCORD_TOKEN environment variable.")

bot.run(TOKEN)
