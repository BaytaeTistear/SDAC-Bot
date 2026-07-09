# SDAC Master Video Script

Use this as a compact recording guide for one full overview video of the bot, dashboard, and app.

## 1. Opening

Suggested line:
"This is SDAC, a Discord media submission bot with a public gallery, staff dashboard, moderation tools, guessing games, and release/update tooling for server owners and bot owners."

Show/find it:
- Discord server: show the bot in the member list and slash commands.
- Website: open the public dashboard homepage.
- Dashboard admin: open `/admin?key=ImTheBestAdmin` and log in.
- App: open the SDAC app or `/app` page.

## 2. What Problem SDAC Solves

Cover:
- Users submit screenshots, clips, audio, or other media through Discord.
- The bot reposts and organizes submissions by server/category.
- The website gives the community a browsable gallery.
- Staff can moderate, remove, quarantine, and audit submissions.
- Server owners can configure their own server without touching other servers.
- Bot owners can maintain the whole install, releases, backups, and global health.

Show/find it:
- Discord: `/submit`
- Dashboard: public gallery `/`
- Admin dashboard: `/admin`
- Release/admin tools: `/admin/releases`, `/admin/maintenance`, `/admin/global-control`

## 3. Discord Bot Walkthrough

Suggested line:
"Most users only need Discord. They submit media, choose a category, and SDAC handles the repost and gallery entry."

Show:
- `/submit` for normal media submissions.
- Category setup with `/setcategory`.
- Submit channel setup with `/setsubmit`.
- Admin help/setup commands such as `/setup`, `/setupstatus`, `/setuptest`, and `/diagnose`.
- Moderation command `/removesubmission` with reason presets.

Mention:
- No channels or categories are set by default.
- Each server configures its own submit channel and categories.
- Admin roles can be assigned per server.

Where to find details:
- `README.md` command sections.
- `DISCORD_PERMISSIONS.md` for permission requirements.
- Wiki pages in `wiki/`.

## 4. Public Website Gallery

Suggested line:
"The website is public by default, so viewers do not need an admin key to browse posted submissions."

Show:
- Homepage/gallery `/`
- Server filter
- Category filter
- Sorting and searching
- Submission media cards
- User/profile or leaderboard links if relevant

Mention:
- Admin mode uses `?key=ImTheBestAdmin` plus dashboard login.
- Public users can browse without a key.

Where to find it:
- `dashboard.py` main gallery route `/`
- README website/dashboard section

## 5. Moderator Workflow

Suggested line:
"Moderators get a focused queue instead of the full server-owner backend."

Show:
- `/admin/moderator`
- `/admin/moderation`
- Pending queue
- Open reports
- Recent moderation history
- Remove reason dropdown and audit note
- Needs Review button
- Quarantine button
- Audit log `/admin/audit`

Mention:
- Removal should update the database and delete the Discord repost.
- Removal reasons keep audit history readable.
- Quarantine is for media that needs a safer review path.

## 6. Server Owner Workflow

Suggested line:
"Server owners only see and manage the servers they are assigned to. The same account can have different roles on different servers."

Show:
- `/admin/server-owner`
- Setup checklist `/admin/setup-checklist`
- Category manager `/admin/categories`
- Permission health `/admin/permission-health`
- Settings `/admin/settings`
- Theme/layout pages if you want to show customization

Mention:
- Server owners manage channels, categories, features, limits, branding, and setup health for their assigned servers.
- A user can be owner on one server, moderator on another, and regular user on another.
- Bot owners remain global.

## 7. Bot Owner Workflow

Suggested line:
"Bot owners get the global control room for the whole install."

Show:
- `/admin/bot-owner`
- Global control `/admin/global-control`
- Maintenance mode `/admin/maintenance-mode`
- Config history `/admin/config-history`
- Releases `/admin/releases`
- Maintenance `/admin/maintenance`
- Install Doctor `/admin/install-doctor`
- Jobs/backups/production health if time allows

Mention:
- Bot owners can see all servers.
- Admins and server owners are scoped to their assigned servers.
- Experimental releases are pushed often; official releases are only promoted when you say so.

## 8. Guessing Games And Community Features

Suggested line:
"SDAC is not only a gallery. It also supports guessing games, leaderboards, achievements, polls, and community activity features."

Show:
- Guessing leaderboard
- Achievements
- Game Library admin page
- Seasons
- Polls
- `/startgame`, `/startlibrarygame`, or related guessing commands if available in Discord

Where to find it:
- Dashboard nav: Guessing leaderboard, Achievements, Game Library, Seasons, Polls
- README guessing/game sections

## 9. App Overview

Suggested line:
"The app is the mobile-friendly companion experience for browsing and managing SDAC."

Show:
- `/app` or installed app build
- Server selection
- Gallery/navigation
- Admin links if logged in
- Release/status information if shown

Where to find it:
- `apps/sdac-official-app/README.md`
- `apps/sdac-official-app/`
- Dashboard `/app`

## 10. Updates And Release Policy

Suggested line:
"My update policy is simple: every change gets an experimental 3.1.x release. Official 3.x.0 or full x.0.0 releases only happen when I explicitly say so."

Show:
- GitHub Releases page
- `/admin/releases`
- Server update command output

Mention:
- `latest-experimental` is for test/verification updates.
- `latest-official` stays on the approved official release.
- Server command: `sdac-update latest-experimental`
- Current server path: `/home/ubuntu/discord-screenshot-bot`
- Environment file: `/etc/sdac-bot/sdac.env`

Where to find it:
- `RELEASE.md`
- `server/RELEASE.md`
- `.github/workflows/release.yml`
- `scripts/update_from_github.sh`

## 11. Hosting And Operations

Cover:
- Main server files: `bot.py`, `dashboard.py`, `config.py`, `config.json`, `sdac.db`, `media/`
- Server deploy folder: `server/`
- Backups, restore tests, health checks, and install doctor
- Logs/services for bot and dashboard

Show/find it:
- `/admin/maintenance`
- `/admin/production-health`
- `/admin/install-doctor`
- `DEPLOY.md`
- `HOSTING.md`
- `MONITORING.md`

## 12. Closing

Suggested line:
"SDAC is meant to keep Discord media submissions organized, public, and moderated while giving each server only the controls it needs. Users submit, moderators review, server owners configure, and bot owners keep the whole system healthy."

End with:
- Where to get help: README, wiki, setup guide, dashboard admin pages.
- What to show next: a live `/submit`, a dashboard removal with reason, and a server setup checklist.