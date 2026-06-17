import argparse
import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database_migrations import (
    DATABASE_SCHEMA_VERSION,
    apply_database_migrations,
    current_schema_version,
)


def main():
    parser = argparse.ArgumentParser(
        description="Apply SDAC SQLite database migrations."
    )
    parser.add_argument(
        "--db",
        default=str(APP_DIR / "sdac.db"),
        help="Path to sdac.db.",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        raise SystemExit(f"Database does not exist: {db_path}")

    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        before = current_schema_version(connection)
        apply_database_migrations(connection)
        connection.commit()
        after = current_schema_version(connection)
    finally:
        connection.close()

    print(f"Migrated {db_path}")
    print(f"Schema version: {before} -> {after}")
    print(f"Expected schema version: {DATABASE_SCHEMA_VERSION}")


if __name__ == "__main__":
    main()
