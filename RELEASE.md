# SDAC Bot Version 2.4.1

Date: 2026-06-18

Version 2.4.1 fixes the Linux updater defaults file permissions introduced in
Version 2.4.

Included:

- `/etc/sdac-bot/update.env` is now installed as readable updater defaults
- `/etc/sdac-bot/sdac.env` remains root-only because it contains secrets
- `sdac-update` now prints a clear fix command if the old updater defaults file
  is still unreadable
- documentation includes the one-time `chmod` fix for older installs
- Linux single-file installer
- Windows single-file installer
- standalone Ubuntu updater release asset
- standalone Windows updater release asset
- `latest-official` update channel
- `latest-experimental` update channel

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
