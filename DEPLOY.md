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

## Upload Rules

Upload the files from the local `server/` folder for the current update. That
folder should contain only files that need to be sent to the Ubuntu server.

Do not upload:

- `__pycache__/`
- `.db` files unless you are intentionally replacing server data
- `.db-wal` or `.db-shm` SQLite sidecar files
- `backups/`
- `deploy-backups/`
- `venv/`
- `.env`
- `media/` unless you are intentionally restoring media

Keep these on the Ubuntu server:

- `sdac.db`
- `media/`
- `config.json`
- `/etc/sdac-bot/sdac.env`

## Update

Recommended one-command GitHub update path:

```bash
sana-update latest-official
```

Stable Version 2 alias:

```bash
sana-update "Version 2"
```

If `sana-update` has not been installed yet:

```bash
cd /tmp
rm -f Sana-Chan-Ubuntu-Update.sh
gh release download latest-official \
  --repo BaytaeTistear/SDAC-Bot \
  --pattern Sana-Chan-Ubuntu-Update.sh \
  --dir /tmp
chmod +x Sana-Chan-Ubuntu-Update.sh

SDAC_APP_DIR=/home/ubuntu/discord-screenshot-bot \
SDAC_APP_USER=ubuntu \
SDAC_ENV_FILE=/etc/sdac-bot/sdac.env \
SDAC_DOMAIN=thelab.us.to \
./Sana-Chan-Ubuntu-Update.sh --install-command

sana-update latest-official
```

Use `sana-update latest-experimental` for the experimental channel. Exact
version numbers also work:

```bash
sana-update 2.6
```

The updater also accepts `latest-expirimental` as a typo-compatible alias.
`Version 2`, `2`, `v2`, and `version-2` always resolve to the latest official
Version 2 release. Exact versions like `2.0` or `2.6` resolve to that
specific `version-*` release.

If an older install says `/etc/sdac-bot/update.env: Permission denied`, fix the
updater defaults file once:

```bash
sudo chmod 644 /etc/sdac-bot/update.env
```

After manually uploading changed files:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/update_ubuntu.sh
```

The update script now also re-renders the systemd service files, so service
hardening and dashboard bind changes are applied during updates. It also runs
database migrations when `sdac.db` exists.

If an older service still points to `/etc/sdac.env`, run:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/standardize_env_file.sh
```

## Rollback

If the update fails after a previous deploy snapshot exists:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/rollback_ubuntu.sh /home/ubuntu/discord-screenshot-bot/deploy-backups/SNAPSHOT-NAME
```

## Services

```bash
sudo systemctl restart sdac-bot
sudo systemctl restart sdac-dashboard
sudo systemctl status sdac-bot --no-pager
sudo systemctl status sdac-dashboard --no-pager
```

## Nginx And HTTPS

Install or refresh the Nginx site:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=thelab.us.to bash scripts/install_nginx_site.sh
```

Issue or renew the Let's Encrypt certificate:

```bash
sudo certbot --nginx -d thelab.us.to --cert-name thelab.us.to --key-type rsa
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

## Health Checks

Public health check:

```text
https://thelab.us.to/health
```

Local health check:

```bash
curl http://127.0.0.1:5000/health
```

Detailed health is available in the dashboard after admin login at:

```text
/admin/health?key=ImTheBestAdmin
```

Human-friendly maintenance, backups, restore tests, and storage warnings are at:

```text
/admin/maintenance?key=ImTheBestAdmin
```

Run the bundled production check:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=thelab.us.to bash scripts/check_production.sh
```

## Restore Test

Test the latest local database backup without modifying production:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/test_restore.sh
```

The bot also runs a scheduled weekly restore test. Change the schedule from the
dashboard Settings page.

## Admin Onboarding

Use this page to see what each Discord server still needs configured:

```text
https://thelab.us.to/admin/onboarding?key=ImTheBestAdmin
```

Use this page to watch pending submissions and recent moderation decisions:

```text
https://thelab.us.to/admin/moderation?key=ImTheBestAdmin
```

In Discord, admins can run this command after permission changes:

```text
/checkpermissions
```

## GitHub Releases

The GitHub Actions workflow in `.github/workflows/release.yml` builds both
single-file installers. Push a tag like `v1.1.0`, or run the workflow manually
from GitHub Actions and provide a tag. Channel tags such as `latest-official`
and `latest-experimental` also publish release assets for one-command updates.

Discord slash commands sync when `sdac-bot` starts. If a new command does not
appear immediately, wait a few minutes and check the bot logs for the synced
command list.
