# SDAC Bot Version 2.4.2 Experimental

Date: 2026-06-18

Version 2.4.2 is an experimental updater-alias release. It does not promote the
official Version 2 channel.

Included:

- `Version 2`, `2`, `v2`, and `version-2` resolve to `latest-official`
- exact versions like `2.0`, `2.4.2`, `v2.4.2`, and `version-2.4.2` resolve to
  that exact `version-*` release
- Linux and Windows updaters use the same alias rules
- Windows updater handles unquoted calls such as `update-sdac.bat Version 2`
- documentation now separates official, experimental, and exact-version update
  commands
- Linux single-file installer
- Windows single-file installer
- standalone Ubuntu updater release asset
- standalone Windows updater release asset

Release channel:

- `version-2.4.2` is this experimental build
- `latest-experimental` points to this build
- `latest-official` is not moved by this build

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files
