# Oracle Server Restore Notes

Use these values when the old Oracle Cloud server is available again.

## Preferred public URL

Set the dashboard to the stable HTTPS domain:

```env
SANA_PUBLIC_URL=https://sanachan.bot.nu
SANA_DASHBOARD_URL=https://sanachan.bot.nu
SANA_DOMAIN=sanachan.bot.nu
SANA_FRIENDLY_URL=https://sanachan.bot.nu
```

The old `SDAC_PUBLIC_URL`, `SDAC_DASHBOARD_URL`, and `SDAC_DOMAIN` names still work, but new installs should use the `SANA_*` names.

## Discord OAuth callback

Add this exact redirect in Discord Developer Portal > OAuth2 > Redirects:

```text
https://sanachan.bot.nu/account/oauth/callback
```

The domain must serve the dashboard directly over HTTPS, not as a plain HTTP web forward.

Use these exact account-provider callbacks too:

```text
https://sanachan.bot.nu/account/mal/callback
https://sanachan.bot.nu/account/anilist/callback
```

Do not use the misspelled `freethefuishies.us.to`; the dashboard normalizes that typo internally, but DNS and Discord OAuth will not.

## Health checks

```bash
curl -fsS https://sanachan.bot.nu/health
SANA_DOMAIN=sanachan.bot.nu bash scripts/check_production.sh
```

## Update command

```bash
sana-update latest-experimental
```
