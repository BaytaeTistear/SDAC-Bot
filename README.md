# SDAC Bot

SDAC Bot is a Discord media submission and guessing-game system with a web dashboard. Discord users submit images, audio, or video through `/submit`. Admins configure categories, review pending submissions, run guessing games, and view submissions, votes, leaderboards, maintenance status, and moderation history from the dashboard.

## What It Does

- Guided Discord `/submit` flow with category, media/text, and confirmation
- Admin category and channel setup through slash commands
- Optional approval queue before media is reposted
- Public web gallery with sorting by newest, votes, and month
- Preserved monthly top 10 submission snapshots
- Guessing games started by admins with `/startgame`
- Website-managed guessing-game library for reusable media, answers, aliases,
  prompts, categories, and hints
- Game-library packs, tags, admin notes, enable/disable controls, and bulk CSV
  import for answer drafts
- Library game randomizer and category filter for `/startlibrarygame`
- Scheduled library games with auto-close support through `/schedulegame`
- Answer aliases, generated hints, automatic hints, `/guess` scoring,
  wrong-guess cooldowns, and monthly leaderboards
- Guessing-game streak achievements and public achievement award history
- Cross-server dashboard filtering and cross-server guessing rankings
- Per-server feature toggles for submissions, approval queues, guessing games,
  weekly posts, public gallery visibility, and cross-server rankings
- Per-server dashboard branding with display name, accent color, and logo URL
- Role-based dashboard admin login on top of the admin key
- Public dashboard account registration with email, optional username, and
  hashed password storage
- Dashboard admin promotion controls for user, trusted, moderator, admin, and
  owner roles
- Consistent admin sidebar navigation across dashboard pages
- Optional Discord OAuth dashboard login with per-server admin scoping
- Admin alert routing for system errors, backup/restore failures, storage
  warnings, repost deletion failures, and stale bot heartbeat warnings
- Public user profiles and submission reports
- Moderation queue bulk review and submission review flags
- Media cleanup dashboard for orphaned, missing, and oversized media
- Media quarantine controls for suspicious/problem submissions
- Background job queue and Jobs page for long-running maintenance actions
- Two-admin approval queue for dangerous admin actions
- Duplicate media fingerprinting with admin-visible anti-spam review scores
- Lightweight gallery mode with generated thumbnails and remote-original badges
- Media lifecycle controls for local original retention, thumbnail size, image
  compression, backed-up original pruning, and old-history archives
- Submission/game analytics dashboard with recent game answer history
- Monthly admin report page and CSV export for top submissions, guessers,
  votes, and activity
- Maintenance page for backups, backup downloads, release status, restore tests,
  backup checksums, storage warnings, config backup restore, bot heartbeat
  status, storage forecast, rollback queueing, and health
- Install Doctor, owner portal, config import diff preview, SQLite optimize,
  monthly restore drills, permission drift alerts, and monthly digest posts
- Server Health Cards page for quick per-server setup, storage, backup, game,
  library, and achievement status
- Release channel dashboard for installed, official, and experimental versions
- Moderation page for pending submissions, public reports, and recent decisions
- Admin audit log under `/audit` and `/admin/audit`
- Admin Privacy page for per-server user data export/delete requests
- Per-server config export/import from dashboard Settings
- Public bot landing page at `/about`
- Public setup guide for server owners at `/setup-guide`
- Onboarding page with setup health scores, saved setup-test reports, invite
  link helper, setup templates, and quick setup commands
- Discord-native `/setup` wizard with presets, permission checks, and full
  setup test
- `/diagnose` self-checks for database, folders, channels, permissions, bot
  runtime state, public URL, and command sync
- `/repository` shows the configured user/fork GitHub repo and the original
  upstream repo
- Website-managed guessing-game seasons with top 10 leaderboard snapshots
- Emergency `/sdacpanic` pause/resume command for submissions and games
- Per-server limits for file size, monthly submissions, active games, and storage
- Content moderation controls for blocked words, allowed media types, new-user
  approval, and spoiler approval
- Public stats page, production health score page, and support bundle helper
- Optional cloud media mirror support through `SDAC_MEDIA_PUBLIC_BASE_URL`
  plus `scripts/sync_media_rclone.sh`
- Per-server rclone backup targets with optional public media URL prefixes,
  guild-scoped database exports, zip backup archives, and opt-in local guild
  media cleanup
- Discord backup setup commands for Google Drive, OneDrive, Dropbox, Mega, S3,
  Backblaze B2, Box, and SFTP through rclone
- Per-server storage dashboard with restore/prune buttons and backup health
  badges
- Docker and Docker Compose files for easier self-hosting
- PostgreSQL export tooling and experimental `SDAC_DATABASE_URL` runtime mode
- New-server welcome message that points admins to `/setup`
- Ubuntu systemd service templates and Nginx helper scripts
- CLI dashboard account management with `scripts/reset_admin_login.py`
- Backup prerequisite and release checklist helpers under `scripts/`
- Linux and Windows single-file installers from GitHub Releases

## Main Files

- `bot.py` - Discord bot and slash commands
- `dashboard.py` - Flask dashboard
- `config.py` - environment loading
- `database_migrations.py` - SQLite schema migrations
- `database_backend.py` - SQLite default backend plus experimental Postgres mode
- `config.json` - Discord server/channel/category settings
- `sdac.db` - production SQLite database, not included in releases
- `media/` - uploaded media, not included in releases
- `scripts/` - install, update, backup, restore, and production helpers
- `systemd/` - Ubuntu service templates
- `nginx/` - dashboard reverse-proxy template
- `Dockerfile` and `docker-compose.yml` - container hosting option

## Command Directory

### One-Time Updater Install

Install the `sdac-update` command once. The latest official installer also installs
this command automatically.

```bash
cd /tmp
rm -f SDAC-Bot-Ubuntu-Update.sh
gh release download latest-official \
  --repo BaytaeTistear/SDAC-Bot \
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

Stable Version 3 alias:

```bash
sdac-update "Version 3"
```

Stable Version 2 alias, pinned to the last Version 2 official release:

```bash
sdac-update "Version 2"
```

Experimental channel:

```bash
sdac-update latest-experimental
```

Explicit numbered release:

```bash
sdac-update 3.0
```

Optional checks:

```bash
SDAC_RUN_RESTORE_TEST=1 SDAC_RUN_PRODUCTION_CHECK=1 sdac-update latest-official
```

The updater always restarts both SDAC services and runs a post-update health
summary for bot service status, dashboard service status, database migration,
local dashboard health, optional public HTTPS health, and Nginx when present.

The updater also accepts `latest`, `official`, `3`, `v3`, `version-3`, `2`,
`v2`, `version-2`, `experimental`, `expirimental`, and
`latest-expirimental` as aliases. `Version 3` resolves to the current official
channel. `Version 2` remains pinned to the last official Version 2 release.
Exact versions like `2.8` or `3.0` resolve to that specific `version-*`
release.

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

The installer prompts for an initial dashboard owner username and password, then
stores that account in the database with a hashed password. The old default
`owner` / `TheOnePieceIsReal` style fallback is not used.

Dedicated service user:

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_APP_USER=sdac SDAC_CREATE_APP_USER=1 bash scripts/install_ubuntu.sh
```

### Dashboard Account Management

Create or reset an owner from the server shell:

```bash
cd /home/ubuntu/discord-screenshot-bot
venv/bin/python scripts/reset_admin_login.py --username owner --role owner
```

Create an admin with an email:

```bash
venv/bin/python scripts/reset_admin_login.py \
  --username alex \
  --email alex@example.com \
  --discord-user-id 123456789012345678 \
  --role admin
```

The Discord user ID link is optional, but it lets `/me` and the dashboard
account page automatically show that user's submissions after login.

List, disable, enable, or delete accounts:

```bash
venv/bin/python scripts/reset_admin_login.py --list
venv/bin/python scripts/reset_admin_login.py --username alex --disable
venv/bin/python scripts/reset_admin_login.py --username alex --enable
venv/bin/python scripts/reset_admin_login.py --username alex --delete
```

Remove legacy default dashboard usernames:

```bash
venv/bin/python scripts/reset_admin_login.py --delete-defaults
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

Free offsite backup options that work well with `scripts/backup_offsite.sh`:

- Google Drive via `rclone`
- Mega via `rclone`
- Backblaze B2 free allowance
- Another VPS or home server over SSH/rsync
- Encrypted config-only archives in a private GitHub release

Example offsite backup:

```bash
sudo apt install rclone
rclone config
SDAC_RCLONE_REMOTE=drive:sdac-backups bash scripts/backup_offsite.sh
```

Mirror media to a cloud/public bucket:

```bash
SDAC_MEDIA_RCLONE_REMOTE=drive:sdac-media bash scripts/sync_media_rclone.sh
```

If the mirrored media has a public URL prefix, set:

```text
SDAC_MEDIA_PUBLIC_BASE_URL=https://cdn.example.com/sdac-media
```

Per-server alternate backups:

```bash
# First set the remote from Discord:
# /setserverbackup true drive:sdac/server-123 https://cdn.example.com/sdac/server-123 true true false

# Then run the guild backup from the host:
SDAC_GUILD_ID=123456789 bash scripts/backup_guild_offsite.sh
```

`scripts/backup_guild_offsite.sh` reads the guild's `external_backup` settings
from `config.json`, exports only that guild's config/database rows, copies only
that guild's `media/<guild_id>` folder, and records the last status back into
the same guild config. If `delete_local_media_after_success` is enabled, local
media for that guild is pruned only after rclone finishes successfully. Keep
that option disabled unless the remote media is also reachable through a public
URL or you are comfortable restoring media manually.

Restore one server's media from its configured rclone remote:

```bash
SDAC_GUILD_ID=123456789 bash scripts/restore_guild_media_rclone.sh
```

Archive old full submission history while preserving monthly top 10 snapshots:

```bash
venv/bin/python scripts/archive_old_history.py --months 18
```

Archive and remove exported full rows from the live `submissions` table:

```bash
venv/bin/python scripts/archive_old_history.py --months 18 --delete-exported
```

The dashboard also exposes these operations under:

```text
/admin/media?key=ImTheBestAdmin
/admin/maintenance?key=ImTheBestAdmin
/my-submissions
```

### Database Migrations

```bash
cd /home/ubuntu/discord-screenshot-bot
venv/bin/python scripts/migrate_database.py --db sdac.db
```

### PostgreSQL

SQLite remains the live default database. Version 2.7.1 adds experimental
runtime support behind `SDAC_DATABASE_URL`; test it before production. To test a
PostgreSQL migration:

```bash
docker compose --profile postgres up -d postgres
venv/bin/python scripts/export_sqlite_to_postgres.py \
  --sqlite sdac.db \
  --database-url "postgresql://sdac:sdac-change-me@localhost:5432/sdac" \
  --drop-existing
```

### Docker

```bash
cp .env.example .env
docker compose up -d --build dashboard bot
```

The compose file stores runtime data in a named `sdac-data` volume and keeps
the app image separate from uploaded media, backups, and `sdac.db`.

### Production Check

```bash
cd /home/ubuntu/discord-screenshot-bot
SDAC_DOMAIN=freethefishies.us.to bash scripts/check_production.sh
```

Include Certbot dry-run:

```bash
SDAC_DOMAIN=freethefishies.us.to SDAC_RUN_CERTBOT_DRY_RUN=1 bash scripts/check_production.sh
```

Create a one-command support bundle:

```bash
bash scripts/support_bundle.sh
```

### Backup Prerequisites And Zip Archives

Install backup tools on Ubuntu:

```bash
cd /home/ubuntu/discord-screenshot-bot
sudo bash scripts/install_backup_prereqs.sh
```

Then configure the provider in Discord:

```text
/backupguide provider:Google Drive
/backupsetup provider:Google Drive remote:drive:sdac/server
/backupnow upload:true
```

Per-server host backup script:

```bash
SDAC_GUILD_ID=123456789 bash scripts/backup_guild_offsite.sh
```

The backup script creates metadata exports, optional media backups, and a zip
archive under `backups/guild-offsite/GUILD_ID/archives/`, then uploads the zip
to `REMOTE/archives` when rclone is configured.

### Dashboard Login Recovery

Reset or create a dashboard owner from the server shell:

```bash
cd /home/ubuntu/discord-screenshot-bot
source venv/bin/activate
python scripts/reset_admin_login.py --username owner --role owner
```

Run a release sanity checklist before promoting an experimental build:

```bash
bash scripts/release_checklist.sh
```

### Rollback

```bash
sudo sdac-update rollback
```

Specific deploy snapshot:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/rollback_ubuntu.sh /home/ubuntu/discord-screenshot-bot/deploy-backups/SNAPSHOT-NAME
```

### Discord User Commands

```text
/commands
/submit
/categories
/guess guess
/hint
```

### Discord Admin Commands

```text
/admincommands
/setsubmit #channel
/clearsubmit
/setcategory category #channel
/editcategory oldname newname #channel
/deletecategory category
/categories
/setup
/setupstatus
/setupchecklist
/setuptest
/diagnose
/repository
/settings
/setfeature submissions true
/checkpermissions
/repairpermissions
/setbranding "Server Name" #7c9cff https://example.com/logo.png
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
/setnotification system_errors #channel true
/setdigest true weekly #channel
/setlimit max_file_mb 25
/setmoderation "badword1,badword2" "image,video,audio" false 7 false
/setgamesettings 30 10 normal
/setserverbackup true drive:sdac/server https://cdn.example.com/sdac/server true true false
/serverbackupstatus
/backupguide provider:Google Drive
/backupsetup provider:Google Drive remote:drive:sdac/server
/backupnow upload:true
/backupstatus
/supportbundle
/sdacpanic true "Cleaning up spam"
/sdacpanic false
/startgame #channel answer media text category hint auto_hint_minutes
/startlibrarygame #channel item_id category random_item
/schedulegame channel:#channel start_time:"2026-07-01 19:30" item_id:0 category:movie random_item:true close_after_minutes:60
/scheduledgames
/cancelscheduledgame scheduled_id:1
/activegame
/correct
/cancelgame
/sethint hint
/revealhint
/reasonpresets
/removesubmission submission_id:1 reason_preset:duplicate reason:"Optional details"
/submissioninfo id
```

### Dashboard Pages

```text
/                              Public submissions
/about                         Public bot landing page and invite flow
/setup-guide                   Public server-owner setup guide
/guessing                       Guessing leaderboard
/achievements                   Monthly achievements
/servers                        Server list
/stats                          Public stats
/account/register               Create a dashboard account
/account/login                  Dashboard account login
/account                        Dashboard account profile
/admin/login?key=ImTheBestAdmin Admin login
/admin/settings?key=ImTheBestAdmin
/admin/game-library?key=ImTheBestAdmin
/admin/seasons?key=ImTheBestAdmin
/admin/onboarding?key=ImTheBestAdmin
/admin/maintenance?key=ImTheBestAdmin
/admin/install-doctor?key=ImTheBestAdmin
/admin/approvals?key=ImTheBestAdmin
/admin/owner-portal?key=ImTheBestAdmin
/admin/server-health?key=ImTheBestAdmin
/admin/media?key=ImTheBestAdmin
/admin/jobs?key=ImTheBestAdmin
/admin/privacy?key=ImTheBestAdmin
/admin/analytics?key=ImTheBestAdmin
/admin/monthly-report?key=ImTheBestAdmin
/admin/releases?key=ImTheBestAdmin
/admin/production-health?key=ImTheBestAdmin
/admin/moderation?key=ImTheBestAdmin
/admin/guild/GUILD_ID/config.json?key=ImTheBestAdmin
/audit?key=ImTheBestAdmin
/admin/audit?key=ImTheBestAdmin
/export/audit.csv?key=ImTheBestAdmin
/export/monthly-report.csv?key=ImTheBestAdmin
/admin/health?key=ImTheBestAdmin
/api/stats
/api/servers
/api/leaderboard
/api/server/GUILD_ID
```

### Windows

Download `SDAC-Bot-Windows-Installer.exe` from the latest GitHub release, run it, enter the Discord token, then start SDAC with:

```bat
start-sdac.bat
```

After latest official is installed on Windows, update with:

```bat
update-sdac.bat latest-official
```

Windows accepts the same channel and version names:

```bat
update-sdac.bat "Version 3"
update-sdac.bat 3.0
update-sdac.bat "Version 2"
update-sdac.bat latest-experimental
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

## SDAC App Install

The dashboard also works as an installable web app. Open the dashboard in a modern mobile or desktop browser and use the browser install prompt, or tap the in-page **Install App** button when it appears. This uses the existing website, Discord login, server selector, submissions, games, and admin pages; no app-store install is required.

The app entry point is `/app`. It sends admins to the admin overview, signed-in users to their account, and guests to the public dashboard.

## Dashboard Performance

The dashboard uses short-lived runtime caching for public stats, admin overview metrics, and Discord OAuth server/member lookups. Media and PWA assets receive browser cache headers, larger text/JSON responses are gzip-compressed when supported, image galleries use thumbnails plus lazy loading, and My Submissions is paginated to avoid large single-page responses.

If the nginx template is installed with `scripts/install_nginx_site.sh`, nginx also enables gzip and sends cache headers for media, the PWA manifest, the service worker, and the app icon.
