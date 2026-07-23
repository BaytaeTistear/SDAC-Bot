# Sana-Chan Local Server Launcher

Use `start_sana_local_server.ps1` when hosting Sana-Chan from the local Hyper-V Ubuntu VM with a Cloudflare quick tunnel.

It does this in one pass:

- starts the `Sana-Ubuntu-Test` Hyper-V VM if it is stopped
- waits for SSH to become available
- starts the Docker Compose `dashboard` and `bot` services in the VM
- opens `cloudflared tunnel --url http://<vm-ip>:5000`
- reads the generated `trycloudflare.com` URL
- updates `SANA_DASHBOARD_URL` and `SDAC_PUBLIC_URL` in the VM `.env`
- restarts the dashboard and bot containers
- writes the current URL, process id, and log path to `%USERPROFILE%\.sana-chan\local-tunnel-status.json`

Run from Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit\scripts\windows\start_sana_local_server.ps1
```

If the VM IP changes, pass the new address:

```powershell
D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit\scripts\windows\start_sana_local_server.ps1 -VmHost 172.17.188.232
```

To start it automatically when Windows logs in:

```powershell
schtasks /Create /TN "Sana Local Server Tunnel" /TR "powershell.exe -ExecutionPolicy Bypass -File D:\CodexStuff\DiscordBots\SDAC\ScreenshotSubmit\scripts\windows\start_sana_local_server.ps1" /SC ONLOGON /RL LIMITED /F
```

Cloudflare quick tunnel URLs can change. When the script prints a new URL, add the matching Discord OAuth redirect:

```text
https://example.trycloudflare.com/account/oauth/callback
```

For production, a named Cloudflare Tunnel with a Cloudflare-managed domain is still more stable than a quick tunnel.