# Server

The production server hosts the Discord bot, Flask dashboard, database, media storage, and release/update tooling.

## Production Path

`/home/ubuntu/discord-screenshot-bot`

## Important Services

- `sdac-bot.service` runs the Discord bot.
- The Flask dashboard runs from the same backend/source of truth.
- `sdac-doctor` is used for install and health checks.

## Environment

Discord bot and OAuth credentials belong in the server `.env` file:

- `DISCORD_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI`

## Maintenance

- Keep backups enabled and visible from the dashboard.
- Track last restart, last backup, database health, and release state.
- Run smoke checks before pushing release changes.
- Use LF line endings for Linux scripts so commands such as `sudo sdac-doctor` do not fail with `bash\r`.

## Future Updates

- Update this page when deployment, `.env`, service, database, backup, or doctor behavior changes.
