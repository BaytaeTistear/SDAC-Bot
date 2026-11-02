"""Sana reaction-role persistence and Discord reaction event handling."""

import discord

from database_backend import using_postgres


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
            display_mode TEXT NOT NULL DEFAULT 'reactions',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    if using_postgres():
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'reaction_role_panels'"
        ).fetchall()
        existing = {row[0] for row in columns}
    else:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reaction_role_panels)").fetchall()
        }
    if "display_mode" not in existing:
        connection.execute(
            "ALTER TABLE reaction_role_panels ADD COLUMN display_mode TEXT NOT NULL DEFAULT 'reactions'"
        )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS reaction_role_options (
            message_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            role_id TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (message_id, emoji),
            FOREIGN KEY (message_id) REFERENCES reaction_role_panels(message_id)
                ON DELETE CASCADE
        )
    """)
    if using_postgres():
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'reaction_role_options'"
        ).fetchall()
        existing = {row[0] for row in columns}
    else:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reaction_role_options)").fetchall()
        }
    if "label" not in existing:
        connection.execute(
            "ALTER TABLE reaction_role_options ADD COLUMN label TEXT NOT NULL DEFAULT ''"
        )


async def apply_component_role_selection(interaction, selected_role_ids, database):
    """Apply or toggle roles selected through a panel's buttons or dropdown."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Use this role panel inside its server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    message_id = str(interaction.message.id)
    with database() as connection:
        ensure_reaction_role_schema(connection)
        panel = connection.execute(
            "SELECT guild_id, mode FROM reaction_role_panels "
            "WHERE message_id = ? AND enabled = 1", (message_id,),
        ).fetchone()
        allowed = {
            str(row["role_id"])
            for row in connection.execute(
                "SELECT role_id FROM reaction_role_options WHERE message_id = ?", (message_id,),
            ).fetchall()
        }
    if not panel or str(panel["guild_id"]) != str(interaction.guild.id):
        await interaction.followup.send("That role panel is no longer active.", ephemeral=True)
        return
    requested = list(dict.fromkeys(str(value) for value in selected_role_ids if str(value) in allowed))
    if not requested:
        await interaction.followup.send("Choose a role from this panel.", ephemeral=True)
        return
    member = interaction.user
    bot_member = interaction.guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        await interaction.followup.send("Sana needs Manage Roles to apply panel roles.", ephemeral=True)
        return
    roles = [interaction.guild.get_role(int(role_id)) for role_id in allowed]
    roles = [role for role in roles if role and not role.managed and role < bot_member.top_role]
    requested_roles = [interaction.guild.get_role(int(role_id)) for role_id in requested]
    if len(requested_roles) != len(requested) or any(
        not role or role.managed or role >= bot_member.top_role for role in requested_roles
    ):
        await interaction.followup.send("One or more roles are unavailable to Sana.", ephemeral=True)
        return
    to_add, to_remove = [], []
    if panel["mode"] == "single":
        selected = requested_roles[0]
        if selected in member.roles:
            to_remove.append(selected)
        else:
            to_add.append(selected)
        to_remove.extend(role for role in roles if role != selected and role in member.roles)
    else:
        for role in requested_roles:
            (to_remove if role in member.roles else to_add).append(role)
    try:
        if to_remove:
            await member.remove_roles(*to_remove, reason="Reaction-role panel selection")
        if to_add:
            await member.add_roles(*to_add, reason="Reaction-role panel selection")
    except discord.Forbidden:
        await interaction.followup.send("Sana could not update your roles. Check role hierarchy and permissions.", ephemeral=True)
        return
    except discord.HTTPException:
        await interaction.followup.send("Discord could not update your roles. Please try again.", ephemeral=True)
        return
    await interaction.followup.send("Your roles were updated.", ephemeral=True)


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
