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
