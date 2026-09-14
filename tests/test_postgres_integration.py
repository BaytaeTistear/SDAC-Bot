import os
import unittest

from database_backend import connect_database, using_postgres
from database_migrations import DATABASE_SCHEMA_VERSION, apply_database_migrations


@unittest.skipUnless(using_postgres(), "SDAC_DATABASE_URL is not configured")
class PostgresIntegrationTests(unittest.TestCase):
    def test_migrations_inserts_and_scheduler_lease_upsert(self):
        connection = connect_database(":memory:")
        try:
            apply_database_migrations(connection)
            version = connection.execute(
                "SELECT version FROM schema_version WHERE id = 1"
            ).fetchone()[0]
            self.assertEqual(version, DATABASE_SCHEMA_VERSION)
            now = "2026-09-14T00:00:00+00:00"
            cursor = connection.execute(
                """
                INSERT INTO community_quotes (
                    guild_id, quote_text, speaker, status, normalized_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                ("postgres-test", "Test quote", "Tester", "hash", now, now),
            )
            self.assertIsNotNone(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO scheduler_leases (lease_key, owner_id, acquired_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (lease_key) DO UPDATE SET owner_id = excluded.owner_id
                """,
                ("integration-test", "runner", now, "2026-09-14T00:05:00+00:00"),
            )
            lease = connection.execute(
                "SELECT owner_id FROM scheduler_leases WHERE lease_key = ?",
                ("integration-test",),
            ).fetchone()
            self.assertEqual(lease["owner_id"], "runner")
            connection.commit()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
