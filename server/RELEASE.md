# SDAC Bot Version 2.7.1 Experimental

Date: 2026-06-23

Version 2.7.1 is an experimental production-readiness build.

Included:

- experimental PostgreSQL runtime mode with `SDAC_DATABASE_URL`
- optional cloud media URL prefix with `SDAC_MEDIA_PUBLIC_BASE_URL`
- rclone media mirror script for cloud buckets/drives
- per-server limits for upload size, monthly submissions, active games, and storage
- content moderation settings for blocked words, media types, new-user approval,
  and spoiler approval
- game reuse cooldown/default auto-hint settings
- `/setlimit`, `/setmoderation`, `/setgamesettings`, and `/supportbundle`
- public `/stats` page
- admin `/admin/production-health` score page
- support bundle shell script for logs/config/service diagnostics
- offsite backup guidance with free options: Google Drive, Mega, Backblaze B2
  free allowance, another VPS/SSH target, or encrypted config-only GitHub storage
- release CI checks for the new commands and production-health/stats routes

Release channel:

- `version-2.7.1` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.7.0 Experimental

Date: 2026-06-23

Version 2.7.0 is an experimental hosting, security, and operations build.

Included:

- optional Discord OAuth dashboard login
- per-server dashboard admin scoping for OAuth and named dashboard users
- `/sdacpanic` emergency pause/resume command for submissions, games, and guesses
- dashboard emergency pause controls in per-guild settings
- game answer history tracking for manual and library-started games
- analytics page with submission totals, monthly volume, categories, submitters,
  active games, and recent answers
- media cleanup page for orphaned, missing, and oversized media
- configurable runtime paths for DB, config, media, backups, and bot heartbeat
- Dockerfile and Docker Compose hosting option
- optional PostgreSQL compose service plus SQLite-to-Postgres export tool
- stronger release CI smoke tests for commands, migrations, dashboard routes,
  Docker build, installer line endings, and the Postgres export tool
- mobile layout improvements on key dashboard pages
- README, `.env.example`, and PostgreSQL guide updates

Release channel:

- `version-2.7.0` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files

---

# SDAC Bot Version 2.6.2 Experimental

Date: 2026-06-21

Version 2.6.2 is an experimental operations and admin-control build.

Included:

- role-based dashboard admin accounts for moderator, admin, and owner access
- dashboard owner tools to create, update, and disable named admin users
- `/setnotification` plus dashboard notification routing for system errors,
  backup/restore failures, storage warnings, repost delete failures, and stale
  heartbeat warnings
- saved setup-test and `/diagnose` reports on the onboarding page
- `/diagnose` runtime checks for database, folders, channels, permissions,
  command sync, public URL, release, and token configuration
- website game-library edit forms with media replacement support
- moderation bulk report review and submission review flags
- game seasons page with top 10 per-season leaderboards and archived winners
- backup checksums and restore-test badges on settings and maintenance pages
- onboarding invite-link helper using `SDAC_BOT_CLIENT_ID` and
  `SDAC_BOT_PERMISSIONS`
- README and environment example updates for the new commands and settings

Release channel:

- `version-2.6.2` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files

---

# SDAC Bot Version 2.6.1 Experimental

Date: 2026-06-21

Version 2.6.1 is an experimental build focused on easier setup, safer
operations, and richer multi-server administration.

Included:

- setup presets in the Discord `/setup` wizard
- full `/setuptest` setup validation for database, writable folders,
  configured channels, permissions, command sync, and public URL/domain hints
- per-server branding through `/setbranding` and the dashboard settings page
- new-server welcome message that tells admins to run `/setup`
- bot heartbeat file surfaced on `/admin/maintenance` and `/admin/health`
- rolling `config.json` backups before config writes
- dashboard action to restore the latest config backup
- website game-library CSV import for answer drafts
- `/startlibrarygame` category filter and random-item option
- installer first-run prompts for public dashboard URL/domain and server label
- README command directory updates for the new commands and pages

Release channel:

- `version-2.6.1` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files

---

# SDAC Bot Version 2.6 Official

Date: 2026-06-21

Version 2.6 is an official release. It promotes the recent website-managed
guessing-game library, admin onboarding fix, and Discord-native setup wizard.

Included:

- website-managed guessing-game library at
  `/admin/game-library?key=ImTheBestAdmin`
- reusable game media, prompts, answers, aliases, categories, custom hints, and
  automatic hint timing
- `/startlibrarygame #channel item_id` for starting saved website library items
  from Discord
- `/setup` admin command with a three-page Discord setup wizard
- `/setupstatus` command for a quick setup checklist
- role selector for SDAC admin access
- channel selectors for submit, category, approval, weekly top, game summary,
  and error channels
- category-name modal after choosing a category repost channel
- timezone modal and weekly schedule modal
- feature-toggle select for per-server features
- built-in permission check from the final wizard page
- `/admin/onboarding` template fix for the setup checklist
- dashboard onboarding quick setup commands now point admins to `/setup`
- Linux and Windows single-file installers
- standalone Ubuntu and Windows update assets

Release channel:

- `version-2.6` is this official build
- `latest-official` points to this build
- `Version 2`, `2`, `v2`, and `version-2` resolve to this official channel

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files

---

# SDAC Bot Version 2.5.3 Experimental

Date: 2026-06-21

Version 2.5.3 adds a Discord-native setup wizard to streamline new server
onboarding.

Included:

- new `/setup` admin command with a three-page Discord setup wizard
- new `/setupstatus` command for a quick setup checklist
- role selector for SDAC admin access
- channel selectors for submit, category, approval, weekly top, game summary,
  and error channels
- category-name modal after choosing a category repost channel
- timezone modal and weekly schedule modal
- feature-toggle select for per-server features
- built-in permission check from the final wizard page
- dashboard onboarding quick setup commands now point admins to `/setup`
- setup actions write to the same `config.json` fields as the existing direct
  slash commands and record admin audit events

Release channel:

- `version-2.5.3` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.5.2 Experimental

Date: 2026-06-21

Version 2.5.2 is an experimental hotfix for the admin onboarding page.

Included:

- fixes `/admin/onboarding` failing with `TypeError:
  'builtin_function_or_method' object is not iterable`
- changes the onboarding template to read the server setup checklist with
  bracket access so Jinja does not confuse the `"items"` list with
  `dict.items`

Release channel:

- `version-2.5.2` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.5.1 Experimental

Date: 2026-06-21

Version 2.5.1 is an experimental build for testing website-managed guessing
games.

Included:

- new `guess_library_items` database table and schema migration
- admin dashboard page at `/admin/game-library?key=ImTheBestAdmin`
- website uploads for reusable guessing-game media, prompts, answers, aliases,
  categories, custom hints, and automatic hint timing
- enable, disable, and delete actions for saved library items
- new `/startlibrarygame #channel item_id` Discord admin command
- `item_id` `0` starts the next unused active library item for that server
- active games copy the saved library media before posting, so the reusable
  website upload is not removed when an active game is replaced or cleaned up

Release channel:

- `version-2.5.1` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

Not included:

- Discord token or `.env`
- SQLite database files such as `sdac.db`
- `media/` uploads
- `backups/`
- `venv/` or Python cache files

---

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
