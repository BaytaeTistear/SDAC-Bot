# Sana-Chan Docker Setup

Docker is the easiest way to move Sana-Chan between Oracle Cloud, another VPS,
a home server, or a low-cost container host. The Compose setup runs the
dashboard and Discord bot as separate containers that share one persistent data
volume.

## Files

- `Dockerfile` builds one reusable Sana-Chan image.
- `docker-compose.yml` starts `dashboard`, `bot`, and optional `postgres`.
- `.env.example` lists the environment variables to copy into `.env`.
- `.dockerignore` keeps secrets, media, build output, and local databases out of
  the image.

## Quick Start

```bash
cp .env.example .env
# Edit .env and set DISCORD_TOKEN, SDAC_ADMIN_KEY, and SDAC_SECRET_KEY.
docker compose up -d --build
docker compose logs -f dashboard
docker compose logs -f bot
```

Open the dashboard at:

```text
http://localhost:5000
```

## Persistent Data

Compose creates a named Docker volume called `screenshotsubmit_sana-data` unless
your Compose project name changes it. Inside the containers, Sana-Chan stores:

- `/data/config.json`
- `/data/sdac.db`
- `/data/media`
- `/data/backups`
- `/data/import_jobs`
- `/data/bot_status.json`

Back this volume up before moving hosts.

## Useful Commands

```bash
docker compose ps
docker compose logs -f dashboard
docker compose logs -f bot
docker compose restart bot
docker compose restart dashboard
docker compose pull
docker compose up -d --build
docker compose exec dashboard python scripts/sdac_doctor.py
```

## Updating

```bash
git pull
docker compose up -d --build
docker compose logs -f bot
```

If you are using release downloads instead of Git, unpack the release, keep your
`.env`, and run the same `docker compose up -d --build` command.

## Optional PostgreSQL

SQLite is simplest for a single small host. PostgreSQL is available for testing
or future growth:

```bash
docker compose --profile postgres up -d
```

Then set this in `.env`:

```text
SDAC_DATABASE_URL=postgresql://sana:change-me@postgres:5432/sana
```

Restart both services afterward:

```bash
docker compose up -d
```

## Notes For Free/Low-Cost Hosts

- The Discord bot needs an always-on container. Avoid hosts that sleep.
- Keep media and database files on a persistent volume.
- If the host only supports one process, run the bot and dashboard as separate
  apps that mount the same data volume, or prefer a small VM.
- For public HTTPS on a home server, Cloudflare Tunnel can sit in front of the
  dashboard while Docker keeps the local setup consistent.
