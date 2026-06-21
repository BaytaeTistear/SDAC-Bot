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
