# SDAC Bot Version 2.2

Date: 2026-06-18

Version 2.2 focuses on one-command server updates and clearer operator docs.

Included:

- standalone Ubuntu updater release asset
- one-stop GitHub update script with systemd reload, service restarts, and optional checks
- expanded README with command directory
- Linux single-file installer
- Windows single-file installer
- GitHub Actions release workflow with Linux installer smoke test
- Ubuntu production hardening helpers
- SQLite migration tooling
- backup restore-test script
- scheduled weekly restore-test tracking
- dashboard Maintenance page
- dashboard Moderation page
- Discord `/checkpermissions` command
- storage warning thresholds
- dedicated Linux service-user install option
- repository line-ending rules for Linux and Windows files
- optional Sentry error reporting
- admin onboarding checklist for each Discord server
- configurable rate limits
- media metadata storage and dashboard display
- PostgreSQL migration planning notes

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
