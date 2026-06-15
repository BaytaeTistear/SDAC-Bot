# SDAC Project Context

This is a Discord + web dashboard media submission app.

Current goals:
- Discord users submit media through `/submit`
- Admins configure submit channel and categories through slash commands
- Admins can delete categories
- Website is public without a key
- Website admin mode uses `?key=ImTheBestAdmin`
- Admins can remove submissions from the website
- Removal should update the database and delete the Discord repost
- No channels or categories should be set by default in config.json

Server path:
`/home/ubuntu/discord-screenshot-bot`

Main files:
- `bot.py`
- `dashboard.py`
- `config.py`
- `config.json`
- `sdac.db`
- `media/`

Important preference:
When making changes, remake the full affected file, not snippets.