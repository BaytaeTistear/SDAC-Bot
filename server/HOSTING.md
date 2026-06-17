# Hosting SDAC On Ubuntu

This guide is for the production Ubuntu server.

Recommended server path:

```bash
/home/ubuntu/discord-screenshot-bot
```

## 1. Install System Packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
```

Optional backup package:

```bash
sudo apt install -y rclone
```

## 2. Put The Bot Files On The Server

Copy or clone the project into:

```bash
/home/ubuntu/discord-screenshot-bot
```

For routine updates, upload only the current files from the local `server/`
folder. Keep server data files on the server.

## 3. Run The Installer

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/install_ubuntu.sh
```

The installer will:

- create `media/` and `backups/`
- create `config.json` if it is missing
- create `/etc/sdac-bot/sdac.env`
- ask for the Discord token and dashboard admin password
- create `venv/`
- install Python dependencies
- install the `sdac-bot` and `sdac-dashboard` systemd services
- bind Gunicorn to `127.0.0.1:5000` for Nginx
- start both services

If an older install still uses `/etc/sdac.env`, standardize it:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/standardize_env_file.sh
```

## 4. Configure Nginx

For the current domain:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/install_nginx_site.sh
```

This installs `/etc/nginx/sites-available/sdac-dashboard`, enables it, sets a
`100M` upload limit, applies basic security headers, tests Nginx, and reloads
it.

If you use a different domain:

```bash
SDAC_DOMAIN=YOUR-DOMAIN bash scripts/install_nginx_site.sh
```

## 5. Add HTTPS

For the current domain:

```bash
sudo certbot --nginx -d freethefishies.us.to --cert-name freethefishies.us.to --key-type rsa
```

If Certbot asks whether you are changing the key type, use the full command
above with both `--cert-name` and `--key-type`.

Test automatic renewal:

```bash
sudo certbot renew --dry-run
```

## 6. Check Services And Logs

```bash
sudo systemctl status sdac-bot --no-pager
sudo systemctl status sdac-dashboard --no-pager
sudo systemctl status nginx --no-pager
```

```bash
journalctl -u sdac-bot -n 80 --no-pager
journalctl -u sdac-dashboard -n 80 --no-pager
```

Optional journal log retention limits:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/install_journal_limits.sh
```

## 7. Production Check

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/check_production.sh
```

Include the Certbot dry-run check:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to SDAC_RUN_CERTBOT_DRY_RUN=1 bash scripts/check_production.sh
```

## 8. Database Migrations And Restore Tests

Apply migrations manually when needed:

```bash
cd /home/ubuntu/discord-screenshot-bot
venv/bin/python scripts/migrate_database.py --db sdac.db
```

Test the newest local backup without touching production:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/test_restore.sh
```

Test a specific backup:

```bash
bash scripts/test_restore.sh /home/ubuntu/discord-screenshot-bot/backups/sdac-BACKUP.db
```

## 9. Optional Sentry Error Reporting

Set these in `/etc/sdac-bot/sdac.env` to enable production error reporting:

```bash
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0
SDAC_RELEASE=v1.1.0
SDAC_SERVER_NAME=all-minecraft-servers
```

Restart both services after editing:

```bash
sudo systemctl restart sdac-bot sdac-dashboard
```

## 10. Health Checks

Public uptime check:

```text
https://freethefishies.us.to/health
```

Local check from the server:

```bash
curl http://127.0.0.1:5000/health
```

Admin-only detailed health check after logging in through the dashboard:

```text
https://freethefishies.us.to/admin/health?key=ImTheBestAdmin
```

## 11. Future Updates

Upload the changed files, then run:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/update_ubuntu.sh
```

The update script creates a deploy snapshot, makes a SQLite database backup,
installs Python dependencies, compiles the Python files, re-renders the systemd
services, restarts both services, checks that both services are active, and
prints a rollback command when a previous deploy snapshot exists.

The update script also applies database migrations before restarting services.

Rollback example:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/rollback_ubuntu.sh /home/ubuntu/discord-screenshot-bot/deploy-backups/OLDER-SNAPSHOT
```

## 12. Environment Settings

The production environment file is:

```bash
/etc/sdac-bot/sdac.env
```

Edit it with:

```bash
sudo nano /etc/sdac-bot/sdac.env
sudo systemctl restart sdac-bot sdac-dashboard
```

Required values:

- `DISCORD_TOKEN`
- `SDAC_ADMIN_KEY`
- `SDAC_ADMIN_PASSWORD`
- `SDAC_SECRET_KEY`

Optional values:

- `SENTRY_DSN`
- `SENTRY_ENVIRONMENT`
- `SENTRY_TRACES_SAMPLE_RATE`
- `SDAC_RELEASE`
- `SDAC_SERVER_NAME`

## 13. Discord Setup

A server owner still needs to invite the bot to Discord with the right
permissions. The Ubuntu installer cannot do that part.

The bot needs permissions for:

- slash commands
- send messages
- attach files
- manage messages
- read message history
- view channels

See [DISCORD_PERMISSIONS.md](DISCORD_PERMISSIONS.md) for the current permission
integer and least-privilege guidance.

After the bot starts, slash commands sync automatically. It can take a few
minutes for Discord to show new commands.

Set a private staff channel for bot error notices:

```text
/seterrorchannel #sdac-errors
```

Admins can check new-server setup progress at:

```text
https://freethefishies.us.to/admin/onboarding?key=ImTheBestAdmin
```

## 14. Off-Server Backups

See [MONITORING.md](MONITORING.md) for `rclone` backup setup and uptime
monitoring.
