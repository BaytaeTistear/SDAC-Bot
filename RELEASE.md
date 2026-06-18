# SDAC Bot Version 2.4

Date: 2026-06-18

Version 2.4 focuses on release channels and matching updater scripts for each
operating system.

Included:

- `latest-official` update channel for production servers
- `latest-experimental` update channel for test builds
- typo-compatible updater aliases including `latest-expirimental`
- Linux `sdac-update` now defaults to `latest-official`
- standalone Ubuntu updater release asset
- standalone Windows updater release asset
- Windows installer now writes `update-sdac.bat`
- GitHub Actions release workflow publishes `latest-*` channel tags
- Linux single-file installer
- Windows single-file installer
- Ubuntu systemd service installation and restart helpers
- Nginx, backup, restore-test, and production-check helpers
- dashboard Maintenance page
- dashboard Moderation page
- Discord `/checkpermissions` command
- cross-server dashboard filtering and guessing rankings
- monthly submission and guessing leaderboards

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
