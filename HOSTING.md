# Hosting SDAC On Ubuntu

This guide is for a fresh Ubuntu server.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 2. Put the bot files on the server

Recommended path:

```bash
/home/ubuntu/discord-screenshot-bot
```

Copy or clone the project into that folder.

## 3. Run the installer

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/install_ubuntu.sh
```

The installer will:

- create `media/` and `backups/`
- create `config.json` if it is missing
- create `.env` and ask for the Discord token and dashboard admin password
- create `venv/`
- install Python dependencies
- install `sdac-bot` and `sdac-dashboard` systemd services
- start both services

## 4. Check logs

```bash
journalctl -u sdac-bot -n 80 --no-pager
journalctl -u sdac-dashboard -n 80 --no-pager
```

## 5. Future updates

Upload the changed files, then run:

```bash
cd /home/ubuntu/discord-screenshot-bot
bash scripts/update_ubuntu.sh
```

## Environment Settings

The installer writes `.env`. You can edit it later:

```bash
nano /home/ubuntu/discord-screenshot-bot/.env
sudo systemctl restart sdac-bot sdac-dashboard
```

Required values:

- `DISCORD_TOKEN`
- `SDAC_ADMIN_KEY`
- `SDAC_ADMIN_PASSWORD`
- `SDAC_SECRET_KEY`

## Discord Setup Still Required

A server owner still needs to invite the bot to Discord with the right permissions. The Ubuntu installer cannot do that part.

The bot needs permissions for:

- slash commands
- send messages
- attach files
- manage messages
- read message history
- view channels

After the bot starts, slash commands sync automatically. It can take a few minutes for Discord to show new commands.
