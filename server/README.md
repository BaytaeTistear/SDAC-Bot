# SDAC Bot

SDAC Bot is a Discord media submission and guessing-game system with a web dashboard. Discord users submit images, audio, or video through `/submit`. Admins configure categories, review pending submissions, run guessing games, and view submissions, votes, leaderboards, maintenance status, and moderation history from the dashboard.

## What It Does

- Guided Discord `/submit` flow with category, media/text, and confirmation
- Admin category and channel setup through slash commands
- Optional approval queue before media is reposted
- Public web gallery with sorting by newest, votes, and month
- Preserved monthly top 10 submission snapshots
- Guessing games started by admins with `/startgame`
- `/guess` scoring, wrong-guess cooldowns, and monthly leaderboards
- Cross-server dashboard filtering and cross-server guessing rankings
- Dashboard admin login on top of the admin key
- Maintenance page for backups, restore tests, storage warnings, and health
- Moderation page for pending submissions and recent decisions
- Ubuntu systemd service templates and Nginx helper scripts
- Linux and Windows single-file installers from GitHub Releases

## Main Files

- `bot.py` - Discord bot and slash commands
- `dashboard.py` - Flask dashboard
- `config.py` - environment loading
- `database_migrations.py` - SQLite schema migrations
- `config.json` - Discord server/channel/category settings
- `sdac.db` - production SQLite database, not included in releases
- `media/` - uploaded media, not included in releases
- `scripts/` - install, update, backup, restore, and production helpers
- `systemd/` - Ubuntu service templates
- `nginx/` - dashboard reverse-proxy template

## Command Directory

### One-Time Updater Install

Install the `sdac-update` command once. The Version 2.4 installer also installs
this command automatically.

```bash
cd /tmp
rm -f SDAC-Bot-Ubuntu-Update.sh
gh release download version-2.4 \
  --repo eatyba12/SDAC-Bot \
  --pattern SDAC-Bot-Ubuntu-Update.sh \
  --dir /tmp
chmod +x SDAC-Bot-Ubuntu-Update.sh

SDAC_APP_DIR=/home/ubuntu/discord-screenshot-bot \
SDAC_APP_USER=ubuntu \
SDAC_ENV_FILE=/etc/sdac-bot/sdac.env \
SDAC_DOMAIN=freethefishies.us.to \
./SDAC-Bot-Ubuntu-Update.sh --install-command
```

### One-Command Ubuntu Updates

After `sdac-update` is installed, future updates are one command:

```bash
sdac-update latest-official
```

Experimental channel:

```bash
sdac-update latest-experimental
```

Optional checks:

```bash
SDAC_RUN_RESTORE_TEST=1 SDAC_RUN_PRODUCTION_CHECK=1 sdac-update latest-official
```

The updater also accepts `latest`, `official`, `experimental`, `expirimental`,
and `latest-expirimental` as aliases.

If an older install says `/etc/sdac-bot/update.env: Permission denied`, fix the
updater defaults file once:

```bash
sudo chmod 644 /etc/sdac-bot/update.env
```

### New Ubuntu Install

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/install_ubuntu.sh
```

Dedicated service user:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_APP_USER=sdac SDAC_CREATE_APP_USER=1 bash scripts/install_ubuntu.sh
```

### Local Ubuntu Update

Use this after manually uploading files from the local `server/` folder:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/update_ubuntu.sh
```

### Services

```bash
sudo systemctl daemon-reload
sudo systemctl restart sdac-bot
sudo systemctl restart sdac-dashboard
sudo systemctl status sdac-bot --no-pager
sudo systemctl status sdac-dashboard --no-pager
```

### Logs

```bash
journalctl -u sdac-bot -n 80 --no-pager
journalctl -u sdac-dashboard -n 80 --no-pager
journalctl -u nginx -n 80 --no-pager
```

### Health Checks

```bash
curl http://127.0.0.1:5000/health
curl -I https://freethefishies.us.to/health
```

Admin JSON health:

```text
https://freethefishies.us.to/admin/health?key=ImTheBestAdmin
```

Human-friendly maintenance page:

```text
https://freethefishies.us.to/admin/maintenance?key=ImTheBestAdmin
```

### Nginx And HTTPS

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/install_nginx_site.sh
sudo certbot --nginx -d freethefishies.us.to --cert-name freethefishies.us.to --key-type rsa
sudo certbot renew --dry-run
```

### Backups And Restore Tests

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/test_restore.sh
```

Specific backup:

```bash
bash scripts/test_restore.sh /home/ubuntu/discord-screenshot-bot/backups/sdac-BACKUP.db
```

### Database Migrations

```bash
cd /home/ubuntu/discord-screenshot-bot
venv/bin/python scripts/migrate_database.py --db sdac.db
```

### Production Check

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/check_production.sh
```

Include Certbot dry-run:

```bash
SDAC_DOMAIN=freethefishies.us.to SDAC_RUN_CERTBOT_DRY_RUN=1 bash scripts/check_production.sh
```

### Rollback

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/rollback_ubuntu.sh /home/ubuntu/discord-screenshot-bot/deploy-backups/SNAPSHOT-NAME
```

### Discord Admin Commands

```text
/setsubmit #channel
/clearsubmit
/setcategory category #channel
/editcategory oldname newname #channel
/deletecategory category
/categories
/settings
/checkpermissions
/setapproval enabled #channel
/setadminrole @role
/removeadminrole @role
/setweeklychannel #channel
/setweeklyday Sunday
/setweeklytime 0 0
/settimezone America/New_York
/setguesstimeout 10
/setgamesummarychannel #channel
/seterrorchannel #channel
/startgame answer media text
/guess guess
/correct
/cancelgame
/sethint hint
/hint
/removesubmission id
/submissioninfo id
```

### Dashboard Pages

```text
/                              Public submissions
/guessing                       Guessing leaderboard
/achievements                   Monthly achievements
/servers                        Server list
/admin/login?key=ImTheBestAdmin Admin login
/admin/settings?key=ImTheBestAdmin
/admin/onboarding?key=ImTheBestAdmin
/admin/maintenance?key=ImTheBestAdmin
/admin/moderation?key=ImTheBestAdmin
/audit?key=ImTheBestAdmin
/admin/health?key=ImTheBestAdmin
```

### Windows

Download `SDAC-Bot-Windows-Installer.exe` from the latest GitHub release, run it, enter the Discord token, then start SDAC with:

```bat
start-sdac.bat
```

After Version 2.4 is installed on Windows, update with:

```bat
update-sdac.bat latest-official
```

The release also includes `SDAC-Bot-Windows-Update.ps1` for Windows-only
updates.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\SDAC-Bot-Windows-Update.ps1 latest-official
```

## Do Not Upload Or Commit

- `.env`
- `sdac.db`, `*.db-wal`, or `*.db-shm`
- `media/`
- `backups/`
- `deploy-backups/`
- `venv/` or `.venv/`
- `__pycache__/`

The local `server/` folder is the clean upload folder for manual Ubuntu updates.
