# SDAC Bot Version 4.0.7 Experimental

Date: 2026-07-12

Update scope: Mobile-friendly `/sdac` panels and simplified slash commands

Version 4.0.7 is an experimental Discord usability update focused on mobile users and cleaner command discovery.

Included:

- changed `/sdac` from dropdown-first navigation to tap-friendly button panels
- kept section-specific `/sdac` submenus for submissions, guessing games, anime profiles, setup, backups, and moderation
- limited synced slash commands by default to `/sdac`, `/submit`, `/guess`, and `/hint`
- kept legacy direct commands available behind `SDAC_SIMPLIFIED_COMMANDS=0` for troubleshooting or power-user installs
- replaced old `/sdac` help browser actions with concise in-panel help that matches simplified mode
- updated README command docs and startup tests for the simplified command surface

Release channel:

- `version-4.0.7` is this experimental mobile panel and simplified slash-command update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---# SDAC Bot Version 4.0.6 Experimental

Date: 2026-07-12

Update scope: Guided command hub submenu fix

Version 4.0.6 is an experimental usability patch for the `/sdac` guided command hub.

Included:

- changed `/sdac` top-level choices to open section-specific submenus instead of leaving the main menu visible
- added dedicated submenus for submissions, guessing games, anime profiles, setup, backups, and moderation
- added a Back button so users and admins can return to the main `/sdac` hub cleanly
- kept advanced User Help and Admin Help as separate command browser views
- preserved the setup wizard launch from the Setup submenu

Release channel:

- `version-4.0.6` is this experimental guided command hub submenu fix
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.5 Experimental

Date: 2026-07-12

Update scope: Guided Discord command hub

Version 4.0.5 is an experimental Discord command simplification update.

Included:

- added `/sdac` as a guided control center for users and admins
- grouped common user actions into dropdown paths for submissions, guessing games, anime profiles, and help
- grouped common admin actions into dropdown paths for setup, setup status, setup tests, diagnostics, backups, moderation, and advanced help
- routed setup from `/sdac` into the existing button/select setup wizard
- updated command help and README docs so `/sdac` is the first command users see
- added startup test coverage for the new guided hub command

Release channel:

- `version-4.0.5` is this experimental guided command hub update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.4 Experimental

Date: 2026-07-12

Update scope: Usable Anime Activities commands and MyAnimeList profile import

Version 4.0.4 is an experimental Anime Activities usability update.

Included:

- enabled the Anime Activities slash command set by default while keeping `SDAC_ENABLE_ANIME_COMMANDS=0` as the disable switch
- added `/animeprofileimport username` to import public MyAnimeList profile data into a user anime profile
- updated the Anime Activities dashboard command list so it shows usable slash-command syntax and MyAnimeList import support
- updated command documentation and smoke coverage for the new anime profile import flow
- added focused bot tests for default Anime command registration and MyAnimeList summary formatting

Release channel:

- `version-4.0.4` is this experimental Anime Activities command usability update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.3 Experimental

Date: 2026-07-11

Update scope: Guess-game CSV example and Anime Activities library seeding

Version 4.0.3 is an experimental admin workflow update for guess-game bulk imports and Anime Activities.

Included:

- added a checked-in example CSV for Game Library bulk imports
- added a Game Library "Download an example CSV" link at `/admin/game-library/example.csv`
- added Anime Activities seeding so admins can create one draft Game Library item for every anime activity key
- added duplicate protection when seeding existing Anime Activity modes for a server
- added smoke and focused test coverage for the example CSV and Anime Activities seed workflow

Release channel:

- `version-4.0.3` is this experimental Anime Activities and CSV example update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.2 Experimental

Date: 2026-07-11

Update scope: Companion app dependency security cleanup

Version 4.0.2 is an experimental security maintenance build for the official companion app scaffold.

Included:

- upgraded the companion app to Capacitor 8 and Vite 8 patched tooling
- removed the vulnerable dev-only `@capacitor/assets` helper and its stale asset generation script
- regenerated the companion app npm lockfile with patched transitive packages
- verified the companion app with a clean `npm audit` and production build
- updated companion app build docs so they no longer reference the removed asset generation command

Release channel:

- `version-4.0.2` is this experimental dependency security cleanup
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.1 Experimental

Date: 2026-07-11

Update scope: Fluid dashboard shell and dedicated removal reasons page

Version 4.0.1 is an experimental responsive layout and moderation navigation patch.

Included:

- converted the shared dashboard shell sizing from fixed layout pixels to fluid clamp/rem/percentage-based CSS variables
- made sidebar width, content width, collapsed gutter, layout gaps, panel padding, and grid minimums scale across viewport sizes
- added shared overflow guards for dashboard tables, forms, inputs, selects, textareas, and buttons
- added a dedicated `/admin/removal-reasons` page for preset removal reasons
- updated the sidebar and Staff Home "Removal Reasons" links so they no longer hard-link to Review Queue
- added the removal reasons route to the all-page dashboard sweep

Release channel:

- `version-4.0.1` is this experimental responsive layout and moderation navigation patch
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
# SDAC Bot Version 4.0.0 Full Release

Date: 2026-07-11

Update scope: Full backend, dashboard, bot, installer, and release-readiness promotion

Version 4.0.0 is a full SDAC release that promotes the current 3.1.x experimental backend polish into a stable full-release line.

Included:

- consolidated the backend simplification work for moderators, server owners, and bot owners
- retained scoped multi-server dashboard access so users only see servers they belong to while supporting different roles per server
- includes the polished shared sidebar, centered dashboard layout, visible Invite Bot action, and hardened server selector
- includes logged-in dashboard voting for posted submissions with vote/unvote support
- includes the updated guessing-game scoring rule where points are only blocked after all generated hints are revealed
- includes release banner/version synchronization fixes for latest experimental and official channels
- keeps experimental anime slash commands opt-in with `SDAC_ENABLE_ANIME_COMMANDS` so the default bot command list stays focused
- includes release-readiness tooling, page sweep coverage, bot startup coverage, public invite coverage, and server mirror validation

Validation completed before publishing:

- full local unit test discovery passed
- core Python compile check passed
- backend release-readiness gate passed
- pre-release smoke test passed
- PostgreSQL export helper help check passed
- Git whitespace check passed

Release channel:

- `version-4.0.0` is this full release
- `latest-official` points to this build after publishing
- `latest-experimental` remains available for future experimental builds

---
# SDAC Bot Version 3.1.25 Experimental

Date: 2026-07-11

Update scope: Dashboard voting and hint scoring adjustment

Version 3.1.25 is an experimental user interaction and guessing-game scoring patch.

Included:

- added logged-in dashboard voting for posted submissions
- made dashboard voting toggleable so users can remove their own vote
- scoped dashboard votes to servers the logged-in account can access
- disabled public gallery caching for logged-in users so vote buttons and vote state render correctly
- changed guessing-game scoring so hints only block points after all generated hints have been revealed
- updated hint messaging to explain that points remain available until generated hints are exhausted
- added regression coverage for dashboard vote/unvote and the revised hint scoring rule

Release channel:

- `version-3.1.25` is this experimental dashboard voting and hint scoring patch
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.24 Experimental

Date: 2026-07-10

Update scope: Invite action, centered dashboard content, and command cleanup

Version 3.1.24 is an experimental dashboard polish and bot command cleanup update.

Included:

- added a visible Invite Bot action to the shared sidebar footer so bot installation is easy to find
- restored centered dashboard content within the available page area beside the sidebar
- kept the sidebar server selector containment from 3.1.23 intact
- moved experimental anime slash commands behind `SDAC_ENABLE_ANIME_COMMANDS` so they do not register by default
- removed the experimental anime section from the default `/commands` help menu
- added regression coverage for the Invite Bot action, centered layout CSS, and default command registry cleanup

Release channel:

- `version-3.1.24` is this experimental dashboard polish and command cleanup patch
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.23 Experimental

Date: 2026-07-10

Update scope: Sidebar server selector containment

Version 3.1.23 is an experimental dashboard layout patch.

Included:

- hardened the shared sidebar server selector so it stays inside the sidebar on every admin page
- isolated the sidebar switcher as a one-column grid so page-level form styles cannot stretch it
- added width, inline-size, and overflow guards for long server names inside the selector
- added regression checks to the admin page sweep for the hardened selector CSS

Release channel:

- `version-3.1.23` is this experimental server selector layout patch
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.22 Experimental

Date: 2026-07-10

Update scope: Staff Home collapsed-sidebar layout repair

Version 3.1.22 is an experimental dashboard layout patch.

Included:

- fixed Staff Home collapsed-sidebar layout so page content no longer starts underneath the fixed Menu button
- added a compact desktop collapsed-sidebar gutter for safe page alignment
- kept mobile collapsed-sidebar behavior full-width with no left padding
- added regression coverage for the collapsed-sidebar gutter CSS on rendered admin pages

Release channel:

- `version-3.1.22` is this experimental Staff Home layout patch
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.21 Experimental

Date: 2026-07-10

Update scope: Public bot invite and launch-readiness pages

Version 3.1.21 is an experimental public-availability preparation update.

Included:

- added a public `/invite` page with Discord install link, required scopes, recommended permissions, and after-install setup steps
- expanded bot invite URL generation with configurable client ID, permissions, scopes, public URL, support URL, privacy URL, terms URL, GitHub URL, bot name, and tagline
- added public `/privacy` and `/terms` placeholder pages that can redirect to final hosted policies with `SDAC_PRIVACY_URL` and `SDAC_TERMS_URL`
- added invite, setup guide, privacy, terms, support, and GitHub metadata to the app bootstrap API
- linked the invite page from public navigation and sidebar
- added public-release environment placeholders to installer templates
- added tests for invite URL generation, public invite rendering, public page sweep, and app bootstrap metadata
- included the public invite test suite in the backend release-readiness gate

Release channel:

- `version-3.1.21` is this experimental public bot launch-readiness update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.20 Experimental

Date: 2026-07-10

Update scope: Backend release-readiness polish

Version 3.1.20 is an experimental preparation update for an upcoming full release.

Included:

- added `scripts/release_readiness.py`, a backend release gate for core Python compile checks, server mirror drift, dashboard helper packaging, release metadata, support tools, and focused backend/dashboard tests
- wired backend readiness into the GitHub release workflow before release smoke tests
- wired backend readiness into the manual experimental release helper
- added backend readiness to the release checklist so full-release preparation has one repeatable command path
- included backend readiness output in support bundles alongside `sdac-doctor`
- packaged the readiness checker with the Linux installer and server mirror
- added regression tests to make sure the readiness checker runs and ships with release tooling

Release channel:

- `version-3.1.20` is this experimental backend release-readiness polish update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.19 Experimental

Date: 2026-07-10

Update scope: Sidebar, menu button, and server selector repair

Version 3.1.19 is an experimental dashboard layout fix update.

Included:

- fixed body class injection so sidebar layout classes are merged instead of creating duplicate `class` attributes
- moved the Menu button into the sidebar gutter so it no longer sits over page titles
- added top sidebar spacing so the Menu button does not cover the SDAC Admin brand area
- stopped the sidebar from reusing stale collapsed browser state on page load
- fixed the sidebar server selector so it submits back to the current page instead of always opening the public gallery
- preserved existing query values such as notices while changing server scope
- added regression tests for sidebar layout classes, Menu button rendering, and server selector form behavior

Release channel:

- `version-3.1.19` is this experimental sidebar and server selector fix
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.18 Experimental

Date: 2026-07-10

Update scope: Dashboard page fixes and release banner repair

Version 3.1.18 is an experimental dashboard fix update.

Included:

- fixed the Release Banner so it reads the version fields that `release_status()` actually provides
- resolved floating GitHub release names like `Latest Experimental (3.1.18)` into display versions instead of showing `latest-experimental`
- added local release-note fallback for installed version detection when the environment does not set `SDAC_RELEASE`
- updated `sdac-update` to write the resolved `SDAC_RELEASE` value for future dashboard status checks
- fixed broken sidebar links for Audit and Media pages
- stopped stale browser sidebar-collapse state from hiding the desktop sidebar across pages
- added regression tests for release banner status and sidebar route targets

Release channel:

- `version-3.1.18` is this experimental dashboard page and banner fix
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.17 Experimental

Date: 2026-07-10

Update scope: Dashboard helper extraction and packaging diagnostics

Version 3.1.17 is an experimental cleanup and safety update for the progressive backend rebuild.

Included:

- moved shared dashboard role constants and role normalization into `dashboard_admin_roles.py`
- moved login/register dashboard templates into `dashboard_account_templates.py`
- added packaging coverage so dashboard helper imports must be included in release, install, and update assets
- expanded `sdac-doctor` with dashboard helper file, import, service, and local `/health` diagnostics
- updated release, install, update, and manual experimental-release packaging for the new helper modules
- kept existing dashboard route behavior unchanged while reducing `dashboard.py`

Release channel:

- `version-3.1.17` is this experimental dashboard helper and diagnostics update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.16 Experimental

Date: 2026-07-10

Update scope: Dashboard sidebar extraction

Version 3.1.16 is an experimental refactor slice for the progressive backend cleanup.

Included:

- moved reusable dashboard sidebar definitions and rendering into `dashboard_sidebar.py`
- kept compatibility wrappers in `dashboard.py` so existing routes and templates keep the same function names
- mirrored the sidebar helper module into the server deployment copy
- updated release, install, and update packaging so dashboard helper modules deploy with `dashboard.py`
- kept the admin/public sidebar behavior unchanged while reducing the main dashboard file size
- fixed the likely cause of post-update local dashboard health failures after dashboard helper extraction
- verified the dashboard page sweep, access tests, and pre-release smoke checks locally with `.venv-win`

Release channel:

- `version-3.1.16` is this experimental dashboard sidebar extraction update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.15 Experimental

Date: 2026-07-10

Update scope: Dashboard shell asset extraction

Version 3.1.15 is an experimental refactor slice for the progressive backend cleanup.

Included:

- moved static PWA and sidebar shell assets out of `dashboard.py`
- added `dashboard_shell_assets.py` as the shared source for injected dashboard shell HTML/CSS/JS
- kept route/auth/sidebar behavior unchanged while reducing the main dashboard file size
- mirrored the extracted shell asset module into the server deployment copy
- verified the dashboard page sweep, access tests, and pre-release smoke checks locally with `.venv-win`

Release channel:

- `version-3.1.15` is this experimental dashboard shell extraction update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.14 Experimental

Date: 2026-07-10

Update scope: Refactor guardrail foundation

Version 3.1.14 is an experimental cleanup-foundation update for the progressive backend rebuild.

Included:

- added a reusable dashboard page sweep test for admin and public routes
- verifies shared sidebar injection on dashboard pages that should use it
- treats `/admin/health` as the JSON health API instead of a sidebar page
- uses temporary database, config, media, backup, and status paths so local verification does not mutate live config
- confirmed the new sweep, dashboard access tests, and pre-release smoke checks pass locally with `.venv-win`

Release channel:

- `version-3.1.14` is this experimental refactor guardrail update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.13 Experimental

Date: 2026-07-09

Update scope: Staff Home link verification

Version 3.1.13 is an experimental dashboard verification fix after enabling the local Windows test environment.

Included:

- fixed the Moderator Home audit action so it opens the real audit page
- fixed the Server Owner Home media action so it opens the media cleanup page
- verified the admin dashboard page sweep locally with the Windows virtual environment
- ignored the local `.venv-win/` folder so the Windows test environment stays out of releases
- mirrored the dashboard link fixes into the server deployment copy

Release channel:

- `version-3.1.13` is this experimental Staff Home link verification update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.12 Experimental

Date: 2026-07-09

Update scope: Sidebar layout stabilization

Version 3.1.12 is an experimental dashboard shell update for the admin sidebar.

Included:

- fixed the shared sidebar layout so admin pages start beside the sidebar instead of drifting across the page
- changed the sidebar into a stable full-height app panel
- limited scrolling to the sidebar navigation and footer areas instead of the entire sidebar jumping around
- kept the mobile sidebar drawer behavior separate from the desktop collapsed sidebar behavior
- removed sidebar heading letter spacing so labels stay readable in the narrow panel
- mirrored the sidebar fix into the server deployment copy

Release channel:

- `version-3.1.12` is this experimental sidebar layout fix update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.11 Experimental

Date: 2026-07-09

Update scope: Admin review and setup fixes

Version 3.1.11 is an experimental admin-side reliability and moderation workflow update.

Included:

- added more premade removal reasons for faster moderator actions
- fixed the Review Queue so it includes both pending and needs-review submissions
- kept quarantined submissions out of public viewing by keeping them in needs-review until a moderator posts them again
- fixed the Server Owner Setup Checklist 500 error
- fixed the Moderator Metrics 500 error
- made the Theme color changer show the selected swatches and current hex values clearly
- mirrored the dashboard fixes into the server deployment copy

Release channel:

- `version-3.1.11` is this experimental admin review and setup fix update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.10 Experimental

Date: 2026-07-09

Update scope: Dashboard polish and documentation

Version 3.1.10 is an experimental dashboard cleanup and video prep update.

Included:

- cleaned up dashboard removal controls so the reason dropdown is labeled and wide enough to read
- renamed the free-text removal field to `Audit note (optional)` so moderators know where the note is saved
- applied the same clearer removal controls to the moderation pending queue
- added `MASTER_VIDEO_SCRIPT.md` as a recording guide for explaining the bot, dashboard, app, admin roles, update policy, and where to find each feature
- mirrored the dashboard cleanup into the server deployment copy

Release channel:

- `version-3.1.10` is this experimental dashboard polish update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.9 Experimental

Date: 2026-07-09

Update scope: Release pipeline update

Version 3.1.9 is an experimental release alias title fix.

Included:

- kept moving alias release titles versioned so updater summaries can resolve `latest-experimental` to the current version
- preserved latest-section-only release notes from the prior release pipeline fix
- ensured future `latest-experimental` releases use titles like `Latest Experimental (3.1.9)` instead of only the alias name

Release channel:

- `version-3.1.9` is this experimental release pipeline update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.8 Experimental

Date: 2026-07-09

Update scope: Release pipeline update

Version 3.1.8 is an experimental release sync fix.

Included:

- fixed release workflow smoke tests so scoped dashboard access is tested with a bot-owner session
- changed GitHub release publishing to use only the newest RELEASE.md section instead of the entire release history
- made existing GitHub release objects update their title and notes when assets are refreshed
- republished latest-experimental through the normal release workflow so updater resolution and installer assets stay in sync

Release channel:

- `version-3.1.8` is this experimental release pipeline update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.7 Experimental

Date: 2026-07-09

Update scope: Bot update

Version 3.1.7 is an experimental per-server dashboard access update.

Included:

- changed dashboard admin role checks to use the user's effective role for the selected server
- limited admin/server-owner server dropdowns to servers where the user has the required role for that page
- allowed one account to have different roles on different servers through the existing per-server access table
- stopped blank dashboard-user server scope from granting access to every server for non-bot-owner users
- kept Bot Owner access global while keeping admins and server owners scoped to their assigned servers

Release channel:

- `version-3.1.7` is this experimental bot update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.6 Experimental

Date: 2026-07-09

Update scope: Bot update

Version 3.1.6 is an experimental admin simplification update.

Included:

- added focused admin pages for setup checklist, category management, permission health, global control, config history, and maintenance mode
- added bot-owner release banner cards to Staff Home so running, official, and experimental versions are visible in one place
- added preset removal reasons to moderation actions and dashboard removals so audit history is easier to scan
- expanded Staff Home and sidebar links so moderators, server owners, and bot owners can reach the simplified workflows directly
- mirrored the dashboard update into the server deployment copy

Release channel:

- `version-3.1.6` is this experimental bot update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.5 Experimental

Date: 2026-07-09

Update scope: Bot update

Version 3.1.5 is an experimental staff backend simplification update.

Included:

- added a role-aware `/admin` Staff Home that sends moderators, server owners, and bot owners to focused workbenches
- added moderator, server owner, and bot owner dashboard modes with role-specific status cards and quick actions
- moved the older admin metrics view to `/admin/overview`
- simplified the admin sidebar into User, Moderator, Server Owner, and Bot Owner sections so routine moderation is separated from server setup and global operations
- kept existing deep admin pages intact for compatibility while making the first backend screen easier to use

Release channel:

- `version-3.1.5` is this experimental bot update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 3.1.0 until this build is promoted

---
# SDAC Bot Version 3.1.4 Experimental

Date: 2026-07-07

Update scope: Bot update

Version 3.1.4 is an experimental server-owner layout preview update.

Included:

- expanded the Server Owner Layout visual test environment so the site layout parameters update the preview live
- added a miniature sidebar, Menu button, content area, filter panel, dashboard cards, and grid sample to the layout sandbox
- made Content Width, Sidebar Width, Card Radius, Panel Padding, Card Grid Minimum, Background Image Opacity, Menu Button Alignment, Background Position, and Density visibly affect the preview before saving
- kept the existing drag/drop dashboard item ordering and selected-item property editing inside the same test environment

Release channel:

- `version-3.1.4` is this experimental bot update
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.1.0 until this build is promoted

---

# SDAC Bot Version 3.1.3 Experimental

Date: 2026-07-07

Update scope: Bot update

Version 3.1.3 is an experimental sidebar menu positioning update.

Included:

- fixed the open sidebar Menu button position so Sidebar Edge places the button just outside the opened sidebar instead of inside the sidebar header area
- kept the collapsed sidebar Menu button on the left edge of the page
- kept the mobile/open button position clamped so it does not overflow narrow screens

Release channel:

- `version-3.1.3` is this experimental bot update
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.1.0 until this build is promoted

---

# SDAC Bot Version 3.1.2 Experimental

Date: 2026-07-07

Update scope: Bot update

Version 3.1.2 is an experimental dashboard sidebar and updater log polish update.

Included:

- fixed the sidebar Menu button so saved Page Left layouts no longer inherit the centered content offset
- changed the default Menu button alignment to Sidebar Edge so the button stays attached to the sidebar when open and returns to the left edge when collapsed
- reduced updater log noise by quieting repeated pip dependency output during server install/update runs
- replaced the full `systemctl status` dump at the end of updates with compact active/inactive service lines
- added an updater failure summary so failed updates end with `Update result: FAILED`, the requested update, the resolved tag, and the resolved version when available
- added installer success/version output so the release installer itself reports `Installer result: SUCCESS` and the packaged version number

Release channel:

- `version-3.1.2` is this experimental bot update
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.1.0 until this build is promoted

---

# SDAC Bot Version 3.1.1 Experimental

Date: 2026-07-07

Update scope: Bot update

Version 3.1.1 is an experimental updater and dashboard sidebar alignment update.

Included:

- added final updater success output that shows `Update result: SUCCESS`
- added `Requested update` to show what the user typed, such as `latest-experimental`
- added `Resolved release tag` and `Resolved version` so moving aliases still report the actual version number
- fixed the dashboard sidebar Menu button alignment so Page Left follows the content area instead of the old sidebar-width offset
- kept Sidebar Edge and Viewport Left as separate editable layout options

Release channel:

- `version-3.1.1` is this experimental bot update
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.1.0 until this build is promoted

---

# SDAC Bot and App Version 3.1.0 Official

Date: 2026-07-06

Update scope: Bot and App update

Version 3.1.0 is an official optimization, operations, and site customization release for the bot and dashboard.

Included:

- added the Admin Optimization dashboard for database, media, cache, watchdog, storage, table, and job visibility
- added Small Server, Medium Server, Large Server, Low Storage, and Low CPU performance presets
- added notification presets for quiet, critical-only, normal, and verbose routing
- added one-click queued optimization actions for thumbnails, media fingerprints, SQLite optimize, cache clearing, and a full optimization suite
- added scheduled bot-side thumbnail pre-generation controlled by dashboard limits
- added scheduled low-impact SQLite maintenance using WAL checkpoint and ANALYZE, while keeping full VACUUM as a queued admin action
- surfaced audit/submissions/guessing exports, storage forecasts, cleanup counts, and recent background jobs from the Optimization page
- fixed dashboard background job queue creation so queued jobs no longer touch undefined OAuth state
- kept per-server storage limits and warnings visible from the new optimization workflow
- added a Server Owner Layout page for content width, sidebar width, card radius, panel spacing, dashboard grid sizing, background image opacity, background position, and compact/comfortable/spacious density
- applied saved layout settings across all themed dashboard and public pages, matching the theme editor behavior
- fixed official release announcements for the moving `latest-official` channel by tracking release fingerprints instead of only the static alias tag
- added a Releases page test button so admins can verify `release_announcements` notification routing immediately

Release channel:

- `version-3.1.0` is this official bot and app build
- `latest-official` points to this build
- `Version 3`, `3`, `v3`, and `version-3` resolve to this official channel
- `latest-experimental` remains available for future test builds

---

# SDAC Bot and App Version 3.0.24 Experimental

Date: 2026-07-02

Version 3.0.24 is an experimental bot and app optimization update that reduces database, media, Discord API, and recurring background load.

Included:

- enabled SQLite busy timeout, foreign keys, WAL mode, and NORMAL synchronous mode for local SQLite installs
- added more database indexes for server/status/date admin, moderation, quarantine, setup-test, submission-report, and submission queries
- moved the rate-limit event server/date index into the migration that owns the table
- added retention cleanup for old setup-test runs, restore-test runs, and closed submission reports
- added global slash-command cooldown buckets for lightweight list/profile/status commands to reduce repeated Discord command load
- enabled image compression by default for new installs while keeping the existing dashboard controls
- added dashboard TTL caching for Owner Portal, Server Health Cards, and media cleanup report data
- added a lazy `/thumbnail/...` route so dashboard galleries can generate/use thumbnails without forcing full original image loads first
- increased dashboard GitHub release and Discord OAuth/member-role cache lifetimes to avoid repeated network lookups during normal browsing
- added longer media and thumbnail cache headers for browser-side reuse

Release channel:

- `version-3.0.24` is this experimental bot and app optimization build
- `latest-experimental` points to this build
- `latest-official` remains on Version 3.0.2 until the Version 3.0.3-3.0.24 line is validated

---

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