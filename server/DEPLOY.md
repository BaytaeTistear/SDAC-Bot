# SDAC Deploy Checklist

Server path:

```bash
/home/ubuntu/discord-screenshot-bot
```

Systemd services:

```bash
sudo systemctl restart sdac-bot
sudo systemctl restart sdac-dashboard
sudo systemctl status sdac-bot --no-pager
sudo systemctl status sdac-dashboard --no-pager
```

Upload the files from the local `server/` folder for the current update. Do not upload:

- `__pycache__/`
- `.db` files unless you are intentionally replacing server data
- `backups/`
- `venv/`
- `.env`

Keep these on the Ubuntu server:

- `sdac.db`
- `media/`
- `config.json`
- systemd environment values such as `DISCORD_TOKEN`, `SDAC_ADMIN_KEY`, `SDAC_ADMIN_PASSWORD`, and `SDAC_SECRET_KEY`

After uploading Python files:

```bash
cd /home/ubuntu/discord-screenshot-bot
python3 -m py_compile bot.py dashboard.py
sudo systemctl restart sdac-bot
sudo systemctl restart sdac-dashboard
journalctl -u sdac-bot -n 60 --no-pager
journalctl -u sdac-dashboard -n 60 --no-pager
```

Discord slash commands sync when `sdac-bot` starts. If a new command does not appear immediately, wait a few minutes and check the bot logs for the synced command list.
