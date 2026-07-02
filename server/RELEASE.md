# SDAC Bot and App Version 3.0.23 Experimental

Date: 2026-07-02

Version 3.0.23 is an experimental bot reset and Bot Owner access-control update.

Included:

- added `/sdacreset confirm:RESET reason:...` so Discord admins can request a bot process restart
- reset requests are audited, write bot status, reply to Discord first, then exit so systemd restarts the bot
- added Bot Owner controls on Owner Portal to remove or restore bot access for a server
- Bot Owner access removal stores contact details and a reason in config
- disabled servers receive the configured reason/contact message when trying to use bot slash commands
- non-Bot-Owners no longer see disabled servers in dashboard server lists
- disabled server features are treated as off by bot and dashboard feature checks

Release channel:

- `version-3.0.23` is this experimental bot and app build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.23 line is validated

---
# SDAC Bot and App Version 3.0.22 Experimental

Date: 2026-07-02

Version 3.0.22 is an experimental anime activities and official-release announcement update.

Included:

- added stable keys for every experimental anime activity while keeping the warning that activities may change or be removed
- added `/animeevent` so admins can post any anime activity prompt to a Discord channel
- added `/animechallenge` so admins can create Game Library guessing items from anime activity modes
- added `/animeprofile` and `/animeprofileview` for experimental member anime favorite/currently-watching profiles
- added `/animeleaderboard` combining monthly submission votes and guessing points
- expanded the Admin Anime Activities page with command entry points and activity keys
- added `release_announcements` notification routing for `/setnotification`
- added a bot scheduler that checks `latest-official` and announces to Discord when the official release changes
- added smoke coverage for the anime activities dashboard entry points

Release channel:

- `version-3.0.22` is this experimental bot and app build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.22 line is validated

---
# SDAC Bot and App Version 3.0.21 Experimental

Date: 2026-07-01

Version 3.0.21 is an experimental bot and app performance update that reduces repeated dashboard, API, media, and Discord lookup work.

Included:

- added short-lived runtime caching for public stats APIs, admin overview metrics, and Discord OAuth guild/user/member-role lookups
- added cache invalidation for stats/API caches when submissions, reports, config, moderation, privacy, or quarantine actions change data
- added gzip compression for larger text, JSON, JavaScript, manifest, and SVG dashboard responses when the browser supports it
- added browser cache headers for media, PWA icon, manifest, service worker, API, and HTML responses
- added nginx template gzip and cache rules for media and PWA assets
- changed My Submissions from a fixed 100-row response to paginated loading
- added database indexes for status/date, user/status/date, created date, guess points, and active game queries
- kept image gallery rendering on generated thumbnails with lazy image loading and full-size originals available when opened

Release channel:

- `version-3.0.21` is this experimental bot and app performance build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.21 line is validated

---
# SDAC Bot and App Version 3.0.20 Experimental

Date: 2026-07-01

Version 3.0.20 is an experimental bot and app update that makes the dashboard installable as a web app.

Included:

- added a Progressive Web App manifest for SDAC
- added a service worker for app install support and light offline shell caching
- added an `/app` entry point that opens the right dashboard/account landing page for the current session
- added an install-app button that appears when the browser supports PWA installation
- added an SVG app icon endpoint and mobile app metadata
- documented the installable SDAC app flow in README
- added PWA endpoints and install metadata to the pre-release smoke test

Release channel:

- `version-3.0.20` is this experimental bot and app build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.20 line is validated

---
# SDAC Bot Version 3.0.19 Experimental

Date: 2026-07-01

Version 3.0.19 is an experimental anime activity catalog update.

Included:

- added 27 anime-related activity ideas across guessing games, community events, profiles, moderation utilities, and advanced challenge modes
- added `/animeactivities` to show the experimental anime activity list in Discord
- added an Admin Anime Activities dashboard page under moderation tools
- each anime activity includes a note that it is experimental and may be changed or deleted in a future release
- added the Anime Activities dashboard page to the pre-release smoke test

Release channel:

- `version-3.0.19` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.19 line is validated

---
# SDAC Bot Version 3.0.18 Experimental

Date: 2026-07-01

Version 3.0.18 is an experimental bot identity management update.

Included:

- added Server Owner controls on Admin Settings to update the bot nickname shown inside a selected Discord server
- added Bot Owner-only control for changing the global Discord bot username
- validates Discord bot names before calling the Discord API and surfaces Discord API failures in the dashboard
- stores each server's bot nickname in config for imports, exports, and future setup flows
- added Admin Settings rendering to the pre-release smoke test

Release channel:

- `version-3.0.18` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.18 line is validated

---

# SDAC Bot Version 3.0.17 Experimental

Date: 2026-07-01

Version 3.0.17 is an experimental doctor-command line-ending hotfix.

Included:

- fixed `sdac-doctor` installing with CRLF line endings that caused `/usr/bin/env: 'bash\r': No such file or directory`
- updated release packaging to normalize extensionless shell wrappers to LF
- added Git line-ending rules for shell/update wrappers
- update/install scripts now strip CRLF from `/usr/local/bin/sdac-doctor` after installation

Release channel:

- `version-3.0.17` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.17 line is validated

---

# SDAC Bot Version 3.0.16 Experimental

Date: 2026-07-01

Version 3.0.16 is an experimental doctor-command packaging hotfix.

Included:

- fixed release payload packaging so `scripts/sdac_doctor.py`, `scripts/sdac-doctor`, and the pre-release smoke script are included
- hardened Ubuntu install/update scripts so `sudo sdac-doctor` is installed even if only `sdac_doctor.py` is present

Release channel:

- `version-3.0.16` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.16 line is validated

---

# SDAC Bot Version 3.0.15 Experimental

Date: 2026-07-01

Version 3.0.15 is an experimental release-safety and diagnostics update.

Included:

- fixed `monthly_leaderboard_scheduler` failing with `21 values for 22 columns`
- added pre-release smoke tests for bot import, dashboard import, key page rendering, migrations, and monthly leaderboard preservation
- wired `tools/release_experimental.ps1` to run the smoke tests before building or tagging
- added `sdac-doctor` server diagnostics for config, database, environment, disk, updater, service status, and recent logs
- added schema migration 16 for dashboard server access and DB-backed Bot Owners
- moved Bot Owner recognition into `dashboard_bot_owners` while keeping `baytae` as bootstrap/rescue owner
- redesigned per-server role management into a user/server role matrix
- added a Bot Owner read-only Preview As page
- added rollback/version commands and service log commands to the dashboard

Release channel:

- `version-3.0.15` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.15 line is validated

---

# SDAC Bot Version 3.0.14 Experimental

Date: 2026-06-30

Version 3.0.14 is an experimental startup hotfix.

Included:

- fixed bot startup after the per-server access update by defining the Bot Owner override username in `bot.py`
- added a bot import/startup regression test that exercises database initialization

Release channel:

- `version-3.0.14` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.14 line is validated

---

# SDAC Bot Version 3.0.13 Experimental

Date: 2026-06-30

Version 3.0.13 is an experimental server-access and diagnostics update.

Included:

- added per-server dashboard roles so a user can be Server Owner on one server and User on another
- added a `dashboard_user_server_access` table with legacy scope backfill
- added an Access Debug page showing role, visibility, selected server, and access source
- added Refresh Discord Servers links that re-run Discord OAuth guild syncing
- added sidebar warnings when an account has no linked servers
- added per-server role management to the Users admin page
- added focused sidebar/server-access regression tests
- added `tools/release_experimental.ps1` to standardize experimental release pushes

Release channel:

- `version-3.0.13` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.13 line is validated

---

# SDAC Bot Version 3.0.12 Experimental

Date: 2026-06-30

Version 3.0.12 is an experimental sidebar server selector fix.

Included:

- fixed the sidebar server selector so it lists every configured server the current user/admin can access
- stopped the selector from depending on public gallery visibility
- made the `baytae` Bot Owner override apply to existing sessions, including older sessions still labeled Server Owner
- kept non-Bot-Owner admin server lists scoped to their stored Discord server access

Release channel:

- `version-3.0.12` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.12 line is validated

---

# SDAC Bot Version 3.0.11 Experimental

Date: 2026-06-29

Version 3.0.11 is an experimental sidebar, filter, and server-scope update.

Included:

- fixed the sidebar Menu button so page-level button styles cannot stretch it across the page
- moved filters into dropdown panels only on Submissions, My Submissions, and Guessing pages
- Discord OAuth now requests the `guilds` scope and stores configured server membership for account scoping
- non-Bot-Owner admin server access now fails closed to the user's stored server scope
- `baytae` is promoted to Bot Owner on login
- added an account server chooser for first/new Discord logins and server switching
- added a Cross Server sidebar section for all-allowed-server views
- added a Server Owner purge tool for non-admin users and submissions in a selected server section
- added a per-server Cross-Server Gallery Visibility feature toggle
- darkened the Theme page file picker styling

Release channel:

- `version-3.0.11` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.11 line is validated

---

# SDAC Bot Version 3.0.10 Experimental

Date: 2026-06-29

Version 3.0.10 is an experimental responsive sidebar repair.

Included:

- fixed sidebar sections stacking incorrectly as horizontal columns
- isolated sidebar navigation from page-level nav styles
- added a collapsible sidebar toggle for desktop pages
- changed mobile behavior to an off-canvas sidebar drawer with a Menu button
- applied the responsive sidebar fix to both the dashboard and server copies

Release channel:

- `version-3.0.10` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.10 line is validated

---

# SDAC Bot Version 3.0.9 Experimental

Date: 2026-06-29

Version 3.0.9 is an experimental sidebar cleanup update.

Included:

- removed the duplicate top navigation bar from sidebar-enabled pages
- kept pagination navigation visible while hiding old header navigation links
- applied the sidebar cleanup to both the dashboard and server copies

Release channel:

- `version-3.0.9` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.9 line is validated

---

# SDAC Bot Version 3.0.8 Experimental

Date: 2026-06-29

Version 3.0.8 is an experimental polls, public sidebar, and release page update.

Included:

- public and not-signed-in pages now render the shared sidebar
- account login always shows the Discord login button
- Discord login now redirects back with a setup notice when OAuth is not configured
- new Discord poll commands: `/createpoll`, `/polls`, `/votepoll`, and `/closepoll`
- new `/admin/polls` dashboard page to create, close, reopen, delete, and review polls
- release page now shows recent version releases and only the latest local patch-notes block
- admin pages keep the full role-aware sidebar

Release channel:

- `version-3.0.8` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.8 line is validated

---

# SDAC Bot Version 3.0.7 Experimental

Date: 2026-06-29

Version 3.0.7 is an experimental public sidebar and Discord-login visibility update.

Included:

- public and not-signed-in pages now render the shared sidebar
- guest sidebar only shows user/public links and account actions
- account login always shows the Discord login button
- Discord login now redirects back with a setup notice when OAuth is not configured
- admin pages keep the full role-aware sidebar

Release channel:

- `version-3.0.7` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.7 line is validated

---

# SDAC Bot Version 3.0.6 Experimental

Date: 2026-06-29

Version 3.0.6 is an experimental dashboard layout polish update.

Included:

- moved the admin overview cards from the gallery landing page to `/admin`
- added a Home link to the admin sidebar
- fixed sidebar rendering on the bare `/admin` route
- extended shared theme styling to public and non-admin pages
- public gallery pages no longer show admin overview metrics

Release channel:

- `version-3.0.6` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.6 line is validated

---

# SDAC Bot Version 3.0.5 Experimental

Date: 2026-06-29

Version 3.0.5 is an experimental dashboard redesign and role-scope update.

Included:

- redesigned admin landing page with persistent sidebar styling and overview panels
- overview panels for known users, submissions by date range, review counts,
  active games, reports, lockouts, last restart, last backup, database size,
  media storage, and bot heartbeat
- all HTML pages now receive shared dashboard theme variables
- Server Owner theme page for color changes and uploaded/linked background images
- normal user accounts can sign in with Discord OAuth
- admin areas now require username/password login; admin Discord OAuth endpoints
  are disabled
- Owner role label changed to Server Owner and is scoped to assigned servers
- new Bot Owner role can access all servers
- Bot Owner sidebar section includes a server selector for switching server views

Release channel:

- `version-3.0.5` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.5 line is validated

---

# SDAC Bot Version 3.0.4 Experimental

Date: 2026-06-29

Version 3.0.4 is an experimental dashboard navigation update.

Included:

- admin sidebar is now split into three collapsible sections
- User section contains public/user-facing dashboard links
- Moderation section contains moderator-and-up moderation workflows
- Owner section is visible only to owner accounts
- sidebar links now escape generated labels and URLs before injection

Release channel:

- `version-3.0.4` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3/3.0.4 line is validated

---

# SDAC Bot Version 3.0.3 Experimental

Date: 2026-06-29

Version 3.0.3 is an experimental admin user-control build.

Included:

- new `/admin/users` dashboard tab for account moderation and user controls
- role-aware dashboard promotion rules: admins and owners can promote users up
  to moderator, while only owners can promote users to admin or owner
- dashboard ban rules now enforce role hierarchy so admins and moderators can
  only ban users below their own role
- the `baytae` owner account can ban another owner only after entering a
  server-generated confirmation code
- Discord user lockouts for guessing games, submissions, or both
- `/submit` and `/guess` now block users with active dashboard lockouts
- schema v15 with the `user_restrictions` table

Release channel:

- `version-3.0.3` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until this build is validated

---

# SDAC Bot Version 3.0.2 Official

Date: 2026-06-29

Version 3.0.2 is an official dashboard account and sidebar completion update.

Included:

- admin sidebar now appears on admin-key dashboard pages outside `/admin/*`,
  including the main submissions gallery, audit page, user profiles, and
  My Submissions
- public gallery navigation now shows account login, registration, account, and
  logout links based on user login state
- dashboard accounts can store a linked Discord user ID
- account registration, admin Settings, and the server CLI can set Discord user
  IDs for accounts
- `/me` and My Submissions now use the linked Discord user ID from the logged-in
  account instead of requiring users to manually search every time
- `/admin/login` now also creates the matching account session for local
  dashboard accounts, so sidebar account links work immediately
- disabled user accounts are logged out when they try to open `/account`

Release channel:

- `version-3.0.2` is this official dashboard completion update
- `latest-official` points to this build
- `Version 3`, `3`, `v3`, and `version-3` resolve to this official channel

---

# SDAC Bot Version 3.0.1 Official

Date: 2026-06-29

Version 3.0.1 is an official submission-flow hotfix.

Included:

- `/submit` no longer takes a category argument
- Step 1 now shows a Discord category selector
- Step 2 asks the user to send one normal message with required image, audio,
  or video media and optional text
- Step 3 shows the preview and confirm/cancel buttons
- removed the hard guided-submission startup block for missing Manage Messages;
  successful submissions can still post even if source-message deletion fails
- updated command docs/help from `/submit category` to `/submit`

Release channel:

- `version-3.0.1` is this official hotfix
- `latest-official` points to this build
- `Version 3`, `3`, `v3`, and `version-3` resolve to this official channel

---

# SDAC Bot Version 3.0 Official

Date: 2026-06-29

Version 3.0 is an official dashboard and account-management release.

Included:

- dashboard accounts can now be registered with email, optional username, and
  password
- dashboard admins can promote users to trusted, moderator, admin, or owner
  roles from the admin Settings page
- server shell account management through `scripts/reset_admin_login.py` for
  create/update, list, disable, enable, delete, and legacy default cleanup
- removed the old default admin password fallback; create a real owner account
  during install or with the CLI helper
- consistent admin sidebar navigation across admin dashboard pages
- Ubuntu and Windows installers now seed an initial dashboard owner account
- submission repost cleanup no longer rolls back a successful submission when
  Discord refuses to delete the source message
- submission reposting now fetches a category channel if Discord has not cached
  it yet
- updater aliases now support `Version 3`, `3`, and `v3`; `Version 2` remains
  pinned to the last official Version 2 release

Release channel:

- `version-3.0` is this official build
- `latest-official` points to this build
- `Version 3`, `3`, `v3`, and `version-3` resolve to this official channel
- `Version 2`, `2`, `v2`, and `version-2` remain pinned to `version-2.8`

---

# SDAC Bot Version 2.8.4 Experimental

Date: 2026-06-29

Version 2.8.4 is an experimental operations and game-library build.

Included:

- Discord backup setup flow with `/backupguide`, `/backupsetup`,
  `/backupnow`, and `/backupstatus`
- per-server zip backup archives with SHA256 sidecars and rclone upload support
- Ubuntu backup prerequisite installer for rclone, zip, unzip, and certificates
- dashboard admin login recovery helper at `scripts/reset_admin_login.py`
- scheduled saved-library games through `/schedulegame`, `/scheduledgames`, and
  `/cancelscheduledgame`
- guessing streak achievements saved to the database and shown on the public
  achievements page
- Game Library pack, tag, notes, and enabled-for-picker metadata
- admin notification digests with `/setdigest`
- `/setupchecklist` production-readiness summary
- standard moderation reason presets for `/removesubmission`
- dashboard Server Health Cards page at `/admin/server-health`
- release checklist helper at `scripts/release_checklist.sh`
- README updates for backup setup, login recovery, new slash commands, and
  dashboard pages

Release channel:

- `version-2.8.4` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.8.3 Experimental

Date: 2026-06-28

Version 2.8.3 is an experimental command-discovery build.

Included:

- new `/commands` public slash command for regular user commands
- new `/admincommands` admin-only slash command for SDAC admin commands
- command help automatically splits long admin command output into safe
  Discord-sized messages
- README command directory now separates Discord user commands from Discord
  admin commands

Release channel:

- `version-2.8.3` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.8.2 Experimental

Date: 2026-06-28

Version 2.8.2 is an experimental operations-safety build for validating the
next production admin workflow.

Included:

- `/repository` Discord admin command showing the configured user/fork repo and
  the original upstream repo
- schema v11 with pending admin approvals, media quarantine, and monthly digest
  run tracking
- `/admin/install-doctor` for setup, permissions, updater, Nginx, Certbot,
  database, and heartbeat checks
- `/admin/approvals` for two-admin review of dangerous actions
- `/admin/owner-portal` for a compact per-server operations overview
- media quarantine controls on submissions and the media cleanup page
- SQLite optimize action on Maintenance
- config import diff preview before replacing a server config
- permission drift monitor for configured Discord channels
- monthly restore drills and monthly digest posts
- public read-only JSON endpoints for stats, servers, leaderboards, and server
  summaries
- bot/dashboard instance IDs in status pages and health JSON
- release page guidance for official, experimental, and explicit-version
  update channels
- README updates for the new commands, pages, APIs, and exact release example

Release channel:

- `version-2.8.2` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.8.1 Experimental

Date: 2026-06-24

Version 2.8.1 is an experimental production-usability build layered on top of
the official Version 2.8 release.

Included:

- public `/about` bot landing page with setup summary and invite helper
- `/admin/releases` release-channel page showing installed, official, and
  experimental release status plus update/rollback commands
- automatic post-update health summary in the Ubuntu updater
- `sdac-update rollback` for restoring the latest deploy snapshot
- dashboard rollback queue action on the Maintenance page
- storage forecast table on Maintenance and in admin health JSON
- `/admin/monthly-report` with monthly top submissions, top guessers, activity
  totals, and CSV export
- `/export/monthly-report.csv` for monthly report downloads
- `/admin/audit` alias for the existing audit log
- onboarding setup template table for common server styles
- clearer `/repairpermissions` preview with scopes and permission integer
- production check script now reports all failed checks before exiting
- Windows updater now runs a local dashboard health check after updates and
  explains that rollback is Linux-only
- README updates for the new pages, rollback command, updater health checks,
  and report export

Release channel:

- `version-2.8.1` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.8 Official

Date: 2026-06-24

Version 2.8 is an official release. It promotes the 2.7 experimental line into
the stable Version 2 channel with production hosting, media lifecycle,
per-server backup, privacy, and operations improvements.

Included:

- optional Discord OAuth dashboard login and per-server admin scoping
- emergency `/sdacpanic` pause/resume command
- dashboard analytics, public stats, production health score, and support
  bundle tooling
- optional PostgreSQL runtime mode and SQLite-to-Postgres export helper
- Docker, Docker Compose, systemd, Nginx, and updater improvements
- per-server upload, game, storage, moderation, and backup controls
- per-server rclone backup targets with public media URL support
- generated image thumbnails, optional image compression, remote-original
  gallery badges, and local original retention/pruning controls
- old-history archiving that preserves monthly top 10 snapshots
- `/my-submissions`, `/me`, and better public gallery/user usability
- schema v10 with background jobs, media fingerprints, and privacy action logs
- `/admin/jobs` for long-running maintenance work
- `/admin/privacy` for per-server user data export/delete requests
- per-server config export/import from dashboard Settings
- duplicate media detection and anti-spam review scoring
- admin-visible spam score badges on gallery submissions
- on-demand media restore buttons for pruned remote originals
- public server-owner setup guide at `/setup-guide`
- new Discord `/repairpermissions` helper with missing-permission summary and
  bot re-authorization link
- mobile layout improvements across key dashboard pages
- refreshed README, permissions guide, release notes, installer defaults,
  release assets, and server copy

Release channel:

- `version-2.8` is this official build
- `latest-official` points to this build
- `Version 2`, `2`, `v2`, and `version-2` resolve to this official channel
- `latest-experimental` remains available for future test builds

---

# SDAC Bot Version 2.7.4 Experimental

Date: 2026-06-23

Version 2.7.4 is an experimental operations and multi-server usability build.

Included:

- schema v10 with background jobs, media fingerprints, and privacy action logs
- dashboard background job queue plus `/admin/jobs`
- long-running thumbnail generation, media pruning, media restore, history
  archive, and duplicate-index rebuild actions now run as background jobs
- per-server config export/import from dashboard Settings
- per-server user privacy export/delete tools under `/admin/privacy`
- duplicate media detection and anti-spam review scoring for submissions
- admin-visible spam score badges on gallery submissions
- on-demand media restore buttons for pruned remote originals
- public server-owner setup guide at `/setup-guide`
- new Discord `/repairpermissions` helper with missing-permission summary and
  bot re-authorization link
- mobile layout improvements for Settings, Jobs, Privacy, and Media pages
- README and release docs updated for the new pages and command

Release channel:

- `version-2.7.4` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.7.3 Experimental

Date: 2026-06-23

Version 2.7.3 is an experimental storage and usability build.

Included:

- generated WebP thumbnails for images when Pillow is installed
- lightweight public gallery image loading with thumbnail-first previews
- optional image compression controls for JPEG/PNG/WebP uploads
- `/submit` guidance showing accepted media, file limits, storage remaining,
  compression status, and retention behavior
- per-server storage dashboard under `/admin/media`
- backup health badges, prune buttons, and rclone restore buttons for each
  server with a configured backup remote
- automatic cleanup of old local originals after successful per-server backup
  and public media URL setup, while keeping thumbnails local
- manual dashboard action to generate missing thumbnails for older uploads
- `/my-submissions` and `/me` page for users to find their public submissions
- old-history archive actions in Maintenance that preserve monthly top 10
  snapshots before optional live-row removal
- `scripts/archive_old_history.py` and `scripts/restore_guild_media_rclone.sh`
- updated installer defaults, requirements, README, and release assets

Release channel:

- `version-2.7.3` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

# SDAC Bot Version 2.7.2 Experimental

Date: 2026-06-23

Version 2.7.2 is an experimental per-server backup build.

Included:

- per-server external backup settings in `config.json`
- new `/setserverbackup` and `/serverbackupstatus` Discord admin commands
- dashboard Settings fields for each guild's backup remote, public media URL,
  backup includes, and local media cleanup switch
- Maintenance page status table for per-server backup targets
- `scripts/backup_guild_offsite.sh` for guild-scoped config/database exports,
  guild media rclone copies, status recording, and optional local guild media
  cleanup after successful backup
- per-guild public media URL support for dashboard media links
- installer payload and README updates for the new backup workflow

Release channel:

- `version-2.7.2` is this experimental build
- `latest-experimental` points to this build
- `latest-official` remains on the latest official Version 2 release

---

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
