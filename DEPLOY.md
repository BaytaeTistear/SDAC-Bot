# SDAC Deploy Checklist

For a new Ubuntu host, use [HOSTING.md](HOSTING.md) and run:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/install_ubuntu.sh
```

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
- `.db-wal` or `.db-shm` SQLite sidecar files
- `backups/`
- `deploy-backups/`
- `venv/`
- `.env`

Keep these on the Ubuntu server:

- `sdac.db`
- `media/`
- `config.json`
- `/etc/sdac-bot/sdac.env` with `DISCORD_TOKEN`, `SDAC_ADMIN_KEY`, `SDAC_ADMIN_PASSWORD`, and `SDAC_SECRET_KEY`

After uploading Python files:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/update_ubuntu.sh
```

If the update fails after a previous deploy snapshot exists:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/rollback_ubuntu.sh /home/ubuntu/discord-screenshot-bot/deploy-backups/SNAPSHOT-NAME
```

Public health check:

```bash
curl http://SERVER-IP:5000/health
```

Detailed health is available in the dashboard after admin login at:

```text
/admin/health?key=ImTheBestAdmin
```

Discord slash commands sync when `sdac-bot` starts. If a new command does not appear immediately, wait a few minutes and check the bot logs for the synced command list.

Saved for the next production pass:

- HTTPS behind Nginx / Let's Encrypt
- real domain name
- Gunicorn bound to localhost behind Nginx
- off-server backups
