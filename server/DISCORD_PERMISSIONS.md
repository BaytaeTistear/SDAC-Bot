# Discord Bot Permissions

Use OAuth2 URL Generator in the Discord Developer Portal with these scopes:

- `bot`
- `applications.commands`

Recommended bot permissions for the current SDAC features:

- View Channels
- Send Messages
- Attach Files
- Read Message History
- Manage Messages
- Use Slash Commands / Application Commands

Current permissions integer:

```text
2147593216
```

The bot does not need Administrator for normal use. Server admins should only
grant access to the channels where SDAC submissions, approvals, weekly posts,
guessing games, summaries, and errors should appear.

After inviting the bot or changing channel overrides, run:

```text
/checkpermissions
/repairpermissions
```

Those commands check configured SDAC channels and report missing required bot
permissions. `/repairpermissions` also includes a bot re-authorization link when
the bot client ID is configured.
