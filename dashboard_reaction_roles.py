"""Moderator dashboard for creating and managing Sana reaction-role panels."""

import json
import re
import emoji as emoji_library
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Blueprint, abort, redirect, request, url_for

from reaction_roles import canonical_reaction_role_emoji, ensure_reaction_role_schema


def create_reaction_roles_blueprint(deps):
    bp = Blueprint("reaction_roles", __name__)

    def api(method, path, payload=None):
        token = deps["TOKEN"]
        if not token:
            return None, "Sana's bot token is not configured for the dashboard."
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        api_request = Request(
            f"https://discord.com/api/v10{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
                "User-Agent": "Sana-Dashboard/4.0",
            },
        )
        try:
            with urlopen(api_request, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return (json.loads(raw) if raw else {}), ""
        except HTTPError as error:
            try:
                detail = error.read().decode("utf-8")[:300]
            except Exception:
                detail = ""
            return None, f"Discord returned HTTP {error.code}. {detail}".strip()
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            return None, f"Could not reach Discord: {error}"

    def scoped_guild(guild_id):
        if not guild_id.isdigit() or not deps["can_access"](guild_id):
            abort(403)
        return guild_id

    def dashboard_url(guild_id, notice="", error=False):
        return redirect(url_for(
            "reaction_roles.manage",
            key=deps["ADMIN_KEY"],
            guild_id=guild_id,
            notice=notice,
            error=1 if error else 0,
        ))

    @bp.route("/admin/reaction-roles", methods=["GET", "POST"])
    def manage():
        login_response = deps["require_admin_login"]("moderator")
        if login_response:
            return login_response
        config_data = deps["load_config"]()
        options = deps["guild_options"](config_data, minimum_role="moderator")
        allowed_ids = {str(item["id"]) for item in options}
        guild_id = request.values.get("guild_id", "").strip()
        if guild_id not in allowed_ids:
            guild_id = str(options[0]["id"]) if options else ""
        if not guild_id:
            return deps["admin_tool_shell"](
                "Reaction Roles", "Create role selection panels for your community.",
                "<p>No moderator-accessible servers are configured for this account.</p>",
            )
        scoped_guild(guild_id)

        if request.method == "POST":
            deps["require_csrf_token"]()
            action = request.form.get("action", "create")
            actor_id, actor_name = deps["web_actor"]()
            if action == "delete":
                message_id = request.form.get("message_id", "")
                with deps["database"]() as connection:
                    ensure_reaction_role_schema(connection)
                    panel = connection.execute(
                        "SELECT channel_id FROM reaction_role_panels WHERE message_id = ? AND guild_id = ?",
                        (message_id, guild_id),
                    ).fetchone()
                if not panel:
                    return dashboard_url(guild_id, "Panel not found.", True)
                _, error = api("DELETE", f"/channels/{panel['channel_id']}/messages/{message_id}")
                if error and "HTTP 404" not in error:
                    return dashboard_url(guild_id, f"Could not delete the Discord panel: {error}", True)
                with deps["database"]() as connection:
                    connection.execute("DELETE FROM reaction_role_options WHERE message_id = ?", (message_id,))
                    connection.execute("DELETE FROM reaction_role_panels WHERE message_id = ?", (message_id,))
                    deps["add_admin_audit_log"](
                        connection, guild_id, "reaction_role_panel_deleted", actor_id,
                        actor_name, "reaction_role_panel", message_id,
                    )
                return dashboard_url(guild_id, "Reaction-role panel deleted.")

            channel_id = request.form.get("channel_id", "")
            title = request.form.get("title", "").strip()[:100]
            description = request.form.get("description", "").strip()[:500]
            mode = request.form.get("mode", "multi")
            if not channel_id.isdigit() or not title or mode not in {"multi", "single"}:
                return dashboard_url(guild_id, "Choose a channel, title, and valid selection mode.", True)
            mappings = []
            for index in range(1, 21):
                emoji = (
                    request.form.get(f"server_emoji_{index}", "").strip()
                    or request.form.get(f"unicode_emoji_{index}", "").strip()
                )
                role_id = request.form.get(f"role_{index}", "").strip()
                if not emoji and not role_id:
                    continue
                if not emoji or not role_id.isdigit():
                    return dashboard_url(guild_id, "Each option needs both an emoji and a role.", True)
                emoji_key = canonical_reaction_role_emoji(emoji)
                if not emoji_key or (":" not in emoji_key and len(emoji_key) > 16):
                    return dashboard_url(guild_id, f"Invalid emoji on option {index}.", True)
                if any(row["emoji"] == emoji_key for row in mappings):
                    return dashboard_url(guild_id, "Each option needs a unique emoji.", True)
                custom_emoji = re.fullmatch(r"<a?:([A-Za-z0-9_]{2,32}):(\d{15,22})>", emoji)
                mappings.append({
                    "emoji": emoji_key,
                    "display": emoji,
                    "role_id": role_id,
                    "custom_id": custom_emoji.group(2) if custom_emoji else "",
                })
            if not mappings:
                return dashboard_url(guild_id, "Add at least one emoji and role option.", True)

            guild, error = api("GET", f"/guilds/{guild_id}?with_counts=true")
            channels, channel_error = api("GET", f"/guilds/{guild_id}/channels")
            roles, role_error = api("GET", f"/guilds/{guild_id}/roles")
            server_emojis, emoji_error = api("GET", f"/guilds/{guild_id}/emojis")
            if error or channel_error or role_error or not isinstance(channels, list) or not isinstance(roles, list):
                return dashboard_url(guild_id, "Could not load server roles/channels. Check Sana's server access.", True)
            server_emoji_ids = {
                str(item.get("id")) for item in (server_emojis or [])
                if isinstance(item, dict) and item.get("id") and item.get("available") is not False
            } if not emoji_error and isinstance(server_emojis, list) else set()
            if any(row["custom_id"] and row["custom_id"] not in server_emoji_ids for row in mappings):
                return dashboard_url(guild_id, "Choose a custom emoji from this server's emoji list, then try again.", True)
            selected_channel = next(
                (channel for channel in channels
                 if str(channel.get("id")) == channel_id and channel.get("type") in {0, 5}),
                None,
            )
            if not selected_channel:
                return dashboard_url(guild_id, "Choose a text or announcement channel in this server.", True)
            role_map = {str(role["id"]): role for role in roles}
            bot_user, _ = api("GET", "/users/@me")
            bot_member = None
            if isinstance(bot_user, dict) and bot_user.get("id"):
                bot_member, _ = api("GET", f"/guilds/{guild_id}/members/{bot_user['id']}")
            bot_role_ids = set(bot_member.get("roles", [])) if isinstance(bot_member, dict) else set()
            bot_top = max(
                (int(role.get("position", 0)) for role in roles if str(role["id"]) in bot_role_ids),
                default=-1,
            )
            dangerous = sum(1 << bit for bit in (1, 2, 3, 4, 5, 13, 27, 28, 29))
            for mapping in mappings:
                role = role_map.get(mapping["role_id"])
                if not role or role.get("managed") or role["id"] == guild_id:
                    return dashboard_url(guild_id, "A selected role is missing, managed, or @everyone.", True)
                if int(role.get("position", 0)) >= bot_top:
                    return dashboard_url(guild_id, "Move Sana's bot role above every role used in this panel.", True)
                if int(role.get("permissions", "0")) & dangerous:
                    return dashboard_url(
                        guild_id,
                        f"The role {role.get('name', '')} has privileged permissions and cannot be self-assigned.",
                        True,
                    )

            lines = [f"**{title}**"]
            if description:
                lines.append(description)
            lines.extend(f"{row['display']} — <@&{row['role_id']}>" for row in mappings)
            content = "\n".join(lines)
            if len(content) > 1900:
                return dashboard_url(guild_id, "Panel text is too long. Shorten the title or description.", True)
            message, error = api(
                "POST", f"/channels/{channel_id}/messages",
                {"content": content, "allowed_mentions": {"parse": []}},
            )
            if error or not isinstance(message, dict) or not message.get("id"):
                return dashboard_url(guild_id, f"Could not create the Discord panel: {error}", True)
            message_id = str(message["id"])
            for mapping in mappings:
                _, error = api(
                    "PUT",
                    f"/channels/{channel_id}/messages/{message_id}/reactions/{quote(mapping['emoji'], safe='')}/@me",
                )
                if error:
                    api("DELETE", f"/channels/{channel_id}/messages/{message_id}")
                    return dashboard_url(
                        guild_id,
                        f"Could not add the {mapping['display']} reaction. Check Add Reactions and Use External Emojis permissions. {error}",
                        True,
                    )
            with deps["database"]() as connection:
                ensure_reaction_role_schema(connection)
                connection.execute(
                    "INSERT INTO reaction_role_panels (message_id,guild_id,channel_id,title,description,mode,created_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (message_id, guild_id, channel_id, title, description, mode, str(actor_id), deps["utc_now_iso"]()),
                )
                for mapping in mappings:
                    connection.execute(
                        "INSERT INTO reaction_role_options (message_id,emoji,role_id) VALUES (?,?,?)",
                        (message_id, mapping["emoji"], mapping["role_id"]),
                    )
                deps["add_admin_audit_log"](
                    connection, guild_id, "reaction_role_panel_created", actor_id,
                    actor_name, "reaction_role_panel", message_id,
                    f"{title}; mode={mode}; options={len(mappings)}",
                )
            return dashboard_url(guild_id, "Reaction-role panel created.")

        channels, _ = api("GET", f"/guilds/{guild_id}/channels")
        roles, _ = api("GET", f"/guilds/{guild_id}/roles")
        emoji_response, emoji_error = api("GET", f"/guilds/{guild_id}/emojis")
        channels = [item for item in (channels or []) if item.get("type") in {0, 5}]
        roles = [item for item in (roles or []) if not item.get("managed") and str(item.get("id")) != guild_id]
        emojis = []
        fully_qualified = emoji_library.STATUS["fully_qualified"]
        for glyph, metadata in emoji_library.EMOJI_DATA.items():
            if metadata.get("status") != fully_qualified:
                continue
            short_name = str(metadata.get("en", "")).strip(":").replace("_", " ")
            emojis.append({
                "value": glyph,
                "label": short_name or "emoji",
                "image_url": "",
                "category": "Discord defaults",
                "kind": "unicode",
            })
        emojis.sort(key=lambda item: item["label"].casefold())
        server_custom_emojis = []
        if isinstance(emoji_response, list):
            for item in emoji_response:
                if (
                    not isinstance(item, dict) or not item.get("id") or not item.get("name")
                    or item.get("available") is False
                ):
                    continue
                animated = bool(item.get("animated"))
                emoji_id = str(item["id"])
                emoji_name = str(item["name"])
                server_custom_emojis.append({
                    "value": f"<{ 'a' if animated else '' }:{emoji_name}:{emoji_id}>",
                    "label": f":{emoji_name}:" + (" (animated)" if animated else ""),
                    "image_url": f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}?size=48",
                    "category": "This server",
                    "kind": "server",
                })
        emojis.extend(server_custom_emojis)
        server_emoji_count = len(server_custom_emojis)
        with deps["database"]() as connection:
            ensure_reaction_role_schema(connection)
            panels = connection.execute(
                "SELECT p.message_id,p.channel_id,p.title,p.mode,p.created_at,COUNT(o.role_id) AS option_count "
                "FROM reaction_role_panels p LEFT JOIN reaction_role_options o USING(message_id) "
                "WHERE p.guild_id = ? GROUP BY p.message_id ORDER BY p.created_at DESC",
                (guild_id,),
            ).fetchall()

        body = """
        <style>
          .rr-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
          .rr-grid label{display:block;font-weight:600}
          .rr-grid input,.rr-grid select,.rr-grid textarea{box-sizing:border-box;width:100%;padding:9px;margin-top:5px}
          .rr-options{display:grid;gap:8px;max-width:760px}
          .rr-option{display:grid;grid-template-columns:minmax(250px,1fr) minmax(180px,1fr);gap:8px;align-items:center}
          .rr-emoji-fields{display:grid;gap:6px}
          .rr-emoji-trigger{display:flex;align-items:center;justify-content:space-between;gap:8px;box-sizing:border-box;width:100%;min-height:42px;padding:6px 10px;text-align:left;cursor:pointer}
          .rr-emoji-trigger:disabled{cursor:not-allowed;opacity:.65}
          .rr-emoji-trigger img{width:32px;height:32px;object-fit:contain}
          .rr-emoji-unicode{box-sizing:border-box;width:100%;padding:8px}
          .rr-option>select{box-sizing:border-box;width:100%;padding:8px}
          .rr-emoji-menu{position:fixed;z-index:99999;width:min(360px,calc(100vw - 24px));max-height:min(420px,calc(100vh - 24px));overflow:auto;padding:8px;border:1px solid #60718e;border-radius:8px;background:#111827;box-shadow:0 12px 32px #0009}
          .rr-emoji-search{position:sticky;top:0;z-index:1;box-sizing:border-box;width:100%;margin:0 0 8px;padding:10px;border:1px solid #52627d;border-radius:6px;background:#172238;color:#fff}
          .rr-emoji-category{margin:9px 4px 4px;color:#9fb0c8;font-size:.82rem;font-weight:700;text-transform:uppercase}
          .rr-emoji-item{display:flex;align-items:center;gap:10px;width:100%;padding:7px;border:0;border-radius:5px;background:transparent;color:#fff;text-align:left;cursor:pointer}
          .rr-emoji-item:hover,.rr-emoji-item:focus{background:#273b59;outline:2px solid #4ac8ef}
          .rr-emoji-item img{flex:0 0 40px;width:40px;height:40px;object-fit:contain}
          .rr-emoji-glyph{display:grid;flex:0 0 40px;width:40px;height:40px;place-items:center;font-size:30px;line-height:1}
          .rr-emoji-empty{padding:10px;color:#c4d0df}
          .rr-panel{padding:12px;border:1px solid #555;border-radius:8px;margin:10px 0}
          @media(max-width:700px){.rr-grid{grid-template-columns:1fr}}
          @media(max-width:540px){.rr-option{grid-template-columns:1fr}}
        </style>
        <form method="get" action="{{ url_for('reaction_roles.manage') }}" class="rr-grid">
          <input type="hidden" name="key" value="{{ admin_key }}">
          <label>Server<select name="guild_id" onchange="this.form.submit()">{% for item in guild_options %}<option value="{{ item.id }}" {% if item.id|string == guild_id|string %}selected{% endif %}>{{ item.name }}</option>{% endfor %}</select></label>
        </form>
        <h2>Create a reaction-role panel</h2>
        <p>Members add or remove the listed roles by reacting. Single choice removes other roles from this panel when a new choice is selected.</p>
        <form method="post" action="{{ url_for('reaction_roles.manage') }}">
          <input type="hidden" name="key" value="{{ admin_key }}"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="guild_id" value="{{ guild_id }}">
          <div class="rr-grid">
            <label>Post in<select name="channel_id" required>{% for channel in channels %}<option value="{{ channel.id }}">#{{ channel.name }}</option>{% endfor %}</select></label>
            <label>Title<input name="title" maxlength="100" required></label>
            <label>Description<textarea name="description" maxlength="500" rows="2"></textarea></label>
            <label>Selection mode<select name="mode"><option value="multi">Multiple roles</option><option value="single">One choice (replaces other panel roles)</option></select></label>
          </div>
          <h3>Emoji and role options (up to 20)</h3>
          {% if emoji_error %}<p>Could not load this server's custom emojis. Discord default emoji are available below.</p>{% elif not server_emoji_count %}<p>Choose a Discord default emoji below, or enter a Unicode emoji.</p>{% else %}<p>Choose a Discord default or server emoji. Server emoji show their image beside the name.</p>{% endif %}
          <div class="rr-options">
          {% for index in range(1, 21) %}<div class="rr-option"><div class="rr-emoji-fields"><button class="rr-emoji-trigger" type="button" aria-expanded="false"><span class="rr-emoji-trigger-label">Choose emoji</span><img alt="" hidden></button><input type="hidden" name="server_emoji_{{ index }}"><input class="rr-emoji-unicode" name="unicode_emoji_{{ index }}" placeholder="or enter Unicode 😀" aria-label="Unicode emoji {{ index }}"></div><select name="role_{{ index }}" aria-label="Role {{ index }}"><option value="">Choose role</option>{% for role in roles %}<option value="{{ role.id }}">{{ role.name }}</option>{% endfor %}</select></div>{% endfor %}
          </div>
          <div id="rr-emoji-menu" class="rr-emoji-menu" role="listbox" aria-label="Discord and server emojis" hidden></div>
          <p><button type="submit">Create panel</button></p>
        </form>
        <script type="application/json" id="rr-server-emojis">{{ emojis|tojson }}</script>
        <script>
        (() => {
          const data = JSON.parse(document.getElementById("rr-server-emojis").textContent || "[]");
          const menu = document.getElementById("rr-emoji-menu");
          let activeTrigger = null;
          let emojiButtons = [];
          const closeMenu = () => {
            menu.hidden = true;
            if (activeTrigger) activeTrigger.setAttribute("aria-expanded", "false");
            activeTrigger = null;
          };
          const filterEmojis = (query) => {
            const value = query.trim().toLocaleLowerCase();
            let visible = 0;
            for (const button of emojiButtons) {
              const matches = !value || button.dataset.search.includes(value);
              button.hidden = !matches;
              if (matches) visible += 1;
            }
            const empty = menu.querySelector(".rr-emoji-empty");
            if (empty) empty.hidden = visible !== 0;
            for (const heading of menu.querySelectorAll(".rr-emoji-category")) {
              heading.hidden = ![...emojiButtons].some((button) => !button.hidden && button.dataset.category === heading.dataset.category);
            }
          };
          const openMenu = (trigger) => {
            activeTrigger = trigger;
            trigger.setAttribute("aria-expanded", "true");
            menu.replaceChildren();
            const search = document.createElement("input");
            search.className = "rr-emoji-search";
            search.type = "search";
            search.placeholder = "Search Discord and server emojis";
            search.setAttribute("aria-label", "Search Discord and server emojis");
            menu.appendChild(search);
            emojiButtons = [];
            let lastCategory = "";
            for (const emoji of data) {
              if (emoji.category !== lastCategory) {
                lastCategory = emoji.category;
                const heading = document.createElement("div");
                heading.className = "rr-emoji-category";
                heading.dataset.category = emoji.category;
                heading.textContent = emoji.category;
                menu.appendChild(heading);
              }
              const button = document.createElement("button");
              button.className = "rr-emoji-item";
              button.type = "button";
              button.setAttribute("role", "option");
              button.dataset.category = emoji.category;
              button.dataset.search = `${emoji.label} ${emoji.value}`.toLocaleLowerCase();
              const icon = document.createElement(emoji.image_url ? "img" : "span");
              if (emoji.image_url) {
                icon.src = emoji.image_url;
                icon.alt = emoji.label;
                icon.loading = "lazy";
              } else {
                icon.className = "rr-emoji-glyph";
                icon.textContent = emoji.value;
                icon.setAttribute("aria-hidden", "true");
              }
              const label = document.createElement("span");
              label.textContent = emoji.image_url ? emoji.label : `${emoji.value} ${emoji.label}`;
              button.append(icon, label);
              button.addEventListener("click", () => {
                const fields = activeTrigger.closest(".rr-emoji-fields");
                fields.querySelector('input[type="hidden"]').value = emoji.value;
                fields.querySelector('input[type="text"]').value = "";
                activeTrigger.querySelector(".rr-emoji-trigger-label").textContent = label.textContent;
                const preview = activeTrigger.querySelector("img");
                if (emoji.image_url) {
                  preview.src = emoji.image_url;
                  preview.alt = emoji.label;
                  preview.hidden = false;
                } else {
                  preview.removeAttribute("src");
                  preview.alt = "";
                  preview.hidden = true;
                }
                closeMenu();
              });
              menu.appendChild(button);
              emojiButtons.push(button);
            }
            const empty = document.createElement("div");
            empty.className = "rr-emoji-empty";
            empty.textContent = "No matching emojis.";
            empty.hidden = data.length > 0;
            menu.appendChild(empty);
            search.addEventListener("input", () => filterEmojis(search.value));
            const bounds = trigger.getBoundingClientRect();
            const width = Math.min(360, window.innerWidth - 24);
            menu.style.left = `${Math.max(12, Math.min(bounds.left, window.innerWidth - width - 12))}px`;
            menu.style.top = `${Math.max(12, Math.min(bounds.bottom + 4, window.innerHeight - 360))}px`;
            menu.hidden = false;
            search.focus();
          };
          document.querySelectorAll(".rr-emoji-trigger").forEach((trigger) => {
            trigger.addEventListener("click", () => {
              if (activeTrigger === trigger && !menu.hidden) closeMenu();
              else openMenu(trigger);
            });
            const unicodeInput = trigger.closest(".rr-emoji-fields").querySelector('input[type="text"]');
            unicodeInput.addEventListener("input", () => {
              trigger.closest(".rr-emoji-fields").querySelector('input[type="hidden"]').value = "";
              trigger.querySelector(".rr-emoji-trigger-label").textContent = "Choose emoji";
              const preview = trigger.querySelector("img");
              preview.removeAttribute("src");
              preview.alt = "";
              preview.hidden = true;
            });
          });
          document.addEventListener("click", (event) => {
            if (menu.hidden || menu.contains(event.target)) return;
            if (event.target instanceof Element && event.target.closest(".rr-emoji-trigger")) return;
            closeMenu();
          });
          document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !menu.hidden) closeMenu();
          });
          window.addEventListener("resize", closeMenu);
          window.addEventListener("scroll", closeMenu, true);
        })();
        </script>
        <h2>Existing panels</h2>
        {% if panels %}{% for panel in panels %}<div class="rr-panel"><strong>{{ panel.title }}</strong> · {{ panel.option_count }} choices · {{ panel.mode }}<br><a href="https://discord.com/channels/{{ guild_id }}/{{ panel.channel_id }}/{{ panel.message_id }}" target="_blank" rel="noopener">Open panel</a>
          <form method="post" action="{{ url_for('reaction_roles.manage') }}" onsubmit="return confirm('Delete this reaction-role panel and its Discord message?')"><input type="hidden" name="key" value="{{ admin_key }}"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="guild_id" value="{{ guild_id }}"><input type="hidden" name="action" value="delete"><input type="hidden" name="message_id" value="{{ panel.message_id }}"><button type="submit">Delete panel</button></form></div>{% endfor %}{% else %}<p>No panels in this server yet.</p>{% endif %}
        <p>Required bot permissions: Manage Roles, View Channel, Send Messages, Read Message History, and Add Reactions. Put Sana's bot role above the selectable roles.</p>
        """
        return deps["admin_tool_shell"](
            "Reaction Roles", "Create and manage moderator reaction-role panels.", body,
            guild_options=options, guild_id=guild_id, channels=channels, roles=roles,
            panels=panels, emojis=emojis, emoji_error=emoji_error,
            server_emoji_count=server_emoji_count,
        )

    return bp
