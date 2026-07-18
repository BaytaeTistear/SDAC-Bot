# Sana-Chan Version 4.3.12 Experimental

Version 4.3.12 is an experimental Game Library queue recovery update.

Update scope: Background import worker startup and queued import recovery

Changes:
- fixes background jobs staying stuck in `queued` because status updates were missing the job id parameter
- lets Recent Imports restart queued Game Library archive imports after an update or worker crash
- adds regression coverage for marking queued jobs as running
- adds regression coverage for Recent Imports restarting queued Game Library import jobs

Notes:
- This is an experimental update. After updating, open the Game Library page again to let Recent Imports kick any still-queued import jobs forward.
# Sana-Chan Version 4.3.11 Experimental

Version 4.3.11 is an experimental Game Library import lock-resilience update.

Update scope: SQLite lock handling for CSV/media archive imports

Changes:
- saves Game Library archive import rows in short retried write transactions instead of one long transaction
- retries temporary SQLite `database is locked` errors for import rows, import audit logs, and background job status/progress updates
- updates import progress only after row write transactions close
- adds regression coverage for temporary SQLite lock retries

Notes:
- This is an experimental update. Failed jobs from earlier versions can be retried by re-uploading the CSV and archive after updating.
# Sana-Chan Version 4.3.10 Experimental

Version 4.3.10 is an experimental Game Library import reliability update.

Update scope: CSV/media archive background importer

Changes:
- fixes media archive imports failing with `guild_storage_limit` is not defined
- adds the missing guild media size helper used by storage-limit checks
- applies server-level and global guild storage limits during CSV/media archive imports
- adds regression coverage for importing a CSV row with matching media through the background importer path

Notes:
- This is an experimental update. Failed jobs from earlier versions can be retried by uploading the CSV and archive again after updating.
# Sana-Chan Version 4.3.9 Experimental

Version 4.3.9 is an experimental Game Library import visibility update.

Update scope: Bulk CSV/media archive import feedback

Changes:
- adds a Recent Imports panel to the Game Library page
- shows accepted CSV filename, media archive filename, archive size, extraction stage, indexed media count, rows seen, imported items, attached media, missing media, skipped rows, timestamps, and failures
- updates the media archive queue notice so admins know to watch Recent Imports after submitting a CSV plus archive
- adds regression coverage proving `.csv` and `.7z` import job progress appears on the Game Library page

Notes:
- This is an experimental update. CSV-only imports still finish immediately; archive-backed imports run as background jobs and update when the page is refreshed.
# Sana-Chan Version 4.3.8 Experimental

Version 4.3.8 is an experimental Game Library route stability update.

Update scope: Dashboard Game Library filter and action buttons

Changes:
- makes the Game Library filter, add, import, edit, status, and delete forms submit explicitly to the dashboard Game Library route
- keeps the admin key and selected server context attached to Game Library actions
- adds regression coverage for Game Library filter, status, edit, and delete requests staying on the dashboard route

Notes:
- This is an experimental update. If a Game Library button still shows ERR_CONNECTION_REFUSED after updating, restart the dashboard service and check the dashboard journal for the request that triggered it.
# Sana-Chan Version 4.3.7 Experimental

Version 4.3.7 is an experimental release packaging cleanup for the sidebar consistency update.

Update scope: Sidebar regression coverage and release tooling

Changes:
- includes the Moderator sidebar consistency regression test in the released commit
- updates release tooling so sidebar layout tests are staged with future releases

Notes:
- This is an experimental update. The user-facing sidebar fix was introduced in 4.3.6; this keeps the test and release tooling in sync.
# Sana-Chan Version 4.3.6 Experimental

Version 4.3.6 is an experimental sidebar consistency update.

Update scope: Dashboard sidebar role display

Changes:
- makes the admin sidebar use the logged-in user's maximum scoped role for menu visibility
- keeps page access checks per-server so users still only access servers/actions they are allowed to use
- fixes Moderator menu links disappearing on pages where the selected server role is lower
- adds a regression test for the full Moderator menu staying visible across selected-server contexts

Notes:
- This is an experimental update. If the browser still shows old sidebar content, hard-refresh once after updating.
# Sana-Chan Version 4.3.5 Experimental

Version 4.3.5 is an experimental public gallery media display fix.

Update scope: Public dashboard gallery and cached page recovery

Changes:
- prefers local `/media/` URLs for gallery display when originals exist on the server
- keeps external/public media URLs as secondary links instead of letting stale external links break previews
- falls image previews back from thumbnail to original media when a thumbnail fails
- adds a visible broken-image fallback style instead of a collapsed black strip
- bumps the service worker cache version so browsers refresh stale public dashboard markup
- updates the public no-results label from SDAC to Sana-Chan

Notes:
- This is an experimental update. After updating, hard-refresh the browser once if it still shows cached SDAC branding or broken image markup.
# Sana-Chan Version 4.3.4 Experimental

Version 4.3.4 is an experimental dashboard recovery and background import update.

Update scope: Dashboard loading and Game Library archive imports

Changes:
- fixes a dashboard syntax issue that could stop pages, login, and media routes from loading
- queues Game Library CSV imports with media archives as background jobs instead of extracting inside the web request
- adds import job progress snapshots for reading CSV, opening archives, indexing archive media, importing rows, and completion
- cleans up staged CSV/archive files after successful or failed import jobs

Notes:
- This is an experimental update. Use the Jobs page to watch archive import progress after submitting a CSV with media archive.
# Sana-Chan Version 4.3.3 Experimental

Version 4.3.3 is an experimental upload limit fix for dashboard submissions.

Update scope: Dashboard and nginx upload handling

Changes:
- raises the packaged nginx dashboard upload limit default from `100M` to `250M`
- adds a dashboard-side request cap controlled by `SDAC_DASHBOARD_MAX_CONTENT_MB` or `SDAC_DASHBOARD_MAX_CONTENT_BYTES`
- returns a clearer 413 message when an upload is too large
- updates release tooling so nginx installer/template changes are staged with future releases

Notes:
- This is an experimental update. After installing, rerun the nginx site installer or set `client_max_body_size 250M;` in the live nginx site and reload nginx.`r`n`r`n# Sana-Chan Version 4.3.2 Experimental

Version 4.3.2 is an experimental release packaging cleanup for the archive import update.

Update scope: Release tooling and archive import coverage

Changes:
- includes the ZIP/TAR archive import test coverage in the experimental release commit
- updates the experimental release helper so future test and official-helper changes are staged correctly
- removes unsupported GitHub release metadata from the official release verification helper

Notes:
- This is an experimental update. Use `sana-update latest-experimental` to pull it.
# Sana-Chan Version 4.3.1 Experimental

Version 4.3.1 is an experimental media archive import update.

Update scope: Guess Game Library bulk media imports

Changes:
- allows Game Library bulk media archives to use `.zip`, `.7z`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, and `.rar`
- keeps existing CSV `media_filename` matching behavior for nested paths and basenames
- adds safe archive member filtering so path traversal entries are ignored
- adds optional `py7zr` and `rarfile` dependencies for 7z/RAR support
- updates the dashboard upload picker to advertise the new archive formats
- adds coverage for TAR media archive imports alongside the existing ZIP import test
- updates release tooling so requirements changes are staged with future releases

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
- RAR imports may require an extraction backend on the server, such as `unar`, `unrar`, or `bsdtar`, in addition to the Python `rarfile` package.

# Sana-Chan Version 4.3.0 Official

Version 4.3.0 is an official release-readiness polish update for public launch preparation.

Update scope: Go-live confidence, dashboard polish, command auditing, app-store readiness, release notes safety, self-tests, and owner/admin guidance

Changes:
- adds a Bot Owner Go Live Control Room combining checklist readiness, notifications, release state, app-store readiness, operations counts, blockers, and manual launch steps
- adds a Release Notes Preview page so only the current release notes are reviewed before publishing
- adds Self Tests for Discord OAuth, bot heartbeat, upload path, vote/review flow, invite flow, release channel, and mobile layout checks
- adds a Bot Command Cleanup Audit page for confirming the simplified public command surface and /sana-first workflow
- adds an App Store Readiness page for package name, target SDK, Android version, version code, signed bundle, and Play listing status
- adds a Mobile Dashboard Pass checklist for sidebar, selectors, action buttons, media previews, tables, cards, and app login/update flows
- adds Guided Empty States guidance so empty tables/pages have clear user-facing next actions
- adds a Role Permission Simulator hub that links directly into Preview As for user/server access checks
- adds a First Install Success page for owner setup confirmation, invite status, server scores, next steps, and wiki access
- adds an Admin Activity Digest for recent submissions, reports, moderation, audit events, and queued jobs
- aligns the Android app shell/package/build metadata to version 4.3.0
- adds official release tooling that promotes the validated commit to both latest-experimental and latest-official when requested

Notes:
- This is an official update. `latest-official` and `latest-experimental` should both point to this validated build after release.

# Sana-Chan Version 4.2.50 Experimental

Version 4.2.50 is an experimental full polish pass for release readiness and daily operations.

Update scope: Dashboard hubs, setup workflow, moderator workflow, safe mode, public pages, app updates, and support reporting

Changes:
- adds a Bot Owner Release Center that combines release status, launch checks, safe mode, install/UI tools, and support reporting links
- adds Dashboard Safe Mode so Bot Owners can temporarily force default theme/layout if custom UI settings break pages
- adds a first-run Setup Wizard for server owners with direct fix buttons for invite, command name, channels, categories, moderation defaults, setup test, and finish
- adds a Moderator Workspace focused on needs-review items, reports, quarantine, recent removals, reason presets, audit log, and Game Library access
- adds a Report A Problem page that generates a support-ready page/server/role/release/browser bundle without secrets
- polishes public About and Setup Guide language around Sana-Chan, /sana, and the guided setup path
- adds a dedicated in-app Updates panel with current version, recommended channel, APK links, checksums, release notes, and report-problem links
- exposes Release Center, Setup Wizard, Moderator Workspace, and Report A Problem in dashboard navigation and app bootstrap routes
- fixes the Go Live checklist limits lookup so Release Center and Go Live pages render reliably

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.49 Experimental

Version 4.2.49 is an experimental dashboard and app polish pass.

Update scope: Dashboard polish, app diagnostics, release checks, and navigation

Changes:
- moves Game Library from Server Owner to Moderator access and sidebar navigation
- adds a Bot Owner UI Preview page with shared controls, badges, bubbles, moderation cards, tables, and empty states for visual QA
- expands UI Health with automated layout check guidance and a direct UI Preview link
- adds a Playwright-backed dashboard layout checker for desktop, tablet, and mobile overflow screenshots
- improves the Invite Bot page with OAuth, permission, setup, and public-doc readiness cards
- expands app diagnostics with backend reachability, cookie name, Discord login URL, invite URL, and release-change status
- adds mobile moderation/card CSS so media previews and action buttons wrap more reliably on small screens
- updates release tooling so the new layout checker and app diagnostics source are staged with future experimental releases

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.48 Experimental

Version 4.2.48 is an experimental dashboard metric bubble layout fix.

Update scope: Dashboard shared theme and server health cards

Changes:
- gives Server Health metric bubbles dedicated layout classes so they are not treated like tiny inline status badges
- stacks each bubble label, value, and detail safely so storage forecasts, counts, and long server details do not overlap
- adds shared bubble/grid safety rules for future metric-pill and bubble-card dashboard elements
- keeps normal badges, tags, and submission status pills compact while preventing their icon dot from shrinking

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.# Sana-Chan Version 4.2.47 Experimental

Version 4.2.47 is an experimental embedded Layout workbench correction.

Update scope: Dashboard theme/layout workbench

Changes:
- changes the Theme page workbench iframe to use an embedded Layout view without injecting the full admin sidebar
- moves Page Layout controls into the workbench right-side panel so the selected item editor stays visible
- adds editable Menu and Home button items to the workbench item list
- keeps Menu/Home out of the dashboard card grid while allowing their text, font, style, visibility, and lock state to be edited
- fixes item move controls so only movable dashboard cards can be reordered

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.46 Experimental

Version 4.2.46 is an experimental Layout workbench usability update.

Update scope: Dashboard theme and layout editor

Changes:
- adds a right-side Editable Items panel to the Layout workbench so owners can select dashboard objects directly
- adds non-drag Move Up and Move Down controls for environments where iframe drag-and-drop is awkward
- adds editable text label, main text/number, font size, object size, color style, visibility, and lock/unlock controls
- saves the new font size and locked state safely with layout item properties

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.45 Experimental

Version 4.2.45 is an experimental release helper staging fix.

Update scope: Release validation and release tooling

Changes:
- commits the Sana-Chan web manifest smoke-test expectation into both root and server copies
- updates the experimental release helper so future smoke-test changes are staged automatically
- keeps the Theme page embedded layout workbench from 4.2.43 and the validation alignment from 4.2.44 intact

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.44 Experimental

Version 4.2.44 is an experimental release smoke-test alignment update.

Update scope: Release validation

Changes:
- updates the pre-release smoke test to expect the Sana-Chan web manifest short name
- keeps the 4.2.43 Theme page workbench changes intact
- verifies the release process against the current Sana-Chan branding instead of the legacy SDAC label

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.43 Experimental

Version 4.2.43 is an experimental Theme page workbench update.

Update scope: Dashboard theme and layout management

Changes:
- renames the Theme page preview area to Live Theme Preview for clearer owner workflow
- embeds the full Layout editor inside the Theme page so owners can adjust object position, card sizing, sidebar width, spacing, background placement, and density from the same page
- keeps the existing standalone Layout page available for direct access

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.42 Experimental

Version 4.2.42 is an experimental dashboard dropdown readability fix.

Update scope: Shared dashboard form styling

Changes:
- forces themed dashboard dropdown menus to use a dark option background with white text
- improves selected, hovered, focused, and disabled dropdown option contrast
- keeps existing server selector layout and sidebar behavior unchanged

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# Sana-Chan Version 4.2.41 Experimental

Version 4.2.41 is an experimental Sana-Chan naming, app-auth, and readiness polish update.

Update scope: Sana naming, self-contained app shell, and public URL cleanup

Changes:
- restores dashboard, app, and docs defaults from `thelab.us.to` to `freethefishies.us.to`
- moves the visible Discord control command from `/sdac` to `/sana` and renames visible pause/reset commands to `/sanapause` and `/sanareset`
- removes the Android Capacitor direct-dashboard wrapper fallback so native builds use the packaged Sana-Chan shell
- updates Android app login to prefer browser/Discord authentication and the `sanachan://login-complete` callback
- renames app-facing assets, CSS variables, and preferred app build settings to Sana names while keeping old settings as compatibility fallbacks where needed
- adds a Bot Owner UI Health page for sidebar, server selector, login, release, invite, and layout readiness checks
- adds a native-app bottom navigation bar and updates the app shell to version 4.2.41
- adds `sana-doctor` as the preferred server doctor command while keeping `sdac-doctor` as a compatibility alias

Notes:
- Internal compatibility names such as existing `SDAC_*` environment variables, service names, database names, and installed paths remain supported so existing servers do not break during the rename.
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.40 Experimental

Version 4.2.40 is an experimental Sana-Chan dashboard formatting fix.

Update scope: Dashboard attention card formatting

Changes:
- fixes the What Needs Attention cards so values, labels, and detail text stack cleanly instead of overlapping
- adds shared grid card sizing and wrapping rules for dashboard stat cards
- keeps the existing dashboard theme and page behavior unchanged

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.39 Experimental

Version 4.2.39 is an experimental Sana-Chan dashboard and app polish update.

Update scope: Shared dashboard and Android app UX polish

Changes:
- adds shared dashboard polish for sidebar icon cues, empty states, status badges, table rows, action rows, focus states, and section headings
- improves responsive table and action layouts so admin and moderation pages behave better on mobile
- updates the Android app shell with the darker Sana-Chan glass theme, gradient heading treatment, and polished loading/error panels
- keeps existing page routes, forms, server selector, and sidebar behavior unchanged while improving the shared presentation layer

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.38 Experimental

Version 4.2.38 is an experimental Sana-Chan sidebar layout stabilization update.

Update scope: Dashboard sidebar consistency

Changes:
- forces sidebar role sections to render full-width instead of shrinking to their label contents
- normalizes closed and open sidebar section sizing across dashboard pages
- improves sidebar summary, link, and footer width rules so the menu stays aligned after theme changes
- keeps the existing collapsible sidebar behavior and server selector behavior unchanged

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.37 Experimental

Version 4.2.37 is an experimental Sana-Chan dashboard typography polish update.

Update scope: Dashboard numeric display styling

Changes:
- updates large dashboard counters and metric values to use a heavier rounded display font stack
- adds tabular lining numerals so stat cards, release cards, and metric cards align more like the Sana-Chan banner mockup
- adds subtle glow and shadow treatment to numeric displays while preserving existing page layouts

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.36 Experimental

Version 4.2.36 is an experimental Sana-Chan dashboard theme polish update.

Update scope: Banner-matched visual styling

Changes:
- deepens the dashboard background toward the Sana-Chan banner's near-black navy base
- adds subtle dotted and angled glow texture behind dashboard pages
- strengthens glass-panel cards with blur, brighter cyan/violet edge lighting, and deeper shadows
- updates sidebar sections, active links, invite button, headings, forms, badges, and buttons to better match the banner palette
- updates the PWA theme color to the darker Sana-Chan base color

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.35 Experimental

Version 4.2.35 is an experimental public artifact naming cleanup for Sana-Chan releases.

Update scope: Release asset names

Changes:
- renames public Linux, Ubuntu updater, Windows installer, and Windows updater downloads to `Sana-Chan-*`
- keeps `sana-update` as the main Ubuntu update command and `sanachan-update` as an alias
- updates release workflow artifact names, smoke tests, Windows updater defaults, docs, and helper tooling to use Sana-Chan names
- deletes stale `SDAC-Bot-*` and `sdac-update` assets when updating an existing GitHub release

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.34 Experimental

Version 4.2.34 is an experimental Sana-Chan updater naming cleanup.

Update scope: Ubuntu update command naming

Changes:
- replaces the public `sdac-update` command with `sana-update`
- ships `sanachan-update` as a second readable alias for the same updater
- renames the standalone Ubuntu updater artifact to `Sana-Chan-Ubuntu-Update.sh`
- updates installer output, release workflow checks, doctor detection, helper release tooling, and docs to use the Sana-Chan updater names
- removes the stale `/usr/local/bin/sdac-update` command during updater install so old servers stop showing the old command

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.33 Experimental

Version 4.2.33 is an experimental dashboard visual polish update for the Sana-Chan site.

Update scope: Banner-inspired dashboard styling

Changes:
- restyles the shared dashboard shell with the new Sana-Chan dark navy, cyan, and violet visual direction
- adds richer panel surfaces, subtle glow accents, app-like controls, and clearer form/button focus states
- updates the PWA theme color to match the darker Sana-Chan site style
- keeps the existing sidebar and dashboard behavior unchanged while refreshing the global look

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.32 Experimental

Version 4.2.32 is an experimental domain and store-listing update for the Sana-Chan dashboard and app.

Update scope: Public dashboard URL and Google Play copy

Changes:
- updates source documentation and app defaults for the hosted dashboard URL
- updates hosted dashboard examples, production checks, certbot examples, and app setup docs
- adds reusable Google Play short and full descriptions for Sana-Chan
- keeps `latest-official` unchanged while moving the experimental channel forward

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.31 Experimental

Version 4.2.31 is an experimental guess-library bulk media import update.

Update scope: CSV + ZIP guess imports and Discord anime challenge media

Changes:
- adds optional `media_filename` support to guess-game bulk import CSVs
- lets admins upload a matching media ZIP with the CSV so rows can attach image, video, or audio files during import
- explains the CSV + ZIP workflow directly on the Game Library dashboard page
- updates the example bulk import CSV files to include `media_filename`
- lets `/animechallenge` accept optional Discord media and save it to the selected anime guess mode
- stores normalized answer aliases for Discord-created anime challenges
- adds a test for ZIP media extraction into the Game Library media folder

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.30 Experimental

Version 4.2.30 is an experimental Google Play review account update.

Update scope: Permanent low-access app review login

Changes:
- seeds a permanent low-access `Default` dashboard account for Google Play review
- keeps the review account at the `Not Added` role with no server scope or admin access
- adds a migration test to confirm the review account stays low-access and login-capable

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.

# SDAC Bot Version 4.2.29 Experimental

Version 4.2.29 is an experimental dashboard account helper update for local testing.

Update scope: Dashboard account CLI role support

Changes:
- allows the server-shell dashboard account helper to create or update accounts with the `Not Added` role
- keeps local test-account setup aligned with the dashboard role model added in 4.2.28

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.28 Experimental

Version 4.2.28 is an experimental dashboard access-control update for server-scoped account management.

Update scope: User access, per-server roles, and authentication codes

Changes:
- adds a `Not Added` dashboard role for accounts that have not authenticated or been assigned to a server
- shows each dashboard account's server access on the Users page
- replaces the wide per-server matrix with per-user server dropdowns that only list servers already linked to that user
- adds controls to add a dashboard user to an accessible server
- adds one-time account authentication codes that users can redeem from their account page
- adds database support and tests for account authentication codes

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.27 Experimental

Version 4.2.27 is an experimental Google Play compatibility update for the Sana-Chan Android bundle.

Update scope: Android target API and Play Console notes

Changes:
- raises the Android target API level from 34 to 35 while continuing to compile with SDK 36
- bumps the Sana-Chan app shell/versionCode to 4.2.27 / 42027
- documents that no deobfuscation file is required while Android release minification remains disabled

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.26 Experimental

Version 4.2.26 is an experimental Android signing update for the Sana-Chan Play Store bundle.

Update scope: Signed Android release bundle

Changes:
- adds ignored Android `keystore.properties` support for release signing
- configures the Sana-Chan release build to sign bundles when the private keystore file is present
- bumps the Sana-Chan app shell/versionCode to 4.2.26 / 42026
- updates the Play Store checklist with the signed AAB status and checksum

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.25 Experimental

Version 4.2.25 is an experimental documentation update for preparing Sana-Chan for Google Play upload.

Update scope: Play Store upload checklist

Changes:
- adds `PLAY_STORE_UPLOAD_CHECKLIST.md` with the generated release bundle path, checksum, app identity, signing requirements, Play Console listing items, policy forms, and testing requirements
- documents that the current generated `app-release.aab` is unsigned and must be rebuilt after upload-keystore signing is configured

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.24 Experimental

Version 4.2.24 is an experimental release packaging fix for the Sana-Chan rename.

Update scope: App source release artifact

Changes:
- fixes the installer build script so it creates `Sana-Chan-App-Source.zip`
- keeps the release workflow and dashboard release metadata aligned with the renamed Sana-Chan APK/source assets

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.23 Experimental

Version 4.2.23 is an experimental branding and app package rename for the project transition to Sana-Chan.

Update scope: Bot, Dashboard, and App rename

Changes:
- renames the visible bot, dashboard, PWA, and Android app branding from SDAC to Sana-Chan
- changes the Android package/application ID to `com.baytae.sanachan`
- updates the Android app display name, deep-link scheme, package namespace, and app shell version to 4.2.23
- renames the release workflow app artifacts to `Sana-Chan-Android-Debug.apk` and `Sana-Chan-App-Source.zip`
- keeps legacy `SDAC_*` environment variables, `/sdac`, and updater/service command names for compatibility with existing installs

Notes:
- This is an experimental update. `latest-experimental` should point here after release, while `latest-official` stays unchanged unless promoted later.
# SDAC Bot Version 4.2.22 Experimental

Release date: 2026-07-14

Update scope: Collapsible dashboard sidebar sections

Version 4.2.22 is an experimental dashboard polish update that makes the sidebar role sections collapsible.

Included in this update:
- changes User, Moderator, Server Owner, and Bot Owner sidebar groups into collapsible sections
- keeps the active role section open by default so the current page remains visible
- preserves the unified sidebar scroll area, Menu/Home controls, server selector, Invite Bot action, and account links
- adds regression coverage for collapsible role navigation sections
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.22` is this experimental collapsible sidebar build.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.21 Experimental

Release date: 2026-07-14

Update scope: Go-live readiness checklist

Version 4.2.21 is an experimental go-live hardening update for final bot, dashboard, server, and app readiness checks before public launch.

Included in this update:
- adds a Bot Owner Go Live Checklist page that combines release channel, OAuth, invite, backups, restore tooling, cooldowns, production health, install doctor, slash-command sync, and Android updater checks
- adds a JSON go-live checklist API for automation or future dashboard widgets
- links Go Live Checklist from the Bot Owner sidebar
- adds the page to dashboard sweep coverage so it cannot silently break before launch
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.21` is this experimental go-live readiness build.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.20 Experimental

Release date: 2026-07-14

Update scope: Guided Android app updater

Version 4.2.20 is an experimental app update that adds a guided APK updater for installs outside the Play Store.

Included in this update:
- exposes Android APK release asset URLs and SHA256 digests through the app bootstrap API
- adds an in-app update panel with official and experimental channel cards
- opens APK, checksum, and release links from the app using the native external browser handoff
- shows install steps for Android sideload updates that require user confirmation
- bumps the Android app shell to 4.2.20 with matching Android version metadata
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.20` is this experimental guided app updater build.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.19 Experimental

Release date: 2026-07-13

Update scope: Dashboard sidebar role-section polish

Version 4.2.19 is an experimental dashboard polish update for the admin/sidebar layout.

Included in this update:
- groups dashboard navigation by User, Moderator, Server Owner, and Bot Owner sections
- moves Home next to Menu in the fixed sidebar controls
- combines user identity, server selection, navigation, invite, and account actions into one sidebar scroll area
- removes separate nested sidebar/footer scrolling so the sidebar behaves consistently across screen sizes
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.19` is this experimental dashboard sidebar polish update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.18 Experimental

Release date: 2026-07-13

Update scope: App sidebar Discord login guard

Version 4.2.18 is an experimental app fix for the dashboard sidebar Discord login link inside the Android app.

Included in this update:
- marks the dashboard iframe as an SDAC app view
- preserves that app-view marker through `/app` redirects
- replaces the sidebar Discord OAuth link in app view with guidance to use the native app login button
- keeps the main app Login with Discord button on the working native handoff flow
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.18` is this experimental app sidebar login fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.17 Experimental

Release date: 2026-07-13

Update scope: Android app Discord login handoff

Version 4.2.17 is an experimental app login fix for Android browser cookie isolation and Forbidden pages after Discord OAuth.

Included in this update:
- adds an app-specific Discord login completion page that returns to the Android app through `sdaccompanion://login-complete`
- adds a signed short-lived app login ticket claim endpoint for the companion app
- updates the Android app to claim the ticket and refresh its own dashboard session
- registers the Android deep-link intent for the app login callback
- keeps `latest-official` unchanged until an official promotion is requested

Release channel:
- `version-4.2.17` is this experimental Android login handoff fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.16 Experimental

Release date: 2026-07-13

Update scope: External Discord login launch

Version 4.2.16 is an experimental app login fix for Discord blocking OAuth inside app-owned browser surfaces.

Included in this update:
- opens Discord OAuth with Android's normal external browser through Capacitor App Launcher
- keeps Capacitor Browser as a fallback if external launch fails
- keeps in-app/browser handling for non-Discord dashboard links
- updates app dependencies and Android sync for the launcher plugin
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.16` is this experimental external Discord login launch fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.

# SDAC Bot Version 4.2.15 Experimental

Release date: 2026-07-13

Update scope: Discord OAuth mobile login fix

Version 4.2.15 is an experimental dashboard/app login fix for Discord OAuth opening in mobile app browser flows.

Included in this update:
- removes `prompt=none` from normal Discord OAuth login starts so Discord can show the interactive login/authorize page on mobile
- keeps explicit silent OAuth available only when requested with `silent=1`
- adds regression tests for the generated Discord OAuth authorize URL
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.15` is this experimental Discord OAuth mobile login fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.14 Experimental

Release date: 2026-07-13

Update scope: Native app fetch fallback

Version 4.2.14 is an experimental app connectivity fix for Android WebView fetch failures in the packaged SDACCompanion shell.

Included in this update:
- enables Capacitor's native HTTP bridge for the app shell
- retries `/api/app/bootstrap` through native HTTP when WebView `fetch` fails
- keeps the normal browser fetch path first so dashboard cookies still work when available
- improves the app error screen with dashboard URL, platform details, Retry, and Open Dashboard actions
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.14` is this experimental native app fetch fallback.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.13 Experimental

Release date: 2026-07-13

Update scope: App backend connection fix

Version 4.2.13 is an experimental app connectivity fix for the packaged SDACCompanion shell.

Included in this update:
- allows the standard Capacitor app origin `capacitor://localhost` to call `/api/app/bootstrap` by default
- keeps unknown browser origins blocked unless they are explicitly listed in `SDAC_APP_ALLOWED_ORIGINS`
- adds regression tests for app bootstrap CORS headers
- updates app docs to clarify that the installed app origin is trusted by default
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.13` is this experimental app backend connection fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.12 Experimental

Release date: 2026-07-13

Update scope: Native app login and release readiness polish

Version 4.2.12 is an experimental app/dashboard polish update focused on making the installed app easier to recover, easier to diagnose, and safer to prepare for a full release.

Included in this update:
- adds native in-app browser handling for Discord login from the SDACCompanion shell
- adds Reset App Login and App Diagnostics panels for app session recovery and troubleshooting
- adds a real app update notice using latest experimental and latest official release data
- changes native builds to use the packaged app shell by default, with optional direct-dashboard mode via SDAC_APP_DIRECT_URL
- adds a bot-owner/admin Release Checklist page for release readiness checks
- expands the Invite Bot page into a guided setup flow with OAuth details, permissions, and next-step links
- adds dashboard page-sweep coverage for the release checklist and horizontal overflow layout guards
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.12` is this experimental native app login and readiness polish update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.11 Experimental

Release date: 2026-07-13

Update scope: App sidebar scroll and Discord login state fix

Version 4.2.11 is an experimental app/dashboard stability update focused on stopping horizontal sidebar scrolling and making Discord login more reliable in the installed app flow.

Included in this update:
- clamps the dashboard app shell at the root `html` and `body` levels to prevent left-right page scrolling
- uses dynamic viewport widths for the off-canvas sidebar so it cannot create extra horizontal space in the app WebView
- adds a short-lived server-side Discord OAuth state fallback so app logins can survive external-browser/WebView session changes
- keeps the normal browser OAuth session check in place while allowing valid app callbacks to complete safely
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.11` is this experimental app sidebar scroll and Discord login state fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.10 Experimental

Release date: 2026-07-13

Update scope: App submission media layout fix

Version 4.2.10 is an experimental dashboard/app polish update focused on restoring the submission image layout and keeping action buttons compact in the app view.

Included in this update:
- makes submission cards use an explicit layout order: details, message, media, then actions
- keeps images and videos in the media area instead of visually falling below the action controls
- stops mobile/app submission action buttons from being forced to full-width one-per-line stacks
- keeps moderation controls wrapped side by side where space allows while preserving full-width inputs for removal reasons
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.10` is this experimental app submission media layout fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.9 Experimental

Release date: 2026-07-13

Update scope: Dashboard app sidebar overflow fix

Version 4.2.9 is an experimental dashboard polish update focused on keeping the app/sidebar navigation contained on narrow screens and long-link layouts.

Included in this update:
- keeps sidebar links, Home, and Invite Bot inside the sidebar width
- allows long sidebar labels to wrap instead of overflowing horizontally
- prevents footer account links from widening or spilling outside the sidebar
- keeps the sidebar footer scrollable when account/admin actions take more vertical space
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.9` is this experimental dashboard sidebar overflow fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.8 Experimental

Release date: 2026-07-13

Update scope: Android Kotlin dependency alignment

Version 4.2.8 is an experimental APK packaging fix focused on resolving duplicate Kotlin runtime classes during the SDACCompanion Android debug APK build.

Included in this update:
- aligns Android Kotlin stdlib dependency variants to Kotlin 1.8.22 across app and Capacitor modules
- fixes duplicate class failures between `kotlin-stdlib:1.8.22` and older `kotlin-stdlib-jdk7/jdk8:1.6.21` transitive dependencies
- keeps the Java 21 APK runner, Android SDK 36 install step, Android Gradle plugin 8.9.1, Gradle 8.11.1, and compile SDK 36
- keeps the release workflow building `SDACCompanion-Android-Debug.apk` and its SHA256 checksum
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.8` is this experimental Android Kotlin dependency alignment fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.7 Experimental

Release date: 2026-07-13

Update scope: Android Java toolchain fix

Version 4.2.7 is an experimental APK packaging fix focused on matching the GitHub release runner Java toolchain to the Capacitor 8 Android build requirements.

Included in this update:
- updates the APK build workflow from Java 17 to Java 21 so Capacitor Android can compile its Java 21 sources
- keeps the Android SDK 36 install step from the prior workflow fix
- keeps Android Gradle plugin 8.9.1, Gradle 8.11.1, and compile SDK 36
- keeps the release workflow building `SDACCompanion-Android-Debug.apk` and its SHA256 checksum
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.7` is this experimental Android Java toolchain fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.6 Experimental

Release date: 2026-07-13

Update scope: Android SDK install workflow fix

Version 4.2.6 is an experimental APK packaging fix focused on making the GitHub runner install the Android 36 SDK platform reliably before building the SDACCompanion APK.

Included in this update:
- updates the release workflow to call `sdkmanager` from the runner Android SDK path instead of assuming it is globally on PATH
- keeps Android Gradle plugin 8.9.1, Gradle 8.11.1, and compile SDK 36 from the prior APK compatibility update
- keeps the release workflow building `SDACCompanion-Android-Debug.apk` and its SHA256 checksum
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.6` is this experimental Android SDK install workflow fix.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.5 Experimental

Release date: 2026-07-13

Update scope: Android APK dependency compatibility

Version 4.2.5 is an experimental APK packaging fix focused on satisfying the AndroidX Browser requirements used by the SDACCompanion Capacitor app build.

Included in this update:
- updates the SDACCompanion Android Gradle plugin from 8.7.3 to 8.9.1
- updates the Android Gradle wrapper from Gradle 8.9 to Gradle 8.11.1
- updates the app compile SDK from 34 to 36 for `androidx.browser:browser:1.9.0`
- keeps target SDK at 34 so runtime behavior is not changed by this packaging fix
- keeps the release workflow building `SDACCompanion-Android-Debug.apk` and its SHA256 checksum
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.5` is this experimental Android APK dependency compatibility update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.4 Experimental

Release date: 2026-07-13

Update scope: Android APK build compatibility

Version 4.2.4 is an experimental APK packaging fix focused on making the SDACCompanion Android build complete on GitHub release runners.

Included in this update:
- updates the SDACCompanion Android Gradle plugin from 8.2.1 to 8.7.3
- updates the Android Gradle wrapper from Gradle 8.2.1 to Gradle 8.9
- keeps Capacitor Android Java compatibility pinned to Java 17
- keeps the release workflow building `SDACCompanion-Android-Debug.apk` and its SHA256 checksum
- keeps the app source zip and bot installer/update artifacts in the same release
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.4` is this experimental Android APK build compatibility update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.3 Experimental

Release date: 2026-07-13

Update scope: Android APK release artifact

Version 4.2.3 is an experimental app release packaging update focused on producing an installable SDACCompanion Android APK whenever release updates are published.

Included in this update:
- builds the SDACCompanion Capacitor web shell during the GitHub release workflow
- syncs the Android project before packaging
- publishes `SDACCompanion-Android-Debug.apk` as a release download for sideload testing
- publishes `SDACCompanion-Android-Debug.apk.sha256` so the APK can be verified after download
- keeps `SDACCompanion-App-Source.zip` and the normal bot installer/update artifacts in the same release
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.3` is this experimental Android APK release artifact update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.2 Experimental

Release date: 2026-07-13

Update scope: App release artifact and release note cleanup

Version 4.2.2 is an experimental release packaging fix focused on shipping the SDACCompanion app source with updates and keeping each GitHub release note body limited to only that update.

Included in this update:
- adds the SDACCompanion app source as a separate release download
- publishes `SDACCompanion-App-Source.zip` as a GitHub release artifact
- excludes generated app folders, local app env files, and Android signing files from the app source artifact
- fixes the release workflow so each release uses only the newest top release note section
- keeps `latest-official` on Version 4.2.0 until an official promotion is requested

Release channel:
- `version-4.2.2` is this experimental app packaging and release note cleanup update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.1 Experimental

Release date: 2026-07-13

Update scope: Remembered dashboard logins

Version 4.2.1 is an experimental login stability update focused on keeping Discord and admin dashboard sessions remembered across browser visits and dashboard restarts.

Included in this update:
- stores a stable local dashboard secret key when `SDAC_SECRET_KEY` is not configured
- keeps `SDAC_SECRET_KEY` support as the preferred production override
- marks successful admin password, account password, account registration, and Discord OAuth logins as persistent sessions
- sets dashboard session cookies to 30 days by default with HttpOnly and SameSite=Lax protections
- ignores the generated `.sdac_secret_key` file so local session secrets are not committed
- adds regression coverage for fallback secret reuse and persistent admin login cookies

Release channel:
- `version-4.2.1` is this experimental remembered-login update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.2.0 until it is promoted.
# SDAC Bot Version 4.2.0 Official

Release date: 2026-07-12

Update scope: Unified dashboard sidebar and saved layout coverage

Version 4.2.0 is an official dashboard polish release focused on making the sidebar consistent across the full dashboard and public page set.

Included in this update:
- changed the dashboard sidebar from multiple collapsible role sections into one continuous navigation section
- kept the Menu button fixed at the top of every sidebar-enabled page
- added a top Home button above the server selector
- preserved the Invite Bot and account actions in the sidebar footer
- kept saved Layout settings applied through the shared sidebar/theme injection path
- strengthened the page sweep to verify sidebar, Home button, single navigation section, server selector hardening, and saved layout variables across all rendered pages
- updated sidebar layout tests to block regressions to the old collapsible sidebar structure

Release channel:
- `version-4.2.0` is this official sidebar and layout consistency update.
- `latest-official` points to this build after publishing.
- `latest-experimental` already included the prior experimental identity setup work that is now part of this official build.
# SDAC Bot Version 4.1.4 Experimental

Release date: 2026-07-12

Update scope: Optional setup identity steps

Version 4.1.4 is an experimental setup polish update that makes bot name and bot image choices part of setup without making either one required.

Included in this update:
- shows Bot Name and Bot Image as optional recommended setup items in the Discord setup wizard
- keeps required setup readiness focused on channels, categories, and core permissions
- tracks selected bot name and global bot image as completed recommended items once configured
- adds Bot Name and Bot Image to the dashboard Setup Checklist as optional recommended items
- updates setup wording so owners know both identity choices are optional during setup
- adds test coverage that bot name and bot image setup rows remain optional

Release channel:
- `version-4.1.4` is this experimental optional setup identity update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.1.0 until it is promoted.
# SDAC Bot Version 4.1.3 Experimental

Release date: 2026-07-12

Update scope: Dashboard and Discord bot image controls

Version 4.1.3 is an experimental identity update that lets bot owners change the bot's global Discord image from either the dashboard or Discord.

Included in this update:
- added `/sdac` -> Setup -> Bot Image for bot owners
- added a Bot Image button to the setup wizard's final page
- added dashboard Settings controls for global bot image upload or HTTPS image URL
- validates PNG, JPEG, GIF, and WebP bot images up to 8 MB
- stores bot image update metadata in config and audit logs
- keeps per-server bot nicknames separate from the global bot image
- added validation coverage for bot image URL and image payload handling
- updated admin docs for the new bot image flows

Release channel:
- `version-4.1.3` is this experimental bot image control update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.1.0 until it is promoted.
# SDAC Bot Version 4.1.2 Experimental

Release date: 2026-07-12

Update scope: Discord bot nickname setup

Version 4.1.2 is an experimental Discord setup update that lets admins change the bot's server nickname directly from Discord.

Included in this update:
- added `/sdac` -> Setup -> Bot Name for server admins
- added a Bot Name button to the setup wizard's final page
- applies the nickname immediately in Discord and stores it in each server's config
- supports leaving the name blank to reset the bot back to its global username
- validates Discord nickname limits and gives clear permission errors when Manage Nicknames or role order blocks the change
- added startup test coverage for bot nickname validation
- updated admin docs for the new Discord nickname flow

Release channel:
- `version-4.1.2` is this experimental bot nickname setup update.
- `latest-experimental` points to this build after publishing.
- `latest-official` remains Version 4.1.0 until it is promoted.
# SDAC Bot Version 4.1.1 Experimental

Date: 2026-07-12

Update scope: Dashboard moderation button layout fix

Version 4.1.1 is an experimental dashboard polish update that fixes clipped moderation controls on submission cards.

Included:

- changed submission card headers to wrap controls instead of forcing every action into one row
- made vote, remove, review, and quarantine actions keep stable button sizes without clipping
- made the removal reason form resize cleanly at desktop, tablet, and mobile widths
- mirrored the dashboard layout fix into the server package copy

Release channel:

- `version-4.1.1` is this experimental dashboard button layout fix
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.1.0 until this build is promoted

---
# SDAC Bot Version 4.1.0 Official

Date: 2026-07-12

Update scope: Official server-owner command and release polish

Version 4.1.0 is an official SDAC backend and Discord usability release that promotes the command-simplification work into the official update channel.

Included:

- added a manual Sync Commands action in `/sdac` setup panels and the setup wizard so owners can refresh Discord commands without a full restart
- expanded setup status and setup tests with command visibility, server alias, and duplicate guild-command cleanup details
- added a command visibility audit to protect the simplified public command surface
- added dashboard and app metadata links for the GitHub repository and wiki/setup docs
- added a Bot Owner Home restart warning when the dashboard release is newer than the bot heartbeat release
- updated server-owner docs and wiki guidance for invite, setup, custom command aliases, command sync, and release restart checks

Release channel:

- `version-4.1.0` is this official server-owner command and release polish update
- `latest-official` points to this build after publishing
- `latest-experimental` remains available for future experimental builds

---
# SDAC Bot Version 4.0.8 Experimental

Date: 2026-07-12

Update scope: Server command launcher aliases and duplicate slash-command cleanup

Version 4.0.8 is an experimental Discord setup update that lets each server choose an optional command launcher while keeping `/sdac` as the stable fallback.

Included:

- added per-server command launcher support so owners can sync an alias like `/pepo` during setup
- added a Command Name control to the setup wizard and `/sdac` setup submenu
- kept `/sdac` available on every server even when a custom launcher is configured
- fixed duplicate Discord slash commands by clearing guild-specific copied commands and syncing guild commands as alias-only
- added GitHub and Wiki link buttons to the `/sdac` control center for easier user access
- added a Codex handoff file with project rules, release policy, and reviewer notes

Release channel:

- `version-4.0.8` is this experimental custom command launcher update
- `latest-experimental` points to this build after publishing
- `latest-official` remains on Version 4.0.0 until this build is promoted

---
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

---
# SDAC Bot Version 4.0.6 Experimental

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







