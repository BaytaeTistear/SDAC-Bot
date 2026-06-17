# SDAC Bot Version 2

Date: 2026-06-17

Version 2 focuses on production setup, easier multi-server operation, and safer
updates.

Included:

- Linux single-file installer
- Windows single-file installer
- GitHub Actions release workflow
- Ubuntu production hardening helpers
- SQLite migration tooling
- backup restore-test script
- optional Sentry error reporting
- admin onboarding checklist for each Discord server
- configurable rate limits
- media metadata storage and dashboard display

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
