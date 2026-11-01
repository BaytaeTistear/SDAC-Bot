"""Sana reaction-role persistence and Discord reaction event handling."""


def canonical_reaction_role_emoji(emoji):
    """Return one stable key for Unicode and custom Discord reaction emojis."""
    if hasattr(emoji, "id") and getattr(emoji, "id", None):
        return f"{emoji.name}:{emoji.id}"
    value = str(emoji or "").strip()
    import re
    custom = re.fullmatch(r"<a?:([A-Za-z0-9_]{2,32}):(\d{15,22})>", value)
    if custom:
        return f"{custom.group(1)}:{custom.group(2)}"
    return value

def ensure_reaction_role_schema(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reaction_role_panels (
            message_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'multi',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reaction_role_options (
            message_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            role_id TEXT NOT NULL,
            PRIMARY KEY (message_id, emoji),
            FOREIGN KEY (message_id) REFERENCES reaction_role_panels(message_id)
                ON DELETE CASCADE
        )
    """)


async def handle_reaction_role_event(payload, bot, database, remove=False):
    """Apply a configured role when a member adds/removes a panel reaction."""
    if not payload.guild_id or (bot.user and payload.user_id == bot.user.id):
        return
    emoji = canonical_reaction_role_emoji(payload.emoji)
    with database() as connection:
        ensure_reaction_role_schema(connection)
        panel = connection.execute(
            "SELECT guild_id, mode FROM reaction_role_panels "
            "WHERE message_id = ? AND enabled = 1",
            (str(payload.message_id),),
        ).fetchone()
        if not panel or str(panel["guild_id"]) != str(payload.guild_id):
            return
        option = connection.execute(
            "SELECT role_id FROM reaction_role_options "
            "WHERE message_id = ? AND emoji = ?",
            (str(payload.message_id), emoji),
        ).fetchone()
        if not option:
            return
        options = connection.execute(
            "SELECT emoji, role_id FROM reaction_role_options WHERE message_id = ?",
            (str(payload.message_id),),
        ).fetchall() if panel["mode"] == "single" and not remove else []

    guild = bot.get_guild(int(payload.guild_id))
    if not guild:
        return
    member = getattr(payload, "member", None) or guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception as error:
            print(f"Reaction role could not resolve member {payload.user_id}: {error}", flush=True)
            return
    bot_member = guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        print(f"Reaction roles need Manage Roles in guild {guild.id}.", flush=True)
        return
    role = guild.get_role(int(option["role_id"]))
    if not role or role.managed or role >= bot_member.top_role:
        print(f"Reaction role target is unavailable or above Sana in guild {guild.id}.", flush=True)
        return
    try:
        if remove:
            await member.remove_roles(role, reason="Reaction role removed")
            return
        if options:
            for other in options:
                other_role = guild.get_role(int(other["role_id"]))
                if other_role and other_role != role and other_role in member.roles:
                    await member.remove_roles(other_role, reason="Single-choice reaction role changed")
        if role not in member.roles:
            await member.add_roles(role, reason="Reaction role selected")
    except Exception as error:
        print(f"Could not apply reaction role in guild {guild.id}: {error}", flush=True)
