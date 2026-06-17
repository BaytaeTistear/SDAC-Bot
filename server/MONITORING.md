# SDAC Monitoring And Backups

Use this after the bot is running behind Nginx.

## Uptime Monitor

Monitor the public health endpoint:

```text
https://freethefishies.us.to/health
```

UptimeRobot, Better Stack, or any other HTTP monitor can check that URL every
five minutes. Alert on any non-200 response.

If you use a different domain, check:

```text
https://YOUR-DOMAIN/health
```

## Local Production Check

Run this from the server:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/check_production.sh
```

Include a Let's Encrypt renewal test when you want the full check:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to SDAC_RUN_CERTBOT_DRY_RUN=1 bash scripts/check_production.sh
```

## Discord Error Channel

Set a private staff channel for bot error notices:

```text
/seterrorchannel #sdac-errors
```

Clear it if needed:

```text
/clearerrorchannel
```

## Off-Server Backups

Install and configure `rclone` on the Ubuntu server:

```bash
sudo apt install -y rclone
rclone config
```

Run a backup:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_RCLONE_REMOTE=remote:sdac bash scripts/backup_offsite.sh
```

Add a daily cron job:

```bash
crontab -e
```

Example cron line:

```cron
15 3 * * * cd /home/ubuntu/discord-screenshot-bot && SDAC_RCLONE_REMOTE=remote:sdac bash scripts/backup_offsite.sh >> backups/offsite.log 2>&1
```

The backup includes `sdac.db`, `config.json`, and `media/`. It does not include
`/etc/sdac-bot/sdac.env` by default because that file contains secrets. If your
remote storage is secure and you intentionally want it included, add:

```bash
SDAC_BACKUP_INCLUDE_ENV=1
```
