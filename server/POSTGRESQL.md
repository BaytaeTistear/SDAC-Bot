# PostgreSQL Migration Support

SDAC still runs on SQLite by default. That keeps single-server installs simple
and compatible with the existing backup/restore tools.

Version 2.7 adds a PostgreSQL migration utility so you can test a move before
the runtime is fully switched to a database repository layer.

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
copies rows. It is intended for migration testing and reporting, not as the live
runtime switch yet.

## Current Status

- SQLite remains the live supported runtime database for Version 2.x.
- `SDAC_DATABASE_URL` is reserved for future runtime Postgres support.
- `psycopg` is included so migration/export tooling works out of the box.
- Docker compose includes an optional Postgres profile for testing.

Before making PostgreSQL the live database, SDAC still needs a repository layer
to replace direct SQLite calls, SQLite backup APIs, and SQLite-specific restore
tests.
