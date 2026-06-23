#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path

import psycopg


TYPE_MAP = {
    "INTEGER": "BIGINT",
    "TEXT": "TEXT",
    "REAL": "DOUBLE PRECISION",
    "BLOB": "BYTEA",
}


def pg_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def sqlite_tables(connection):
    return [
        row["name"]
        for row in connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
    ]


def column_definitions(sqlite_connection, table):
    columns = []
    for row in sqlite_connection.execute(f"PRAGMA table_info({pg_ident(table)})"):
        raw_type = (row["type"] or "TEXT").split()[0].upper()
        pg_type = TYPE_MAP.get(raw_type, "TEXT")
        nullable = "" if row["notnull"] else ""
        columns.append((row["name"], f"{pg_ident(row['name'])} {pg_type} {nullable}".strip()))
    return columns


def create_table(pg_connection, sqlite_connection, table):
    columns = column_definitions(sqlite_connection, table)
    if not columns:
        return []
    column_sql = ", ".join(definition for _name, definition in columns)
    with pg_connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {pg_ident(table)} ({column_sql})"
        )
    return [name for name, _definition in columns]


def copy_table(pg_connection, sqlite_connection, table):
    columns = create_table(pg_connection, sqlite_connection, table)
    if not columns:
        return 0
    quoted_columns = ", ".join(pg_ident(column) for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    rows = sqlite_connection.execute(
        f"SELECT {quoted_columns} FROM {pg_ident(table)}"
    ).fetchall()
    if not rows:
        return 0
    values = [tuple(row[column] for column in columns) for row in rows]
    with pg_connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO {pg_ident(table)} ({quoted_columns}) VALUES ({placeholders})",
            values,
        )
    return len(values)


def main():
    parser = argparse.ArgumentParser(
        description="Export an SDAC SQLite database into PostgreSQL tables."
    )
    parser.add_argument("--sqlite", default="sdac.db", help="Path to sdac.db")
    parser.add_argument("--database-url", required=True, help="PostgreSQL URL")
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop destination tables before importing",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite database was not found: {sqlite_path}")

    sqlite_connection = sqlite3.connect(sqlite_path)
    sqlite_connection.row_factory = sqlite3.Row
    tables = sqlite_tables(sqlite_connection)

    with psycopg.connect(args.database_url) as pg_connection:
        if args.drop_existing:
            with pg_connection.cursor() as cursor:
                for table in reversed(tables):
                    cursor.execute(f"DROP TABLE IF EXISTS {pg_ident(table)} CASCADE")
        for table in tables:
            count = copy_table(pg_connection, sqlite_connection, table)
            print(f"{table}: {count} row(s)")
        pg_connection.commit()


if __name__ == "__main__":
    main()
