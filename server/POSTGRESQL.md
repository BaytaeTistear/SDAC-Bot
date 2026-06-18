# PostgreSQL Migration Plan

SDAC currently uses SQLite because it is simple, portable, and works well for a
single bot/dashboard server. Move to PostgreSQL when you expect multiple app
servers, very high write volume, or managed off-server database backups.

Recommended path:

1. Keep SQLite for Version 2.x production installs.
2. Add a database URL setting such as `SDAC_DATABASE_URL`.
3. Move database access behind a small repository layer instead of direct
   `sqlite3` calls in `bot.py` and `dashboard.py`.
4. Add PostgreSQL migrations with a real migration tool.
5. Build a one-time export/import command:

```bash
venv/bin/python scripts/export_sqlite_to_postgres.py --sqlite sdac.db --database-url "$SDAC_DATABASE_URL"
```

Do not replace SQLite in-place without that compatibility layer. The current
code relies on SQLite-specific connection behavior, backup APIs, and local file
restore tests.
