# Oracle Server Restore Notes

Use these values when the old Oracle Cloud server is available again.

## Preferred public URL

Set the dashboard to the stable HTTPS domain:

```env
SANA_PUBLIC_URL=https://freethefishies.us.to
SANA_DASHBOARD_URL=https://freethefishies.us.to
SANA_DOMAIN=freethefishies.us.to
SANA_FRIENDLY_URL=http://sanachan.bot.nu
```

The old `SDAC_PUBLIC_URL`, `SDAC_DASHBOARD_URL`, and `SDAC_DOMAIN` names still work, but new installs should use the `SANA_*` names.

## Discord OAuth callback

Add this exact redirect in Discord Developer Portal > OAuth2 > Redirects:

```text
https://freethefishies.us.to/account/oauth/callback
```

Only add this one if `sanachan.bot.nu` is serving the dashboard directly over HTTPS, not as a plain HTTP web forward:

```text
https://sanachan.bot.nu/account/oauth/callback
```

Do not use the misspelled `freethefuishies.us.to`; the dashboard normalizes that typo internally, but DNS and Discord OAuth will not.

## Health checks

```bash
curl -fsS https://freethefishies.us.to/health
SANA_DOMAIN=freethefishies.us.to bash scripts/check_production.sh
```

## Update command

```bash
sana-update latest-experimental
```
