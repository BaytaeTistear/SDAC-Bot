# SDAC Bot Codex Handoff Notes

Last updated: 2026-07-12
Workspace: D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit
Repository: BaytaeTistear/SDAC-Bot
Server install path: /home/ubuntu/discord-screenshot-bot

## Project Summary

SDAC is a Discord bot plus Flask dashboard for media submissions, moderation, guessing games, anime profile/activity features, server-owner setup, bot-owner operations, backups, release/update management, and public dashboard pages.

Main local files:

- bot.py
- dashboard.py
- config.py
- config.json
- sdac.db
- media/
- server/bot.py and server/dashboard.py are release/server mirrors

## Owner Preferences And Standing Orders

- Keep communication non-technical where possible.
- Do not revert user changes unless explicitly told to.
- When making project changes, keep affected files fully updated rather than leaving snippets or partial mirrors.
- Always protect unrelated dirty files.
- Push a new experimental release for every code/docs change.
- Experimental releases use 3.0.x/3.1.x previously, and now the current full-release line is 4.0.x.
- Only push an official update like 3.x.0 / 4.x.0 or a full update like x.0.0 when the owner explicitly says so.
- latest-experimental should move for experimental builds.
- latest-official should stay pinned unless the owner explicitly promotes a release.
- Release notes must include only the newest release section when publishing GitHub release notes, not the entire release history.
- Do not use WSL. The owner said WSL previously corrupted the computer and should not be used.
- Avoid staging local/private files such as config.json, sdac.db, media, temp video frames, or scratch notes unless explicitly requested.

## Important Current Local State

Known unrelated or local-only files have appeared before and should usually be left unstaged:

- config.json modified
- .codex_video_frames/ untracked
- CLAUDE.md untracked
- New Text Document.txt untracked
- New Text Document (2).txt untracked

Before committing, always run a fresh git status and stage only intended files.

## Current Release Policy

For any completed change:

1. Update RELEASE.md and server/RELEASE.md with the next experimental version.
2. Mirror changed server files when needed.
3. Run compile/tests/readiness checks.
4. Commit only intended files.
5. Tag the numbered version, move latest-experimental, and push.
6. Do not move latest-official unless the owner asks for an official/full release.

Current known official baseline from prior work: latest-official stayed on 4.0.0.
Latest experimental before this handoff was 4.0.7.
The next experimental should likely be 4.0.8 if not already completed by another bot.

## Recent Feature Work In Progress

The owner asked whether server owners can choose their own launcher command like /sdac, /pepo, etc. Discord does not allow true per-server renaming of a global slash command, so the implemented approach is:

- Keep /sdac as the always-available global fallback.
- Let each guild set an optional guild-specific alias like /pepo.
- Sync only that alias as a guild command.
- Do not copy global commands into guild command sync, because that creates duplicate command listings in Discord.

Implemented in bot.py and mirrored to server/bot.py:

- PROJECT_GITHUB_URL and PROJECT_WIKI_URL constants.
- COMMAND_ALIAS_PATTERN and command alias validation helpers.
- DEFAULT_GUILD_CONFIG now includes command_alias.
- setup_status_rows shows Command launcher.
- Setup wizard page 3 includes Command Name.
- /sdac > Setup includes Command Name.
- SetupCommandAliasModal saves the alias and syncs the guild commands.
- SDAC hub has GitHub and Wiki link buttons.
- sync_guild_slash_commands clears guild-specific commands and only adds the alias if configured.

Critical duplicate-command fix:

- Do not call tree.copy_global_to(guild=...) during normal guild sync.
- Guild sync should clear the guild command list and add only the custom alias.
- The global commands remain /sdac, /submit, /guess, and /hint by default.

## Why Commands Appeared Twice In Discord

Discord showed duplicate /sdac and /submit because the bot had both:

- global commands synced by tree.sync(), and
- guild-specific copies created by tree.copy_global_to(guild=...) followed by tree.sync(guild=...).

Discord displays both global and guild commands. After the fix and bot restart/sync, duplicate guild copies should be removed. Discord may take a minute to refresh.

## Programs And Permissions That Help

Already useful/expected:

- Python 3.12
- Node.js and npm
- Git
- GitHub CLI authenticated with repo access
- PowerShell

Most helpful permissions for this machine/session:

- Allow read/write commands inside D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit.
- Allow Python test commands such as .\.venv-win\Scripts\python.exe -m unittest ...
- Allow Git commands for status, diff, add, commit, tag, and push.
- Allow GitHub CLI commands for release/tag/wiki operations.
- Allow network only when cloning/updating the GitHub wiki or publishing releases.

Not wanted:

- Do not use WSL.

## Checks To Run Before Release

Recommended local checks:

```powershell
.\.venv-win\Scripts\python.exe -m py_compile bot.py server\bot.py dashboard.py server\dashboard.py
.\.venv-win\Scripts\python.exe -m unittest tests.test_bot_startup
.\.venv-win\Scripts\python.exe scripts\pre_release_smoke.py
.\.venv-win\Scripts\python.exe scripts\release_readiness.py
git -c safe.directory=D:/CodexStuff/DiscordBots/SDAC/ScreenshotSubmit diff --check
```

If tests fail because of the new alias feature, add or update focused tests in tests/test_bot_startup.py.

## Wiki Update Needed

Update the GitHub wiki to explain:

- /sdac is always the fallback.
- Server owners can set a custom launcher like /pepo from /sdac > Setup > Command Name or the setup wizard final page.
- Discord may take a minute to show the new command after sync.
- GitHub and Wiki links are available in the /sdac panel.
- Simplified default commands are /sdac, /submit, /guess, and /hint.

GitHub wiki repo is usually:

```text
https://github.com/BaytaeTistear/SDAC-Bot.wiki.git
```

## Reviewer Notes

Please inspect these areas carefully:

- bot.py around command alias helpers near normalize_command_alias.
- bot.py around SetupCommandAliasModal.
- bot.py around SetupWizardView page 3 buttons.
- bot.py around SDACSubmenuButton setup_command_alias handling.
- bot.py around sync_guild_slash_commands.
- server/bot.py mirror should match bot.py.

Potential concern:

- Guild command sync currently clears all guild-specific commands managed by this command tree and adds only the alias. That is intended for SDAC simplified mode, but confirm there are no required guild-only SDAC commands that should remain.

## Current User Request Context

The owner asked:

- Whether more programs/permissions are needed to run better.
- For this handoff/memory/orders file so another bot can review it.
- To fix duplicate Discord commands shown in the attached screenshot.

Answer summary:

- No more programs are likely needed right now.
- Stable repo write/test/git/GitHub permissions are the main improvement.
- Duplicate commands were caused by global commands plus guild-copied commands.
- The fix is to sync guild commands as alias-only and clear copied guild commands.
