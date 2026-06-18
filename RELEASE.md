# SDAC Bot Version 2.1

Date: 2026-06-18

Version 2.1 focuses on production polish, safer cross-platform installers, and
admin maintenance tools.

Included:

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
