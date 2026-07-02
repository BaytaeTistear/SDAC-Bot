import os
import re
import sqlite3


POSTGRES_URL_PREFIXES = ("postgres://", "postgresql://")
ID_TABLES = {
    "submissions",
    "category_history",
    "moderation_history",
    "admin_audit_log",
    "background_jobs",
    "setup_test_runs",
    "admin_notifications",
    "game_seasons",
    "guess_games",
    "guess_library_items",
    "guess_answer_history",
    "guess_points",
    "media_fingerprints",
    "rate_limit_events",
    "submission_reports",
    "support_bundles",
    "content_moderation_events",
    "offsite_backup_runs",
    "privacy_actions",
    "pending_admin_actions",
    "media_quarantine",
    "monthly_digest_runs",
    "scheduled_games",
    "user_achievements",
    "backup_archives",
}


def database_url():
    return os.getenv("SDAC_DATABASE_URL", "").strip()


def using_postgres():
    return database_url().casefold().startswith(POSTGRES_URL_PREFIXES)


class CompatRow:
    def __init__(self, columns, values):
        self._columns = list(columns or [])
        self._values = tuple(values or ())
        self._data = {
            column: self._values[index]
            for index, column in enumerate(self._columns)
        }

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._columns)

    def __len__(self):
        return len(self._values)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


class CompatCursor:
    def __init__(self, cursor, lastrowid=None, prefetched=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self._prefetched = prefetched

    def _columns(self):
        if not self._cursor.description:
            return []
        return [column.name for column in self._cursor.description]

    def _wrap(self, row):
        if row is None:
            return None
        return CompatRow(self._columns(), row)

    def fetchone(self):
        if self._prefetched is not None:
            row = self._prefetched
            self._prefetched = None
            return row
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        first = []
        if self._prefetched is not None:
            first.append(self._prefetched)
            self._prefetched = None
        return first + [self._wrap(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                break
            yield row


def _replace_qmark_placeholders(sql):
    result = []
    in_single = False
    in_double = False
    index = 1
    for character in sql:
        if character == "'" and not in_double:
            in_single = not in_single
        elif character == '"' and not in_single:
            in_double = not in_double
        if character == "?" and not in_single and not in_double:
            result.append(f"%s")
            index += 1
        else:
            result.append(character)
    return "".join(result)


def _postgres_column_type(sql_type):
    sql_type = (sql_type or "TEXT").upper()
    sql_type = re.sub(r"\s+DEFAULT\s+.+$", "", sql_type).strip()
    if sql_type.startswith("INTEGER"):
        return "BIGINT"
    if sql_type.startswith("REAL"):
        return "DOUBLE PRECISION"
    if sql_type.startswith("BLOB"):
        return "BYTEA"
    return "TEXT"


def _translate_sqlite_sql(sql):
    translated = sql.strip()
    ignore_insert = bool(
        re.match(r"INSERT\s+OR\s+IGNORE\s+INTO", translated, re.IGNORECASE)
    )
    translated = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+CHECK\s*\([^)]+\)",
        "BIGINT PRIMARY KEY",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        translated,
        flags=re.IGNORECASE,
    )
    if ignore_insert and re.match(r"INSERT\s+INTO", translated, re.IGNORECASE):
        if "ON CONFLICT" not in translated.upper():
            translated += " ON CONFLICT DO NOTHING"
    translated = _replace_qmark_placeholders(translated)
    return translated


class PostgresCompatConnection:
    def __init__(self, url):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "SDAC_DATABASE_URL is set, but psycopg is not installed. "
                "Install requirements.txt before enabling PostgreSQL mode."
            ) from error

        self._psycopg = psycopg
        self._connection = psycopg.connect(url)

    def execute(self, sql, parameters=()):
        normalized = " ".join(sql.strip().split())
        lowered = normalized.casefold()
        if lowered.startswith("pragma busy_timeout"):
            return CompatCursor(self._connection.cursor(), prefetched=CompatRow(["busy_timeout"], [0]))
        if lowered.startswith("pragma journal_mode"):
            return CompatCursor(self._connection.cursor(), prefetched=CompatRow(["journal_mode"], ["wal"]))
        if lowered.startswith("pragma foreign_keys"):
            return CompatCursor(self._connection.cursor(), prefetched=CompatRow(["foreign_keys"], [1]))
        if lowered.startswith("pragma integrity_check"):
            return CompatCursor(self._connection.cursor(), prefetched=CompatRow(["integrity_check"], ["ok"]))
        if lowered.startswith("pragma table_info"):
            match = re.search(r"pragma\s+table_info\s*\(([^)]+)\)", normalized, re.IGNORECASE)
            table = match.group(1).strip('"') if match else ""
            rows = self._table_info_rows(table)
            cursor = self._connection.cursor()
            return _StaticCursor(rows)
        if "from sqlite_master" in lowered:
            return self._sqlite_master_query(sql, parameters)

        translated = _translate_sqlite_sql(sql)
        cursor = self._connection.cursor()
        lastrowid = None
        returning_added = False
        insert_match = re.match(
            r'\s*INSERT\s+INTO\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
            translated,
            re.IGNORECASE,
        )
        if insert_match and insert_match.group(1) in ID_TABLES:
            if (
                " RETURNING " not in translated.upper()
                and "ON CONFLICT DO NOTHING" not in translated.upper()
            ):
                translated += " RETURNING id"
                returning_added = True
        cursor.execute(translated, parameters or ())
        prefetched = None
        if returning_added and cursor.description:
            row = cursor.fetchone()
            if row:
                lastrowid = row[0]
                prefetched = CompatRow([column.name for column in cursor.description], row)
        return CompatCursor(cursor, lastrowid=lastrowid, prefetched=prefetched)

    def executemany(self, sql, seq_of_parameters):
        translated = _translate_sqlite_sql(sql)
        cursor = self._connection.cursor()
        cursor.executemany(translated, seq_of_parameters)
        return CompatCursor(cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def cursor(self):
        return self._connection.cursor()

    def _table_info_rows(self, table):
        cursor = self._connection.cursor()
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        rows = []
        for index, row in enumerate(cursor.fetchall()):
            name, data_type, is_nullable, default = row
            rows.append(CompatRow(
                ["cid", "name", "type", "notnull", "dflt_value", "pk"],
                [
                    index,
                    name,
                    data_type,
                    0 if is_nullable == "YES" else 1,
                    default,
                    1 if name == "id" else 0,
                ],
            ))
        return rows

    def _sqlite_master_query(self, sql, parameters):
        table_name = parameters[0] if parameters else ""
        cursor = self._connection.cursor()
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
            LIMIT 1
        """, (table_name,))
        row = cursor.fetchone()
        rows = [CompatRow(["1"], [1])] if row else []
        return _StaticCursor(rows)


class _StaticCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    @property
    def lastrowid(self):
        return None

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self):
        rows = self._rows
        self._rows = []
        return rows

    def __iter__(self):
        return iter(self.fetchall())


def connect_database(sqlite_path, timeout=30):
    if using_postgres():
        return PostgresCompatConnection(database_url())
    connection = sqlite3.connect(sqlite_path, timeout=timeout)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
