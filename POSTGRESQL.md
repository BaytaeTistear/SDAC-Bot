# PostgreSQL Migration Support

SDAC still runs on SQLite by default. That keeps single-server installs simple
and compatible with the existing backup/restore tools.

Version 2.7.1 adds a PostgreSQL migration utility plus experimental runtime
support through `SDAC_DATABASE_URL`.

## Start A Test PostgreSQL Container

```bash
docker compose --profile postgres up -d postgres
```

The compose profile starts PostgreSQL at:

```text
postgresql://sdac:sdac-change-me@localhost:5432/sdac
```

## Export SQLite Into PostgreSQL

From the app directory:

```bash
venv/bin/python scripts/export_sqlite_to_postgres.py \
  --sqlite sdac.db \
  --database-url "postgresql://sdac:sdac-change-me@localhost:5432/sdac" \
  --drop-existing
```

The tool introspects the SQLite tables, creates matching PostgreSQL tables, and
copies rows.

## Experimental Runtime Mode

Set `SDAC_DATABASE_URL` in `/etc/sdac-bot/sdac.env` to make the bot and
dashboard use PostgreSQL through the compatibility backend:

```text
SDAC_DATABASE_URL=postgresql://sdac:sdac-change-me@localhost:5432/sdac
```

Then restart both services:

```bash
sudo systemctl restart sdac-dashboard sdac-bot
```

Use this mode on a test server first. SQLite remains the default and safest
single-server runtime.

## Current Status

- SQLite remains the default live runtime database for Version 2.x.
- `SDAC_DATABASE_URL` enables experimental runtime Postgres support.
- `psycopg` is included so migration/export tooling works out of the box.
- Docker compose includes an optional Postgres profile for testing.

Long term, SDAC should still move direct SQL calls behind a repository layer.
That will make PostgreSQL support cleaner and easier to optimize.
