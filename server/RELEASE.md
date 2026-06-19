# SDAC Bot Version 2.5 Official

Date: 2026-06-19

Version 2.5 is an official release. It promotes the recent multi-server
feature work and updates GitHub release/update defaults for the new repository
owner, `BaytaeTistear`.

Included:

- GitHub release/update defaults now use `BaytaeTistear/SDAC-Bot`
- per-server feature toggles for submissions, approval queues, guessing games,
  weekly posts, public gallery visibility, and cross-server rankings
- guessing-game answer aliases using `|`
- generated hints, manual `/revealhint`, and optional automatic hints
- public user profiles
- public submission report form and admin report review queue
- audit filters for actor and date range
- maintenance release-channel display
- admin backup download links
- onboarding setup health score and quick setup wizard
- Linux and Windows updaters retain the Version 2/latest/exact-version aliases
- Linux single-file installer
- Windows single-file installer
- standalone Ubuntu updater release asset
- standalone Windows updater release asset

Release channel:

- `version-2.5` is this official build
- `latest-official` points to this build
- `Version 2`, `2`, `v2`, and `version-2` resolve to this official channel

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
